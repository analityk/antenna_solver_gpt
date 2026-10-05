"""PCB-v0 native preparation through audited XML; no FDTD execution."""

from pathlib import Path
from xml.etree import ElementTree
from dataclasses import asdict
from math import isfinite, pi

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import PcbGeometry
from antenna_lab.pcb.port import resolve_pcb_lumped_port
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


def _audit_port_grid(csx, domain_mesh, after=False, context=None):
    grid = csx.GetGrid()
    unit = grid.GetDeltaUnit()
    axes = tuple(tuple(grid.GetLines(axis)) for axis in 'xyz')
    expected = (domain_mesh.x_lines_m, domain_mesh.y_lines_m, domain_mesh.z_lines_m)
    if unit != 1.0 or axes != expected:
        detail = 'delta unit' if unit != 1.0 else next(
            axis for axis, actual, wanted in zip('xyz', axes, expected) if actual != wanted)
        message = ('Natywna instalacja portu zmodyfikowała zamrożoną siatkę PCB' if after else
                   'PCB port: siatka CSXCAD nie odpowiada zamrożonej domenie')
        if context:
            message = f"PCB frozen grid audit ({context}): siatka lub jednostka różni się od domeny"
        raise ConfigurationError(f"{message} ({detail}); instalacja przerwana bez naprawiania siatki.")


def install_pcb_lumped_port(engine, csx, geometry: PcbGeometry,
                            domain_mesh: PcbDomainMesh, settings: PcbSimulationSettings):
    """Install on an engine already associated with csx; never modify the grid.

    Spec resolution and preflight complete before any engine method is called.
    Metadata describes the resolved contract, not audited native edge internals.
    """
    spec = resolve_pcb_lumped_port(geometry, domain_mesh, settings)
    _audit_port_grid(csx, domain_mesh)
    port = engine.AddLumpedPort(spec.port_nr, spec.reference_impedance_ohm,
                               list(spec.start_m), list(spec.stop_m), spec.exc_dir,
                               spec.excite, priority=spec.priority)
    _audit_port_grid(csx, domain_mesh, after=True)
    if port is None:
        raise ConfigurationError("PCB port: AddLumpedPort zwrócił None; sprawdź natywną instalację openEMS.")
    metadata = asdict(spec)
    metadata.update(surface_plane_z_m=0.0, model='planar_lumped_port')
    return port, spec, metadata


def prepare_pcb_native_model(geometry: PcbGeometry, settings: PcbSimulationSettings):
    """Return engine, CSX, port, mesh, spec, metadata; no waveform, BC, XML or run."""
    domain_mesh = make_pcb_domain_mesh(geometry, settings)
    from .openems import native_modules
    ems_module, csx_module = native_modules()
    csx = csx_module.ContinuousStructure()
    engine = ems_module.openEMS(NrTS=settings.max_timesteps, EndCriteria=settings.end_criteria)
    engine.SetCSX(csx)
    geometry_metadata = install_pcb_geometry(csx, geometry, domain_mesh, settings)
    port, spec, port_metadata = install_pcb_lumped_port(engine, csx, geometry, domain_mesh, settings)
    metadata = {'geometry': geometry_metadata, 'port': port_metadata,
                'engine': {'max_timesteps': settings.max_timesteps, 'end_criteria': settings.end_criteria}}
    return engine, csx, port, domain_mesh, spec, metadata


def configure_pcb_fdtd(engine, csx, domain_mesh: PcbDomainMesh,
                       settings: PcbSimulationSettings) -> dict:
    """Activate the specified waveform and PML; never execute the engine."""
    _audit_port_grid(csx, domain_mesh, context='before FDTD configuration')
    count = settings.pml_cells
    if (isinstance(count, bool) or not isinstance(count, int) or not 6 <= count <= 20
            or domain_mesh.pml_cells != count):
        raise ConfigurationError("PCB FDTD: pml_cells musi być zgodne z domeną i należeć do zakresu 6–20.")
    engine.SetGaussExcite(settings.excitation_center_hz, settings.excitation_cutoff_hz)
    _audit_port_grid(csx, domain_mesh, context='after SetGaussExcite')
    boundaries = [f'PML_{count}'] * 6
    engine.SetBoundaryCond(list(boundaries))
    _audit_port_grid(csx, domain_mesh, context='after SetBoundaryCond')
    return {'excitation': {'type': 'gaussian', 'center_hz': settings.excitation_center_hz,
                           'cutoff_hz': settings.excitation_cutoff_hz,
                           'mesh_design_frequency_hz': settings.excitation_center_hz+settings.excitation_cutoff_hz},
            'boundary_conditions': {'order': ['x_min','x_max','y_min','y_max','z_min','z_max'],
                                    'values': boundaries, 'pml_cells': count}}


def write_pcb_xml(engine, csx, domain_mesh: PcbDomainMesh, xml_path) -> dict:
    """Write only the requested XML and audit syntax, size and frozen grid."""
    _audit_port_grid(csx, domain_mesh, context='before Write2XML')
    path = Path(xml_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine.Write2XML(str(xml_path))
    _audit_port_grid(csx, domain_mesh, context='after Write2XML')
    if not path.is_file():
        raise ConfigurationError(f"PCB XML: brak zwykłego pliku {path} po Write2XML.")
    size = path.stat().st_size
    if size == 0:
        raise ConfigurationError(f"PCB XML: pusty plik {path}.")
    try:
        ElementTree.parse(path)
    except (ElementTree.ParseError, OSError) as exc:
        raise ConfigurationError(f"PCB XML: nie można odczytać poprawnego XML {path}: {exc}") from exc
    return {'path': str(xml_path), 'size_bytes': size, 'parse_status': 'passed'}


def prepare_pcb_xml_model(geometry: PcbGeometry, settings: PcbSimulationSettings, xml_path):
    """Prepare reusable XML; no Run, result processing or additional files."""
    engine, csx, port, mesh, spec, metadata = prepare_pcb_native_model(geometry, settings)
    metadata = {**metadata, **configure_pcb_fdtd(engine, csx, mesh, settings),
                'xml': write_pcb_xml(engine, csx, mesh, xml_path)}
    return engine, csx, port, mesh, spec, metadata
