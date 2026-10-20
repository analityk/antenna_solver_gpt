"""Auditable source strokes. Final copper is authoritative, never regenerated.

No angle tolerance, polygon snapping, or topology repair. The same numerical
membership tolerance as PCB validation permits only boundary arithmetic residue.
A rejected route disables FAST use, not full-wave use of the final copper.
"""
from dataclasses import replace
from math import isfinite
from shapely.geometry import Polygon, Point, LineString
from .regions import copper_shape
from .validation import TOLERANCE_M


def route_footprint(route):
    return Polygon(route.footprint_xy_m, route.footprint_holes_xy_m)


def audit_routes(routes, copper, *, initial=False):
    shapes=[(c.id,c.layer_role,copper_shape(c)) for c in copper]
    result=[]
    for r in routes:
        owner=None; candidates=(); status='clear_operation'
        if r.polarity_dark:
            valid=(isfinite(r.width_m) and r.width_m>0 and
                   len(set(r.footprint_xy_m))>=3 and
                   all(len(set(h))>=3 for h in r.footprint_holes_xy_m))
            shape=route_footprint(r) if valid else Polygon()
            if not valid or shape.is_empty or not shape.is_valid:
                status='invalid_or_collapsed_footprint'
            else:
                touched=[(id,s) for id,role,s in shapes if role==r.layer_role and s.intersects(shape)]
                candidates=tuple(sorted(id for id,_ in touched))
                if not touched: status='removed_by_composition'
                elif len(touched)!=1: status='ambiguous_conductor'
                else:
                    id,s=touched[0]
                    if not s.buffer(TOLERANCE_M).covers(shape): status='stroke_not_preserved'
                    else: owner=id; status='verified'
            if r.kind=='Line' and r.start_xy_m==r.stop_xy_m:
                owner=None; status='collapsed_axis'
            if not initial and r.conductor_id and owner!=r.conductor_id:
                owner=None; status='ownership_or_survival_changed'
        result.append(replace(r,conductor_id=owner,candidate_conductor_ids=candidates,
            status=status,source_status=status if initial else r.source_status))
    return tuple(result)


def tick_audit_fingerprint(value):
    """Bind the existing quantization._audit success to its immutable inputs/output.

    Not a second topology auditor, nor a security signature. A stale/mutated
    result cannot reuse the receipt when materialized for FAST.
    """
    from dataclasses import asdict
    from hashlib import sha256
    import json
    data=asdict(value)
    data.pop('topology_audit_sha256')
    return sha256(json.dumps(data,sort_keys=True,allow_nan=False).encode()).hexdigest()


def projection_fingerprint(geometry):
    """Bind detached source evidence and modeled geometry, excluding this digest."""
    from hashlib import sha256
    import json
    data=geometry.as_dict()
    if data['route_projection'] is not None:
        data['route_projection'].pop('geometry_sha256',None)
    return sha256(json.dumps(data,sort_keys=True,allow_nan=False).encode()).hexdigest()


def source_records(data):
    """Restore detached evidence only; never used to replace modeled copper."""
    from .model import PcbRoute, CopperPolygon
    routes=[]
    for record in data['routes']:
        r=dict(record)
        for key in ('start_xy_m','stop_xy_m','center_xy_m'):
            if r[key] is not None:r[key]=tuple(r[key])
        r['candidate_conductor_ids']=tuple(r['candidate_conductor_ids'])
        r['footprint_xy_m']=tuple(map(tuple,r['footprint_xy_m']))
        r['footprint_holes_xy_m']=tuple(tuple(map(tuple,h)) for h in r['footprint_holes_xy_m'])
        routes.append(PcbRoute(**r))
    copper=[CopperPolygon(**c) for c in data['copper']]
    return tuple(routes),copper


def route_axis(route):
    """Centerline evidence, including endpoints; Arc is NOT a TL model.

    Arc sampling uses the importer's existing Gerbonara curve budget, without
    a new survival tolerance. No fitting, lead extension, or endpoint movement.
    """
    if route.kind=='Line':
        return LineString((route.start_xy_m,route.stop_xy_m))
    if route.kind=='Arc' and route.center_xy_m is not None:
        from gerbonara.utils import approximate_arc
        from .gerber import CURVE_ERROR_M
        if route.start_xy_m==route.center_xy_m or route.stop_xy_m==route.center_xy_m:
            return LineString()
        points=list(approximate_arc(*route.center_xy_m,*route.start_xy_m,
            *route.stop_xy_m,route.clockwise,max_error=CURVE_ERROR_M/2))
        # Gerbonara's approximation endpoints must not replace source terminals.
        points[0]=route.start_xy_m;points[-1]=route.stop_xy_m
        return LineString(points)
    return LineString()


def audit_projected_routes(routes, copper, source_routes):
    """Semantic survival AFTER successful physical quantization audit.

    Source ordered-composition proof remains mandatory. Independently projected
    footprint vertices are diagnostic provenance, not another physical image.
    The caller must bind this result to the existing topology-audit receipt.
    """
    original={r.id:r for r in source_routes}
    shapes=[(c.id,c.layer_role,copper_shape(c)) for c in copper]
    result=[]
    for r in routes:
        source=original.get(r.id)
        owner=None; candidates=(); status='source_proof_missing'
        if source is not None and not source.polarity_dark:
            status='clear_operation'
        elif source is not None and source.source_status==source.status=='removed_by_composition':
            status='removed_by_composition'
        elif (source is not None and source.source_status==source.status=='verified'
              and source.conductor_id is not None
              and tuple(source.candidate_conductor_ids)==(source.conductor_id,)):
            if not isfinite(r.width_m) or r.width_m<=0:
                status='collapsed_width'
            else:
                axis=route_axis(r)
                if axis.is_empty or axis.length<=TOLERANCE_M:
                    status='collapsed_axis'
                else:
                    touched=[(id,s) for id,role,s in shapes
                             if role==r.layer_role and s.intersects(axis)]
                    candidates=tuple(sorted(id for id,_ in touched))
                    if not touched:status='removed_by_projection'
                    elif len(touched)!=1:status='ambiguous_conductor'
                    elif touched[0][0]!=source.conductor_id:status='ownership_changed'
                    elif not touched[0][1].buffer(TOLERANCE_M).covers(axis):
                        status='centerline_not_preserved'
                    else:owner=source.conductor_id;status='verified'
        elif source is not None:
            status=source.status  # partial clear can never acquire a fresh proof
        result.append(replace(r,conductor_id=owner,candidate_conductor_ids=candidates,status=status))
    return tuple(result)
