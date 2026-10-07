"""Geometry-resolution projection; the existing float EM mesher is independent.

Production and detached diagnostics share this projection. Coordinates are projected
after one normalization; mesh coordinates are NOT restricted to the geometry
lattice. Raw source data are provenance, never a source of downstream anchors.
"""
from dataclasses import asdict, dataclass

from antenna_lab.pcb.grid import PcbGrid, QuantizedPcbGeometry
from antenna_lab.pcb.model import (
    BoardOutline, CopperPolygon, CopperLayer, CopperImageStats, DielectricLayer,
    Substrate, PcbGeometry, PcbPort, QuantizedPcbDrill, PcbLumpedComponent, PcbSourceProvenance,
)
from antenna_lab.pcb.quantization import quantize_pcb_geometry
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.validation import validate_pcb_geometry
from antenna_lab.solvers.pcb_mesh import PcbDomainMesh, make_pcb_domain_mesh, make_gerber_mesh_anchor_plan


def materialize_quantized_geometry(value: QuantizedPcbGeometry) -> PcbGeometry:
    """Single deterministic tick -> SI boundary; no second normalization.

    All spatial values come from the audited tick records. Source JSON supplies
    only non-spatial composition statistics and the legacy/stackup distinction.
    Conducting-sheet/plating input thicknesses remain material/provenance data.
    """
    metre = value.grid.to_metres
    point = lambda xy: tuple(metre(v) for v in xy)
    ring = lambda vertices: tuple(point(v) for v in vertices)
    outline = BoardOutline(ring(value.outline))
    layers = tuple(DielectricLayer(BoardOutline(ring(d.outline)),metre(d.bottom),metre(d.top),
                    d.epsilon_r,d.loss_tangent,d.name) for d in value.dielectrics)
    top = layers[0]
    source = value.provenance
    source_drills = {d['id']: d for d in source.get('drills',())}
    result = PcbGeometry(
        model=value.model, outline=outline,
        copper=[CopperPolygon(c.id,ring(c.outer),metre(c.z),c.layer_role,
                              tuple(ring(h) for h in c.holes)) for c in value.copper],
        substrate=Substrate(top.outline,top.z_min_m,top.z_max_m,top.epsilon_r,top.loss_tangent),
        port=PcbPort(value.port.id,point(value.port.negative),point(value.port.positive),metre(value.port.width)),
        assumptions=list(value.assumptions),
        dielectric_layers=layers if source.get('dielectric_layers') else (),
        copper_layers=tuple(CopperLayer(c.role,metre(c.z),c.model,c.material_thickness_m,
                            c.conductivity_s_m,c.source_sha256) for c in value.copper_layers),
        copper_composition=tuple(CopperImageStats(**s) for s in source.get('copper_composition',())),
        drills=tuple(QuantizedPcbDrill(d.id,*point(d.centre),metre(d.diameter),d.plated,d.source_file_role,
                     d.source_tool,d.source_file_sha256,d.plating_thickness_m,
                     metre(d.outer_radius) if d.outer_radius is not None else None,
                     d.connected_layer_roles,geometry_resolution_nm=value.grid.quantum_nm,
                     source_drill_diameter_m=source_drills[d.id]['drill_diameter_m'])
                     for d in value.drills),
        components=tuple(PcbLumpedComponent(c.id,c.kind,c.value_si,c.value_text,c.pin1_net,c.pin2_net,
                         point(c.pin1),point(c.pin2),c.layer,c.axis,point(c.gap_start),point(c.gap_stop),
                         ring(c.contact_window),c.source_sha256,c.flying_probe_sha256) for c in value.components),
        source_port=(PcbSourceProvenance(value.source_port.refdes,value.source_port.pin_nets,
                     point(value.source_port.pin1),point(value.source_port.pin2),
                     value.source_port.enet_sha256,value.source_port.flying_probe_sha256)
                     if value.source_port else None),
    )
    validate_pcb_geometry(result)
    return result


def apply_geometry_resolution(normalized_geometry: PcbGeometry, grid: PcbGrid):
    """Project an already normalized model exactly once; never normalize here."""
    quantized, audit = quantize_pcb_geometry(normalized_geometry, grid)
    return materialize_quantized_geometry(quantized), quantized, audit


