"""Local thirds-L2 sensitivity decomposition; no physical validation."""

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
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh, pcb_port_edge_policy
from .control import (make_synthetic_control_case, run_control_model,
                      add_frequency_arguments, frequency_arguments_hz)
from .convergence import equivalent_capacitance
from .edge_convergence import audit_experiment_result
from .port import resolve_pcb_lumped_port
from .simulation import validate_pcb_simulation_settings
from .spatial_convergence import compare_spatial_results, MESH_KEYS

VARIANT_NAMES = ('thirds_L2_reference', 'thirds_wave50', 'thirds_port8',
                 'thirds_substrate16', 'thirds_L3_combined')
PORT_EDGE_MODE = 'thirds'
PORT_KEYS = ('x_cell_count', 'y_cell_count', 'active_ex_edge_count')
FREQUENCY_KEYS = ('excitation_center_hz', 'excitation_cutoff_hz',
                  'result_frequency_hz', 'loss_reference_frequency_hz')


def make_refined_variants(baseline):
    """Five fixed experiments; retain the caller's band and resource limit."""
    reference = replace(baseline, cells_per_wavelength=40, min_port_gap_cells=6,
        min_port_width_cells=6, min_substrate_cells_z=12,
        air_padding_wavelengths=.25, pml_cells=8, end_criteria=1e-5,
        max_timesteps=100000, growth_ratio_target=1.4, growth_ratio_limit=1.5,
        reference_impedance_ohm=50.)
    changes = ({}, {'cells_per_wavelength': 50},
        {'min_port_gap_cells': 8, 'min_port_width_cells': 8},
        {'min_substrate_cells_z': 16},
        {'cells_per_wavelength': 50, 'min_port_gap_cells': 8,
         'min_port_width_cells': 8, 'min_substrate_cells_z': 16})
    return tuple((name, validate_pcb_simulation_settings(replace(reference, **change)))
                 for name, change in zip(VARIANT_NAMES, changes))


def _complex_record(value):
    return {'real': value.real, 'imag': value.imag}


def compare_to_reference(result, reference):
    rows = compare_spatial_results(result, reference)
    for row in rows:
        row['delta_Z_ohm'] = _complex_record(complex(row['delta_R_ohm'], row['delta_X_ohm']))
    return rows


def decompose_comparisons(comparisons):
    """Vector interaction is a diagnostic, not an error estimator or a gate."""
    rows = []
    for wave, port, substrate, combined in zip(*(comparisons[n] for n in VARIANT_NAMES[1:])):
        increments = [complex(r['delta_R_ohm'], r['delta_X_ohm'])
                      for r in (wave, port, substrate, combined)]
        dw, dp, ds, dc = increments
        linear = dw + dp + ds
        residual = dc - linear
        denominator = max(abs(dc), 1.)
        factors = sorted(zip(('wavelength', 'port', 'substrate_z'), map(abs, increments[:3])),
                         key=lambda pair: pair[1], reverse=True)
        # No change in any one-factor sample cannot identify a dominant factor.
        dominant = ('mixed' if factors[0][1] == 0 or
                    factors[0][1] - factors[1][1] < .1*factors[0][1] else factors[0][0])
        row = dict(frequency_hz=wave['frequency_hz'],
            dZ_wave_ohm=_complex_record(dw), dZ_port_ohm=_complex_record(dp),
            dZ_substrate_ohm=_complex_record(ds), dZ_combined_ohm=_complex_record(dc),
            dZ_linear_sum_ohm=_complex_record(linear), interaction_residual_ohm=_complex_record(residual),
            abs_interaction_residual_ohm=abs(residual),
            relative_interaction_residual=abs(residual)/denominator,
            abs_dZ_wave_ohm=abs(dw), abs_dZ_port_ohm=abs(dp),
            abs_dZ_substrate_ohm=abs(ds), abs_dZ_combined_ohm=abs(dc),
            wave_fraction_of_combined=abs(dw)/denominator,
            port_fraction_of_combined=abs(dp)/denominator,
            substrate_fraction_of_combined=abs(ds)/denominator,
            diagnostic_denominator_ohm=denominator, dominant_factor=dominant,
            strong_interaction=abs(residual) > .5*abs(dc))
        rows.append(row)
    dominant = {row['dominant_factor'] for row in rows}
    if any(row['strong_interaction'] for row in rows):
        overall = 'strong_interaction'
    elif len(dominant) == 1 and 'mixed' not in dominant:
        overall = next(iter(dominant)) + '_dominated'
    else:
        overall = 'mixed'
    json.dumps(rows, allow_nan=False)
    return rows, overall


