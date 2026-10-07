"""PCB anchors, physical policy, and deterministic Cartesian meshes.

The placeholder spans anchors only. The domain mesh adds graded air and PML
coordinates; neither API instantiates a solver or claims convergence.
"""

from dataclasses import dataclass
from math import hypot, ceil, isfinite, prod, sqrt

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import PcbGeometry
from antenna_lab.pcb.simulation import PcbSimulationSettings
from antenna_lab.pcb.validation import validate_pcb_geometry

C0 = 299792458.0

# Absolute distances in metres. Merge numerical residue, not real features.
ANCHOR_MERGE_TOLERANCE_M = 1e-10
NORMALIZED_FRAME_TOLERANCE_M = 1e-10


@dataclass(frozen=True)
class PcbMeshAnchorPlan:
    x_required_m: tuple[float, ...]
    y_required_m: tuple[float, ...]
    z_required_m: tuple[float, ...]
    port_length_m: float
    port_width_m: float
    substrate_thickness_m: float
    drill_centres_xy_m: tuple[tuple[float, float], ...] = ()


def component_terminal_anchors(geometry, axis):
    """Only longitudinal contact faces; no package/transverse/Z refinement."""
    return tuple(v[axis] for c in geometry.components if c.axis == 'xy'[axis]
                 for v in (c.gap_start_xy_m, c.gap_stop_xy_m))


def _merge(values, critical=()):
    """Keep critical coordinates first, then the smallest eligible coordinate.

    A candidate within tolerance of any retained coordinate is discarded.
    Clusters are representative-based, not transitive chains: this avoids
    bridging distinct features through a series of near-identical values.
    Never average. Distinct critical anchors cannot be collapsed safely.
    """
    retained = sorted(critical)
    if any(b - a <= ANCHOR_MERGE_TOLERANCE_M for a, b in zip(retained, retained[1:])):
        raise ConfigurationError("PCB: krytyczne kotwice portu/wierceń są zbyt blisko względem tolerancji scalania; nie zostaną scalone ani pominięte.")
    for value in sorted(values):
        if all(abs(value - other) > ANCHOR_MERGE_TOLERANCE_M for other in retained):
            retained.append(value)
    return tuple(sorted(retained))


def _z_interfaces(geometry):
    """Require the exact shared PCB-v0 solver plane, without moving geometry.

    Geometry validation tolerates residue; solver-facing export does not.
    """
    if geometry.copper_layers:
        required = sorted({v for d in geometry.dielectrics for v in (d.z_min_m,d.z_max_m)})
        if any(b-a <= ANCHOR_MERGE_TOLERANCE_M for a,b in zip(required, required[1:])):
            raise ConfigurationError('PCB Z: unresolved dielectric interfaces; do not merge thin physical layers.')
        planes = {c.role:c.z_m for c in geometry.copper_layers}
        if required[-1] != 0.0 or any(c.z_m != planes[c.layer_role] for c in geometry.copper):
            raise ConfigurationError('PCB stackup: exact shared copper/interface Z lines required, top z=0.')
        if not set(planes.values()).issubset(required):
            raise ConfigurationError('PCB stackup: copper plane missing dielectric interface.')
        return tuple(required)
    bottom, top = geometry.substrate.z_min_m, geometry.substrate.z_max_m
    if top - bottom <= ANCHOR_MERGE_TOLERANCE_M:
        raise ConfigurationError(
            "PCB Z: interfejsy laminatu są nierozdzielalne; grubość musi być "
            f"większa niż {ANCHOR_MERGE_TOLERANCE_M:g} m.")
    if top != 0.0:
        raise ConfigurationError(
            "PCB v0: eksport do siatki solvera wymaga dokładnie z=0 dla góry laminatu "
            "(substrate.z_max_m). Tolerancja walidacji geometrii nie obowiązuje przy eksporcie; "
            "popraw geometrię wejściową.")
    for copper in geometry.copper:
        if copper.z_m != 0.0:
            raise ConfigurationError(
                f"PCB v0: eksport do siatki solvera wymaga dokładnie z=0 dla miedzi {copper.id!r}. "
                "Tolerancja walidacji geometrii nie obowiązuje przy eksporcie; popraw geometrię wejściową.")
    return bottom, 0.0


