"""PCB-v0 native preparation and isolated, unverified control solve."""

from pathlib import Path
from xml.etree import ElementTree
from dataclasses import asdict
from math import isfinite, pi

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import PcbGeometry
from antenna_lab.pcb.copper import copper_metadata
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from antenna_lab.pcb.simulation import PcbSimulationSettings
from .pcb_clearances import copper_priority_plan, install_copper_clearances
from .pcb_mesh import PcbDomainMesh, make_pcb_domain_mesh, make_pcb_mesh_anchor_plan, make_pcb_solver_anchor_plan, audit_pcb_port_edge_mesh

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
    csx, geometry: PcbGeometry, domain_mesh: PcbDomainMesh, settings: PcbSimulationSettings, *, port_edge_mode='aligned', gerber_quality=None, copper_config=None) -> dict:
    """Install a validated geometry/mesh pair in a fresh CSXCAD structure.

    Dielectric loss uses constant kappa, matching tan(delta) only at the
    configured loss-reference frequency. Copper remains planar PEC or a finite-conductivity surface sheet.
    Preflight failures do not touch CSXCAD. Readback failures stop before
    material/metal creation (the grid has necessarily already been written).
    """
    plan = make_pcb_solver_anchor_plan(geometry, settings, port_edge_mode, gerber_quality=gerber_quality)
    if geometry.copper_layers:
        from antenna_lab.pcb.stackup import resolved_stackup_metadata
        copper_info = dict(copper_model='stackup', resolved_stackup=resolved_stackup_metadata(
            geometry, settings.loss_reference_frequency_hz))
    else:
        copper_info = copper_metadata(copper_config)
    priority_plan = copper_priority_plan(geometry)
    copper_priorities = {c.id:p["copper_priority"] for c,p in zip(geometry.copper,priority_plan)}
    axes = (domain_mesh.x_lines_m, domain_mesh.y_lines_m, domain_mesh.z_lines_m)
    if domain_mesh.pml_cells != settings.pml_cells:
        raise ConfigurationError("PCB grid: pml_cells domeny nie zgadza się z ustawieniami eksperymentu.")
    for axis, lines in zip('xyz', axes):
        if len(lines) < 2 or any(not isfinite(v) for v in lines) or any(
                a >= b for a, b in zip(lines, lines[1:])):
            raise ConfigurationError(f"PCB grid {axis}: wymagane skończone, ściśle rosnące linie.")
    _require_lines(axes, plan, domain_mesh)
    from .pcb_components import resolve_component_boxes, install_components
    component_specs = resolve_component_boxes(geometry, axes)
    audit_pcb_port_edge_mesh(geometry, settings, domain_mesh, port_edge_mode)
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
    plan = make_pcb_solver_anchor_plan(geometry, settings, port_edge_mode, gerber_quality=gerber_quality)
    # Diagnose critical missing coordinates independently of whole-axis equality.
    _require_lines(readback, plan, domain_mesh)
    for axis, expected, actual in zip('xyz', axes, readback):
        if actual != expected:
            raise ConfigurationError(f"PCB grid {axis}: odczyt CSXCAD różni się od finalnej osi domeny; "
                                     "nie wolno wygładzać, zaokrąglać ani usuwać linii.")

    if geometry.copper_layers:
        stack = copper_info['resolved_stackup']
        dielectric_info = [v for v in stack['layers'] if v['type'] == 'dielectric']
        for index, (layer, info) in enumerate(zip(geometry.dielectrics, dielectric_info)):
            material = csx.AddMaterial(f'pcb_dielectric_{index}', epsilon=layer.epsilon_r,
                                       kappa=info['kappa_s_per_m'])
            material.AddLinPoly(points=_xy_polygon_points(layer.outline.vertices_xy_m),
                norm_dir='z', elevation=layer.z_min_m, length=layer.z_max_m-layer.z_min_m, priority=0)
        for layer in geometry.copper_layers:
            name = 'pcb_copper_'+layer.role
            material = (csx.AddMetal(name) if layer.model == 'pec' else
                csx.AddConductingSheet(name, conductivity=layer.conductivity_s_m, thickness=layer.thickness_m))
            for copper in geometry.copper:
                if copper.layer_role == layer.role:
                    material.AddPolygon(points=_xy_polygon_points(copper.vertices_xy_m),
                        norm_dir='z', elevation=copper.z_m, priority=copper_priorities[copper.id])
    else:
        material = csx.AddMaterial('pcb_substrate', epsilon=substrate.epsilon_r, kappa=kappa)
        material.AddLinPoly(points=_xy_polygon_points(substrate.outline.vertices_xy_m),
                            norm_dir='z', elevation=substrate.z_min_m,
                            length=substrate.z_max_m-substrate.z_min_m, priority=0)
        metal = (csx.AddMetal('pcb_top_copper_PEC') if copper_info['copper_model'] == 'pec' else
                 csx.AddConductingSheet('pcb_top_copper_sheet',
                    conductivity=copper_info['copper_conductivity_s_m'],
                    thickness=copper_info['copper_thickness_m']))
        for copper in geometry.copper:
            metal.AddPolygon(points=_xy_polygon_points(copper.vertices_xy_m),
                             norm_dir='z', elevation=0.0, priority=copper_priorities[copper.id])
    clearance_metadata = install_copper_clearances(csx, geometry, priority_plan, _xy_polygon_points)
    from .pcb_drills import install_drills
    drill_metadata = install_drills(csx, geometry, priority_plan)
    _audit_port_grid(csx, domain_mesh, context='after dielectric/copper/clearance/drill installation')
    component_metadata = install_components(csx, component_specs)
    _audit_port_grid(csx, domain_mesh, context='after ideal component installation')
    return {
        'ideal_components': component_metadata,
        **copper_info,
        'copper_clearances': clearance_metadata,
        'drills': drill_metadata,
        'copper_composition': [asdict(v) for v in geometry.copper_composition],
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
        'copper': {'model': 'PEC' if copper_info['copper_model'] == 'pec' else copper_info['copper_model'], 'polygon_count': len(geometry.copper),
                   'ids': [copper.id for copper in geometry.copper]},
    }


