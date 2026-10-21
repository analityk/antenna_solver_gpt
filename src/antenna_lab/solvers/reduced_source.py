"""FAST adapter of neutral CAD primitives, not polygon centerline recovery.

Analytic source ARC metrics; no coupling bypass or guessed leads. Source absolute pads can be
ideal equipotential terminal regions with exactly one route junction; this
explicitly omits their internal electrical length/parasitics.
"""
from dataclasses import asdict
from math import hypot, isfinite, radians, sin, cos
from shapely import union_all
from shapely.geometry import LineString,Point,Polygon
from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.regions import copper_shape
from antenna_lab.pcb.validation import TOLERANCE_M


def source_axis(route):
    """Physical contact predicate only, using the importer's curve tolerance.

    Electrical ARC length never comes from this polyline approximation.
    """
    if route.kind=='LINE':return LineString((route.start_xy_m,route.stop_xy_m))
    if route.kind!='ARC':raise ConfigurationError(f'Reduced source route {route.id}: unsupported {route.kind}.')
    from gerbonara.utils import approximate_arc
    from antenna_lab.pcb.gerber import CURVE_ERROR_M
    return LineString(list(approximate_arc(*route.center_xy_m,*route.start_xy_m,*route.stop_xy_m,
        route.signed_sweep_deg<0,max_error=CURVE_ERROR_M/2)))


