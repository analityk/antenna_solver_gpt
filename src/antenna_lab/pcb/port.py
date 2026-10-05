"""Discrete PCB solver-grid contact/gap audit, not polygon unions or net inference."""

from dataclasses import dataclass
from math import isfinite

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import PcbGeometry
from antenna_lab.pcb.simulation import PcbSimulationSettings
from antenna_lab.pcb.validation import _contains
from antenna_lab.solvers.pcb_mesh import PcbDomainMesh, make_pcb_mesh_anchor_plan


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
    geometry: PcbGeometry, domain_mesh: PcbDomainMesh, settings: PcbSimulationSettings,
) -> PcbLumpedPortSpec:
    """Resolve an exact planar +X port without touching geometry, mesh or CSXCAD.

    Boundary-inclusive membership uses PCB validation's existing tolerance.
    Contacts are sampled on Y grid lines; the gap on Ex-edge midpoints and
    XY-cell centres. This does not prove the absence of subcell copper slivers.
    Requires validated experiment settings; no native source is created.
    """
    plan = make_pcb_mesh_anchor_plan(geometry)
    n, p = geometry.port.negative_xy_m, geometry.port.positive_xy_m
    if n[1] != p[1]:
        raise ConfigurationError("PCB port: port płaski +X wymaga dokładnie negative.y == positive.y.")
    ym, half = (n[1]+p[1])/2, geometry.port.width_m/2
    start, stop = (n[0], ym-half, 0.0), (p[0], ym+half, 0.0)
    axes = (domain_mesh.x_lines_m, domain_mesh.y_lines_m, domain_mesh.z_lines_m)
    if domain_mesh.pml_cells != settings.pml_cells:
        raise ConfigurationError("PCB port: niezgodne pml_cells geometrii domeny i eksperymentu.")
    required = (plan.x_required_m+(n[0],0.0,p[0]),
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
