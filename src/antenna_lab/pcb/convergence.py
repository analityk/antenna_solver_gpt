"""Sequential numerical sensitivity study; no physical validation or resume."""

import argparse
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from math import hypot, pi
from pathlib import Path
import sys
from tempfile import mkdtemp

from antenna_lab.core.config import ConfigurationError
from .control import (make_synthetic_control_case, run_control_model,
                      add_frequency_arguments, frequency_arguments_hz)
from .simulation import validate_pcb_simulation_settings


def make_convergence_variants(baseline):
    """Ordered immutable experiments; one factor at a time then combined reference."""
    changes = (
        ('baseline', {}),
        ('wavelength_fine', {'cells_per_wavelength': 30}),
        ('port_fine', {'min_port_gap_cells': 4, 'min_port_width_cells': 4}),
        ('substrate_z_fine', {'min_substrate_cells_z': 8}),
        ('air_padding_wide', {'air_padding_wavelengths': .50}),
        ('pml_deep', {'pml_cells': 12}),
        ('time_strict', {'end_criteria': 1e-6}),
        ('reference_fine', {'cells_per_wavelength': 30, 'min_substrate_cells_z': 8,
                            'min_port_gap_cells': 4, 'min_port_width_cells': 4,
                            'air_padding_wavelengths': .50, 'pml_cells': 12,
                            'end_criteria': 1e-6}),
    )
    return tuple((name, validate_pcb_simulation_settings(replace(baseline, **values)))
                 for name, values in changes)


def compare_impedance(result, reference):
    """Signed R/X differences; relative values are magnitudes, not percentages."""
    frequencies = result['frequency_hz']
    if frequencies != reference['frequency_hz']:
        raise ConfigurationError('PCB convergence: niezgodne częstotliwości porównania.')
    if result['reference_impedance_ohm'] != reference['reference_impedance_ohm']:
        raise ConfigurationError('PCB convergence: niezgodna impedancja odniesienia.')
    for data in (result, reference):
        if any(len(data[key]) != len(frequencies) for key in ('resistance_ohm','reactance_ohm')):
            raise ConfigurationError('PCB convergence: niezgodne długości widma.')
    rows = []
    for i, frequency in enumerate(frequencies):
        r0, x0 = reference['resistance_ohm'][i], reference['reactance_ohm'][i]
        dr, dx = result['resistance_ohm'][i]-r0, result['reactance_ohm'][i]-x0
        dz = hypot(dr, dx)
        rows.append(dict(frequency_hz=frequency, delta_R_ohm=dr, delta_X_ohm=dx,
                         relative_R=abs(dr)/max(abs(r0),1.),
                         relative_X=abs(dx)/max(abs(x0),1.),
                         delta_Z_magnitude_ohm=dz,
                         relative_Z_magnitude=dz/max(hypot(r0,x0),reference['reference_impedance_ohm'])))
    json.dumps(rows, allow_nan=False)
    return rows


def equivalent_capacitance(frequency, reactance):
    """Series-equivalent diagnostic in F; noncapacitive reactance has no value."""
    return -1/(2*pi*frequency*reactance) if reactance < 0 else None