def geometry_anchor_diagnostics(value: QuantizedPcbGeometry, mesh):
    """Closest distinct explicit modeled coordinate pair, versus final EM steps.

    Coordinates, not every vertex, are collected for diagnosis only. They are
    NOT promoted to required mesh anchors. Counts exclude nonphysical numerical
    bbox midpoints, air/PML and mesher-generated lines. Those belong to EM mesh
    policy. Geometric circle extrema and source faces are included explicitly.
    """
    from fractions import Fraction
    from decimal import Decimal
    def metres(tick):
        if isinstance(tick,Fraction):
            return float(Decimal(tick.numerator)/Decimal(tick.denominator)*value.grid.quantum_decimal_m)
        return value.grid.to_metres(tick)
    axes = ({},{},{})
    def add(axis,tick,category,owner):
        axes[axis].setdefault(tick,set()).add((category,owner))
    def xy(p,category,owner):
        for i,t in enumerate(p):add(i,t,category,owner)
    def ring(points,category,owner):
        for p in points:xy(p,category,owner)
    ring(value.outline,'board','outline')
    for c in value.copper:
        ring(c.outer,'copper',c.id)
        for h in c.holes:ring(h,'copper',c.id)
        add(2,c.z,'copper',c.id)
    for d in value.dielectrics:
        ring(d.outline,'board',d.name)
        for z in (d.bottom,d.top):add(2,z,'material interface',d.name)
    for p in (value.port.negative,value.port.positive):xy(p,'port',value.port.id)
    # A derived half-width face can be at a half tick for odd tick widths. Do
    # not hide it by rounding. It is diagnosed, not made a new quantization rule.
    mid_y=Fraction(value.port.negative[1]+value.port.positive[1],2)
    for t in (mid_y-Fraction(value.port.width,2),mid_y+Fraction(value.port.width,2)):
        add(1,t,'port',value.port.id+' face')
    add(2,0,'port',value.port.id)
    for d in value.drills:
        xy(d.centre,'drill',d.id)
        radius=d.outer_radius if d.plated else d.radius
        for axis in range(2):
            for sign in (-1,1):add(axis,d.centre[axis]+sign*radius,'drill',d.id+' extent')
    for c in value.components:
        for p in (c.pin1,c.pin2,c.gap_start,c.gap_stop,*c.contact_window):xy(p,'component',c.id)
    if value.source_port:
        for p in (value.source_port.pin1,value.source_port.pin2):xy(p,'port',value.source_port.refdes+' pin')
    result={}
    for name,coordinates,lines in zip('xyz',axes,(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)):
        ordered=sorted(coordinates)
        if len(ordered)<2:
            closest=None;separation=None
        else:
            a,b=min(zip(ordered,ordered[1:]),key=lambda pair:(pair[1]-pair[0],pair[0]))
            separation=metres(b-a)
            closest=[dict(coordinate_m=metres(t),
                          owners=[dict(category=c,owner=o) for c,o in sorted(coordinates[t])]) for t in (a,b)]
        result[name]=dict(minimum_geometry_anchor_separation_m=separation,
            minimum_mesh_step_m=min(b-a for a,b in zip(lines,lines[1:])),
            closest_geometry_anchor_pair=closest,distinct_geometry_coordinate_count=len(ordered))
    return result


def format_modeled_mm(metres, grid: PcbGrid) -> str:
    """Display only; never applied to frequency, impedance or R/L/C values."""
    decimals={100000:1,10000:2,1000:3,100:4}[grid.quantum_nm]
    return f'{metres*1000:.{decimals}f} mm'


@dataclass(frozen=True)
class GeometryResolutionCandidate:
    modeled_geometry: PcbGeometry
    quantized_geometry: QuantizedPcbGeometry
    mesh: PcbDomainMesh
    diagnostics: dict


def prepare_geometry_resolution_candidate(source: PcbGeometry, settings, *, grid=PcbGrid(), quality='preview'):
    """Import is caller-owned. Normalize once -> audit -> SI -> existing mesher.

    No native object, XML, FDTD, output directory, CLI option or production
    fallback. Topology failure propagates before materialization/mesh creation.
    """
    from antenna_lab.pcb.gerber_quality import gerber_cost_preflight
    from antenna_lab.pcb.port import resolve_pcb_lumped_port
    from antenna_lab.solvers.pcb_components import resolve_component_boxes
    normalized,transform=normalize_port_orientation(source)
    modeled,quantized,audit=apply_geometry_resolution(normalized,grid)
    plan,anchor_metadata=make_gerber_mesh_anchor_plan(modeled,settings,quality)
    mesh=make_pcb_domain_mesh(modeled,settings,gerber_quality=quality)
    port=resolve_pcb_lumped_port(modeled,mesh,settings,gerber_quality=quality)
    components=resolve_component_boxes(modeled,(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m))
    diagnostics=dict(
        geometry_resolution_um=grid.quantum_um,
        normalization=asdict(transform),source_geometry=source.as_dict(),
        normalized_source_geometry=normalized.as_dict(),quantization=audit,
        geometry_and_mesh=geometry_anchor_diagnostics(quantized,mesh),
        mesh_anchor_policy=anchor_metadata,
        required_mesh_anchors_m=dict(x=plan.x_required_m,y=plan.y_required_m,z=plan.z_required_m),
        port=asdict(port),ideal_components=[asdict(c) for c in components],
        cost=gerber_cost_preflight(mesh,settings),
        mesh=dict(shape_cells=mesh.shape_cells,cell_count=mesh.cell_count),
        note='Geometry resolution is independent of EM mesh resolution; no mesh lattice constraint.',
    )
    return GeometryResolutionCandidate(modeled,quantized,mesh,diagnostics)
