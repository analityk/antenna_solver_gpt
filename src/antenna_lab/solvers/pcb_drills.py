"""Native round through primitives. Thickness never participates in meshing."""
from dataclasses import asdict
from antenna_lab.pcb.drills import PTH_MODEL_NOTE, validate_drills


def install_drills(csx, geometry, copper_priorities):
    if not geometry.drills:
        return dict(pth_count=0,npth_count=0,records=[],extra_z_lines=0)
    validate_drills(geometry)
    priority=1+max(max(p['copper_priority'],p['clearance_priority'] or 0) for p in copper_priorities)
    bottom=min(d.z_min_m for d in geometry.dielectrics)
    metal=csx.AddMetal('pcb_pth_solid_PEC') if any(d.plated for d in geometry.drills) else None
    air=csx.AddMaterial('pcb_npth_air',epsilon=1.0,kappa=0.0) if any(not d.plated for d in geometry.drills) else None
    for d in geometry.drills:
        material=metal if d.plated else air
        material.AddCylinder(start=[d.x_m,d.y_m,0.0],stop=[d.x_m,d.y_m,bottom],
            radius=d.equivalent_outer_radius_m if d.plated else d.drill_diameter_m/2,
            priority=priority if d.plated else priority+1)
    return dict(pth_count=sum(d.plated for d in geometry.drills),
        npth_count=sum(not d.plated for d in geometry.drills),
        records=[asdict(d) for d in geometry.drills],pth_priority=priority,npth_priority=priority+1,
        pth_model='solid_pec_equivalent',model_note=PTH_MODEL_NOTE,extra_z_lines=0,
        mesh_policy='exact XY centres only; no plating/radius/tessellation anchors')