def make_pcb_mesh_anchor_plan(geometry: PcbGeometry) -> PcbMeshAnchorPlan:
    """Derive required locations from valid, explicitly normalized PCB geometry."""
    validate_pcb_geometry(geometry)
    n, p = geometry.port.negative_xy_m, geometry.port.positive_xy_m
    mx, my = (n[0] + p[0]) / 2, (n[1] + p[1]) / 2
    tol = NORMALIZED_FRAME_TOLERANCE_M
    if not (n[0] < 0 < p[0] and abs(n[1] - p[1]) <= tol
            and abs(mx) <= tol and abs(my) <= tol):
        raise ConfigurationError("PCB: wymagany znormalizowany port +X ze środkiem w (0, 0).")
    board = geometry.outline.vertices_xy_m
    x = [min(v[0] for v in board), max(v[0] for v in board)]
    y = [min(v[1] for v in board), max(v[1] for v in board)]
    z = _z_interfaces(geometry)
    for copper in geometry.copper:
        for axis, anchors in ((0, x), (1, y)):
            low = min(v[axis] for v in copper.vertices_xy_m)
            high = max(v[axis] for v in copper.vertices_xy_m)
            anchors.extend((low, (low + high) / 2, high))
    half = geometry.port.width_m / 2
    return PcbMeshAnchorPlan(
        _merge(x, sorted({n[0], mx, p[0], *(d.x_m for d in geometry.drills), *component_terminal_anchors(geometry, 0)})),
        _merge(y, sorted({my-half, my, my+half, *(d.y_m for d in geometry.drills), *component_terminal_anchors(geometry, 1)})),
        z, hypot(p[0] - n[0], p[1] - n[1]), geometry.port.width_m,
        max(d.z_max_m for d in geometry.dielectrics) - min(d.z_min_m for d in geometry.dielectrics),
        tuple((d.x_m,d.y_m) for d in geometry.drills),
    )


@dataclass(frozen=True)
class PcbPlaceholderMeshSettings:
    max_step_xy_m: float
    max_step_z_m: float
    max_cells: int


@dataclass(frozen=True)
class PcbPlaceholderMesh:
    """Anchor-bounded infrastructure mesh, not a complete FDTD domain."""

    x_lines_m: tuple[float, ...]
    y_lines_m: tuple[float, ...]
    z_lines_m: tuple[float, ...]
    shape_cells: tuple[int, int, int]
    cell_count: int
    min_step_m: float
    max_step_m: float


def _subdivide(anchors, counts):
    """Equal cells within each interval; append original endpoints verbatim."""
    lines = [anchors[0]]
    for left, right, count in zip(anchors, anchors[1:], counts):
        lines.extend(left + (right - left) * (i / count) for i in range(1, count))
        lines.append(right)
    if any(b <= a for a, b in zip(lines, lines[1:])):
        raise ConfigurationError("PCB: podział przekracza precyzję współrzędnych.")
    return tuple(lines)


def make_pcb_placeholder_mesh(
    geometry: PcbGeometry, settings: PcbPlaceholderMeshSettings,
) -> PcbPlaceholderMesh:
    """Subdivide using caller-supplied steps; no physical resolution policy."""
    for name in ("max_step_xy_m", "max_step_z_m"):
        value = getattr(settings, name)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not isfinite(value) or value <= ANCHOR_MERGE_TOLERANCE_M):
            raise ConfigurationError(f"{name}: wymagany skończony krok większy od tolerancji kotwic.")
    if (isinstance(settings.max_cells, bool) or not isinstance(settings.max_cells, int)
            or settings.max_cells <= 0):
        raise ConfigurationError("max_cells: wymagana dodatnia liczba całkowita.")
    plan = make_pcb_mesh_anchor_plan(geometry)
    axes = (plan.x_required_m, plan.y_required_m, plan.z_required_m)
    targets = (settings.max_step_xy_m, settings.max_step_xy_m, settings.max_step_z_m)
    counts = []
    for anchors, target in zip(axes, targets):
        divisions = []
        for a, b in zip(anchors, anchors[1:]):
            ratio = (b - a) / target
            if not isfinite(ratio):
                raise ConfigurationError("PCB: liczba komórek przekracza zakres obliczeń.")
            divisions.append(ceil(ratio))
        counts.append(divisions)
    shape = tuple(sum(axis_counts) for axis_counts in counts)
    if any(count <= 0 for count in shape):
        raise ConfigurationError("PCB: każda oś siatki musi zawierać co najmniej jedną komórkę.")
    cell_count = prod(shape)
    if cell_count <= 0:
        raise ConfigurationError("PCB: liczba komórek siatki musi być dodatnia.")
    # Check before allocating axes, including extremely fine caller settings.
    if cell_count > settings.max_cells:
        raise ConfigurationError(f"PCB: {cell_count} komórek przekracza max_cells={settings.max_cells}.")
    lines = tuple(_subdivide(axis, divisions) for axis, divisions in zip(axes, counts))
    steps = [b - a for axis in lines for a, b in zip(axis, axis[1:])]
    return PcbPlaceholderMesh(*lines, shape, cell_count, min(steps), max(steps))


