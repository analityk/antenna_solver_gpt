"""FAST adapter of neutral CAD primitives, not polygon centerline recovery.

No Arc physics, coupling bypass or guessed leads. Source absolute pads can be
ideal equipotential terminal regions with exactly one route junction; this
explicitly omits their internal electrical length/parasitics.
"""
from dataclasses import asdict
from math import hypot
from shapely import union_all
from shapely.geometry import LineString,Point,Polygon
from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.regions import copper_shape
from antenna_lab.pcb.validation import TOLERANCE_M


def extract_source_sections(geometry,active_ids,section_type):
    active_ids=set(c.id for c in geometry.top_copper) if active_ids is None else active_ids
    from antenna_lab.pcb.routes import projection_fingerprint
    receipt=geometry.route_projection
    if receipt is not None and (receipt.get('kind')!='easyeda_source' or
            receipt.get('physical_topology_audit')!='passed' or
            receipt.get('geometry_sha256')!=projection_fingerprint(geometry)):
        raise ConfigurationError('Reduced EasyEDA: stale/missing physical projection audit.')
    shapes={c.id:copper_shape(c) for c in geometry.top_copper}
    for id,kind in geometry.design_source['feature_kinds'].items():
        if kind=='pour' and geometry.design_source['feature_owners'][id] in active_ids:
            raise ConfigurationError(f'Reduced EasyEDA {id}: active source POUR is not a transmission line.')
    # Source envelopes are not reconstructed from final polygon edges.
    # Check nonlocal contacts before any analytical network can be emitted.
    from antenna_lab.pcb.easyeda_model import route_shape
    raw_routes=geometry.source_routes
    if receipt is not None:
        from antenna_lab.pcb.source_ir import SourceRoutePrimitive
        raw_routes=tuple(SourceRoutePrimitive(**r) for r in receipt['source_routes'])
    selected=[r for r in raw_routes if r.layer_role=='top' and r.conductor_id in active_ids]
    for i,a in enumerate(selected):
        if a.kind!='LINE':continue
        for b in selected[:i]:
            if b.kind!='LINE' or a.conductor_id!=b.conductor_id:continue
            ends_a={tuple(a.start_xy_m),tuple(a.stop_xy_m)};ends_b={tuple(b.start_xy_m),tuple(b.stop_xy_m)}
            if ends_a==ends_b and a.width_m==b.width_m:continue
            allowed=union_all([Point(p).buffer(max(a.width_m,b.width_m)) for p in ends_a&ends_b])
            overlap=route_shape(a).intersection(route_shape(b)).difference(allowed)
            if overlap.area>TOLERANCE_M*(route_shape(a).length+route_shape(b).length):
                raise ConfigurationError(f'Reduced EasyEDA {a.id}/{b.id}: nonlocal source stroke contact unsupported.')
    sections=[];seen=set();evidence=[]
    for r in geometry.source_routes:
        if r.layer_role!='top' or r.conductor_id not in active_ids:continue
        label=f'{r.kind} {r.id}, net={r.net}, record={r.record_index}, source={r.source_file}'
        if r.kind=='ARC':raise ConfigurationError(f'Reduced EasyEDA source ARC unsupported: {label}; signed sweep={r.signed_sweep_deg}; curved/coupled TL physics not implemented.')
        if r.kind!='LINE':raise ConfigurationError('Reduced EasyEDA unsupported route '+label)
        if r.width_m<=0 or hypot(*(b-a for a,b in zip(r.start_xy_m,r.stop_xy_m)))<=TOLERANCE_M:
            raise ConfigurationError('Reduced EasyEDA collapsed route '+label)
        axis=LineString((r.start_xy_m,r.stop_xy_m))
        owners=[id for id,s in shapes.items() if s.intersects(axis)]
        if owners!=[r.conductor_id] or not shapes[r.conductor_id].buffer(TOLERANCE_M).covers(axis):
            raise ConfigurationError('Reduced EasyEDA changed/ambiguous centerline ownership: '+label)
        if geometry.design_source['conductor_nets'].get(r.conductor_id)!=r.net:
            raise ConfigurationError('Reduced EasyEDA route net ownership mismatch: '+label)
        a,b=sorted((r.start_xy_m,r.stop_xy_m));key=(r.conductor_id,a,b,r.width_m)
        if key not in seen:
            seen.add(key);sections.append(section_type('source:'+r.id,r.conductor_id,a,b,r.width_m,(r.id,)))
        evidence.append(asdict(r))
    for owner in active_ids:
        own=[s for s in sections if s.owner==owner]
        if not own:raise ConfigurationError(f'Reduced EasyEDA {owner}: active copper has no semantic LINE; pads/pours are not transmission lines.')
        # Axis connectivity is explicit CAD topology. No segment fitting.
        degree={}
        for s in own:
            for p in (s.start_xy_m,s.stop_xy_m):degree[p]=degree.get(p,0)+1
        if any(v>2 for v in degree.values()):raise ConfigurationError(f'Reduced EasyEDA {owner}: branched source route unsupported.')
        for i,a in enumerate(own):
            for b in own[:i]:
                common={a.start_xy_m,a.stop_xy_m}&{b.start_xy_m,b.stop_xy_m}
                cross=LineString((a.start_xy_m,a.stop_xy_m)).intersection(LineString((b.start_xy_m,b.stop_xy_m)))
                if not cross.is_empty and (cross.geom_type!='Point' or tuple(cross.coords[0]) not in common):
                    raise ConfigurationError(f'Reduced EasyEDA {owner}: interior/overlapping route junction unsupported.')
        pending=set(degree);todo=[min(pending)]
        while todo:
            p=todo.pop()
            if p not in pending:continue
            pending.remove(p)
            for s in own:
                if p in (s.start_xy_m,s.stop_xy_m):todo.extend((s.start_xy_m,s.stop_xy_m))
        if pending:raise ConfigurationError(f'Reduced EasyEDA {owner}: disconnected route axes; unresolved pad/junction semantics.')
    return tuple(sections),evidence


def pad_terminal_node(geometry,point,owner,sections):
    """An explicitly modeled pad is equipotential, not an inferred lead length."""
    pads=[p for p in geometry.source_pads if p.conductor_id==owner and
          Polygon(p.vertices_xy_m).buffer(TOLERANCE_M).covers(Point(point))]
    if len(pads)!=1:return []
    pad=Polygon(pads[0].vertices_xy_m)
    metal=next(copper_shape(c) for c in geometry.top_copper if c.id==owner)
    if not metal.buffer(TOLERANCE_M).covers(pad):
        raise ConfigurationError(f'Reduced EasyEDA PAD {pads[0].id}: modeled pad leaves its physical conductor.')
    points={p for s in sections if s.owner==owner for p in (s.start_xy_m,s.stop_xy_m)
            if pad.buffer(TOLERANCE_M).covers(Point(p))}
    if len(points)!=1:
        raise ConfigurationError(f'Reduced EasyEDA PAD {pads[0].id}: require exactly one source route junction; no guessed pad interconnect.')
    return sorted(points)
