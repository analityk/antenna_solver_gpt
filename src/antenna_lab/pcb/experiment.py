"""ZIP experiment resolution: independent local -> one parent resource lookup."""
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from antenna_lab.core.config import ConfigurationError
from .easyeda_stackup import stackup_format, normalize_stackup
from .sources import file_sha256, zip_members, resolve_bundle_root


@dataclass(frozen=True)
class ResolvedResource:
    source_path: Path
    source_sha256: str
    source_directory: Path
    scope: str
    format: str

    def metadata(self):
        return {k:str(v) if isinstance(v,Path) else v for k,v in asdict(self).items()}


@dataclass(frozen=True)
class ResolvedExperiment:
    archive_path: Path
    archive_sha256: str
    logical_bundle_root: str
    stackup: ResolvedResource
    netlist: ResolvedResource
    members: tuple
    physical_json: str
    stackup_audit_json: str
    input_kind: str = 'zip'

    def metadata(self):
        return dict(input_kind=self.input_kind,gerber_archive=dict(path=str(self.archive_path),
                    sha256=self.archive_sha256,bundle_root=self.logical_bundle_root),
                    stackup=self.stackup.metadata(),netlist=self.netlist.metadata(),
                    stackup_normalization=json.loads(self.stackup_audit_json))


def _json(path):
    try: return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError) as exc:
        raise ConfigurationError(f'Invalid PCB stackup JSON {path}: {exc}') from exc


def _candidate_format(path, kind):
    if kind=='netlist': return 'enet' if path.suffix.lower()=='.enet' else None
    if path.suffix.lower()!='.json': return None
    try: value=json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError,UnicodeError): return None
    return stackup_format(value)


def _resolve_resource(local, kind):
    for scope,directory in (('local',local),('parent',local.parent)):
        candidates=[(p,fmt) for p in sorted(directory.iterdir(),key=lambda p:p.name)
                    if p.is_file() and (fmt:=_candidate_format(p,kind))]
        if len(candidates)>1:
            raise ConfigurationError(f'PCB ZIP {kind} ambiguous in {scope} directory {directory}: '+
                                     ', '.join(p.name for p,_ in candidates))
        if candidates:
            path,fmt=candidates[0]
            return ResolvedResource(path.resolve(),file_sha256(path),path.resolve().parent,scope,fmt)
    raise ConfigurationError(f'PCB ZIP {kind} not found: local: {local}; parent: {local.parent}')


def resolve_experiment(path, pcb_config=None):
    path=Path(path).resolve()
    members=zip_members(path)
    root,members=resolve_bundle_root(members)
    netlist=_resolve_resource(path.parent,'netlist')
    if pcb_config is not None:
        source=Path(pcb_config).resolve();value=_json(source)
        stackup=ResolvedResource(source,file_sha256(source),source.parent,'explicit_cli',stackup_format(value) or 'unknown')
    else:
        stackup=_resolve_resource(path.parent,'stackup');value=_json(stackup.source_path)
    physical,audit=normalize_stackup(value)
    return ResolvedExperiment(path,file_sha256(path),root,stackup,netlist,members,
                              json.dumps(physical,sort_keys=True,allow_nan=False),
                              json.dumps(audit,sort_keys=True,allow_nan=False))


def load_experiment_geometry(experiment):
    from .bundle import load_bundle_geometry
    probes=[m for m in experiment.members if m.name.lower()=='flyingprobetesting.json']
    if len(probes)!=1:
        raise ConfigurationError('PCB ZIP ENET requires exactly one FlyingProbeTesting.json; candidates: '+
                                 (', '.join(str(p) for p in probes) or '(none)'))
    physical=json.loads(experiment.physical_json)
    config,geometry,metadata=load_bundle_geometry(experiment.archive_path,
        physical_value=physical,members=experiment.members,
        component_sources=(experiment.netlist.source_path,probes[0]))
    for record in metadata['discovered_files']:
        if record['path']==str(probes[0]):
            record.update(role='flying_probe',disposition='modeled')
    assumptions=json.loads(experiment.stackup_audit_json)['assumptions']
    geometry.assumptions.extend(assumptions)
    metadata.update(experiment_input=experiment.metadata(),
        source_directory=str(experiment.archive_path)+'::'+experiment.logical_bundle_root,
        physical_config_source=f'{experiment.stackup.source_path} [{experiment.stackup.scope}]',
        assumptions=list(geometry.assumptions))
    return config,geometry,metadata