@dataclass(frozen=True)
class PcbPhysicalMeshPolicy:
    """Independent local step limits, not mesh axes or a complete FDTD domain.

    Uses the shortest dielectric wavelength for shared Cartesian XY planes; mu_r=1.
    Growth values are carried forward only; grading is not performed here.
    air_padding_m is the clearance from structure to START of PML, excluding
    PML thickness. pml_cells is metadata only; no PML geometry is constructed.
    """

    padding_frequency_hz: float
    padding_air_wavelength_m: float
    air_padding_m: float
    pml_cells: int
    f_mesh_hz: float
    air_wavelength_m: float
    substrate_wavelength_m: float
    max_air_step_m: float
    max_substrate_xy_step_m: float
    max_substrate_z_step_m: float
    max_port_gap_step_m: float
    max_port_width_step_m: float
    min_substrate_cells_z: int
    min_port_gap_cells: int
    min_port_width_cells: int
    growth_ratio_target: float
    growth_ratio_limit: float
    max_cells: int


def derive_pcb_physical_mesh_policy(
    geometry: PcbGeometry, settings: PcbSimulationSettings,
) -> PcbPhysicalMeshPolicy:
    """Derive local limits from validated experiment settings and anchor features.

    Result sampling never determines resolution. The excitation sets f_mesh.
    No full-domain cell estimate, geometry changes, or solver operations occur.
    """
    plan = make_pcb_mesh_anchor_plan(geometry)
    f_mesh = settings.excitation_center_hz + settings.excitation_cutoff_hz
    padding_frequency = min(settings.result_frequency_hz)
    padding_wavelength = C0 / padding_frequency
    air = C0 / f_mesh
    substrate = air / sqrt(max(d.epsilon_r for d in geometry.dielectrics))
    substrate_step = substrate / settings.cells_per_wavelength
    return PcbPhysicalMeshPolicy(
        padding_frequency_hz=padding_frequency,
        padding_air_wavelength_m=padding_wavelength,
        air_padding_m=settings.air_padding_wavelengths * padding_wavelength,
        pml_cells=settings.pml_cells,
        f_mesh_hz=f_mesh, air_wavelength_m=air, substrate_wavelength_m=substrate,
        max_air_step_m=air / settings.cells_per_wavelength,
        max_substrate_xy_step_m=substrate_step,
        max_substrate_z_step_m=min(substrate_step, plan.substrate_thickness_m / settings.min_substrate_cells_z),
        max_port_gap_step_m=plan.port_length_m / settings.min_port_gap_cells,
        max_port_width_step_m=plan.port_width_m / settings.min_port_width_cells,
        min_substrate_cells_z=settings.min_substrate_cells_z,
        min_port_gap_cells=settings.min_port_gap_cells,
        min_port_width_cells=settings.min_port_width_cells,
        growth_ratio_target=settings.growth_ratio_target,
        growth_ratio_limit=settings.growth_ratio_limit, max_cells=settings.max_cells,
    )


# Relative allowance for subtraction/ratio arithmetic, not coordinate snapping.
_DOMAIN_REL_TOL = 1e-10


@dataclass(frozen=True)
class PcbDomainMesh:
    """Complete coordinate domain; no solver objects or convergence claim.

    PML starts exclude absorber thickness. Selected required anchors are exact;
    optional Gerber policy can omit noncritical numerical copper anchors.
    """

    x_lines_m: tuple[float, ...]
    y_lines_m: tuple[float, ...]
    z_lines_m: tuple[float, ...]
    shape_cells: tuple[int, int, int]
    cell_count: int
    pml_start_min_m: tuple[float, float, float]
    pml_start_max_m: tuple[float, float, float]
    outer_min_m: tuple[float, float, float]
    outer_max_m: tuple[float, float, float]
    pml_cells: int
    min_step_m: float
    max_step_m: float
    worst_growth_ratio: float
    drill_centres_xy_m: tuple[tuple[float, float], ...] = ()


