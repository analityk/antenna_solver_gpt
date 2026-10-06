"""One explicit Gerber PCB run using the existing economical PCB pipeline."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys
from tempfile import mkdtemp

from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model, read_pcb_native_statistics
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh, make_gerber_mesh_anchor_plan
from .config import load_pcb_config
from .control import (run_control_model, add_frequency_arguments,
                      frequency_arguments_hz)
from .gerber import load_pcb_geometry
from .gerber_quality import gerber_quality_settings, gerber_cost_preflight, require_excitation_fits
from .gerber_sweep import sweep_frequencies_hz, sampled_diagnostics, print_sweep_summary
from .port import resolve_pcb_lumped_port
from .transform import normalize_port_orientation


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def run_gerber_control(config_path, output_dir, *, prepare_only=False, quality='design', sweep_request=None, **frequency_settings):
    """Import, normalize once, preflight, then XML or one solve for all frequencies."""
    config = load_pcb_config(config_path)
    source = load_pcb_geometry(config)
    geometry, transform = normalize_port_orientation(source)
    settings, exact = gerber_quality_settings(quality, **frequency_settings)
    frequencies = settings.result_frequency_hz
    sweep = dict(mode='explicit', start_hz=frequencies[0], stop_hz=frequencies[-1], point_count=len(frequencies))
    if sweep_request is not None:
        expected = sweep_frequencies_hz(*sweep_request)
        if expected != tuple(frequencies):
            raise ConfigurationError('Sweep metadata does not match result frequencies.')
        sweep.update(mode='regular', requested_start_hz=sweep_request[0]*1e6,
                     requested_stop_hz=sweep_request[1]*1e6, requested_step_hz=sweep_request[2]*1e6,
                     stop_policy='include_if_on_regular_grid')
    output = Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ConfigurationError(f'PCB Gerber: wymagany pusty/nowy katalog {output}.')
    metadata = {
        'config_path': str(Path(config_path).resolve()),
        'resolved_config': {key: str(value) if isinstance(value, Path) else value
                            for key,value in asdict(config).items()},
        'files': {role: {'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()}
                  for role,path in (('top_copper',config.copper_top_path),('outline',config.board_outline_path))},
        'dependencies': {name: version(name) for name in ('gerbonara','shapely')},
        'normalization': asdict(transform), 'assumptions': list(geometry.assumptions),
        'port_edge_mode': 'aligned', 'validation_status': 'unverified',
    }
    print('PCB Gerber: '+str(output), flush=True)
    for assumption in geometry.assumptions:
        print('  '+assumption, flush=True)
    output.mkdir(parents=True, exist_ok=True)
    diagnostics = dict(sweep=sweep, quality_profile=quality, actual_iterations=None, termination_status='not_started')
    try:
        _, anchor_metadata = make_gerber_mesh_anchor_plan(geometry, settings, quality)
        diagnostics['suppressed_noncritical_anchors'] = anchor_metadata.pop('suppressed_noncritical_anchors')
        diagnostics['mesh_anchor_policy'] = anchor_metadata
        mesh = make_pcb_domain_mesh(geometry, settings, gerber_quality=quality)
        resolve_pcb_lumped_port(geometry, mesh, settings, gerber_quality=quality)
        cost = gerber_cost_preflight(mesh, settings)
        diagnostics.update(cost)
        print(f"Quality: {quality}\nMesh: {mesh.shape_cells} = {mesh.cell_count} cells\n"
              f"Minimum steps: {cost['min_axis_steps_m']} m\n"
              f"Estimated excitation: {cost['estimated_excitation_steps']} timesteps (optimistic minimum)\n"
              f"Cost indicator: {cost['estimated_cell_updates']} cell updates (excitation only)", flush=True)
        require_excitation_fits(cost, settings)
        if prepare_only:
            output.mkdir(parents=True, exist_ok=True)
            native = output/'native'
            native.mkdir()
            _, _, _, _, _, preparation = prepare_pcb_xml_model(geometry, settings, native/'model.xml', gerber_quality=quality)
            result = dict(status='prepared', validation_status='unverified', preparation=preparation,
                simulation_settings=asdict(settings), mesh={'shape_cells': mesh.shape_cells, 'cell_count': mesh.cell_count})
        else:
            result = run_control_model(geometry, settings, output, gerber_quality=quality,
                                       exact_endcriteria=exact, dump_statistics=True)
            diagnostics['actual_iterations'] = result['native_statistics']['number_of_iterations']
            if not 0 < diagnostics['actual_iterations'] < settings.max_timesteps:
                raise ConfigurationError('Gerber native termination not established: timestep limit reached.')
            diagnostics['termination_status'] = 'completed_before_limit'
            result['status'] = 'completed'
            result['note'] = result['note'].replace('First synthetic PCB FDTD control result.', 'PCB FDTD result imported from Gerber geometry.')
            result.update(sampled_diagnostics(result))
        if prepare_only:
            diagnostics['termination_status'] = 'not_run'
        result.update(diagnostics)
        result['import'] = metadata
        _write_json(output/'summary.json', result)
        if not prepare_only:
            print_sweep_summary(result)
    except (Exception, KeyboardInterrupt) as exc:
        if output.is_dir():
            stats_path = output/'native/openEMS_stats.txt'
            if stats_path.exists():
                diagnostics['termination_status'] = 'not_established'
                try:
                    stats = read_pcb_native_statistics(stats_path)
                    diagnostics['actual_iterations'] = stats['number_of_iterations']
                    if stats['number_of_iterations'] >= settings.max_timesteps:
                        diagnostics['termination_status'] = 'max_timesteps_reached'
                except ConfigurationError:
                    pass
            elif (output/'native').exists():
                diagnostics['termination_status'] = 'not_established'
            _write_json(output/'summary.json', dict(diagnostics, status='failed',
                validation_status='unverified', error=str(exc), simulation_settings=asdict(settings),
                import_metadata=metadata))
            _write_json(output/'import_failure.json', dict(status='failed', error=str(exc), import_metadata=metadata))
        raise
    finally:
        if output.is_dir():
            _write_json(output/'geometry.source.json', source.as_dict())
            _write_json(output/'geometry.json', geometry.as_dict())
            _write_json(output/'import.json', metadata)
    return json.loads(json.dumps(result, allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Import top-copper/outline Gerbers and run one unverified PCB model')
    parser.add_argument('config', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--quality', choices=('preview','design','verify'), default='design')
    parser.add_argument('--prepare-only', action='store_true', help='Write native XML without running FDTD')
    add_frequency_arguments(parser)
    parser.set_defaults(frequencies_mhz=None)
    for name in ('start', 'stop', 'step'):
        parser.add_argument(f'--sweep-{name}-mhz', type=float)
    args = parser.parse_args(argv)
    try:
        request = (args.sweep_start_mhz, args.sweep_stop_mhz, args.sweep_step_mhz)
        sweep_options = {}
        if any(v is not None for v in request):
            if not all(v is not None for v in request):
                raise ConfigurationError('Provide all three sweep start/stop/step arguments.')
            if args.frequencies_mhz is not None:
                raise ConfigurationError('--frequencies-mhz cannot be combined with sweep arguments.')
            frequencies = sweep_frequencies_hz(*request)
            sweep_options['sweep_request'] = request
            args.frequencies_mhz = [1300., 1420., 1500.]
            band = frequency_arguments_hz(args)
            band['result_frequency_hz'] = frequencies
        else:
            if args.frequencies_mhz is None:
                args.frequencies_mhz = [1300., 1420., 1500.]
            band = frequency_arguments_hz(args)
        # Validate the unchanged excitation-band rule before creating output/native objects.
        gerber_quality_settings(args.quality, **band)
        output = args.output
        if output is None:
            root = Path('outcomes/pcb_gerber')
            root.mkdir(parents=True, exist_ok=True)
            output = Path(mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_'), dir=root))
        result = run_gerber_control(args.config, output, prepare_only=args.prepare_only, quality=args.quality, **sweep_options, **band)
        print(f"Status: {result['status']}; validation_status: unverified\n{output.resolve()/'summary.json'}")
        if not args.prepare_only:
            print(output.resolve()/'impedance.csv')
        return 0
    except (ConfigurationError, OSError, RuntimeError, ValueError, KeyboardInterrupt) as exc:
        print(f'PCB Gerber: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
