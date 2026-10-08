"""One explicit Gerber PCB run using the existing economical PCB pipeline."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys

from antenna_lab.core.config import ConfigurationError
from antenna_lab.core.catalog import variant_slug
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model, read_pcb_native_statistics
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh, make_gerber_mesh_anchor_plan
from .config import load_pcb_config
from .copper import copper_metadata
from .control import (run_control_model, add_frequency_arguments,
                      frequency_arguments_hz)
from .gerber import load_pcb_geometry
from .gerber_quality import gerber_quality_settings, gerber_cost_preflight, require_excitation_fits
from .gerber_sweep import sweep_frequencies_hz, sampled_diagnostics, print_sweep_summary
from .port import resolve_pcb_lumped_port
from .transform import normalize_port_orientation
from .grid import PcbGrid
from .geometry_resolution import apply_geometry_resolution, format_modeled_mm
from .quantization import QuantizationError


GEOMETRY_POLICY = "Geometry resolution applies before EM meshing; FDTD mesh remains independent."

def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def _default_output_dir(config_path, root=Path('outcomes/pcb_gerber')):
    """Create <input-name>_<series> without timestamps or random suffixes."""
    source=Path(config_path)
    name=source.name if source.is_dir() else source.stem
    prefix=variant_slug(name) or 'pcb'
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    used=[]
    marker=prefix+'_'
    for path in root.iterdir():
        if not path.is_dir() or not path.name.startswith(marker):continue
        suffix=path.name[len(marker):]
        if suffix.isdigit():used.append(int(suffix))
    number=max(used,default=0)+1
    while True:
        candidate=root/f'{prefix}_{number:03d}'
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            number+=1


def run_gerber_control(config_path, output_dir, *, prepare_only=False, quality=None, sweep_request=None, pcb_config=None, field_frequency_hz=None, geometry_resolution_um=10, resolved_profile=None, **frequency_settings):
    """Import, normalize once, project geometry, preflight, then XML or one solve."""
    # Public API uses the same explicit choices as the CLI; no implicit string/bool coercion.
    if isinstance(geometry_resolution_um, bool) or not isinstance(geometry_resolution_um, (int, float)) or geometry_resolution_um not in (100, 10, 1, .1):
        raise ConfigurationError("Geometry resolution must be one of 100, 10, 1, 0.1 um.")
    grid = PcbGrid({100:100000, 10:10000, 1:1000, .1:100}[geometry_resolution_um])
    from antenna_lab.solvers.profiles import resolve_profile
    profile = resolved_profile or resolve_profile(quality, experiment=frequency_settings, field_frequency_hz=field_frequency_hz)
    settings = profile.settings
    from .simulation import validate_pcb_simulation_settings
    validate_pcb_simulation_settings(settings)
    quality = profile.name
    field_frequency_hz = profile.field_frequency_hz
    exact = settings.runtime.exact_endcriteria
    bundle_metadata = {}
    if Path(config_path).is_dir():
        from .bundle import load_bundle_geometry
        config, source, bundle_metadata = load_bundle_geometry(config_path, pcb_config)
    elif Path(config_path).suffix.lower() == '.zip':
        from .experiment import resolve_experiment, load_experiment_geometry
        experiment = resolve_experiment(config_path, pcb_config)
        print(f'Gerber archive: {experiment.archive_path}\n'
              f'Stackup: {experiment.stackup.source_path} [{experiment.stackup.scope}]\n'
              f'Netlist: {experiment.netlist.source_path} [{experiment.netlist.scope}]',flush=True)
        config, source, bundle_metadata = load_experiment_geometry(experiment)
    else:
        if pcb_config is not None:
            raise ConfigurationError('--pcb-config is for directory input; legacy JSON already specifies physical parameters.')
        config = load_pcb_config(config_path)
        source = load_pcb_geometry(config)
        from .bundle import audit_physical_feed
        audit_physical_feed(source)
    normalized_source, transform = normalize_port_orientation(source)
    geometry = normalized_source  # provenance only until projection below
    modeled = False
    from antenna_lab.solvers.pcb_fields import validate_field_frequencies, pcb_field_layout
    field_frequency_hz = validate_field_frequencies(field_frequency_hz, settings)
    field_options = {"field_frequency_hz": field_frequency_hz} if field_frequency_hz else {}
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
        'config_path': str(Path(pcb_config or config_path).resolve()) if pcb_config or not Path(config_path).is_dir() else None,
        'resolved_config': {**asdict(config), 'copper_top_path': str(config.copper_top_path),
                            'board_outline_path': str(config.board_outline_path)},
        'files': {role: {'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()}
                  for role,path in (('top_copper',config.copper_top_path),('outline',config.board_outline_path))},
        'dependencies': {name: version(name) for name in ('gerbonara','shapely')},
        'normalization': asdict(transform), 'assumptions': list(geometry.assumptions),
        'port_edge_mode': 'aligned', 'validation_status': 'unverified',
        'copper_composition': [asdict(v) for v in geometry.copper_composition],
        'drills': [asdict(v) for v in geometry.drills],
        'components': [asdict(v) for v in geometry.components],
        'source_port': asdict(geometry.source_port) if geometry.source_port else None,
        'composition_method': 'ordered primitive union/difference; later dark restores copper',
    }
    metadata.update(bundle_metadata)
    if 'experiment_input' in metadata:
        metadata['config_path'] = metadata['experiment_input']['stackup']['source_path']
    if 'source_directory' not in metadata:
        metadata['source_directory'] = str(config.copper_top_path.parent)
    print('PCB Gerber: '+str(output), flush=True)
    if geometry.copper_layers:
        from .stackup import resolved_stackup_metadata
        material_metadata = dict(copper_model='stackup',
            resolved_stackup=resolved_stackup_metadata(geometry, settings.loss_reference_frequency_hz))
        print(f'Material assumptions (unverified): {len(geometry.copper_layers)} copper layers, '
              f'{len(geometry.dielectrics)} explicit dielectrics; '
              f"{material_metadata['resolved_stackup']['total_dielectric_thickness_m']*1e3:g} mm", flush=True)
    else:
        material_metadata = copper_metadata(config)
        print(f'Material assumptions (unverified): substrate {config.substrate_thickness_m*1e3:g} mm, '
              f'epsilon_r={config.substrate_epsilon_r:g}, loss_tangent={config.substrate_loss_tangent:g}; '
              f'copper {config.copper_model}, physical thickness input {config.copper_thickness_m*1e6:g} um', flush=True)
    for assumption in geometry.assumptions:
        print('  '+assumption, flush=True)
    output.mkdir(parents=True, exist_ok=True)
    diagnostics = dict(material_metadata, sweep=sweep, quality_profile=quality, actual_iterations=None, termination_status='not_started',
                       openems_profile=profile.metadata, report_phase_step_deg=settings.runtime.report_phase_step_deg)
    try:
        try:
            geometry, _, audit = apply_geometry_resolution(normalized_source, grid)
        except QuantizationError as exc:
            resolution = dict(exc.audit, requested_um=geometry_resolution_um,
                              quantum_nm=grid.quantum_nm, policy=GEOMETRY_POLICY)
            diagnostics['geometry_resolution'] = metadata['geometry_resolution'] = resolution
            port = normalized_source.port
            source_width = port.width_m
            modeled_width = grid.to_metres(grid.nearest_tick(source_width))
            finer = {100: "10 um or finer", 10: "1 um or finer", 1: "0.1 um"}.get(geometry_resolution_um)
            advice = (f"Choose a finer geometry resolution: {finer}." if finer else
                      "No finer supported geometry resolution; revise the affected source feature.")
            raise ConfigurationError(
                f"Geometry resolution {geometry_resolution_um:g} um is too coarse for this PCB: {exc}. "
                f"Source port width {source_width*1e3:g} mm -> modeled {modeled_width*1e3:g} mm. "
                + advice
            ) from exc
        modeled = True
        if geometry.copper_layers:
            diagnostics['resolved_stackup'] = resolved_stackup_metadata(geometry, settings.loss_reference_frequency_hz)
        resolution = dict(audit, requested_um=geometry_resolution_um,
                          quantum_nm=grid.quantum_nm, policy=GEOMETRY_POLICY)
        diagnostics['geometry_resolution'] = metadata['geometry_resolution'] = resolution
        # These records describe the actual solver model. Original values remain in source files.
        metadata.update(drills=[asdict(d) for d in geometry.drills],
                        components=[asdict(c) for c in geometry.components],
                        source_port=asdict(geometry.source_port) if geometry.source_port else None)
        print(f"Geometry resolution: {geometry_resolution_um:g} um\n"
              f"Geometry quantization: {audit['adjusted']} / {audit['total_spatial_values_examined']} spatial values adjusted\n"
              f"Maximum XY geometry change: {audit['maximum_xy_displacement_m']*1e6:.3g} um\n"
              f"Maximum Z geometry change: {audit['maximum_z_displacement_m']*1e6:.3g} um\n"
              f"Geometry topology: {audit['topology_status']}", flush=True)
        p = geometry.port
        print(f"CSRC gap: {format_modeled_mm(p.negative_xy_m[0],grid)} -> {format_modeled_mm(p.positive_xy_m[0],grid)}\n"
              f"CSRC width: {format_modeled_mm(p.width_m,grid)}", flush=True)
        _, anchor_metadata = make_gerber_mesh_anchor_plan(geometry, settings, quality)
        diagnostics['suppressed_noncritical_anchors'] = anchor_metadata.pop('suppressed_noncritical_anchors')
        diagnostics['mesh_anchor_policy'] = anchor_metadata
        mesh = make_pcb_domain_mesh(geometry, settings, gerber_quality=quality)
        from antenna_lab.solvers.pcb_features import audit_copper_mesh
        diagnostics['copper_mesh_fidelity'] = audit_copper_mesh(geometry, mesh, source_geometry=normalized_source)
        resolve_pcb_lumped_port(geometry, mesh, settings, gerber_quality=quality)
        from antenna_lab.solvers.pcb_components import resolve_component_boxes
        diagnostics['ideal_components'] = [asdict(c) for c in resolve_component_boxes(
            geometry, (mesh.x_lines_m, mesh.y_lines_m, mesh.z_lines_m))]
        cost = gerber_cost_preflight(mesh, settings)
        diagnostics.update(cost)
        print(f"Quality: {quality}\nMesh: {mesh.shape_cells} = {mesh.cell_count} cells\n"
              f"Minimum steps: {cost['min_axis_steps_m']} m\n"
              f"Estimated CFL dt: {cost['estimated_cfl_dt_s']:g} s; NrTS safety ceiling: {settings.max_timesteps}\n"
              f"Estimated excitation: {cost['estimated_excitation_steps']} timesteps (optimistic minimum)\n"
              f"Cost indicator: {cost['estimated_cell_updates']} cell updates (excitation only)", flush=True)
        require_excitation_fits(cost, settings)
        if field_frequency_hz:
            layout = pcb_field_layout(geometry, mesh, settings, field_frequency_hz)
            from math import prod
            samples = sum(prod(p['shape_xyz']) for p in layout)*len(field_frequency_hz)
            print('Field frequencies: '+', '.join(f'{f/1e6:g} MHz' for f in field_frequency_hz)+
                  '\nField planes: xy_air, xz_feed, yz_feed'+
                  f'\nField DFT samples: {samples*6} complex components ({samples} spatial points × frequencies)'+
                  '\nMesh changed by fields: no\nAdditional FDTD runs: 0', flush=True)
        if prepare_only:
            output.mkdir(parents=True, exist_ok=True)
            native = output/'native'
            native.mkdir()
            _, _, _, native_mesh, _, preparation = prepare_pcb_xml_model(geometry, settings, native/'model.xml', gerber_quality=quality, copper_config=config, **field_options)
            if native_mesh != mesh:
                raise ConfigurationError("Native PCB mesh differs from geometry-resolution preflight mesh.")
            result = dict(status='prepared', validation_status='unverified', preparation=preparation,
                simulation_settings=asdict(settings), mesh={'shape_cells': mesh.shape_cells, 'cell_count': mesh.cell_count})
        else:
            result = run_control_model(geometry, settings, output, gerber_quality=quality,
                                       exact_endcriteria=exact, dump_statistics=settings.runtime.dump_statistics, copper_config=config, expected_domain_mesh=mesh, **field_options)
            if settings.runtime.dump_statistics:
                diagnostics['actual_iterations'] = result['native_statistics']['number_of_iterations']
                if not 0 < diagnostics['actual_iterations'] < settings.max_timesteps:
                    raise ConfigurationError('Gerber native termination not established: timestep limit reached.')
                diagnostics['termination_status'] = 'completed_before_limit'
                result['status'] = 'completed'
            else:
                diagnostics['termination_status'] = 'not_established_statistics_disabled'
                result['status'] = 'finished_unverified'
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
            _write_json(output/'geometry.normalized_source.json', normalized_source.as_dict())
            if modeled:
                _write_json(output/'geometry.json', geometry.as_dict())
            _write_json(output/'import.json', metadata)
    if not prepare_only:
        # Match antenna best-effort reporting: presentation never invalidates FDTD.
        try:
            from antenna_lab.visualization.report import generate_report
            report = generate_report(output, automatic=True, phase_step=settings.runtime.report_phase_step_deg)
            print(f'Raport HTML: {report}', flush=True)
        except Exception as exc:
            warning = f'Nie utworzono raportu HTML: {type(exc).__name__}: {exc}. Wyniki FDTD są zachowane; użyj polecenia report.'
            result.setdefault('warnings', []).append(warning)
            print(warning, file=sys.stderr, flush=True)
            try:
                _write_json(output/'summary.json', result)
            except OSError as write_error:
                print(f'Nie zapisano ostrzeżenia raportu: {write_error}; ukończony wynik pozostaje zachowany.', file=sys.stderr)
    return json.loads(json.dumps(result, allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Import top-copper/outline Gerbers and run one unverified PCB model')
    parser.add_argument('config', type=Path, help='Gerber ZIP experiment, directory, or legacy PCB JSON')
    parser.add_argument('--pcb-config', type=Path, help='Physical config override; ZIP otherwise resolves stackup locally or in one parent')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--geometry-resolution-um', type=float, choices=(100,10,1,.1), default=10,
                        help='CAD geometry resolution in um (default 10); independent of FDTD mesh resolution')
    parser.add_argument('--quality', choices=('preview','design','verify'))
    from antenna_lab.solvers.profiles import DEFAULT_CONFIG
    parser.add_argument('--openems-config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--openems-set', action='append', default=[], metavar='KEY=VALUE')
    parser.add_argument('--yes', action='store_true', help='Accept resolved settings without a prompt')
    parser.add_argument('--no-fields', action='store_true', help='Explicitly disable passive E/H output')
    parser.add_argument('--fields-mhz', type=float, nargs='+', help='1–3 passive E/H frequencies; same single Run')
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
        from antenna_lab.solvers.profiles import parse_override
        from .profile_cli import approve_profile
        overrides = dict(parse_override(v) for v in args.openems_set)
        profile = approve_profile(dict(name=args.quality, config_path=args.openems_config,
            experiment=band, cli_overrides=overrides,
            field_frequency_hz=None if args.fields_mhz is None else tuple(f*1e6 for f in args.fields_mhz),
            no_fields=args.no_fields), yes=args.yes, prepare_only=args.prepare_only)
        if profile is None:
            print('Cancelled before native preparation/FDTD.'); return 0
        # Run-specific edits to the array supersede the original regular sweep.
        if sweep_options and tuple(profile.settings.result_frequency_hz) != tuple(band['result_frequency_hz']):
            sweep_options = {}
        output = args.output
        if output is None:
            output = _default_output_dir(args.config)
        result = run_gerber_control(args.config, output, prepare_only=args.prepare_only, quality=profile.name, geometry_resolution_um=args.geometry_resolution_um, **sweep_options, pcb_config=args.pcb_config, resolved_profile=profile)
        print(f"Status: {result['status']}; validation_status: unverified\n{output.resolve()/'summary.json'}")
        if not args.prepare_only:
            print(output.resolve()/'impedance.csv')
        return 0
    except (ConfigurationError, OSError, RuntimeError, ValueError, KeyboardInterrupt) as exc:
        print(f'PCB Gerber: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