def _domain_count_guard(shape, maximum):
    cells = prod(shape)
    if any(n <= 0 for n in shape) or cells <= 0 or cells > maximum:
        raise ConfigurationError(
            f"PCB domain: shape={tuple(shape)}, cell_count={cells}, max_cells={maximum}. "
            "Zwiększ limit lub zmień jawne ustawienia rozdzielczości/domeny.")
    return cells


def _domain_steps(lines):
    steps = [b - a for a, b in zip(lines, lines[1:])]
    if not steps or any(not isfinite(v) for v in lines) or any(
            step <= ANCHOR_MERGE_TOLERANCE_M for step in steps):
        raise ConfigurationError(
            "PCB domain: brak postępu numerycznego lub komórka nie większa od tolerancji kotwic.")
    return steps


def _worst_growth(steps):
    return max((max(a, b) / min(a, b) for a, b in zip(steps, steps[1:])), default=1.)


def _grade_domain_axis(lines, target, cell_budget):
    """Deterministic left-to-right insertion, bounded by the axis cell budget.

    Split next to the smaller neighbour. Cap the adjacent piece at
    L*target/(1+target) so a barely excessive ratio cannot create a tiny
    remainder. Every iteration either advances or adds one line; insertions
    are bounded and both new cells must exceed the coordinate tolerance.
    No original coordinate is moved or removed.
    """
    lines = list(lines)
    _domain_steps(lines)
    i = 1
    while i < len(lines) - 1:
        left, right = lines[i] - lines[i-1], lines[i+1] - lines[i]
        if max(left, right) <= min(left, right) * target * (1 + _DOMAIN_REL_TOL):
            i += 1
            continue
        if len(lines) - 1 >= cell_budget:
            raise ConfigurationError(
                f"PCB grading: max_cells ogranicza oś do {cell_budget} komórek; "
                "zwiększ limit lub zmień ustawienia rozdzielczości.")
        large, small = max(left, right), min(left, right)
        adjacent = min(small * target, large * (target / (1 + target)))
        index = i if left > right else i + 1
        point = lines[i] - adjacent if left > right else lines[i] + adjacent
        if not (lines[index-1] < point < lines[index]) or min(
                point - lines[index-1], lines[index] - point) <= ANCHOR_MERGE_TOLERANCE_M:
            raise ConfigurationError(
                "PCB grading: brak postępu numerycznego; podział tworzy komórkę "
                "nie większą od tolerancji kotwic. Zmień ustawienia gradingu/rozdzielczości.")
        lines.insert(index, point)
        i = max(1, index - 1)
    return tuple(lines)


def _audit_domain_axis(lines, boundaries, limits, growth_limit):
    """Independent final audits against each original local restriction."""
    steps = _domain_steps(lines)
    if _worst_growth(steps) > growth_limit * (1 + _DOMAIN_REL_TOL):
        raise ConfigurationError("PCB domain: końcowy audyt growth_ratio_limit nie przeszedł.")
    if not set(boundaries).issubset(lines):
        raise ConfigurationError("PCB domain: utracono dokładną kotwicę lub granicę PML.")
    interval = 0
    for a, b, step in zip(lines, lines[1:], steps):
        while interval < len(limits)-1 and a >= boundaries[interval+1]:
            interval += 1
        if b > boundaries[interval+1] or step > limits[interval] * (1 + _DOMAIN_REL_TOL):
            raise ConfigurationError("PCB domain: końcowy audyt lokalnego maksimum kroku nie przeszedł.")


def _add_domain_pml(lines, count):
    left_step, right_step = lines[1] - lines[0], lines[-1] - lines[-2]
    result = (tuple(lines[0] - i * left_step for i in range(count, 0, -1))
              + lines + tuple(lines[-1] + i * right_step for i in range(1, count+1)))
    steps = _domain_steps(result)
    if result.index(lines[0]) != count or len(result)-1-result.index(lines[-1]) != count:
        raise ConfigurationError("PCB PML: nieprawidłowa liczba komórek.")
    for actual, expected in ((steps[:count], left_step), (steps[-count:], right_step)):
        if any(abs(step - expected) > expected * _DOMAIN_REL_TOL for step in actual):
            raise ConfigurationError("PCB PML: precyzja współrzędnych nie pozwala na równe komórki.")
    return result


