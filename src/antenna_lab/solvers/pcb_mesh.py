"""Feature anchors only: no axis filling, cell sizes or simulation settings."""

from dataclasses import dataclass
from math import hypot

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
