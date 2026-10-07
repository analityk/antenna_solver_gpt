"""Strict multilayer folder import; Gerbonara owns all Gerber parsing."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import re

from gerbonara import GerberFile

from antenna_lab.core.config import ConfigurationError
from .gerber import _read, _outline, _copper, ASSUMPTIONS
from .model import PcbGeometry, PcbPort, Substrate, CopperImageStats
from .stackup import ResolvedPcbStackupConfig, resolve_stackup
from .validation import validate_pcb_geometry


def _layer_number(path, role):
    """Resolve inner ordinal from parsed X2 physical L-number and filename hints.

    X2 L2 means inner1. In1_Cu, InnerLayer1 and .G1/.GP1 mean inner1.
    Ambiguous/non-contiguous orders are errors, never lexicographic guesses.
    """
    parsed = GerberFile.open(path, enable_includes=False)
    function = parsed.file_attrs.get('.FileFunction', ())
    numbers = [int(v[1:]) for v in function if re.fullmatch(r'L[1-9][0-9]*', v, re.I)]
    if len(numbers) > 1:
        raise ConfigurationError(f'{path.name}: ambiguous physical layer number {function}.')
    physical = numbers[0] if numbers else None
    hints = []
    ext = re.fullmatch(r'\.g(?:p)?([1-9][0-9]*)', path.suffix.lower())
    name = re.search(r'(?:^|[_. -])(?:in|inner(?:layer)?)[_. -]?([1-9][0-9]*)(?:[_ .-]|$)', path.stem.lower())
    if ext: hints.append(int(ext[1]))
    if name: hints.append(int(name[1]))
    if role == 'inner_copper':
        if physical is not None: hints.append(physical-1)
        if not hints or min(hints) < 1 or len(set(hints)) != 1:
            raise ConfigurationError(f'{path.name}: impossible/ambiguous inner-layer ordering; numbers {hints}.')
        return hints[0], physical
    return None, physical


def discover_stackup_bundle(directory, expected_roles):
    from .bundle import _role
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise ConfigurationError(f'Gerber directory not found: {directory}')
    from .components import discover_component_sources
    component_files = discover_component_sources(directory)
    component_roles = dict(zip(component_files or (), ('enet','flying_probe')))
    records, physical_numbers = [], {}
    for path in sorted((p for p in directory.iterdir() if p.is_file()), key=lambda p:p.name):
        role = component_roles.get(path) or _role(path)
        if role == 'drill':
            from .drills import read_drill_source
            _, info = read_drill_source(path, len(expected_roles))
            role = info['classification']
        if role in ('top_copper','bottom_copper','inner_copper'):
            index, physical = _layer_number(path, role)
            role = {'top_copper':'top','bottom_copper':'bottom'}.get(role, f'inner{index}')
            if physical is not None: physical_numbers[path.name] = (role, physical)
        if role == 'unclassified_gerber':
            raise ConfigurationError(f'{path.name}: unsupported or unrecognized Gerber role; supply conventional copper/outline filenames or X2 metadata.')
        records.append(dict(name=path.name, path=str(path), role=role,
            sha256=sha256(path.read_bytes()).hexdigest(),
            disposition='modeled' if role in (*expected_roles,'outline','PTH','NPTH','enet','flying_probe') else 'omitted'))
    available = ', '.join(r['name'] for r in records)
    copper_records = [r for r in records if r['role'] in ('top','bottom') or r['role'].startswith('inner')]
    extras = [r['name'] for r in copper_records if r['role'] not in expected_roles]
    if extras:
        raise ConfigurationError('Extra copper Gerbers not represented by stackup: '+', '.join(extras))
    selected = {}
    for role in (*expected_roles, 'outline'):
        candidates = [r for r in records if r['role'] == role]
        if len(candidates) != 1:
            raise ConfigurationError(f'Require exactly one {role}; candidates: '+
                (', '.join(r['name'] for r in candidates) or '(none)')+'; available: '+available)
        selected[role] = Path(candidates[0]['path'])
    for name, (role, physical) in physical_numbers.items():
        if physical != expected_roles.index(role)+1:
            raise ConfigurationError(f'{name}: X2 L{physical} inconsistent with stackup role {role}; candidates: {available}')
    return selected, records


def load_multilayer_bundle(directory, value):
    from .bundle import detect_feed, audit_physical_feed
    roles = [v['role'] for v in value['stackup'] if v['type'] == 'copper']
    selected, records = discover_stackup_bundle(directory, roles)
    outline = _outline(_read(selected['outline'], 'board outline'))
    hashes = {r['role']:r['sha256'] for r in records if r['role'] in roles}
    layers, dielectrics = resolve_stackup(value, outline, hashes)
    copper, top_file, composition = [], None, []
    for layer in layers:
        parsed = _read(selected[layer.role], 'top copper' if layer.role == 'top' else layer.role+' copper')
        counts = {}
        polygons = _copper(parsed, counts)
        composition.append(CopperImageStats(layer.role, **counts))  # Per-file boolean union; never across Z layers.
        copper.extend(replace(p, id=layer.role+':'+p.id, z_m=layer.z_m, layer_role=layer.role) for p in polygons)
        if layer.role == 'top': top_file = parsed
    from .components import load_components, IDEAL_NOTE
    netfiles = {r['role']:Path(r['path']) for r in records if r['role'] in ('enet','flying_probe')}
    components, source_port = (), None
    if netfiles:
        port, components, source_port = load_components(netfiles['enet'], netfiles['flying_probe'], copper)
        feed = dict(mode='enet_CSRC', source_refdes='CSRC', source_pin_nets=source_port.source_pin_nets)
    elif value['port']['mode'] == 'auto':
        port, feed = detect_feed(top_file, [c for c in copper if c.layer_role == 'top'])
    else:
        p = value['port']
        port = PcbPort('gerber_feed', tuple(v*1e-3 for v in p['negative_mm']),
                       tuple(v*1e-3 for v in p['positive_mm']), p['width_mm']*1e-3)
        feed = dict(mode='explicit')
    feed['layer'] = 'top'
    first = dielectrics[0]
    # Compatibility view only; solvers/mesh use all actual dielectric layers.
    substrate = Substrate(outline, first.z_min_m, first.z_max_m, first.epsilon_r, first.loss_tangent)
    assumptions = [a for a in ASSUMPTIONS if not a.startswith(('top copper:', 'no bottom copper', 'no vias', 'substrate parameters:'))]
    assumptions += ['stackup materials: from physical config v2, assumptions/unverified',
        'PTH barrel model: solid PEC equivalent cylinder; plating losses and hollow barrel geometry are not modeled.',
        'absence of drill files does not establish physical completeness',
        'copper roughness: omitted', 'conducting-sheet thickness: material parameter; no geometric extrusion']
    geometry = PcbGeometry('pcb', outline, copper, substrate, port, assumptions, dielectrics, layers, tuple(composition))
    geometry.components, geometry.source_port = components, source_port
    if source_port: geometry.assumptions.append(IDEAL_NOTE)
    from .drills import load_drills
    geometry, drill_sources = load_drills(geometry, records, value.get('drills'))
    validate_pcb_geometry(geometry); audit_physical_feed(geometry)
    config = ResolvedPcbStackupConfig(2, 'pcb', selected['top'], selected['outline'], layers, dielectrics,
        port.negative_xy_m, port.positive_xy_m, port.width_m)
    return config, geometry, dict(source_directory=str(Path(directory).resolve()), discovered_files=records,
        drill_sources=drill_sources, physical_config=value, physical_config_source='--pcb-config v2 (unverified assumptions)', feed_detection=feed)