def make_pcb_domain_mesh(
    geometry: PcbGeometry, settings: PcbSimulationSettings, *, port_edge_mode='aligned', gerber_quality=None,
) -> PcbDomainMesh:
    """Refine local PCB/air intervals, audit, then attach uniform PML cells.

    Requires validated simulation settings. Stores only 1-D axes, never a
    Cartesian cell array. Intermediate count estimates are lower bounds;
    all refinements only increase counts. No native solver is instantiated.
    """
    plan = make_pcb_solver_anchor_plan(geometry, settings, port_edge_mode, gerber_quality=gerber_quality)
    policy = derive_pcb_physical_mesh_policy(geometry, settings)
    pml = policy.pml_cells
    if isinstance(pml, bool) or not isinstance(pml, int) or not 6 <= pml <= 20:
        raise ConfigurationError("PCB domain: pml_cells musi być liczbą całkowitą od 6 do 20.")
    if not (isfinite(policy.growth_ratio_target) and isfinite(policy.growth_ratio_limit)
            and 1 < policy.growth_ratio_target <= policy.growth_ratio_limit):
        raise ConfigurationError("PCB domain: wymagane 1 < growth_ratio_target <= growth_ratio_limit.")
    anchors = (plan.x_required_m, plan.y_required_m, plan.z_required_m)
    n, p = geometry.port.negative_xy_m, geometry.port.positive_xy_m
    mid_y = (n[1] + p[1]) / 2
    local_ranges = ((n[0], p[0]), (mid_y-plan.port_width_m/2, mid_y+plan.port_width_m/2))
    local_steps = (policy.max_port_gap_step_m, policy.max_port_width_step_m)
    boundaries, limits, counts = [], [], []
    for axis, required in enumerate(anchors):
        edges = (required[0]-policy.air_padding_m, *required, required[-1]+policy.air_padding_m)
        if not all(isfinite(x) for x in edges) or any(b <= a for a, b in zip(edges, edges[1:])):
            raise ConfigurationError("PCB domain: odstęp powietrza nie daje rozdzielnych, skończonych granic.")
        core_limits = []
        for a, b in zip(required, required[1:]):
            maximum = policy.max_substrate_z_step_m if axis == 2 else policy.max_substrate_xy_step_m
            if axis == 2 and geometry.dielectric_layers:
                layer = next(d for d in geometry.dielectrics if d.z_min_m <= a and b <= d.z_max_m)
                # Wavelength follows the actual material. The existing minimum
                # substrate count applies to total dielectric depth, NOT N cells
                # per layer: interfaces alone may already exceed that minimum.
                maximum = min(policy.air_wavelength_m / sqrt(layer.epsilon_r) / settings.cells_per_wavelength,
                              plan.substrate_thickness_m / settings.min_substrate_cells_z)
            if axis < 2 and local_ranges[axis][0] <= a and b <= local_ranges[axis][1]:
                maximum = min(maximum, local_steps[axis])
            core_limits.append(maximum)
        axis_limits = (policy.max_air_step_m, *core_limits, policy.max_air_step_m)
        divisions = []
        for a, b, maximum in zip(edges, edges[1:], axis_limits):
            if not isfinite(maximum) or maximum <= 0:
                raise ConfigurationError("PCB domain: fizyczny limit kroku musi być dodatni i skończony.")
            ratio = (b-a) / maximum
            if not isfinite(ratio) or ratio > policy.max_cells:
                raise ConfigurationError("PCB domain: wymagany podział osi przekracza max_cells.")
            count = ceil(ratio)
            if port_edge_mode == 'thirds' and axis < 2:
                edge = pcb_port_edge_policy(geometry, settings, port_edge_mode)
                hints = edge['x_hints' if axis == 0 else 'y_hints']
                if (a,b) in (hints[:2],hints[2:]) and ratio <= 1 + _DOMAIN_REL_TOL:
                    count = 1  # preserve edge cell despite subtraction residue
            divisions.append(count)
        boundaries.append(edges)
        limits.append(axis_limits)
        counts.append(divisions)
    shape = [sum(divisions) + 2*pml for divisions in counts]
    _domain_count_guard(shape, policy.max_cells)  # Before allocating even 1-D axes.
    ordinary = []
    for axis in range(3):
        initial = _subdivide(boundaries[axis], counts[axis])
        # Other axes' known lower bounds include PML; safe also at exact budget.
        budget = policy.max_cells // prod(shape[j] for j in range(3) if j != axis) - 2*pml
        graded = _grade_domain_axis(initial, policy.growth_ratio_target, budget)
        _audit_domain_axis(graded, boundaries[axis], limits[axis], policy.growth_ratio_limit)
        shape[axis] = len(graded)-1 + 2*pml
        _domain_count_guard(shape, policy.max_cells)
        ordinary.append(graded)
    _domain_count_guard(tuple(len(a)-1 for a in ordinary), policy.max_cells)
    axes = tuple(_add_domain_pml(a, pml) for a in ordinary)
    shape = tuple(len(a)-1 for a in axes)
    cell_count = _domain_count_guard(shape, policy.max_cells)
    all_steps = [_domain_steps(axis) for axis in axes]
    worst = max(_worst_growth(steps) for steps in all_steps)
    if worst > policy.growth_ratio_limit * (1 + _DOMAIN_REL_TOL):
        raise ConfigurationError("PCB domain: końcowy audyt wzrostu z PML nie przeszedł.")
    for axis, core in zip(axes, anchors):
        if not axis[0] < axis[pml] < core[0] < core[-1] < axis[-pml-1] < axis[-1]:
            raise ConfigurationError("PCB domain: nieprawidłowy porządek granic struktury, powietrza i PML.")
    mesh = PcbDomainMesh(
        *axes, shape, cell_count,
        tuple(a[0] for a in ordinary), tuple(a[-1] for a in ordinary),
        tuple(a[0] for a in axes), tuple(a[-1] for a in axes), pml,
        min(min(s) for s in all_steps), max(max(s) for s in all_steps), worst,
        plan.drill_centres_xy_m,
    )

    audit_pcb_port_edge_mesh(geometry, settings, mesh, port_edge_mode)
    return mesh


