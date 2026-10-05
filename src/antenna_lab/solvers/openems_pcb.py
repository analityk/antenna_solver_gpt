"""PCB-v0 CSXCAD geometry installation only: no engine, port, XML or FDTD."""

from math import isfinite, pi

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import PcbGeometry
from antenna_lab.pcb.simulation import PcbSimulationSettings
from .pcb_mesh import PcbDomainMesh, make_pcb_domain_mesh, make_pcb_mesh_anchor_plan

EPS0 = 8.8541878128e-12


def _xy_polygon_points(vertices):
    """CSXCAD uses 2-by-N coordinates; retain winding and all non-closing points."""
    if vertices[-1] == vertices[0]:
        vertices = vertices[:-1]
    return [[p[0] for p in vertices], [p[1] for p in vertices]]


def _require_lines(axes, plan, domain_mesh):
    required = (plan.x_required_m, plan.y_required_m, plan.z_required_m)
    for index, (axis, lines, anchors) in enumerate(zip('xyz', axes, required)):
        present = set(lines)
        for coordinate in (*anchors, domain_mesh.pml_start_min_m[index], domain_mesh.pml_start_max_m[index]):
            if coordinate not in present:
                raise ConfigurationError(f"PCB grid {axis}: brak wymaganej linii {coordinate!r} m; "
                                         "sprawdź zgodność geometrii i domeny oraz odczyt CSXCAD.")
    if 0.0 not in axes[2]:
        raise ConfigurationError("PCB grid z: wymagana dokładna linia z=0 m.")


def install_pcb_geometry(
    csx, geometry: PcbGeometry, domain_mesh: PcbDomainMesh, settings: PcbSimulationSettings,
) -> dict:
    """Install a validated geometry/mesh pair in a fresh CSXCAD structure.

    Dielectric loss uses constant kappa, matching tan(delta) only at the
    configured loss-reference frequency. Copper is zero-thickness PEC.
    Preflight failures do not touch CSXCAD. Readback failures stop before
    material/metal creation (the grid has necessarily already been written).
    """
    plan = make_pcb_mesh_anchor_plan(geometry)
    axes = (domain_mesh.x_lines_m, domain_mesh.y_lines_m, domain_mesh.z_lines_m)
    if domain_mesh.pml_cells != settings.pml_cells:
        raise ConfigurationError("PCB grid: pml_cells domeny nie zgadza się z ustawieniami eksperymentu.")
    for axis, lines in zip('xyz', axes):
        if len(lines) < 2 or any(not isfinite(v) for v in lines) or any(
                a >= b for a, b in zip(lines, lines[1:])):
            raise ConfigurationError(f"PCB grid {axis}: wymagane skończone, ściśle rosnące linie.")
    _require_lines(axes, plan, domain_mesh)
    substrate = geometry.substrate
    frequency = settings.loss_reference_frequency_hz
    if not isfinite(frequency) or frequency <= 0:
        raise ConfigurationError("loss_reference_frequency_hz musi być dodatnie i skończone.")
    kappa = (0.0 if substrate.loss_tangent == 0 else
             2*pi*frequency*EPS0*substrate.epsilon_r*substrate.loss_tangent)
    if not isfinite(kappa):
        raise ConfigurationError("PCB substrate: obliczona kappa nie jest skończona.")

    grid = csx.GetGrid()
    grid.SetDeltaUnit(1.0)
    for axis, lines in zip('xyz', axes):
        grid.SetLines(axis, lines)
    if grid.GetDeltaUnit() != 1.0:
        raise ConfigurationError("PCB grid: CSXCAD zmienił delta unit; wymagane dokładnie 1.0 m.")
    readback = tuple(tuple(grid.GetLines(axis)) for axis in 'xyz')
    # Recheck the solver-facing geometry contract after native grid installation.
    plan = make_pcb_mesh_anchor_plan(geometry)
    # Diagnose critical missing coordinates independently of whole-axis equality.
    _require_lines(readback, plan, domain_mesh)
    for axis, expected, actual in zip('xyz', axes, readback):
        if actual != expected:
            raise ConfigurationError(f"PCB grid {axis}: odczyt CSXCAD różni się od finalnej osi domeny; "
                                     "nie wolno wygładzać, zaokrąglać ani usuwać linii.")

    material = csx.AddMaterial('pcb_substrate', epsilon=substrate.epsilon_r, kappa=kappa)
    material.AddLinPoly(points=_xy_polygon_points(substrate.outline.vertices_xy_m),
                        norm_dir='z', elevation=substrate.z_min_m,
                        length=substrate.z_max_m-substrate.z_min_m, priority=0)
    metal = csx.AddMetal('pcb_top_copper_PEC')
    for copper in geometry.copper:
        metal.AddPolygon(points=_xy_polygon_points(copper.vertices_xy_m),
                         norm_dir='z', elevation=0.0, priority=10)
    return {
        'delta_unit_m': 1.0,
        'grid_line_counts': {axis: len(lines) for axis, lines in zip('xyz', readback)},
        'substrate': {
            'epsilon_r': substrate.epsilon_r,
            'loss_tangent_input': substrate.loss_tangent,
            'loss_reference_frequency_hz': frequency,
            'kappa_s_per_m': kappa,
            'loss_model': 'constant_kappa',
            'z_min_m': substrate.z_min_m, 'z_max_m': substrate.z_max_m,
        },
        'copper': {'model': 'PEC', 'polygon_count': len(geometry.copper),
                   'ids': [copper.id for copper in geometry.copper]},
    }


def prepare_pcb_csx(geometry: PcbGeometry, settings: PcbSimulationSettings):
    """Build the domain before loading native modules; return CSX, mesh, metadata."""
    domain_mesh = make_pcb_domain_mesh(geometry, settings)
    from .openems import native_modules
    _, csx_module = native_modules()
    csx = csx_module.ContinuousStructure()
    metadata = install_pcb_geometry(csx, geometry, domain_mesh, settings)
    return csx, domain_mesh, metadata