def prepare_pcb_csx(geometry: PcbGeometry, settings: PcbSimulationSettings, *, port_edge_mode='aligned', gerber_quality=None, copper_config=None):
    """Build the domain before loading native modules; return CSX, mesh, metadata."""
    domain_mesh = make_pcb_domain_mesh(geometry, settings, port_edge_mode=port_edge_mode, **({'gerber_quality': gerber_quality} if gerber_quality is not None else {}))
    from .openems import native_modules
    _, csx_module = native_modules()
    csx = csx_module.ContinuousStructure()
    metadata = install_pcb_geometry(csx, geometry, domain_mesh, settings, copper_config=copper_config, port_edge_mode=port_edge_mode, **({'gerber_quality': gerber_quality} if gerber_quality is not None else {}))
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
                            domain_mesh: PcbDomainMesh, settings: PcbSimulationSettings, *, port_edge_mode='aligned', gerber_quality=None):
    """Install on an engine already associated with csx; never modify the grid.

    Spec resolution and preflight complete before any engine method is called.
    Metadata describes the resolved contract, not audited native edge internals.
    """
    spec = resolve_pcb_lumped_port(geometry, domain_mesh, settings, port_edge_mode=port_edge_mode, **({'gerber_quality': gerber_quality} if gerber_quality is not None else {}))
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


def prepare_pcb_native_model(geometry: PcbGeometry, settings: PcbSimulationSettings, *, port_edge_mode='aligned', gerber_quality=None, copper_config=None):
    """Return engine, CSX, port, mesh, spec, metadata; no waveform, BC, XML or run."""
    domain_mesh = make_pcb_domain_mesh(geometry, settings, port_edge_mode=port_edge_mode, **({'gerber_quality': gerber_quality} if gerber_quality is not None else {}))
    from .openems import native_modules
    ems_module, csx_module = native_modules()
    csx = csx_module.ContinuousStructure()
    engine = ems_module.openEMS(NrTS=settings.max_timesteps, EndCriteria=settings.end_criteria)
    engine.SetCSX(csx)
    geometry_metadata = install_pcb_geometry(csx, geometry, domain_mesh, settings, copper_config=copper_config, port_edge_mode=port_edge_mode, **({'gerber_quality': gerber_quality} if gerber_quality is not None else {}))
    port, spec, port_metadata = install_pcb_lumped_port(engine, csx, geometry, domain_mesh, settings, port_edge_mode=port_edge_mode, **({'gerber_quality': gerber_quality} if gerber_quality is not None else {}))
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


