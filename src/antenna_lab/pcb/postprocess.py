"""Replayable PCB result processing. Never imports CAD or executes FDTD.

The immutable preparation manifest is the boundary between the model builder
and the result reader. Recovery writes a separate revision, never raw evidence.
"""
import argparse
from dataclasses import asdict, fields, is_dataclass
import hashlib
import json
from pathlib import Path
import shutil
from types import UnionType
from typing import get_args, get_origin, get_type_hints, Union

from antenna_lab.core.config import ConfigurationError


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                          parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f'PCB artifact {path}: {exc}') from exc


def write_json(path, value):
    path = Path(path)
    text = json.dumps(value, indent=2, allow_nan=False)+'\n'
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)


def _restore(cls, value):
    """Decode only the statically declared dataclass types, never JSON class names."""
    if value is None:
        return None
    origin, args = get_origin(cls), get_args(cls)
    if origin in (Union, UnionType):
        cls = next(t for t in args if t is not type(None))
        return _restore(cls, value)
    if is_dataclass(cls):
        from .model import PcbDrill, QuantizedPcbDrill
        if cls is PcbDrill and 'geometry_resolution_nm' in value:
            cls = QuantizedPcbDrill
        hints = get_type_hints(cls)
        return cls(**{f.name: _restore(hints[f.name], value[f.name])
                      for f in fields(cls) if f.name in value})
    if origin in (list, tuple):
        if origin is tuple and args and args[-1] is not Ellipsis:
            return tuple(_restore(t, v) for t, v in zip(args, value))
        return origin(_restore(args[0], v) for v in value)
    return value


def save_preparation(output, geometry, settings, mesh, spec, metadata, *, context=None):
    """Called after XML preparation but BEFORE Run. No native objects serialized."""
    output = Path(output)
    manifest = dict(schema_version=1, model='pcb', native_directory='native',
        geometry=geometry.as_dict(), simulation_settings=asdict(settings),
        domain_mesh=asdict(mesh), port=asdict(spec), preparation=metadata,
        context=context or {}, xml_sha256=hashlib.sha256((output/'native/model.xml').read_bytes()).hexdigest())
    path = output/'pcb-run.json'
    if path.exists():
        raise ConfigurationError(f'Immutable preparation already exists: {path}')
    write_json(path, manifest)
    write_json(output/'geometry.json', manifest['geometry'])
    for name, value in (context or {}).get('artifacts', {}).items():
        if Path(name).name != name:
            raise ConfigurationError('Preparation artifact must be a filename.')
        write_json(output/name, value)
    return manifest


def native_directory(root):
    candidates = [root/name for name in ('native', 'openems') if (root/name/'model.xml').is_file()]
    if len(candidates) != 1:
        raise ConfigurationError(f'PCB requires exactly one native/ or openems/ directory containing model.xml; found {candidates}')
    return candidates[0]


def load_preparation(root):
    root = Path(root)
    if (root/'pcb-run.json').is_file():
        value = read_json(root/'pcb-run.json')
        if value.get('schema_version') != 1 or value.get('model') != 'pcb':
            raise ConfigurationError('Unsupported PCB preparation manifest version/model.')
    else:
        # Legacy compatibility uses explicit recorded contracts only. No CAD import,
        # new meshing, inferred port width, frequencies or guessed default material.
        summary = read_json(root/'summary.json')
        value = dict(schema_version=1, model='pcb', context={'summary': summary},
                     preparation=summary.get('preparation'),
                     simulation_settings=summary.get('simulation_settings'))
        for key, filename in (('geometry','geometry.json'), ('domain_mesh','mesh.json')):
            value[key] = read_json(root/filename) if (root/filename).is_file() else None
        value['port'] = (value['preparation'] or {}).get('port')
    missing = [k for k in ('geometry','simulation_settings','domain_mesh','port','preparation') if not value.get(k)]
    if missing:
        raise ConfigurationError('Incomplete PCB preparation; missing explicit artifacts: '+', '.join(missing)+
                                 '. Preserve raw probes/HDF5/XML; no values will be guessed.')
    native = native_directory(root)
    if value.get('xml_sha256') and hashlib.sha256((native/'model.xml').read_bytes()).hexdigest()!=value['xml_sha256']:
        raise ConfigurationError('PCB model.xml differs from immutable preparation SHA256.')
    return value, native