def pcb_port_edge_policy(geometry, settings, port_edge_mode='aligned'):
    """Four synthetic feed edges only; no vertex-to-grid or automatic net policy."""
    if port_edge_mode not in ('aligned', 'thirds'):
        raise ConfigurationError('PCB port_edge_mode: wymagane aligned albo thirds.')
    policy = derive_pcb_physical_mesh_policy(geometry,settings)
    n,p = geometry.port.negative_xy_m,geometry.port.positive_xy_m
    my = (n[1]+p[1])/2
    yl,yu = my-geometry.port.width_m/2,my+geometry.port.width_m/2
    hx = min(policy.max_port_gap_step_m,policy.max_substrate_xy_step_m)
    hy = min(policy.max_port_width_step_m,policy.max_substrate_xy_step_m)
    return dict(mode=port_edge_mode,edge_resolution_x=hx,edge_resolution_y=hy,
        physical_x_edges=(n[0],p[0]),physical_y_edges=(yl,yu),
        x_hints=(n[0]-hx/3,n[0]+2*hx/3,p[0]-2*hx/3,p[0]+hx/3),
        y_hints=(yl-2*hy/3,yl+hy/3,yu-hy/3,yu+2*hy/3))


def _audit_thirds_pads(geometry, edge):
    """Conservative geometric proof for two rectangular synthetic terminals.

    Supports only axis-aligned rectangular pads (rotation residue tolerated).
    Full transverse contacts and the occupied X side are checked geometrically,
    not inferred from IDs. General polygon/edge recognition is deliberately absent.
    """
    from antenna_lab.pcb.validation import _contains, TOLERANCE_M
    if len(geometry.copper) != 2 or any(c.holes_xy_m for c in geometry.copper):
        raise ConfigurationError('PCB thirds: wymagane dokładnie dwa prostokątne pady syntetyczne.')
    n,p = geometry.port.negative_xy_m,geometry.port.positive_xy_m
    yl,yu = edge['physical_y_edges']
    owners=[]
    for endpoint,side in ((n,'negative'),(p,'positive')):
        found=[c for c in geometry.copper if _contains(endpoint,list(c.vertices_xy_m))]
        if len(found)!=1:
            raise ConfigurationError(f'PCB thirds {side}: niejednoznaczny kontakt.')
        copper=found[0];vertices=list(copper.vertices_xy_m)
        if vertices[-1]==vertices[0]: vertices.pop()
        xmin,xmax=min(v[0] for v in vertices),max(v[0] for v in vertices)
        ymin,ymax=min(v[1] for v in vertices),max(v[1] for v in vertices)
        corners={(min((0,1),key=lambda i:abs(v[0]-(xmin,xmax)[i])),
                  min((0,1),key=lambda i:abs(v[1]-(ymin,ymax)[i]))) for v in vertices}
        rectangular=(len(vertices)==4 and len(corners)==4 and all(
            min(abs(x-xmin),abs(x-xmax))<=TOLERANCE_M and
            min(abs(y-ymin),abs(y-ymax))<=TOLERANCE_M for x,y in vertices))
        inner=xmax if side=='negative' else xmin
        inside=edge['x_hints'][0] if side=='negative' else edge['x_hints'][-1]
        if (not rectangular or abs(inner-endpoint[0])>TOLERANCE_M or
            abs(ymin-yl)>TOLERANCE_M or abs(ymax-yu)>TOLERANCE_M or
            not xmin < inside < xmax):
            raise ConfigurationError(f'PCB thirds {side}: błędna strona metalu lub niepełny prostokątny kontakt; '
                                     'ujemny pad musi zajmować -X, dodatni +X, z krawędziami Y na szerokości portu.')
        owners.append(copper.id)
    if owners[0]==owners[1]:
        raise ConfigurationError('PCB thirds: wspólny przewodnik zwiera port.')


