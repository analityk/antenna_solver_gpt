"""PCB feature anchors and placeholder Cartesian subdivision.

Axes span required anchors only: no air domain or absorbing boundaries.
This infrastructure mesh is not a complete runnable FDTD domain.
"""

from dataclasses import dataclass
from math import hypot, ceil, isfinite, prod

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import PcbGeometry
from antenna_lab.pcb.validation import validate_pcb_geometry

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


def _merge(values, critical=()):
    """Keep critical coordinates first, then the smallest eligible coordinate.

    A candidate within tolerance of any retained coordinate is discarded.
    Clusters are representative-based, not transitive chains: this avoids
    bridging distinct features through a series of near-identical values.
    Never average. Distinct critical anchors cannot be collapsed safely.
    """
    retained = sorted(critical)
    if any(b - a <= ANCHOR_MERGE_TOLERANCE_M for a, b in zip(retained, retained[1:])):
        raise ConfigurationError("port: krytyczne kotwice są zbyt blisko względem tolerancji scalania.")
    for value in sorted(values):
        if all(abs(value - other) > ANCHOR_MERGE_TOLERANCE_M for other in retained):
            retained.append(value)
    return tuple(sorted(retained))


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
    z = [geometry.substrate.z_min_m, geometry.substrate.z_max_m]
    for copper in geometry.copper:
        for axis, anchors in ((0, x), (1, y)):
            low = min(v[axis] for v in copper.vertices_xy_m)
            high = max(v[axis] for v in copper.vertices_xy_m)
            anchors.extend((low, (low + high) / 2, high))
        z.append(copper.z_m)
    half = geometry.port.width_m / 2
    return PcbMeshAnchorPlan(
        _merge(x, (n[0], mx, p[0])),
        _merge(y, (my - half, my, my + half)),
        _merge(z), hypot(p[0] - n[0], p[1] - n[1]), geometry.port.width_m,
        geometry.substrate.z_max_m - geometry.substrate.z_min_m,
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
    cell_count = prod(shape)
    # Check before allocating axes, including extremely fine caller settings.
    if cell_count > settings.max_cells:
        raise ConfigurationError(f"PCB: {cell_count} komórek przekracza max_cells={settings.max_cells}.")
    lines = tuple(_subdivide(axis, divisions) for axis, divisions in zip(axes, counts))
    steps = [b - a for axis in lines for a, b in zip(axis, axis[1:])]
    return PcbPlaceholderMesh(*lines, shape, cell_count, min(steps), max(steps))
