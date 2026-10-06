"""Balanced spatial ladder; engineering diagnostics, never physical validation."""

import argparse
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from tempfile import mkdtemp

from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from .control import (make_synthetic_control_case, run_control_model,
                      add_frequency_arguments, frequency_arguments_hz)
from .convergence import compare_impedance, equivalent_capacitance
from .simulation import validate_pcb_simulation_settings

LEVEL_NAMES = ('L0_baseline', 'L1_medium', 'L2_fine', 'L3_extra_fine')
MESH_KEYS = ('shape_cells', 'cell_count', 'pml_cells', 'min_step_m', 'max_step_m', 'worst_growth_ratio')
# A floor for the capacitance diagnostic only; it never affects the engineering gate.
CAPACITANCE_RELATIVE_FLOOR_F = 1e-18


def make_spatial_levels(baseline):
    """Change only four spatial settings, retaining all other experiment values."""
    return tuple((name, validate_pcb_simulation_settings(replace(baseline,
        cells_per_wavelength=wave, min_port_gap_cells=port,
        min_port_width_cells=port, min_substrate_cells_z=substrate)))
        for name, (wave, port, substrate) in zip(LEVEL_NAMES,
            ((20,2,4), (30,4,8), (40,6,12), (50,8,16))))


def compare_spatial_results(new, old):
    """Reuse impedance denominators; capacitance differences require two capacitive samples."""
    rows = compare_impedance(new, old)
    for i, row in enumerate(rows):
        cn = equivalent_capacitance(row['frequency_hz'], new['reactance_ohm'][i])
        co = equivalent_capacitance(row['frequency_hz'], old['reactance_ohm'][i])
        delta = None if cn is None or co is None else cn-co
        row['delta_equivalent_capacitance_f'] = delta
        row['relative_equivalent_capacitance'] = (None if delta is None else
            abs(delta)/max(abs(co), CAPACITANCE_RELATIVE_FLOOR_F))
    json.dumps(rows, allow_nan=False)
    return rows


def engineering_gate(last_pair):
    """Inclusive project thresholds on every sample, not a validation theorem."""
    return bool(last_pair) and all(row['relative_Z_magnitude'] <= .01 and
        row['relative_X'] <= .01 and row['relative_R'] <= .05 for row in last_pair)


def convergence_trend(pairwise):
    """Strict shrinking of absolute delta Z; nonmonotonic data remain reportable."""
    a,b,d = (pairwise[name] for name in LEVEL_NAMES[1:])
    return [dict(frequency_hz=x['frequency_hz'],
                 L2_change_smaller_than_L1=y['delta_Z_magnitude_ohm'] < x['delta_Z_magnitude_ohm'],
                 L3_change_smaller_than_L2=z['delta_Z_magnitude_ohm'] < y['delta_Z_magnitude_ohm'])
            for x,y,z in zip(a,b,d)]


