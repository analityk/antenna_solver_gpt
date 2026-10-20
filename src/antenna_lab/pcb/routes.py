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