def prepare_pcb_xml_model(geometry: PcbGeometry, settings: PcbSimulationSettings, xml_path, *, port_edge_mode='aligned', gerber_quality=None, field_frequency_hz=(), copper_config=None):
    """Prepare reusable XML; no Run, result processing or additional files."""
    engine, csx, port, mesh, spec, metadata = prepare_pcb_native_model(geometry, settings, copper_config=copper_config, port_edge_mode=port_edge_mode, **({'gerber_quality': gerber_quality} if gerber_quality is not None else {}))
    metadata = {**metadata, **configure_pcb_fdtd(engine, csx, mesh, settings)}
    if field_frequency_hz:
        from .pcb_fields import install_pcb_fields
        metadata['fields'] = install_pcb_fields(csx, geometry, mesh, settings, field_frequency_hz)
    metadata['xml'] = write_pcb_xml(engine, csx, mesh, xml_path)
    return engine, csx, port, mesh, spec, metadata


def run_pcb_fdtd(engine, csx, port, domain_mesh: PcbDomainMesh,
                 settings: PcbSimulationSettings, native_dir, *, exact_endcriteria=False, dump_statistics=False, field_frequency_hz=()) -> dict:
    """Execute an already prepared control model; port ratios remain unverified."""
    import os
    import numpy as np

    from .pcb_fields import validate_field_frequencies
    field_frequency_hz = validate_field_frequencies(field_frequency_hz, settings)
    _audit_port_grid(csx, domain_mesh, context='before Run')
    native_dir = Path(native_dir).resolve()
    xml = native_dir / 'model.xml'
    if not native_dir.is_dir() or not xml.is_file() or xml.stat().st_size == 0:
        raise ConfigurationError(f'PCB Run: wymagany istniejący, niepusty {xml}; przygotuj XML najpierw.')
    if not isinstance(exact_endcriteria, bool) or not isinstance(dump_statistics, bool):
        raise ConfigurationError('PCB Run: exact_endcriteria/dump_statistics muszą być bool.')
    options = {}
    if exact_endcriteria: options['exact_endcriteria'] = True
    if dump_statistics:
        options['dump_statistics'] = True
        if (native_dir/'openEMS_stats.txt').exists():
            raise ConfigurationError('PCB Run: istnieją stare openEMS_stats.txt; użyj nowego katalogu.')
    cwd = Path.cwd()
    try:
        status = engine.Run(str(native_dir), cleanup=False, numThreads=settings.threads, **options)
    finally:
        os.chdir(cwd)
    if status not in (None, 0):
        raise RuntimeError(f'PCB Run: openEMS zwrócił kod {status!r}; sprawdź pliki natywne w {native_dir}.')
    statistics = None
    if dump_statistics:
        statistics = read_pcb_native_statistics(native_dir/'openEMS_stats.txt')
        if statistics['number_of_iterations'] >= settings.max_timesteps:
            raise ConfigurationError('PCB: temporal termination not established; iterations >= max_timesteps.')
    frequencies = np.asarray(settings.result_frequency_hz, dtype=float)
    calc_frequencies = np.asarray(sorted(set((*frequencies, *field_frequency_hz)))) if field_frequency_hz else frequencies
    port.CalcPort(str(native_dir), calc_frequencies, ref_impedance=settings.reference_impedance_ohm)

    def spectrum(name):
        try:
            values = np.asarray(getattr(port, name), dtype=complex)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ConfigurationError(f'PCB port: brak lub niepoprawne widmo {name}: {exc}') from exc
        # Only singleton dimensions can be removed; never flatten a true matrix.
        values = np.atleast_1d(values.squeeze())
        if values.ndim != 1 or values.size != calc_frequencies.size or not np.isfinite(values).all():
            raise ConfigurationError(f'PCB port: {name} musi zawierać {calc_frequencies.size} skończonych próbek widma 1D.')
        return values

    voltage, current = spectrum('uf_tot'), spectrum('if_tot')
    field_reference = None
    if field_frequency_hz:
        from .pcb_fields import voltage_scale
        field_voltage = voltage[np.searchsorted(calc_frequencies,field_frequency_hz)]
        voltage_scale(field_voltage)  # Reject unusable references before field export.
        field_reference = dict(frequency_hz=list(field_frequency_hz),
            voltage_real=field_voltage.real.tolist(), voltage_imag=field_voltage.imag.tolist())
        selected = np.searchsorted(calc_frequencies, frequencies)
        voltage, current = voltage[selected], current[selected]
    if np.any(current == 0):
        raise ConfigurationError('PCB port: zerowy prąd w widmie; nie można obliczyć Z.')
    reference = settings.reference_impedance_ohm
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        impedance = voltage / current
        denominator = impedance + reference
        if not np.isfinite(impedance).all() or not np.isfinite(denominator).all() or np.any(denominator == 0):
            raise ConfigurationError('PCB port: nieskończone Z lub zerowy/nieskończony mianownik S11 (Z + Z0).')
        s11 = (impedance - reference) / denominator
        rho = np.abs(s11)
        if not np.isfinite(s11).all() or not np.isfinite(rho).all():
            raise ConfigurationError('PCB port: nieskończone S11.')
        if np.any(rho >= 1):
            raise ConfigurationError('PCB control: non-passive or unconverged port data (|S11| >= 1); wymaga zbadania, bez ograniczania wartości.')
        swr = (1 + rho) / (1 - rho)
        db = [None if r == 0 else float(20*np.log10(r)) for r in rho]
    if not np.isfinite(swr).all():
        raise ConfigurationError('PCB port: nieskończone SWR.')
    result = {
        'validation_status': 'unverified',
        'note': 'First synthetic PCB FDTD control result. Port, mesh, PML and material convergence have not yet been established. Exact zero reflection is stored as s11_db=null (minus infinity dB).',
        'frequency_hz': frequencies.tolist(), 'reference_impedance_ohm': reference,
        'resistance_ohm': impedance.real.tolist(), 'reactance_ohm': impedance.imag.tolist(),
        's11_real': s11.real.tolist(), 's11_imag': s11.imag.tolist(),
        's11_magnitude': rho.tolist(), 's11_db': db, 'swr': swr.tolist(),
        'mesh': {'shape_cells': list(domain_mesh.shape_cells), 'cell_count': domain_mesh.cell_count,
                 'pml_cells': domain_mesh.pml_cells},
    }

    if field_reference is not None:
        result['field_port_reference'] = field_reference
    if statistics is not None:
        result['native_statistics'] = statistics
        result['run_options'] = dict(exact_endcriteria=exact_endcriteria, dump_statistics=dump_statistics)
    return result