def _write_study(study, output):
    serialized = json.dumps(study, indent=2, allow_nan=False)
    temporary = output/'convergence.json.tmp'
    temporary.write_text(serialized+'\n', encoding='utf-8')
    temporary.replace(output/'convergence.json')
    # On failure the CSV retains successful variants; unavailable comparisons are empty.
    metrics = ('delta_R_ohm','delta_X_ohm','relative_R','relative_X',
               'delta_Z_magnitude_ohm','relative_Z_magnitude')
    header = ['variant','frequency_hz','resistance_ohm','reactance_ohm','s11_magnitude','swr',
              'equivalent_capacitance_f']
    header += [f'{key}_vs_{ref}' for ref in ('baseline','reference') for key in metrics]
    header += ['mesh_cell_count','mesh_shape_x','mesh_shape_y','mesh_shape_z']
    with (output/'convergence.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for name, variant in study['variants'].items():
            if variant['status'] != 'completed':
                continue
            result = variant['result']
            for i, frequency in enumerate(result['frequency_hz']):
                row = [name,frequency,*[result[key][i] for key in
                       ('resistance_ohm','reactance_ohm','s11_magnitude','swr')],
                       variant['equivalent_capacitance_f'][i]]
                for ref in ('baseline','reference'):
                    comparisons = study['comparisons_to_'+ref].get(name)
                    row += [comparisons[i][key] if comparisons else None for key in metrics]
                row += [result['mesh']['cell_count'],*result['mesh']['shape_cells']]
                writer.writerow(row)


def run_convergence_study(output_dir, **frequency_settings):
    """Fail fast, preserving completed runs and a failed study manifest. No resume."""
    geometry, baseline = make_synthetic_control_case(**frequency_settings)
    variants = make_convergence_variants(baseline)
    geometry_data = geometry.as_dict()
    geometry_json = json.dumps(geometry_data,sort_keys=True,allow_nan=False)
    base = asdict(baseline)
    output = Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ConfigurationError(f'PCB convergence: wymagany pusty/nowy katalog: {output}')
    output.mkdir(parents=True,exist_ok=True)
    # Exclusive claim prevents concurrent studies from sharing variant directories.
    with (output/'convergence.json').open('x',encoding='utf-8') as stream:
        stream.write('{}\n')
    study = dict(status='running', frequency_configuration={key:base[key] for key in
        ('excitation_center_hz','excitation_cutoff_hz','result_frequency_hz','loss_reference_frequency_hz')},
        geometry={'model':geometry.model,'sha256':hashlib.sha256(geometry_json.encode()).hexdigest(),
                  'normalized_geometry':geometry_data},
        baseline_variant='baseline', refined_reference_variant='reference_fine', variants={},
        comparisons_to_baseline={}, comparisons_to_reference={}, notes=[
            'This study measures numerical sensitivity of the synthetic PCB control case. '
            'It does not establish physical validation of the port, material model, or real PCB.',
            'reference_fine is a refined numerical reference, not exact truth.',
            'Completion does not prove EndCriteria was reached before max_timesteps.',
            'Relative metrics are fractions; R/X floors are 1 ohm and Z floor is reference impedance.'])
    for name, settings in variants:
        values = asdict(settings)
        study['variants'][name] = dict(status='pending', output_directory=name,
            settings=values, changed_settings={k:v for k,v in values.items() if v != base[k]})
    _write_study(study, output)
    selected = min(range(len(baseline.result_frequency_hz)),
                   key=lambda i:abs(baseline.result_frequency_hz[i]-baseline.excitation_center_hz))
    current = None
    try:
        for index, (name, settings) in enumerate(variants, 1):
            current = study['variants'][name]
            current['status'] = 'running'
            _write_study(study, output)
            print(f'[{index}/{len(variants)}] {name}',flush=True)
            result = run_control_model(geometry, settings, output/name)
            if geometry.as_dict() != geometry_data:
                raise ConfigurationError('PCB convergence: przebieg zmienił stałą geometrię.')
            if result['frequency_hz'] != list(settings.result_frequency_hz):
                raise ConfigurationError('PCB convergence: wynik ma inne częstotliwości niż eksperyment.')
            current.update(result=result, equivalent_capacitance_f=[equivalent_capacitance(f,x)
                for f,x in zip(result['frequency_hz'],result['reactance_ohm'])])
            # Validate result serialization before marking this variant complete.
            json.dumps(current,allow_nan=False)
            current['status'] = 'completed'
            study['comparisons_to_baseline'][name] = compare_impedance(
                result,study['variants']['baseline']['result'])
            _write_study(study,output)
            print(f"  {result['frequency_hz'][selected]/1e9:.3f} GHz: "
                  f"Z={result['resistance_ohm'][selected]:.9g} + j({result['reactance_ohm'][selected]:.9g}) ohm",flush=True)
        reference = study['variants']['reference_fine']['result']
        study['comparisons_to_reference'] = {name:compare_impedance(v['result'],reference)
                                            for name,v in study['variants'].items()}
        study['status'] = 'diagnostic_pending_review'
        _write_study(study,output)
    except (Exception, KeyboardInterrupt) as exc:
        study['status'] = 'failed'
        if current is not None:
            current['status'] = 'failed'
            # Do not serialize malformed/nonfinite native data into a failure manifest.
            current.pop('result',None)
            current.pop('equivalent_capacitance_f',None)
        study['error'] = f'{type(exc).__name__}: {exc}'
        _write_study(study,output)
        raise
    return json.loads(json.dumps(study,allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Synthetic PCB numerical convergence study')
    parser.add_argument('--output',type=Path)
    add_frequency_arguments(parser)
    args = parser.parse_args(argv)
    band = frequency_arguments_hz(args)
    try:
        output = args.output
        if output is None:
            root = Path('outcomes/pcb_convergence')
            root.mkdir(parents=True,exist_ok=True)
            output = Path(mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_'),dir=root))
        output = output.resolve()
        print('PCB synthetic convergence study\nBand: '+
              ', '.join(f'{f/1e9:.3f}' for f in band['result_frequency_hz'])+' GHz\n'+
              f'Output: {output}\nVariants: 8\nStatus: DIAGNOSTIC',flush=True)
        run_convergence_study(output,**band)
        print(f'Study complete\nStatus: DIAGNOSTIC_PENDING_REVIEW\n'
              f'convergence.csv: {output/"convergence.csv"}\nconvergence.json: {output/"convergence.json"}')
        return 0
    except (ConfigurationError,RuntimeError,OSError,ValueError,KeyboardInterrupt) as exc:
        print(f'PCB convergence: {exc}',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