def make_pcb_solver_anchor_plan(geometry, settings, port_edge_mode='aligned', *, gerber_quality=None):
    """Default aligned plan is unchanged; Gerber filtering is explicitly opt-in."""
    from dataclasses import replace
    if gerber_quality is not None:
        if port_edge_mode != 'aligned':
            raise ConfigurationError('Gerber economical anchors require aligned port edges.')
        return make_gerber_mesh_anchor_plan(geometry, settings, gerber_quality)[0]
    plan=make_pcb_mesh_anchor_plan(geometry)
    if port_edge_mode=='aligned': return plan
    edge=pcb_port_edge_policy(geometry,settings,port_edge_mode)
    _audit_thirds_pads(geometry,edge)
    n,p=geometry.port.negative_xy_m,geometry.port.positive_xy_m
    mids=((n[0]+p[0])/2,(n[1]+p[1])/2)
    modified=[]
    for axis,required in enumerate((plan.x_required_m,plan.y_required_m)):
        forbidden=edge['physical_x_edges' if axis==0 else 'physical_y_edges']
        hints=edge['x_hints' if axis==0 else 'y_hints']
        # Board extremes and copper centres/outer edges are independent anchors.
        board=[v[axis] for v in geometry.outline.vertices_xy_m]
        independent=[min(board),max(board),mids[axis]]
        for copper in geometry.copper:
            vals=[v[axis] for v in copper.vertices_xy_m];lo,hi=min(vals),max(vals)
            independent.append((lo+hi)/2)
            independent.extend(v for v in (lo,hi) if all(abs(v-f)>ANCHOR_MERGE_TOLERANCE_M for f in forbidden))
        if any(abs(v-f)<=ANCHOR_MERGE_TOLERANCE_M for v in independent for f in forbidden):
            raise ConfigurationError('PCB thirds: niezależna kotwica koliduje z fizyczną krawędzią portu.')
        remaining=[v for v in required if all(abs(v-f)>ANCHOR_MERGE_TOLERANCE_M for f in forbidden)]
        modified.append(_merge(remaining,(*hints,mids[axis])))
    return replace(plan,x_required_m=modified[0],y_required_m=modified[1])