def write_pcb_port_results(result: dict, output_dir) -> dict:
    """Write only CSV and strict JSON; null dB is an empty CSV cell."""
    import csv
    import json

    serialized = json.dumps(result, allow_nan=False, indent=2)
    detached = json.loads(serialized)
    keys = ('frequency_hz', 'resistance_ohm', 'reactance_ohm', 's11_real',
            's11_imag', 's11_magnitude', 's11_db', 'swr')
    count = len(detached['frequency_hz'])
    if any(len(detached[key]) != count for key in keys):
        raise ConfigurationError('PCB wyniki: niezgodne długości kolumn.')
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/'impedance.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow((*keys[:3], 'reference_ohm', *keys[3:]))
        for i in range(count):
            writer.writerow((*[detached[k][i] for k in keys[:3]], detached['reference_impedance_ohm'],
                             *[detached[k][i] for k in keys[3:]]))
    (directory/'summary.json').write_text(serialized+'\n', encoding='utf-8')
    return detached



def read_pcb_native_statistics(path):
    """openEMS DumpStatistics numeric-tab-%label format (openems.cpp)."""
    import math
    names={'number of iterations':'number_of_iterations','timestep (s)':'fdtd_timestep_s',
           'total numerical time (s)':'total_numerical_time_s'}
    values={}
    try:
        for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
            number,sep,label=line.partition('%')
            key=names.get(label.strip())
            if not sep or key is None: continue
            if key in values: raise ValueError(f'duplicate {key}')
            value=float(number.strip())
            if not math.isfinite(value) or value<=0: raise ValueError(f'invalid {key}')
            values[key]=value
        if set(values)!=set(names.values()): raise ValueError('missing required statistics')
        iterations=values['number_of_iterations']
        if not iterations.is_integer(): raise ValueError('non-integer iterations')
        values['number_of_iterations']=int(iterations)
        if not math.isclose(values['total_numerical_time_s'],iterations*values['fdtd_timestep_s'],rel_tol=1e-12):
            raise ValueError('numerical time does not match iterations * timestep')
    except (OSError,ValueError) as exc:
        raise ConfigurationError(f'PCB: invalid/missing openEMS_stats.txt; temporal termination not established: {exc}') from exc
    return values
