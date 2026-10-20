"""Source-route extraction for FAST; no recovery of axes from polygon edges.

Only proven dark circular strokes become sections. Pads/regions can remain
width-local endpoint/junction parasitics (the existing FAST approximation),
never lines. Arc, partial clear/restore, unresolved branches and disconnected
route graphs fail with source identity. No native or mesh operations.
"""
from dataclasses import asdict
from math import hypot
from shapely import union_all
from shapely.geometry import LineString, Point, Polygon
from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.routes import (audit_routes, route_footprint, audit_projected_routes,
                                    projection_fingerprint, source_records)
from antenna_lab.pcb.regions import copper_shape
from antenna_lab.pcb.validation import TOLERANCE_M


def extract_source_routes(geometry, active_ids, section_type):
    shapes={c.id:copper_shape(c) for c in geometry.top_copper if c.id in active_ids}
    receipt=getattr(geometry,'route_projection',None)
    if receipt is not None:
        if (receipt['physical_topology_audit']!='passed' or
                receipt['geometry_sha256']!=projection_fingerprint(geometry)):
            raise ConfigurationError('Reduced source route: missing/stale physical quantization audit; no polygon fallback.')
        source_routes,source_copper=source_records(receipt['source'])
        audited=audit_projected_routes(geometry.routes,geometry.copper,source_routes)
    else:
        audited=audit_routes(geometry.routes,geometry.copper)
    selected=[]
    for r in audited:
        if r.layer_role!='top' or not r.polarity_dark:continue
        if r.source_status==r.status=='removed_by_composition':continue
        if not (set(r.candidate_conductor_ids)&active_ids):
            if r.conductor_id and r.conductor_id not in active_ids:continue
            # A completely removed route has no active copper, but a projection
            # which removed a once-proven stroke must not silently drop it.
            if r.status=='removed_by_composition' and r.source_status!='verified':continue
            if r.candidate_conductor_ids:continue
        label=f'{r.id} ({r.source_file}, object {r.source_object_index}, SHA256 {r.source_sha256})'
        if r.source_status!='verified' or r.status!='verified':
            raise ConfigurationError(f'Reduced source route {label}: original={r.source_status}, modeled={r.status}; '
                                     'clear/restore ownership or stroke survival unproven; no polygon fallback.')
        if r.conductor_id not in active_ids:continue
        if r.kind=='Arc':
            raise ConfigurationError(f'Reduced source route Arc unsupported: {label}; no guessed TL arc.')
        if r.kind!='Line':raise ConfigurationError(f'Reduced source route unsupported kind: {label}.')
        if not shapes[r.conductor_id].buffer(TOLERANCE_M).covers(LineString((r.start_xy_m,r.stop_xy_m))):
            raise ConfigurationError(f'Reduced source route {label}: modeled centerline leaves final copper.')
        selected.append(r)
    if receipt is not None:
        # Pad/region coverage and nonlocal stroke contacts are source-image
        # questions. Prove them there, then use the existing physical topology
        # receipt plus the modeled route-axis checks. Never compare two
        # independently projected tessellations as physical copper images.
        from types import SimpleNamespace
        source=SimpleNamespace(routes=source_routes,copper=source_copper,
            top_copper=[c for c in source_copper if c.layer_role=='top'])
        extract_source_routes(source,active_ids,section_type)
    sections=[]; footprints={}; evidence=[]
    # Duplicate/reversed overdraw is provenance, not a parallel electrical path.
    groups={}
    for r in selected:
        a,b=sorted((r.start_xy_m,r.stop_xy_m))
        key=(r.conductor_id,a,b,r.width_m)
        groups.setdefault(key,[]).append(r)
    for (owner,a,b,width),records in sorted(groups.items()):
        if hypot(b[0]-a[0],b[1]-a[1])<=TOLERANCE_M:
            raise ConfigurationError(f'Reduced source route {records[0].id}: collapsed axis.')
        s=section_type(f'line_{len(sections):04d}',owner,a,b,width,tuple(sorted(r.id for r in records)))
        sections.append(s)
        if receipt is None:
            footprints[s.id]=union_all([route_footprint(r) for r in records])
        evidence.extend(asdict(r) for r in records)
    for owner,shape in shapes.items():
        own=[s for s in sections if s.owner==owner]
        if not own:
            raise ConfigurationError(f'Reduced source route {owner}: no verified Line strokes; '
                                     'flashes/regions are not transmission lines; no polygon fallback.')
        # Prove route graph without fitting an axis or extending guessed leads.
        degree={}
        for s in own:
            for point in (s.start_xy_m,s.stop_xy_m):degree[point]=degree.get(point,0)+1
        if any(d>2 for d in degree.values()):
            raise ConfigurationError(f'Reduced source route {owner}: branched route graph unsupported.')
        for i,a in enumerate(own):
            for b in own[:i]:
                ends_a={a.start_xy_m,a.stop_xy_m};ends_b={b.start_xy_m,b.stop_xy_m}
                common=ends_a&ends_b
                intersection=LineString((a.start_xy_m,a.stop_xy_m)).intersection(LineString((b.start_xy_m,b.stop_xy_m)))
                if not intersection.is_empty and (intersection.geom_type!='Point' or
                        tuple(intersection.coords[0]) not in common):
                    raise ConfigurationError(f'Reduced source routes {a.feature_ids}/{b.feature_ids}: '
                                             'overlapping/interior junction unsupported; no guessed graph.')
                if receipt is None:
                    allowed=union_all([Point(p).buffer(max(a.width_m,b.width_m)) for p in common])
                    extra=footprints[a.id].intersection(footprints[b.id]).difference(allowed)
                    if extra.area>TOLERANCE_M*shape.length:
                        raise ConfigurationError(f'Reduced source routes {a.feature_ids}/{b.feature_ids}: '
                                                 'nonlocal physical stroke contact unsupported.')
        pending=set(degree);todo=[min(pending)]
        while todo:
            point=todo.pop()
            if point not in pending:continue
            pending.remove(point)
            for s in own:
                if point in (s.start_xy_m,s.stop_xy_m):todo.extend((s.start_xy_m,s.stop_xy_m))
        if pending:
            raise ConfigurationError(f'Reduced source route {owner}: disconnected axes despite connected copper; '
                                     'unresolved pad/region/route junction, no guessed lead.')
        if receipt is None:
            covered=union_all([footprints[s.id] for s in own])
            local=union_all([Point(p).buffer(s.width_m) for s in own for p in (s.start_xy_m,s.stop_xy_m)])
            if shape.difference(covered).difference(local).area>TOLERANCE_M*shape.length:
                raise ConfigurationError(f'Reduced source route {owner}: nonlocal pad/region copper not represented by strokes.')
    return tuple(sections),evidence
