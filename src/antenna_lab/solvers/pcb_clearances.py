"""Planar copper/air priorities, including islands nested inside clearance rings.

No mesh operations or triangulation. Priority nesting is layer-local. A restored
island must win over its enclosing clearance, which wins over its parent sheet.
"""
COPPER_BASE_PRIORITY = 10
CLEARANCE_MATERIAL = 'pcb_copper_clearance_air'


def copper_priority_plan(geometry):
    if not any(c.holes_xy_m for c in geometry.copper):
        return [dict(copper_id=c.id, layer_role=c.layer_role, z_m=c.z_m,
                     copper_priority=COPPER_BASE_PRIORITY, clearance_priority=None, hole_count=0)
                for c in geometry.copper]
    from shapely.geometry import Polygon
    records = []
    for copper in geometry.copper:
        outer = Polygon(copper.vertices_xy_m)
        depth = sum(Polygon(hole).contains(outer) for other in geometry.copper
                    if other is not copper and other.layer_role == copper.layer_role and other.z_m == copper.z_m
                    for hole in other.holes_xy_m)
        priority = COPPER_BASE_PRIORITY+2*depth
        records.append(dict(copper_id=copper.id, layer_role=copper.layer_role, z_m=copper.z_m,
            copper_priority=priority, clearance_priority=priority+1 if copper.holes_xy_m else None,
            hole_count=len(copper.holes_xy_m)))
    return records


def install_copper_clearances(csx, geometry, plan, xy_points):
    records = [p for p in plan if p['hole_count']]
    if records:
        air = csx.AddMaterial(CLEARANCE_MATERIAL, epsilon=1.0, kappa=0.0)
        for copper, item in zip(geometry.copper, plan):
            for ring in copper.holes_xy_m:
                air.AddPolygon(points=xy_points(ring), norm_dir='z', elevation=copper.z_m,
                               priority=item['clearance_priority'])
    return dict(material=CLEARANCE_MATERIAL if records else None,
        epsilon=1.0, kappa_s_per_m=0.0, geometric_thickness_m=0.0, extra_z_lines=0,
        priorities=plan, priority_policy='10 + 2 * same-layer hole nesting depth; corresponding clearance +1')