def _write_report(study, output):
    serialized = json.dumps(study, indent=2, allow_nan=False)
    temporary = output/'refined_sensitivity.json.tmp'
    temporary.write_text(serialized+'\n', encoding='utf-8')
    temporary.replace(output/'refined_sensitivity.json')
    header = ['variant', 'frequency_hz', 'R', 'X', 's11_magnitude', 'swr',
              'equivalent_capacitance_f', 'mesh_shape_x', 'mesh_shape_y', 'mesh_shape_z',
              'cell_count', 'min_step_m', 'max_step_m', 'worst_growth_ratio', *PORT_KEYS,
              'number_of_iterations', 'fdtd_timestep_s', 'total_numerical_time_s',
              'delta_R_vs_L2', 'delta_X_vs_L2', 'delta_Z_vs_L2', 'abs_delta_Z_vs_L2',
              'relative_R_vs_L2', 'relative_X_vs_L2', 'relative_Z_vs_L2',
              'delta_equivalent_capacitance_f_vs_L2']
    with (output/'refined_sensitivity.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for name, variant in study['variants'].items():
            if variant['status'] != 'completed':
                continue
            result, mesh, port = variant['result'], variant['mesh'], variant['port']
            stats = result['native_statistics']
            for i, frequency in enumerate(result['frequency_hz']):
                comparison = study['comparisons_to_L2'][name][i]
                writer.writerow([name, frequency, *[result[k][i] for k in
                    ('resistance_ohm', 'reactance_ohm', 's11_magnitude', 'swr')],
                    variant['equivalent_capacitance_f'][i], *mesh['shape_cells'],
                    *[mesh[k] for k in ('cell_count', 'min_step_m', 'max_step_m', 'worst_growth_ratio')],
                    *[port[k] for k in PORT_KEYS],
                    *[stats[k] for k in ('number_of_iterations', 'fdtd_timestep_s', 'total_numerical_time_s')],
                    comparison['delta_R_ohm'], comparison['delta_X_ohm'],
                    json.dumps(comparison['delta_Z_ohm'], allow_nan=False),
                    comparison['delta_Z_magnitude_ohm'], comparison['relative_R'], comparison['relative_X'],
                    comparison['relative_Z_magnitude'], comparison['delta_equivalent_capacitance_f']])


def run_refined_study(output_dir, **frequency_settings):
    """Run exactly five variants sequentially through the existing control pipeline."""
    geometry, baseline = make_synthetic_control_case(**frequency_settings)
    variants = make_refined_variants(baseline)
    identity = geometry.as_dict()
    encoded = json.dumps(identity, sort_keys=True, allow_nan=False)
    output = Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ConfigurationError(f'PCB sensitivity: wymagany pusty/nowy katalog {output}.')
    output.mkdir(parents=True, exist_ok=True)
    with (output/'refined_sensitivity.json').open('x', encoding='utf-8') as stream:
        stream.write('{}\n')
    base = asdict(baseline)
    study = dict(status='running', port_edge_mode=PORT_EDGE_MODE,
        frequency_configuration={k: base[k] for k in FREQUENCY_KEYS},
        geometry={'model': geometry.model, 'sha256': hashlib.sha256(encoded.encode()).hexdigest(),
                  'normalized_geometry': identity},
        variants={}, comparisons_to_L2={}, combined_comparison=[], vector_decomposition=[],
        dominant_factor_by_frequency=[], interaction_strength_by_frequency=[], overall_classification=None,
        notes=[
            'Local numerical sensitivity decomposition, not physical validation or an error estimator.',
            'aligned remains the production default. Only the five declared thirds variants are run.',
            'Complex increments may cancel; magnitude fractions are not normalized to 100%.',
            'R/X relative denominators use a 1 ohm floor; Z uses the existing Zref floor.',
            'Interaction/fraction denominator: max(abs(dZ_combined), 1 ohm). Strong interaction uses unfloored abs(dZ_combined).',
            'Mixed means the two largest contributions differ by less than 10% of the larger, or all are zero.',
            'Native LumpedPort combines lumped element, excitation and voltage/current probes; the port box is snapped to the solver mesh.',
            'openEMS scales per-cell lumped RLC values using series/parallel cell counts. Active Ex count alone does not imply a changed 50-ohm source.',
            'Capacitance is diagnostic only for X<0. No resistor, probe, geometry or physical port dimensions are changed.',
            'Completed samples require exact_endcriteria and dump_statistics with iterations below max_timesteps.'])
    for name, settings in variants:
        study['variants'][name] = dict(status='pending', edge_mode=PORT_EDGE_MODE,
            settings=asdict(settings), output_directory=name)
    current = None
    _write_report(study, output)
    try:
        for index, (name, settings) in enumerate(variants, 1):
            current = study['variants'][name]
            current['status'] = 'preflight'
            _write_report(study, output)
            print(f'[{index}/5] {name}', flush=True)
            if geometry.as_dict() != identity:
                raise ConfigurationError('PCB sensitivity: geometria zmieniona przed przebiegiem.')
            mesh = make_pcb_domain_mesh(geometry, settings, port_edge_mode=PORT_EDGE_MODE)
            spec = resolve_pcb_lumped_port(geometry, mesh, settings, port_edge_mode=PORT_EDGE_MODE)
            current['mesh'] = {k: getattr(mesh, k) for k in MESH_KEYS}
            current['port'] = asdict(spec)
            current['edge_policy'] = pcb_port_edge_policy(geometry, settings, PORT_EDGE_MODE)
            print(f'mesh: {mesh.shape_cells}, cells={mesh.cell_count}; '
                  f'port X={spec.x_cell_count}, Y={spec.y_cell_count}, Ex={spec.active_ex_edge_count}', flush=True)
            if geometry.as_dict() != identity:
                raise ConfigurationError('PCB sensitivity: geometria zmieniona przez preflight.')
            current['status'] = 'running'
            _write_report(study, output)
            result = run_control_model(geometry, settings, output/name, port_edge_mode=PORT_EDGE_MODE,
                                       exact_endcriteria=True, dump_statistics=True)
            if geometry.as_dict() != identity:
                raise ConfigurationError('PCB sensitivity: geometria zmieniona przez przebieg.')
            audit_experiment_result(result, settings)
            json.dumps(result, allow_nan=False)
            for expected, actual, label in (
                (current['mesh'], {k: result['mesh'][k] for k in MESH_KEYS}, 'mesh'),
                (current['port'], {k: result['preparation']['port'][k] for k in current['port']}, 'port'),
                (asdict(settings), result['simulation_settings'], 'settings')):
                if json.dumps(expected, sort_keys=True) != json.dumps(actual, sort_keys=True):
                    raise ConfigurationError(f'PCB sensitivity: {label} solvera różni się od preflight.')
            reference = result if name == VARIANT_NAMES[0] else study['variants'][VARIANT_NAMES[0]]['result']
            comparison = compare_to_reference(result, reference)
            caps = [equivalent_capacitance(f, x) for f, x in zip(result['frequency_hz'], result['reactance_ohm'])]
            json.dumps(caps, allow_nan=False)
            study['comparisons_to_L2'][name] = comparison
            current.update(status='completed', result=result, equivalent_capacitance_f=caps)
            _write_report(study, output)
        current = None
        study['combined_comparison'] = study['comparisons_to_L2'][VARIANT_NAMES[-1]]
        decomposition, overall = decompose_comparisons(study['comparisons_to_L2'])
        study['vector_decomposition'] = decomposition
        study['overall_classification'] = overall
        study['dominant_factor_by_frequency'] = [
            {k: row[k] for k in ('frequency_hz', 'dominant_factor')} for row in decomposition]
        study['interaction_strength_by_frequency'] = [
            {k: row[k] for k in ('frequency_hz', 'abs_interaction_residual_ohm',
                                'relative_interaction_residual', 'strong_interaction')} for row in decomposition]
        study['status'] = 'diagnostic_pending_review'
        _write_report(study, output)
    except (Exception, KeyboardInterrupt) as exc:
        study['status'] = 'failed'
        if current is not None and current['status'] != 'completed':
            current['status'] = 'failed'
        study['error'] = f'{type(exc).__name__}: {exc}'
        _write_report(study, output)
        raise
    for row, combined in zip(decomposition, study['combined_comparison']):
        print(f"{row['frequency_hz']/1e9:.3f} GHz: {row['dominant_factor']}; "
              f"combined delta Z={100*combined['relative_Z_magnitude']:.6g}%; "
              f"interaction={row['relative_interaction_residual']:.6g}", flush=True)
    return json.loads(json.dumps(study, allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Local refined PCB thirds sensitivity decomposition')
    parser.add_argument('--output', type=Path)
    add_frequency_arguments(parser)
    args = parser.parse_args(argv)
    try:
        output = args.output
        if output is None:
            root = Path('outcomes/pcb_refined_sensitivity')
            root.mkdir(parents=True, exist_ok=True)
            output = Path(mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_'), dir=root))
        output = output.resolve()
        print(f'PCB refined sensitivity\nOutput: {output}', flush=True)
        study = run_refined_study(output, **frequency_arguments_hz(args))
        print(f"Status: {study['status']}\nClassification: {study['overall_classification']}\n"
              f"{output/'refined_sensitivity.json'}\n{output/'refined_sensitivity.csv'}")
        return 0
    except (ConfigurationError, RuntimeError, OSError, ValueError, KeyboardInterrupt) as exc:
        print(f'PCB sensitivity: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