def restore_inputs(manifest):
    from .model import PcbGeometry
    from .simulation import PcbSimulationSettings, validate_pcb_simulation_settings
    from antenna_lab.solvers.pcb_mesh import PcbDomainMesh
    from .port import PcbLumpedPortSpec
    try:
        geometry = _restore(PcbGeometry, manifest['geometry'])
        settings = _restore(PcbSimulationSettings, manifest['simulation_settings'])
        mesh = _restore(PcbDomainMesh, manifest['domain_mesh'])
        spec = _restore(PcbLumpedPortSpec, manifest['port'])
        validate_pcb_simulation_settings(settings)
        import math
        axes = [getattr(mesh, a+'_lines_m') for a in 'xyz']
        if any(len(a)<2 or any(not math.isfinite(v) for v in a) or
               any(x>=y for x,y in zip(a,a[1:])) for a in axes):
            raise ValueError('domain_mesh requires finite strictly increasing complete axes')
        shape = tuple(len(a)-1 for a in axes)
        if shape!=mesh.shape_cells or math.prod(shape)!=mesh.cell_count:
            raise ValueError('domain_mesh shape/cell_count inconsistent with saved axes')
        if spec.exc_dir!='x' or spec.start_m[2]!=0. or spec.stop_m[2]!=0.:
            raise ValueError('unsupported saved planar port contract')
        for axis,lo,hi in zip(axes,spec.start_m,spec.stop_m):
            if lo not in axis or hi not in axis:
                raise ValueError('saved port boundary missing from saved mesh')
        if spec.reference_impedance_ohm!=settings.reference_impedance_ohm:
            raise ValueError('saved port reference differs from simulation settings')
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f'Incomplete/invalid saved PCB contract: {exc}') from exc
    return geometry, settings, mesh, spec


def process_results(manifest, native, output, *, port=None, execution=None):
    """Shared normal/recovery pipeline. Port and fields have independent outcomes."""
    from antenna_lab.solvers.openems_pcb import postprocess_pcb_port, write_pcb_port_results, pcb_termination_evidence
    geometry, settings, mesh, spec = restore_inputs(manifest)
    output = Path(output)
    result = dict(manifest.get('context', {}).get('summary', {}))
    for key in ('frequency_hz','reference_impedance_ohm','resistance_ohm','reactance_ohm',
                's11_real','s11_imag','s11_magnitude','s11_db','swr','fields',
                'field_port_reference','native_statistics','stages'):
        result.pop(key, None)
    result.update(status='postprocess_failed', validation_status='unverified',
                  preparation=manifest['preparation'], simulation_settings=manifest['simulation_settings'])
    stages = {'engine': execution or {'status':'not_recorded'}, 'port': {'status':'pending'},
              'fields': {'status':'not_requested'}, 'report': {'status':'not_requested'}}
    statistics, termination = pcb_termination_evidence(settings, native)
    if statistics is not None:
        result['native_statistics'] = statistics
    stages['temporal_completion'] = termination
    result['termination_status'] = termination['status']
    field_data = manifest['preparation'].get('fields', {})
    frequencies = field_data.get('frequency_hz', ())
    try:
        if port is None:
            from antenna_lab.solvers.openems_pcb import restore_pcb_port_reader
            port = restore_pcb_port_reader(spec, mesh)
        result.update(postprocess_pcb_port(port, mesh, settings, native, field_frequency_hz=frequencies))
        stages.update(result.pop('stages'))
        result['mesh'].update(min_step_m=mesh.min_step_m, max_step_m=mesh.max_step_m,
                              worst_growth_ratio=mesh.worst_growth_ratio)
        from .gerber_sweep import sampled_diagnostics
        result.update(sampled_diagnostics(result))
        # Commit valid spectrum before potentially failing field conversion.
        write_pcb_port_results(result, output)
    except Exception as exc:
        stages['port'] = {'status':'failed', 'reason':f'{type(exc).__name__}: {exc}'}
    if frequencies:
        if stages['port']['status'] != 'processed':
            stages['fields'] = {'status':'blocked', 'reason':'No valid port-voltage phase reference.'}
        else:
            try:
                from tempfile import TemporaryDirectory
                from antenna_lab.solvers.pcb_fields import finish_pcb_fields
                if not field_data.get('planes'):
                    raise ConfigurationError('Missing saved field-plane layout.')
                if (output/'fields').exists():
                    raise ConfigurationError('Refusing to overwrite an existing field artifact set.')
                combined = None
                failures = {}
                for plane in field_data['planes']:
                    try:
                        with TemporaryDirectory(dir=output, prefix='field-processing-') as temporary:
                            converted = finish_pcb_fields(geometry, mesh, [plane], frequencies,
                                result['field_port_reference'], temporary, native_dir=native)
                            if combined is None:
                                combined = dict(converted, planes=[])
                                (output/'fields').mkdir()
                            combined['planes'].extend(converted['planes'])
                            shutil.move(str(Path(temporary)/'fields'/(plane['name']+'.npz')),
                                        str(output/'fields'/(plane['name']+'.npz')))
                    except Exception as exc:
                        failures[plane['name']] = f'{type(exc).__name__}: {exc}'
                if combined:
                    combined['failed_planes'] = failures
                    write_json(output/'fields/metadata.json', combined)
                    result['fields'] = combined
                stages['fields'] = {'status': 'partial' if failures and combined else
                                    'failed' if failures else 'processed'}
                if failures:
                    stages['fields']['reason'] = str(failures)
            except Exception as exc:
                stages['fields'] = {'status':'failed', 'reason':f'{type(exc).__name__}: {exc}'}
    if result.get('status') == 'completed' and stages['engine'].get('status') != 'returned':
        result['status'] = 'finished_unverified'
    result['stages'] = stages
    result['warnings'] = list(result.get('warnings', []))
    for name, state in stages.items():
        if state.get('reason'):
            result['warnings'].append(f"{name}: {state['reason']}")
    if stages['port']['status']=='processed' and stages['fields']['status'] in ('failed','partial'):
        result['status']='postprocess_partial'
    write_json(output/'summary.json', result)
    return result


