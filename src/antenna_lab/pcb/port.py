"""Discrete PCB solver-grid contact/gap audit, not polygon unions or net inference."""

from dataclasses import dataclass
from math import isfinite

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import PcbGeometry
from antenna_lab.pcb.simulation import PcbSimulationSettings
from antenna_lab.pcb.validation import _contains
from antenna_lab.solvers.pcb_mesh import PcbDomainMesh, make_pcb_mesh_anchor_plan, make_pcb_solver_anchor_plan


@dataclass(frozen=True)
class PcbLumpedPortSpec:
    port_nr: int
    port_id: str
    start_m: tuple[float, float, float]
    stop_m: tuple[float, float, float]
    exc_dir: str
    reference_impedance_ohm: float
    excite: float
    priority: int
    negative_copper_id: str
    positive_copper_id: str
    x_cell_count: int
    y_cell_count: int
    active_ex_edge_count: int


def resolve_pcb_lumped_port(
    geometry: PcbGeometry, domain_mesh: PcbDomainMesh, settings: PcbSimulationSettings, *, port_edge_mode='aligned', gerber_quality=None,
) -> PcbLumpedPortSpec:
    """Resolve an exact planar +X port without touching geometry, mesh or CSXCAD.

    Boundary-inclusive membership uses PCB validation's existing tolerance.
    Contacts are sampled on Y grid lines; the gap on Ex-edge midpoints and
    XY-cell centres. This does not prove the absence of subcell copper slivers.
    Requires validated experiment settings; no native source is created.
    """
    if gerber_quality is not None and port_edge_mode != 'aligned':
        raise ConfigurationError('Gerber anchors require aligned port.')
    if port_edge_mode != 'aligned':
        return _resolve_thirds_port(geometry, domain_mesh, settings, port_edge_mode)
    plan = (make_pcb_mesh_anchor_plan(geometry) if gerber_quality is None else
            make_pcb_solver_anchor_plan(geometry, settings, gerber_quality=gerber_quality))
    n, p = geometry.port.negative_xy_m, geometry.port.positive_xy_m
    mx = (n[0]+p[0])/2
    ym, half = (n[1]+p[1])/2, geometry.port.width_m/2
    start, stop = (n[0], ym-half, 0.0), (p[0], ym+half, 0.0)
    if gerber_quality is not None:
        # Filtering noncritical edges must not hide a PEC sliver from the
        # existing discrete gap audit. Use physical polygons, not mesh anchors.
        from shapely.geometry import Polygon, box
        from antenna_lab.pcb.validation import TOLERANCE_M
        tol = TOLERANCE_M
        if stop[0]-start[0] <= 2*tol or stop[1]-start[1] <= 2*tol:
            raise ConfigurationError('Gerber port surface is unresolved at geometry tolerance.')
        interior = box(start[0]+tol, start[1]+tol, stop[0]-tol, stop[1]-tol)
        for copper in geometry.copper:
            if interior.intersects(Polygon(copper.vertices_xy_m)):
                raise ConfigurationError(f'Gerber port: miedź {copper.id!r} wewnątrz szczeliny; '
                                         'economical anchors cannot remove physical copper.')
    axes = (domain_mesh.x_lines_m, domain_mesh.y_lines_m, domain_mesh.z_lines_m)
    if domain_mesh.pml_cells != settings.pml_cells:
        raise ConfigurationError("PCB port: niezgodne pml_cells geometrii domeny i eksperymentu.")
    required = (plan.x_required_m+(n[0],mx,p[0]),
                plan.y_required_m+(start[1],ym,stop[1]), plan.z_required_m+(0.0,))
    for axis, lines, anchors in zip('xyz', axes, required):
        if len(lines)<2 or any(not isfinite(v) for v in lines) or any(a>=b for a,b in zip(lines,lines[1:])):
            raise ConfigurationError(f"PCB port: oś {axis} musi być skończona i ściśle rosnąca.")
        present = set(lines)
        for coordinate in anchors:
            if coordinate not in present:
                raise ConfigurationError(f"PCB port: brak dokładnej linii {axis}={coordinate!r} m; "
                                         "domena nie odpowiada geometrii.")
    x, y, _ = axes
    ix0, ix1 = x.index(start[0]), x.index(stop[0])
    iy0, iy1 = y.index(start[1]), y.index(stop[1])
    nx, ny = ix1-ix0, iy1-iy0
    if nx < settings.min_port_gap_cells:
        raise ConfigurationError(f"PCB port: szczelina ma {nx} komórek, wymagane {settings.min_port_gap_cells}.")
    if ny < settings.min_port_width_cells:
        raise ConfigurationError(f"PCB port: szerokość ma {ny} komórek, wymagane {settings.min_port_width_cells}.")
    polygons = []
    for copper in geometry.copper:
        vertices = list(copper.vertices_xy_m)
        if vertices[-1] == vertices[0]:
            vertices.pop()
        polygons.append(vertices)

    def members(point):
        return [i for i, polygon in enumerate(polygons) if _contains(point, polygon)]

    # The anchor planner already validated unique, distinct endpoint ownership.
    negative, positive = members(n)[0], members(p)[0]
    rows = y[iy0:iy1+1]
    for side, coordinate, owner in (('negative',n[0],negative), ('positive',p[0],positive)):
        for row in rows:
            point = (coordinate,row)
            found = members(point)
            if found != [owner]:
                reason = 'niejednoznaczny kontakt' if len(found)>1 else 'niepełny kontakt'
                raise ConfigurationError(f"PCB port {side}: {reason} w {point!r} m; "
                                         f"oczekiwano miedzi {geometry.copper[owner].id!r}.")
    centres_y = tuple(a+(b-a)/2 for a,b in zip(rows,rows[1:]))
    for a,b in zip(x[ix0:ix1],x[ix0+1:ix1+1]):
        centre_x = a+(b-a)/2
        for row in (*rows,*centres_y):
            point = (centre_x,row)
            found = members(point)
            if found:
                raise ConfigurationError(f"PCB port: miedź {geometry.copper[found[0]].id!r} "
                                         f"wewnątrz szczeliny w {point!r} m.")
    return PcbLumpedPortSpec(1, geometry.port.id, start, stop, 'x',
        settings.reference_impedance_ohm, 1.0, 5, geometry.copper[negative].id,
        geometry.copper[positive].id, nx, ny, nx*(ny+1))



