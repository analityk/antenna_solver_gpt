"""Thin D4 project -> existing feature-aware PCB openEMS workflow.

No manufacturing files, reduced solver, new mesh policy or native run loop.
Source snapshots are flushed on exit, including failures: run_control_model
owns an initially empty directory and writes the existing native/results tree.
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys

from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model, read_pcb_native_statistics
from antenna_lab.solvers.pcb_mesh import (make_gerber_mesh_anchor_plan, make_pcb_domain_mesh,
                                         derive_pcb_physical_mesh_policy)
from antenna_lab.solvers.pcb_features import audit_copper_mesh
from antenna_lab.solvers.pcb_components import resolve_component_boxes
from antenna_lab.solvers.pcb_fields import validate_field_frequencies, pcb_field_layout
from antenna_lab.solvers.profiles import DEFAULT_CONFIG, resolve_profile, parse_override
from .control import run_control_model
from .easyeda_project import (load_easyeda_project, resolve_project_components,
                              materialize_project_source, strict_json)
from .easyeda_model import build_source_layout, source_layout_geometry
from .frequency import add_frequency_arguments, frequency_arguments_hz
from .geometry_resolution import apply_geometry_resolution
from .gerber_quality import gerber_cost_preflight, require_excitation_fits
from .gerber_sweep import sweep_frequencies_hz, sampled_diagnostics, print_sweep_summary
from .grid import PcbGrid
from .output import allocate_output_dir
from .port import resolve_pcb_lumped_port
from .profile_cli import approve_profile
from .quantization import QuantizationError
from .simulation import validate_pcb_simulation_settings
from .stackup import resolved_stackup_metadata
from .transform import normalize_port_orientation
from .validation import validate_pcb_geometry


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def run_easyeda_control(project_path, output_dir, *, source_config, source_pcb_id=None,
                       prepare_only=False, quality=None, geometry_resolution_um=10,
                       resolved_profile=None, sweep_request=None, **frequency_settings):
    """Use D4 unchanged; all electrical overrides are explicit source-config data."""
    if isinstance(geometry_resolution_um, bool) or geometry_resolution_um not in (100,10,1,.1):
        raise ConfigurationError('Geometry resolution requires 100, 10, 1 or 0.1 um.')
    grid=PcbGrid({100:100000,10:10000,1:1000,.1:100}[geometry_resolution_um])
    profile=resolved_profile or resolve_profile(quality, experiment=frequency_settings)
    settings=profile.settings
    validate_pcb_simulation_settings(settings)
    fields=validate_field_frequencies(profile.field_frequency_hz,settings)
    field_options={'field_frequency_hz':fields} if fields else {}
    frequencies=settings.result_frequency_hz
    sweep=dict(mode='explicit',start_hz=frequencies[0],stop_hz=frequencies[-1],point_count=len(frequencies))
    if sweep_request is not None:
        if sweep_frequencies_hz(*sweep_request)!=tuple(frequencies):
            raise ConfigurationError('Sweep metadata does not match resolved result frequencies.')
        sweep.update(mode='regular',requested_start_hz=sweep_request[0]*1e6,
                     requested_stop_hz=sweep_request[1]*1e6,requested_step_hz=sweep_request[2]*1e6,
                     stop_policy='include_if_on_regular_grid')
    output=Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ConfigurationError(f'PCB EasyEDA requires an empty/new output directory: {output}')
    output.mkdir(parents=True,exist_ok=True)
    snapshots={}
    provenance=dict(design_source='easyeda_project',manufacturing_validation='not_requested',
                    project_path=str(Path(project_path).resolve()),validation_status='unverified')
    diagnostics=dict(design_source='easyeda_project',manufacturing_validation='not_requested',
        validation_status='unverified',quality_profile=profile.name,openems_profile=profile.metadata,
        geometry_resolution_um=geometry_resolution_um,simulation_settings=asdict(settings),
        sweep=sweep,actual_iterations=None,termination_status='not_started',
        report_phase_step_deg=settings.runtime.report_phase_step_deg)
    stage='source_import'
    result={}
    try:
        project=load_easyeda_project(project_path,pcb_id=source_pcb_id)
        snapshots['project.source.json']=project.as_dict()
        provenance.update(archive_sha256=project.archive_sha256,pcb_id=project.pcb_id)
        bindings=resolve_project_components(project)
        snapshots['component_bindings.json']=bindings
        source_ir=materialize_project_source(project)
        snapshots['source_ir.json']=source_ir.as_dict()
        layout=build_source_layout(source_ir)
        snapshots['source_model.json']=layout
        provenance.update(source_file=source_ir.source_file,source_sha256=source_ir.source_sha256,
                          contact_audit=layout.get('contact_audit'),
                          resolved_components=layout.get('resolved_components',[]))
        stage='source_config'
        if source_config is None:
            raise ConfigurationError('EasyEDA full-wave requires --source-config for port, plating and component_values.')
        config_path=Path(source_config)
        raw=config_path.read_bytes()
        overrides=strict_json(raw.decode('utf-8-sig'),str(config_path))
        provenance['source_config']=dict(path=str(config_path.resolve()),sha256=sha256(raw).hexdigest(),resolved=overrides)
        source=source_layout_geometry(layout,overrides)
        # D4 can materialize a layout without all electrical values for inspection.
        # Full-wave must never silently omit an unresolved passive component.
        unresolved=[c['designator'] for c in layout.get('resolved_components',())
                    if c['role']!='source' and c['designator'] not in {p.id for p in source.components}]
        if unresolved:
            raise ConfigurationError('EasyEDA full-wave: explicit component_values required for '+', '.join(unresolved))
        stage='canonical_validation'
        validate_pcb_geometry(source)
        snapshots['geometry.source.json']=source.as_dict()
        diagnostics['canonical_geometry_status']='passed'
        stage='normalization'
        normalized,transform=normalize_port_orientation(source)
        snapshots['geometry.normalized_source.json']=normalized.as_dict()
        provenance['normalization']=asdict(transform)
        stage='geometry_resolution'
        geometry,_,audit=apply_geometry_resolution(normalized,grid)
        snapshots['geometry.json']=geometry.as_dict()
        resolution=dict(audit,requested_um=geometry_resolution_um,quantum_nm=grid.quantum_nm)
        provenance['geometry_resolution']=diagnostics['geometry_resolution']=resolution
        provenance.update(assumptions=list(geometry.assumptions),
                          drills=[asdict(d) for d in geometry.drills],components=[asdict(c) for c in geometry.components])
        diagnostics['resolved_stackup']=resolved_stackup_metadata(geometry,settings.loss_reference_frequency_hz)
        print(f'PCB EasyEDA: {output}\nBoard/copper geometry: passed\n'
              f'Geometry resolution: {geometry_resolution_um:g} um\n'
              f"Maximum XY/Z geometry change: {audit['maximum_xy_displacement_m']:g} / {audit['maximum_z_displacement_m']:g} m\n"
              f"Topology audit: {audit['topology_status']}",flush=True)
        stage='feature_aware_mesh'
        _,anchors=make_gerber_mesh_anchor_plan(geometry,settings,profile.name)
        diagnostics['suppressed_noncritical_anchors']=anchors.pop('suppressed_noncritical_anchors')
        diagnostics['mesh_anchor_policy']=anchors
        mesh=make_pcb_domain_mesh(geometry,settings,gerber_quality=profile.name)
        diagnostics['mesh']={k:v for k,v in asdict(mesh).items() if k not in ('x_lines_m','y_lines_m','z_lines_m')}
        policy=derive_pcb_physical_mesh_policy(geometry,settings)
        diagnostics['mesh_physical_policy']=asdict(policy)
        cost=gerber_cost_preflight(mesh,settings)
        diagnostics.update(cost)
        print(f'Quality: {profile.name}\nMesh: {mesh.shape_cells} = {mesh.cell_count} cells\n'
              f'Min/max step: {mesh.min_step_m:g} / {mesh.max_step_m:g} m\n'
              f'Worst growth ratio: {mesh.worst_growth_ratio:g}; PML cells: {mesh.pml_cells}\n'
              f'Air padding to PML start: {policy.air_padding_m:g} m\n'
              f"Minimum XYZ steps: {cost['min_axis_steps_m']} m\n"
              f"Estimated CFL dt: {cost['estimated_cfl_dt_s']:g} s\n"
              f"Estimated excitation: {cost['estimated_excitation_steps']} steps; NrTS ceiling: {settings.max_timesteps}\n"
              f"Estimated cell updates: {cost['estimated_cell_updates']} (excitation only)",flush=True)
        stage='physical_mesh_audit'
        diagnostics['copper_mesh_fidelity']=audit_copper_mesh(geometry,mesh,source_geometry=normalized)
        resolve_pcb_lumped_port(geometry,mesh,settings,gerber_quality=profile.name)
        diagnostics['ideal_components']=[asdict(c) for c in resolve_component_boxes(
            geometry,(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m))]
        require_excitation_fits(cost,settings)
        if fields:
            from math import prod
            planes=pcb_field_layout(geometry,mesh,settings,fields)
            print('Field frequencies: '+', '.join(f'{f/1e6:g} MHz' for f in fields)+
                  '\nField planes: xy_air, xz_feed, yz_feed'+
                  f"\nField DFT samples: {6*len(fields)*sum(prod(p['shape_xyz']) for p in planes)} complex components"+
                  '\nMesh changed by fields: no\nAdditional FDTD runs: 0',flush=True)
        stage='native_preparation' if prepare_only else 'native_run'
        if prepare_only:
            native=output/'native';native.mkdir()
            _,_,_,native_mesh,_,preparation=prepare_pcb_xml_model(
                geometry,settings,native/'model.xml',gerber_quality=profile.name,**field_options)
            if native_mesh!=mesh:
                raise ConfigurationError('Native PCB mesh differs from source preflight mesh.')
            result=dict(status='prepared',preparation=preparation)
            diagnostics['termination_status']='not_run'
            print(f"XML: {native/'model.xml'}",flush=True)
        else:
            # Keep output empty until this existing controller has claimed it.
            result=run_control_model(geometry,settings,output,gerber_quality=profile.name,
                expected_domain_mesh=mesh,exact_endcriteria=settings.runtime.exact_endcriteria,
                dump_statistics=settings.runtime.dump_statistics,**field_options)
            if settings.runtime.dump_statistics:
                iterations=result['native_statistics']['number_of_iterations']
                diagnostics['actual_iterations']=iterations
                if not 0<iterations<settings.max_timesteps:
                    raise ConfigurationError('PCB native termination not established: timestep limit reached.')
                diagnostics['termination_status']='completed_before_limit'
                result['status']='completed'
            else:
                diagnostics['termination_status']='not_established_statistics_disabled'
                result['status']='finished_unverified'
            result['note']=result['note'].replace('First synthetic PCB FDTD control result.',
                                                   'PCB FDTD result imported from EasyEDA project geometry.')
            result.update(sampled_diagnostics(result))
        result.update(diagnostics)
        result['import']=provenance
        if not prepare_only:print_sweep_summary(result)
    except (Exception,KeyboardInterrupt) as exc:
        if isinstance(exc,QuantizationError):
            diagnostics['geometry_resolution']=dict(exc.audit,requested_um=geometry_resolution_um,quantum_nm=grid.quantum_nm)
        stats_path=output/'native/openEMS_stats.txt'
        if (output/'native').exists():diagnostics['termination_status']='not_established'
        if stats_path.exists():
            try:
                stats=read_pcb_native_statistics(stats_path)
                diagnostics['actual_iterations']=stats['number_of_iterations']
                if stats['number_of_iterations']>=settings.max_timesteps:
                    diagnostics['termination_status']='max_timesteps_reached'
            except ConfigurationError:
                pass
        result=dict(diagnostics,status='failed',failed_stage=stage,error=str(exc),import_metadata=provenance)
        raise
    finally:
        for name,value in snapshots.items():_write_json(output/name,value)
        _write_json(output/'import.json',provenance)
        _write_json(output/'summary.json',result)
    if not prepare_only:
        # Existing offline PCB report, with the same best-effort solve protection.
        try:
            from antenna_lab.visualization.report import generate_report
            report=generate_report(output,automatic=True,phase_step=settings.runtime.report_phase_step_deg)
            print(f'Raport HTML: {report}',flush=True)
        except Exception as exc:
            warning=f'Nie utworzono raportu HTML: {type(exc).__name__}: {exc}. Wyniki FDTD zachowane.'
            result.setdefault('warnings',[]).append(warning)
            print(warning,file=sys.stderr,flush=True)
            try:_write_json(output/'summary.json',result)
            except OSError as error:print(f'Nie zapisano ostrzeżenia raportu: {error}',file=sys.stderr)
    return json.loads(json.dumps(result,allow_nan=False))


def main(argv=None):
    parser=argparse.ArgumentParser(description='EasyEDA D4 project -> existing PCB openEMS full-wave pipeline')
    parser.add_argument('--easyeda-project',type=Path,required=True)
    parser.add_argument('--source-pcb-id')
    parser.add_argument('--source-config',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--geometry-resolution-um',type=float,choices=(100,10,1,.1),default=10)
    parser.add_argument('--quality',choices=('preview','design','verify'))
    parser.add_argument('--openems-config',type=Path,default=DEFAULT_CONFIG)
    parser.add_argument('--openems-set',action='append',default=[],metavar='KEY=VALUE')
    parser.add_argument('--yes',action='store_true')
    parser.add_argument('--no-fields',action='store_true')
    parser.add_argument('--fields-mhz',type=float,nargs='+')
    parser.add_argument('--prepare-only',action='store_true')
    add_frequency_arguments(parser);parser.set_defaults(frequencies_mhz=None)
    for name in ('start','stop','step'):parser.add_argument(f'--sweep-{name}-mhz',type=float)
    args=parser.parse_args(argv)
    try:
        request=(args.sweep_start_mhz,args.sweep_stop_mhz,args.sweep_step_mhz)
        sweep=any(v is not None for v in request)
        if sweep and (not all(v is not None for v in request) or args.frequencies_mhz is not None):
            raise ConfigurationError('Provide all sweep start/stop/step values, without --frequencies-mhz.')
        if args.frequencies_mhz is None:args.frequencies_mhz=[1300.,1420.,1500.]
        band=frequency_arguments_hz(args)
        if sweep:band['result_frequency_hz']=sweep_frequencies_hz(*request)
        profile=approve_profile(dict(name=args.quality,config_path=args.openems_config,experiment=band,
            cli_overrides=dict(parse_override(v) for v in args.openems_set),
            field_frequency_hz=None if args.fields_mhz is None else tuple(f*1e6 for f in args.fields_mhz),
            no_fields=args.no_fields),yes=args.yes,prepare_only=args.prepare_only)
        if profile is None:
            print('Cancelled before native preparation/FDTD.');return 0
        output=args.output or allocate_output_dir(args.easyeda_project,Path('outcomes/pcb_easyeda'))
        result=run_easyeda_control(args.easyeda_project,output,source_config=args.source_config,
            source_pcb_id=args.source_pcb_id,prepare_only=args.prepare_only,
            geometry_resolution_um=args.geometry_resolution_um,resolved_profile=profile,
            sweep_request=request if sweep and tuple(profile.settings.result_frequency_hz)==tuple(band['result_frequency_hz']) else None)
        print(f"Status: {result['status']}; validation_status: unverified\n{output.resolve()/'summary.json'}")
        if not args.prepare_only:print(output.resolve()/'impedance.csv')
        return 0
    except (ConfigurationError,OSError,RuntimeError,ValueError,KeyboardInterrupt) as exc:
        print(f'PCB EasyEDA: {exc}',file=sys.stderr);return 1


if __name__=='__main__':
    raise SystemExit(main())