def render_report(output, result, *, phase_step=None):
    try:
        from antenna_lab.visualization.report import generate_report
        path = generate_report(output, automatic=True, **({'phase_step':phase_step} if phase_step else {}))
        result['stages']['report'] = {'status':'generated', 'path':str(path)}
        print(f'Raport HTML: {path}')
    except Exception as exc:
        result['stages']['report'] = {'status':'failed', 'reason':f'{type(exc).__name__}: {exc}'}
        result.setdefault('warnings', []).append(f'Report: {type(exc).__name__}: {exc}; FDTD artifacts preserved.')
    try:
        write_json(Path(output)/'summary.json', result)
    except OSError as exc:
        print(f'Report status could not be saved: {exc}; prior result artifacts preserved.')


def recover_run(run_dir, *, render=True, reuse=True):
    """Read original artifacts; write isolated revision. Never overwrite originals."""
    from .output import allocate_output_dir
    root = Path(run_dir).resolve()
    destination = None
    # Existing complete processed data is sufficient for offline re-rendering.
    if reuse and (root/'impedance.csv').is_file() and (root/'summary.json').is_file():
        summary = read_json(root/'summary.json')
        requested = summary.get('preparation', {}).get('fields', {}).get('frequency_hz', [])
        field_meta = root/'fields/metadata.json'
        complete_fields = not requested
        if requested and field_meta.is_file():
            from antenna_lab.visualization.fields import load_plane
            metadata = read_json(field_meta)
            expected_names = {p['name'] for p in summary['preparation']['fields']['planes']}
            complete_fields = {p['name'] for p in metadata['planes']} == expected_names
            try:
                for plane in metadata['planes']:
                    load_plane(root/'fields'/(plane['name']+'.npz'), plane, requested)
            except (OSError, ValueError, KeyError):
                complete_fields = False
        if summary.get('frequency_hz') and complete_fields:
            from antenna_lab.visualization.report_data import load_report_data
            load_report_data(root)  # Validate saved spectrum before treating it as reusable.
            destination = allocate_output_dir(Path('postprocess'), root/'postprocessed')
            for name in ('impedance.csv','summary.json','geometry.json','import.json'):
                if (root/name).is_file(): shutil.copy2(root/name, destination/name)
            if field_meta.is_file(): shutil.copytree(root/'fields', destination/'fields')
            summary.setdefault('stages', {})['postprocess']={'status':'reused', 'source':str(root)}
            if render: render_report(destination, summary)
            else: write_json(destination/'summary.json', summary)
            return destination, summary
    manifest, native = load_preparation(root)
    restore_inputs(manifest)
    destination = allocate_output_dir(Path('postprocess'), root/'postprocessed')
    write_json(destination/'geometry.json', manifest['geometry'])
    if (root/'import.json').is_file(): shutil.copy2(root/'import.json', destination/'import.json')
    execution = read_json(root/'execution.json') if (root/'execution.json').is_file() else None
    result = process_results(manifest, native, destination, execution=execution)
    result['recovery_source'] = str(root)
    if render: render_report(destination, result)
    else: write_json(destination/'summary.json', result)
    return destination, result


def main(argv=None):
    parser = argparse.ArgumentParser(description='PCB offline postprocessing; never runs FDTD')
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--recompute', action='store_true', help='Re-read raw probes/fields instead of reusing processed files')
    args = parser.parse_args(argv)
    try:
        output, result = recover_run(args.run_dir, reuse=not args.recompute)
        print(f'Postprocessing: {output}\nStatus: {result["status"]}')
        print(json.dumps(result.get('stages', {}), indent=2))
        return int(any(v.get('status') in ('failed','blocked','partial') for v in result.get('stages', {}).values()))
    except (ConfigurationError, OSError, ValueError) as exc:
        print(f'PCB postprocessing: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
