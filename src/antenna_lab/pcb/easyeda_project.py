"""Bounded, read-only EasyEDA Pro V2 project/library resolver.

No extraction to disk, Gerber fallback, Device override of PCB footprints or
native imports. Archive records and member hashes remain detached provenance.
"""
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile
import json
import stat

from antenna_lab.core.config import ConfigurationError

MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 4096
MAX_RECORDS = 1_000_000
MAX_COMPRESSION_RATIO = 1000


def strict_json(text, label):
    def bad(value):
        raise ValueError('non-finite JSON ' + value)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key ' + key)
            result[key] = value
        return result
    try:
        result = json.loads(text, parse_constant=bad, object_pairs_hook=pairs)
        json.dumps(result, allow_nan=False)
        return result
    except (ValueError, TypeError, RecursionError) as exc:
        raise ConfigurationError(f'EasyEDA {label}: invalid strict JSON: {exc}') from exc


def documents(raw, name):
    """Split concatenated 1.8 documents; keep physical source line numbers."""
    result = []
    current = None
    try:
        lines = raw.decode('utf-8-sig').splitlines()
    except UnicodeError as exc:
        raise ConfigurationError(f'EasyEDA {name}: invalid UTF-8.') from exc
    if len(lines) > MAX_RECORDS:
        raise ConfigurationError(f'EasyEDA {name}: record limit exceeded.')
    for index, line in enumerate(lines, 1):
        if not line.strip():
            continue
        r = strict_json(line, f'{name}:{index}')
        if r == []:  # Explicit separator emitted by the V2 editor.
            continue
        if not isinstance(r, list) or not r or not isinstance(r[0], str):
            raise ConfigurationError(f'EasyEDA {name}:{index}: primitive array required.')
        if r[0] == 'DOCTYPE':
            if r not in (['DOCTYPE', 'PCB', '1.8'], ['DOCTYPE', 'FOOTPRINT', '1.8']):
                raise ConfigurationError(f'EasyEDA {name}:{index}: unsupported document/version {r!r}.')
            current = dict(kind=r[1], start_line=index, records=[], source_file=name,
                           source_sha256=sha256(raw).hexdigest())
            result.append(current)
        if current is None:
            raise ConfigurationError(f'EasyEDA {name}:{index}: missing DOCTYPE.')
        current['records'].append(dict(record_index=index, data=r))
    if not result:
        raise ConfigurationError(f'EasyEDA {name}: empty document.')
    for doc in result:
        heads = [e['data'][1] for e in doc['records'] if e['data'][0] == 'HEAD']
        if len(heads) > 1 or (heads and not isinstance(heads[0], dict)):
            raise ConfigurationError(f'EasyEDA {name}: ambiguous HEAD.')
        doc['head'] = heads[0] if heads else {}
        editor = doc['head'].get('editorVersion')
        if editor is not None and (not isinstance(editor, str) or not editor.startswith('2.2.')):
            raise ConfigurationError(f'EasyEDA {name}: unsupported editorVersion {editor!r}.')
    return result


@dataclass(frozen=True)
class EasyEdaProject:
    """Immutable detached archive selection; JSON properties return copies."""
    archive_path: str
    archive_sha256: str
    pcb_id: str
    data_json: str

    @property
    def data(self):
        return json.loads(self.data_json)

    def as_dict(self):
        return dict(archive_path=self.archive_path, archive_sha256=self.archive_sha256,
                    pcb_id=self.pcb_id, **self.data)