def _write_report(study, output):
    serialized = json.dumps(study, indent=2, allow_nan=False)
    temporary = output/'spatial_convergence.json.tmp'
    temporary.write_text(serialized+'\n', encoding='utf-8')
    temporary.replace(output/'spatial_convergence.json')
    metrics = ('delta_R_ohm','delta_X_ohm','relative_R','relative_X',
               'delta_Z_magnitude_ohm','relative_Z_magnitude',
               'delta_equivalent_capacitance_f','relative_equivalent_capacitance')
    header = ['level','frequency_hz','resistance_ohm','reactance_ohm','s11_magnitude','swr',
              'equivalent_capacitance_f','mesh_cell_count','mesh_shape_x','mesh_shape_y','mesh_shape_z',
              'min_step_m','max_step_m','worst_growth_ratio']
    header += [f'{key}_vs_{ref}' for ref in ('previous','finest') for key in metrics]
    with (output/'spatial_convergence.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for name, level in study['levels'].items():
            if level['status'] != 'completed':
                continue
            result, mesh = level['result'], level['mesh']
            for i, f in enumerate(result['frequency_hz']):
                row = [name,f,*[result[key][i] for key in
                    ('resistance_ohm','reactance_ohm','s11_magnitude','swr')],
                    level['equivalent_capacitance_f'][i], mesh['cell_count'],*mesh['shape_cells'],
                    mesh['min_step_m'],mesh['max_step_m'],mesh['worst_growth_ratio']]
                for group in ('pairwise_comparisons','comparisons_to_finest'):
                    comparison = study[group].get(name)
                    row += [comparison[i][key] if comparison else None for key in metrics]
                writer.writerow(row)


def run_spatial_study(output_dir, **frequency_settings):
    """Sequential preflight/solve, retaining earlier results on failure; no resume."""
    geometry, baseline = make_synthetic_control_case(**frequency_settings)
    levels = make_spatial_levels(baseline)
    identity = geometry.as_dict()
    geometry_json = json.dumps(identity,sort_keys=True,allow_nan=False)
    output = Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ConfigurationError(f'PCB spatial: wymagany pusty/nowy katalog: {output}')
    output.mkdir(parents=True,exist_ok=True)
    with (output/'spatial_convergence.json').open('x',encoding='utf-8') as stream:
        stream.write('{}\n')
    base = asdict(baseline)
    study = dict(status='running',candidate_spatially_converged=False,
        frequency_configuration={key:base[key] for key in ('excitation_center_hz',
            'excitation_cutoff_hz','result_frequency_hz','loss_reference_frequency_hz')},
        geometry={'model':geometry.model,'sha256':hashlib.sha256(geometry_json.encode()).hexdigest(),
                  'normalized_geometry':identity}, levels={}, pairwise_comparisons={},
        comparisons_to_finest={}, convergence_trend=[],
        engineering_gate=dict(relative_Z_limit=.01,relative_X_limit=.01,relative_R_limit=.05),
        notes=[
            'The thresholds are project engineering criteria only.',
            'Passing this ladder does not establish physical validation of the planar lumped port.',
            'Failure to converge indicates that port/grid formulation must be reviewed before Gerber integration.',
            'L3 is the finest tested numerical reference, not exact truth. No extra refinement is automatic.',
            'Relative metrics are fractions, not percentages. R/X denominators have a 1 ohm floor; Z uses Zref.',
            'Capacitance comparison is null unless both samples are capacitive; denominator floor is 1e-18 F.',
            'Run completion does not prove EndCriteria was reached before max_timesteps.',
            'Preflight mesh is rebuilt deterministically by the existing control pipeline; mesh metadata must agree.'])
    for name, settings in levels:
        values = asdict(settings)
        study['levels'][name] = dict(status='pending', output_directory=name,settings=values,
            changed_settings={k:v for k,v in values.items() if v!=base[k]})
    _write_report(study,output)
    current = None
    try:
        for index, (name, settings) in enumerate(levels):
            current = study['levels'][name]
            current['status'] = 'preflight'
            _write_report(study,output)
            print(f'[{index+1}/4] {name}',flush=True)
            if geometry.as_dict() != identity:
                raise ConfigurationError('PCB spatial: zmieniona geometria przed przebiegiem.')
            try:
                mesh = make_pcb_domain_mesh(geometry,settings)
            except ConfigurationError as exc:
                raise ConfigurationError(f'{name}: mesh preflight failed before native execution '
                    f'(max_cells={settings.max_cells}); {exc}') from exc
            metadata = {key:getattr(mesh,key) for key in MESH_KEYS}
            current['mesh'] = metadata
            print(f"mesh: shape={mesh.shape_cells}, cells={mesh.cell_count}, "
                  f"min_step_m={mesh.min_step_m:.9g}, max_step_m={mesh.max_step_m:.9g}, "
                  f"worst_growth_ratio={mesh.worst_growth_ratio:.9g}",flush=True)
            current['status'] = 'running'
            _write_report(study,output)
            result = run_control_model(geometry,settings,output/name)
            if geometry.as_dict() != identity:
                raise ConfigurationError('PCB spatial: przebieg zmienił geometrię.')
            if result['frequency_hz'] != list(settings.result_frequency_hz):
                raise ConfigurationError('PCB spatial: niezgodne częstotliwości wyniku.')
            # Tuple/list differences from JSON are representational only.
            if json.dumps({k:result['mesh'][k] for k in MESH_KEYS},sort_keys=True) != json.dumps(metadata,sort_keys=True):
                raise ConfigurationError('PCB spatial: siatka solvera nie odpowiada preflight.')
            compare_spatial_results(result,result)  # length, reference and finite comparison audit
            json.dumps(result,allow_nan=False)
            caps = [equivalent_capacitance(f,x) for f,x in zip(result['frequency_hz'],result['reactance_ohm'])]
            json.dumps(caps,allow_nan=False)
            if index:
                study['pairwise_comparisons'][name] = compare_spatial_results(
                    result,study['levels'][levels[index-1][0]]['result'])
            current.update(status='completed',result=result,equivalent_capacitance_f=caps,
                impedance_ohm=[{'real':r,'imag':x} for r,x in zip(result['resistance_ohm'],result['reactance_ohm'])])
            _write_report(study,output)
            for i,f in enumerate(result['frequency_hz']):
                print(f"  {f/1e9:.3f} GHz: Z = {result['resistance_ohm'][i]:.9g} "
                      f"+ j({result['reactance_ohm'][i]:.9g}) ohm",flush=True)
        current = None  # report failures must not relabel a completed native level
        finest = study['levels'][LEVEL_NAMES[-1]]['result']
        study['comparisons_to_finest'] = {name:compare_spatial_results(v['result'],finest)
                                        for name,v in study['levels'].items()}
        study['convergence_trend'] = convergence_trend(study['pairwise_comparisons'])
        candidate = engineering_gate(study['pairwise_comparisons'][LEVEL_NAMES[-1]])
        study['candidate_spatially_converged'] = candidate
        study['status'] = 'diagnostic_candidate_converged' if candidate else 'diagnostic_not_converged'
        _write_report(study,output)
    except (Exception,KeyboardInterrupt) as exc:
        study['status'] = 'failed'
        study['candidate_spatially_converged'] = False
        if current is not None and current['status'] != 'completed':
            current['status'] = 'failed'
        study['error'] = f'{type(exc).__name__}: {exc}'
        _write_report(study,output)
        raise
    for i,f in enumerate(baseline.result_frequency_hz):
        print(f'{f/1e9:.3f} GHz:')
        for j,name in enumerate(LEVEL_NAMES[1:]):
            delta = study['pairwise_comparisons'][name][i]['relative_Z_magnitude']
            print(f'  L{j} -> L{j+1}: delta Z = {100*delta:.6g} %')
    print('candidate spatial convergence: '+('YES' if candidate else 'NO'),flush=True)
    return json.loads(json.dumps(study,allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Balanced synthetic PCB spatial convergence ladder')
    parser.add_argument('--output',type=Path)
    add_frequency_arguments(parser)
    args = parser.parse_args(argv)
    try:
        output = args.output
        if output is None:
            root = Path('outcomes/pcb_spatial_convergence')
            root.mkdir(parents=True,exist_ok=True)
            output = Path(mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_'),dir=root))
        output = output.resolve()
        print(f'PCB balanced spatial convergence\nOutput: {output}',flush=True)
        study = run_spatial_study(output,**frequency_arguments_hz(args))
        print(f"Status: {study['status']}\n{output/'spatial_convergence.csv'}\n{output/'spatial_convergence.json'}")
        return 0
    except (ConfigurationError,RuntimeError,OSError,ValueError,KeyboardInterrupt) as exc:
        print(f'PCB spatial: {exc}',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