def audit_pcb_port_edge_mesh(geometry, settings, mesh, port_edge_mode='aligned'):
    """Audit exact hints, forbidden edge lines, and unsplit edge cells in thirds."""
    if port_edge_mode=='aligned': return
    edge=pcb_port_edge_policy(geometry,settings,port_edge_mode)
    for axis,lines in (('x',mesh.x_lines_m),('y',mesh.y_lines_m)):
        hints=edge[axis+'_hints']
        if not set(hints).issubset(lines) or any(v in lines for v in edge['physical_'+axis+'_edges']):
            raise ConfigurationError(f'PCB thirds {axis}: brak dokładnych hints lub ponownie dodana fizyczna krawędź.')
        for a,b in (hints[:2],hints[2:]):
            if any(a<v<b for v in lines):
                raise ConfigurationError(f'PCB thirds {axis}: grading/podział rozbił komórkę krawędziową 1/3–2/3; '
                                         'zmień jawne ustawienia, nie osłabiaj gradingu.')
    if 0.0 not in mesh.z_lines_m:
        raise ConfigurationError('PCB thirds: brak dokładnej płaszczyzny z=0.')


def make_gerber_mesh_anchor_plan(geometry, settings, quality):
    """Filter only numerical copper anchors; never change physical polygons.

    Board/material outer bounds and the complete feed anchor set take precedence.
    Sorted candidate edges (then verify-only bounding-box midpoints) are accepted
    only at distances >= half the smaller local resolution of the two anchors.
    Local resolution is substrate XY outside the feed interval and the smaller
    substrate/port step inside it. Critical-critical separations are never repaired.
    """
    from dataclasses import replace
    if quality not in ('preview', 'design', 'verify'):
        raise ConfigurationError('Unknown Gerber anchor quality.')
    base = make_pcb_mesh_anchor_plan(geometry)
    policy = derive_pcb_physical_mesh_policy(geometry, settings)
    n,p = geometry.port.negative_xy_m, geometry.port.positive_xy_m
    mx,my = (n[0]+p[0])/2, (n[1]+p[1])/2
    half = geometry.port.width_m/2
    feed = ((n[0],mx,p[0]), (my-half,my,my+half))
    port_steps = (policy.max_port_gap_step_m, policy.max_port_width_step_m)
    bounds = geometry.bounds
    axes, suppressed = [], []
    for axis in range(2):
        board = [v[axis] for v in geometry.outline.vertices_xy_m]
        critical = sorted(set((*feed[axis], *component_terminal_anchors(geometry, axis), *(p[axis] for p in base.drill_centres_xy_m), min(board), max(board), bounds[0][axis], bounds[1][axis])))
        retained = list(_merge((), critical))
        def resolution(v):
            return min(policy.max_substrate_xy_step_m, port_steps[axis]) if feed[axis][0] <= v <= feed[axis][-1] else policy.max_substrate_xy_step_m
        candidates = []
        for copper in geometry.copper:
            values = [v[axis] for v in copper.vertices_xy_m]
            low,high = min(values),max(values)
            candidates.extend((0,v,copper.id,kind) for v,kind in ((low,'edge_min'),(high,'edge_max')))
            candidates.append((1,(low+high)/2,copper.id,'bbox_midpoint'))
        for _,value,identifier,kind in sorted(candidates):
            record = dict(axis='xy'[axis], coordinate_m=value, copper_id=identifier, kind=kind)
            if value in retained:
                continue  # Exact coordinate is already represented, not suppressed.
            if kind == 'bbox_midpoint' and quality != 'verify':
                suppressed.append(dict(record, reason='nonphysical_midpoint_omitted'))
                continue
            conflicts = [(other, .5*min(resolution(value),resolution(other))) for other in sorted(retained)
                         if abs(value-other) < .5*min(resolution(value),resolution(other))]
            if conflicts:
                other,minimum = min(conflicts, key=lambda pair:(abs(pair[0]-value),pair[0]))
                suppressed.append(dict(record, reason='below_half_local_resolution',
                    retained_neighbor_m=other, minimum_separation_m=minimum, separation_m=abs(value-other)))
            else:
                retained.append(value)
        axes.append(tuple(sorted(retained)))
    return replace(base,x_required_m=axes[0],y_required_m=axes[1]), dict(
        name='gerber_economical_v1', quality=quality, drill_centres_xy_m=base.drill_centres_xy_m, minimum_interval_fraction=.5,
        copper_midpoints=quality=='verify', suppressed_noncritical_anchors=suppressed,
        component_terminal_anchors_m={a:component_terminal_anchors(geometry,i) for i,a in enumerate('xy')})