def load_easyeda_project(path, *, pcb_id=None):
    path = Path(path)
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ConfigurationError('EasyEDA archive exceeds compressed byte limit.')
    digest = sha256(path.read_bytes()).hexdigest()
    members = {}; manifest = []
    try:
        with ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
                raise ConfigurationError('EasyEDA archive member/expanded-byte limit exceeded.')
            seen = set()
            for i in infos:
                name = i.filename
                parts = name.rstrip('/').split('/')
                if (not name or '\\' in name or '\x00' in name or ':' in name or
                    name.startswith('/') or any(p in ('', '.', '..') for p in parts) or
                    name.casefold() in seen):
                    raise ConfigurationError(f'EasyEDA unsafe/duplicate archive member {name!r}.')
                seen.add(name.casefold())
                mode = i.external_attr >> 16
                if stat.S_ISLNK(mode) or i.flag_bits & 1:
                    raise ConfigurationError(f'EasyEDA encrypted/link member unsupported: {name}.')
                if i.file_size > MAX_MEMBER_BYTES or i.file_size > MAX_COMPRESSION_RATIO * max(i.compress_size, 1):
                    raise ConfigurationError(f'EasyEDA decompression limit: {name}.')
                if i.is_dir():
                    continue
                raw = z.read(i)  # Verifies CRC for every file, including unused symbols.
                if len(raw) != i.file_size:
                    raise ConfigurationError(f'EasyEDA truncated member: {name}.')
                members[name] = raw
                manifest.append(dict(path=name, bytes=len(raw), sha256=sha256(raw).hexdigest()))
    except (BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ConfigurationError(f'EasyEDA invalid archive/integrity: {exc}') from exc
    if 'project.json' not in members:
        raise ConfigurationError('EasyEDA archive requires root project.json.')
    project = strict_json(members['project.json'].decode('utf-8-sig'), 'project.json')
    if not isinstance(project, dict) or not isinstance(project.get('config'), dict):
        raise ConfigurationError('EasyEDA project.json: project/config object required.')
    editor = project['config'].get('editorVersion', '')
    if not isinstance(editor, str) or not editor.startswith('2.2.'):
        raise ConfigurationError(f'EasyEDA project version unsupported: {editor!r}; V2 2.2.x required.')
    pcbs = project.get('pcbs')
    if not isinstance(pcbs, dict) or not pcbs:
        raise ConfigurationError('EasyEDA project.json: nonempty pcbs index required.')
    if pcb_id is None:
        if len(pcbs) != 1:
            raise ConfigurationError(f'EasyEDA ambiguous PCB selection: {sorted(pcbs)}; supply --source-pcb-id.')
        pcb_id = next(iter(pcbs))
    if pcb_id not in pcbs:
        raise ConfigurationError(f'EasyEDA PCB ID {pcb_id!r} absent from project index.')
    pcb_name = f'PCB/{pcb_id}.epcb'
    if pcb_name not in members:
        raise ConfigurationError(f'EasyEDA missing PCB document {pcb_name}.')
    docs = documents(members[pcb_name], pcb_name)
    selected = [d for d in docs if d['kind'] == 'PCB']
    if len(selected) != 1:
        raise ConfigurationError(f'EasyEDA {pcb_name}: require exactly one PCB document.')
    footprints = []
    for name in sorted(members):
        if name.startswith('FOOTPRINT/') and name.endswith('.efoo'):
            blocks = documents(members[name], name)
            if len(blocks) != 1 or blocks[0]['kind'] != 'FOOTPRINT':
                raise ConfigurationError(f'EasyEDA {name}: one FOOTPRINT document required.')
            footprints.append(dict(key=PurePosixPath(name).stem, **blocks[0]))
    for doc in docs:
        if doc['kind'] == 'FOOTPRINT':
            key = doc['head'].get('uuid')
            if not isinstance(key, str) or not key:
                raise ConfigurationError(f'EasyEDA embedded FOOTPRINT at {doc["start_line"]}: HEAD.uuid required.')
            footprints.append(dict(key=key, **doc))
    data = dict(project=project, pcb=selected[0], footprints=footprints, members=manifest,
                archive_integrity='crc_passed', manufacturing_validation='not_requested')
    return EasyEdaProject(str(path), digest, pcb_id, json.dumps(data, sort_keys=True, allow_nan=False))


def resolve_project_components(project):
    """Resolve identities and PAD_NET BEFORE materialization; not a geometry PASS."""
    data = project.data
    records = data['pcb']['records']
    direct = {}; aliases = {}
    for fp in data['footprints']:
        if fp['key'] in direct:
            raise ConfigurationError(f'EasyEDA duplicate footprint identity {fp["key"]}.')
        direct[fp['key']] = fp
        for alias in (fp['head'].get('uuid'), fp['head'].get('source')):
            if isinstance(alias, str) and alias:
                aliases.setdefault(alias, []).append(fp)
    attrs = {}; mappings = {}; components = []
    for e in records:
        r = e['data']
        if r[0] == 'ATTR' and len(r) >= 9:
            target = attrs.setdefault(r[3], {})
            if r[7] in target and target[r[7]] != r[8]:
                raise ConfigurationError(f'EasyEDA conflicting ATTR {r[3]}/{r[7]}.')
            target[r[7]] = r[8]
        elif r[0] == 'PAD_NET':
            if len(r) not in (4, 5):
                raise ConfigurationError(f'EasyEDA malformed PAD_NET at {e["record_index"]}.')
            mappings.setdefault(r[1], []).append(e)
        elif r[0] == 'COMPONENT':
            components.append(e)
    resolved = []; seen = set(); source_indices = []
    for entry in components:
        r = entry['data']; cid = r[1]
        if cid in seen or len(r) not in (9, 10) or not isinstance(r[7], dict):
            raise ConfigurationError(f'EasyEDA invalid/duplicate COMPONENT {cid}.')
        seen.add(cid)
        a = dict(r[7]); a.update(attrs.get(cid, {}))
        device_id = a.get('Device')
        device = data['project'].get('devices', {}).get(device_id, {})
        explicit = a.get('Footprint')
        key = explicit if explicit else device.get('attributes', {}).get('Footprint')
        if not isinstance(key, str) or not key:
            raise ConfigurationError(f'EasyEDA COMPONENT {cid}: missing footprint reference (PCB and Device fallback).')
        candidates = [direct[key]] if key in direct else aliases.get(key, [])
        if len(candidates) != 1:
            raise ConfigurationError(f'EasyEDA COMPONENT {cid}: footprint {key!r} missing/ambiguous; candidates={[f["key"] for f in candidates]}.')
        fp = candidates[0]
        pads = [e for e in fp['records'] if e['data'][0] == 'PAD']
        ids = {}; numbers = {}
        for p in pads:
            pad = p['data']
            if len(pad) < 12 or not isinstance(pad[5], str) or pad[1] in ids:
                raise ConfigurationError(f'EasyEDA {fp["source_file"]}: malformed/duplicate PAD.')
            ids[pad[1]] = p
            numbers.setdefault(pad[5], []).append(pad[1])
        assigned = {}; bindings = []
        for m in mappings.get(cid, []):
            mr = m['data']; num = mr[2]; pid = mr[4] if len(mr) == 5 else None
            if pid is None:
                choices = numbers.get(num, [])
                if len(choices) != 1:
                    raise ConfigurationError(f'EasyEDA {cid}: PAD_NET number {num!r} ambiguous/missing ID.')
                pid = choices[0]
            if pid not in ids or ids[pid]['data'][5] != num:
                raise ConfigurationError(f'EasyEDA {cid}: PAD_NET number/ID mismatch {num!r}/{pid!r}.')
            if pid in assigned:
                raise ConfigurationError(f'EasyEDA {cid}: duplicate PAD_NET for {pid}.')
            assigned[pid] = mr[3]
            bindings.append(dict(pad_id=pid, pad_number=num, net=mr[3], record_index=m['record_index']))
        if set(assigned) != set(ids):
            raise ConfigurationError(f'EasyEDA {cid}: unmapped footprint pads {sorted(set(ids)-set(assigned))}; no guessed nets.')
        ref = a.get('Designator', cid)
        source_index = None
        if ref == 'CSRC' or a.get('Solver Role') == 'source':
            value = a.get('Value')  # Never from Device's nominal capacitor value.
            if not isinstance(value, str) or not value.isascii() or not value.isdigit():
                raise ConfigurationError(f'EasyEDA source {ref}: explicit nonnegative integer Value required.')
            source_index = int(value)
            source_indices.append(source_index)
        resolved.append(dict(component_id=cid, designator=ref, source_index=source_index,
            role='source' if source_index is not None else 'component', attributes=a,
            device_id=device_id, footprint_key=fp['key'], footprint_reference=key,
            footprint_resolution='pcb_explicit' if explicit else 'device_fallback',
            footprint_title=data['project'].get('footprints', {}).get(fp['key'], {}).get('title', fp['head'].get('title')),
            footprint=fp, component_record=entry, bindings=bindings))
    if set(mappings)-seen:
        raise ConfigurationError(f'EasyEDA PAD_NET references missing COMPONENT: {sorted(set(mappings)-seen)}.')
    if sorted(source_indices) != list(range(len(source_indices))):
        raise ConfigurationError('EasyEDA explicit source indices must be unique and contiguous from 0.')
    return resolved


def materialize_project_source(project):
    """Resolve pads in SI then reuse existing source parser/canonical pipeline."""
    from .easyeda import parse_easyeda_source
    from .easyeda_footprints import instantiate_components
    resolved = resolve_project_components(project)
    data = project.data
    pcb = data['pcb']
    # Parse the selected PCB block without changing/hash-replacing original bytes.
    raw = '\n'.join(json.dumps(e['data']) for e in pcb['records']).encode()
    source = parse_easyeda_source(raw, source_file=pcb['source_file'])
    line_map = {i+1:e['record_index'] for i,e in enumerate(pcb['records'])}
    source = replace(source, source_sha256=pcb['source_sha256'],
        records_json=json.dumps(pcb['records'], sort_keys=True, allow_nan=False),
        routes=tuple(replace(r, record_index=line_map[r.record_index], source_sha256=pcb['source_sha256']) for r in source.routes),
        vias=tuple(replace(v, record_index=line_map[v.record_index], source_sha256=pcb['source_sha256']) for v in source.vias))
    semantic = source.semantics
    instances, pads, drills = instantiate_components(resolved, semantic['layers'], semantic['nets'])
    semantic['pads'].extend(pads)
    semantic.update(resolved_components=instances, footprint_drills=drills,
        project_provenance=project.as_dict())
    return replace(source, semantic_json=json.dumps(semantic, sort_keys=True, allow_nan=False))