def source_arc_radius(route):
    """Prove source centre + signed sweep actually reaches its given endpoint."""
    label=f'ARC {route.id}, record={route.record_index}, source={route.source_file}'
    if route.center_xy_m is None or route.signed_sweep_deg is None:
        raise ConfigurationError(f'Reduced {label}: missing centre/signed sweep.')
    values=(*route.start_xy_m,*route.stop_xy_m,*route.center_xy_m,route.signed_sweep_deg,route.width_m)
    if not all(isfinite(v) for v in values) or not 0<abs(route.signed_sweep_deg)<360:
        raise ConfigurationError(f'Reduced {label}: invalid source arc geometry.')
    cx,cy=route.center_xy_m;dx,dy=route.start_xy_m[0]-cx,route.start_xy_m[1]-cy
    radius=hypot(dx,dy);theta=radians(route.signed_sweep_deg)
    end=(cx+dx*cos(theta)-dy*sin(theta),cy+dx*sin(theta)+dy*cos(theta))
    if radius<=TOLERANCE_M or hypot(end[0]-route.stop_xy_m[0],end[1]-route.stop_xy_m[1])>TOLERANCE_M:
        raise ConfigurationError(f'Reduced {label}: centre/radius/signed sweep inconsistent with source endpoint.')
    if radius<=route.width_m/2:
        raise ConfigurationError(f'Reduced {label}: stroke inner radius collapsed; no uniform curved TL.')
    return radius


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
    raw_by_id={r.id:r for r in raw_routes}
    if len(raw_by_id)!=len(raw_routes):raise ConfigurationError('Reduced EasyEDA duplicate source route ID.')
    for r in selected:
        if r.kind=='ARC':source_arc_radius(r)
    for i,a in enumerate(selected):
        for b in selected[:i]:
            if a.conductor_id!=b.conductor_id:continue
            ends_a={tuple(a.start_xy_m),tuple(a.stop_xy_m)};ends_b={tuple(b.start_xy_m),tuple(b.stop_xy_m)}
            if a.kind==b.kind=='LINE' and ends_a==ends_b and a.width_m==b.width_m:continue
            allowed=union_all([Point(p).buffer(max(a.width_m,b.width_m)) for p in ends_a&ends_b])
            overlap=route_shape(a).intersection(route_shape(b)).difference(allowed)
            if overlap.area>TOLERANCE_M*(route_shape(a).length+route_shape(b).length):
                raise ConfigurationError(f'Reduced EasyEDA {a.id}/{b.id}: nonlocal source stroke contact unsupported.')
    # CAD component copper is not an implicit electrical two-terminal model.
    # Arc retains its precise guard; for LINE-only projects never silently omit RLC.
    unresolved=[c['designator'] for c in geometry.design_source.get('resolved_components',())
                if c['role']!='source' and c['designator'] not in {p.id for p in geometry.components}]
    if unresolved:
        raise ConfigurationError('Reduced EasyEDA explicit component electrical model/contact mapping required: '+', '.join(unresolved))
    sections=[];seen=set();evidence=[]
    for r in geometry.source_routes:
        if r.layer_role!='top' or r.conductor_id not in active_ids:continue
        label=f'{r.kind} {r.id}, net={r.net}, record={r.record_index}, source={r.source_file}'
        if r.kind not in ('LINE','ARC'):raise ConfigurationError('Reduced EasyEDA unsupported route '+label)
        raw=raw_by_id.get(r.id)
        if raw is None or (raw.kind,raw.net,raw.layer_role,raw.conductor_id,raw.signed_sweep_deg)!=(r.kind,r.net,r.layer_role,r.conductor_id,r.signed_sweep_deg):
            raise ConfigurationError('Reduced EasyEDA changed semantic route identity: '+label)
        radius=source_arc_radius(raw) if r.kind=='ARC' else None
        if r.width_m<=0 or hypot(*(b-a for a,b in zip(r.start_xy_m,r.stop_xy_m)))<=TOLERANCE_M:
            raise ConfigurationError('Reduced EasyEDA collapsed route '+label)
        # Original semantic axis and projected terminal nodes must remain inside
        # the audited physical owner. No q-sized tolerance or refitted circle.
        axis=source_axis(raw)
        owners=[id for id,shape in shapes.items() if shape.intersects(axis)]
        if owners!=[r.conductor_id] or not shapes[r.conductor_id].buffer(TOLERANCE_M).covers(axis):
            raise ConfigurationError('Reduced EasyEDA changed/ambiguous centerline ownership: '+label)
        if any(not shapes[r.conductor_id].buffer(TOLERANCE_M).covers(Point(p)) for p in (r.start_xy_m,r.stop_xy_m)):
            raise ConfigurationError('Reduced EasyEDA changed projected endpoint ownership: '+label)
        if geometry.design_source['conductor_nets'].get(r.conductor_id)!=r.net:
            raise ConfigurationError('Reduced EasyEDA route net ownership mismatch: '+label)
        a,b=tuple(r.start_xy_m),tuple(r.stop_xy_m)
        key=(r.conductor_id,*sorted((a,b)),r.width_m) if r.kind=='LINE' else ('ARC',r.id)
        if key not in seen:
            seen.add(key);sections.append(section_type('source:'+r.id,r.conductor_id,a,b,r.width_m,(r.id,),
                r.kind,tuple(raw.start_xy_m),tuple(raw.stop_xy_m),
                tuple(raw.center_xy_m) if raw.center_xy_m is not None else None,raw.signed_sweep_deg,radius))
        evidence.append(dict(asdict(r),source_geometry=asdict(raw),
            axis_metric='original_semantic_radius_times_abs_signed_sweep' if r.kind=='ARC' else 'original_semantic_endpoint_distance',
            projected_endpoint_ownership='passed'))
    for owner in active_ids:
        own=[s for s in sections if s.owner==owner]
        if not own:raise ConfigurationError(f'Reduced EasyEDA {owner}: active copper has no semantic LINE/ARC; pads/pours are not transmission lines.')
        # Axis connectivity is explicit CAD topology. No segment fitting.
        degree={}
        for s in own:
            for p in (s.start_xy_m,s.stop_xy_m):degree[p]=degree.get(p,0)+1
        if any(v>2 for v in degree.values()):raise ConfigurationError(f'Reduced EasyEDA {owner}: branched source route unsupported.')
        for i,a in enumerate(own):
            for b in own[:i]:
                common={a.start_xy_m,a.stop_xy_m}&{b.start_xy_m,b.stop_xy_m}
                ra,rb=raw_by_id[a.feature_ids[0]],raw_by_id[b.feature_ids[0]]
                source_common={tuple(ra.start_xy_m),tuple(ra.stop_xy_m)} & {tuple(rb.start_xy_m),tuple(rb.stop_xy_m)}
                if len(common)!=len(source_common):
                    raise ConfigurationError(f'Reduced EasyEDA {owner}: projection changed route junction topology.')
                cross=source_axis(ra).intersection(source_axis(rb))
                local=union_all([Point(p).buffer(TOLERANCE_M) for p in source_common])
                if not cross.difference(local).is_empty:
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
          Polygon(p.vertices_xy_m,p.holes_xy_m).buffer(TOLERANCE_M).covers(Point(point))]
    if len(pads)!=1:return []
    pad=Polygon(pads[0].vertices_xy_m,pads[0].holes_xy_m)
    metal=next(copper_shape(c) for c in geometry.top_copper if c.id==owner)
    if not metal.buffer(TOLERANCE_M).covers(pad):
        raise ConfigurationError(f'Reduced EasyEDA PAD {pads[0].id}: modeled pad leaves its physical conductor.')
    points={p for s in sections if s.owner==owner for p in (s.start_xy_m,s.stop_xy_m)
            if pad.buffer(TOLERANCE_M).covers(Point(p))}
    if len(points)!=1:
        raise ConfigurationError(f'Reduced EasyEDA PAD {pads[0].id}: require exactly one source route junction; no guessed pad interconnect.')
    return sorted(points)