def _resolve_thirds_port(geometry, mesh, settings, mode):
    """Physical contact and discrete intersecting-cell audit; no coordinate snapping.

    Counts describe intersecting XY intervals. Active Ex edges use X-cell centres
    inside the gap and Y mesh rows inside the physical width, not (ny+1).
    They are a project grid audit, not inspection of native resistor internals.
    """
    from antenna_lab.solvers.pcb_mesh import make_pcb_solver_anchor_plan, audit_pcb_port_edge_mesh
    plan=make_pcb_solver_anchor_plan(geometry,settings,mode)
    audit_pcb_port_edge_mesh(geometry,settings,mesh,mode)
    axes=(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)
    if mesh.pml_cells!=settings.pml_cells:
        raise ConfigurationError('PCB thirds: niezgodne pml_cells.')
    for lines,required in zip(axes,(plan.x_required_m,plan.y_required_m,plan.z_required_m)):
        if (not set(required).issubset(lines) or any(not isfinite(v) for v in lines)
                or any(a>=b for a,b in zip(lines,lines[1:]))):
            raise ConfigurationError('PCB thirds: niezgodna geometria/siatka lub brak krytycznych linii.')
    n,p=geometry.port.negative_xy_m,geometry.port.positive_xy_m
    my=(n[1]+p[1])/2;half=geometry.port.width_m/2
    yl,yu=my-half,my+half
    x,y,_=axes
    intervals=lambda lines,lo,hi: [(a,b) for a,b in zip(lines,lines[1:]) if a<hi and b>lo]
    xi,yi=intervals(x,n[0],p[0]),intervals(y,yl,yu)
    if len(xi)<settings.min_port_gap_cells or len(yi)<settings.min_port_width_cells:
        raise ConfigurationError('PCB thirds: niewystarczająca liczba komórek przecinających port.')
    polygons=[]
    for copper in geometry.copper:
        vertices=list(copper.vertices_xy_m)
        if vertices[-1]==vertices[0]: vertices.pop()
        polygons.append(vertices)
    members=lambda pt: [i for i,v in enumerate(polygons) if _contains(pt,v)]
    ni,pi=members(n)[0],members(p)[0]
    rows=[v for v in y if yl<v<yu]
    centres_y=[max(a,yl)+(min(b,yu)-max(a,yl))/2 for a,b in yi]
    for side,xx,owner in (('negative',n[0],ni),('positive',p[0],pi)):
        for yy in (yl,yu,my,*rows,*centres_y):
            if members((xx,yy))!=[owner]:
                raise ConfigurationError(f'PCB thirds {side}: niepełny/niejednoznaczny kontakt przy {(xx,yy)}.')
    centres_x=[a+(b-a)/2 for a,b in xi]
    if not rows or any(not n[0]<v<p[0] for v in centres_x):
        raise ConfigurationError('PCB thirds: środki aktywnych komórek Ex muszą leżeć w szczelinie.')
    for xx in centres_x:
        for yy in (yl,yu,*rows,*centres_y):
            if members((xx,yy)):
                raise ConfigurationError(f'PCB thirds: miedź w szczelinie przy {(xx,yy)}.')
    return PcbLumpedPortSpec(1,geometry.port.id,(n[0],yl,0.0),(p[0],yu,0.0),'x',
        settings.reference_impedance_ohm,1.,5,geometry.copper[ni].id,geometry.copper[pi].id,
        len(xi),len(yi),len(centres_x)*len(rows))
