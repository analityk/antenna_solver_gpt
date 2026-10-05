"""Synthetic PCB integration checkpoint; no Gerber IO or simulation stages."""

from dataclasses import dataclass
from math import hypot, isfinite

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.config import ResolvedPcbConfig, load_pcb_config
from antenna_lab.pcb.model import (
    BoardOutline, CopperPolygon, PcbGeometry, PcbPort, PcbTransform, Substrate,
)
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.validation import validate_pcb_geometry


@dataclass(frozen=True)
class PcbWorkflowResult:
    config: ResolvedPcbConfig
    source_geometry: PcbGeometry
    normalized_geometry: PcbGeometry
    transform: PcbTransform


def make_synthetic_pcb_geometry(config: ResolvedPcbConfig) -> PcbGeometry:
    """Build two rectangles around configured endpoints, in their local basis.

    Depth and board margin are max(gap, port width); conductor half-width is
    min(width/2, gap/4). Dimensions are temporary infrastructure, not Gerbers.
    The caller validates the result before normalization.
    """
    n, p = config.port_negative_xy_m, config.port_positive_xy_m
    dx, dy = p[0] - n[0], p[1] - n[1]
    gap = hypot(dx, dy)
    if not isfinite(gap) or gap <= 0:
        raise ConfigurationError("port: wymagana dodatnia skończona długość.")
    ux, uy = dx / gap, dy / gap
    vx, vy = -uy, ux
    depth = margin = max(gap, config.port_width_m)
    half_width = min(config.port_width_m / 2, gap / 4)

    def rectangle(origin, left, right, half):
        return tuple((origin[0] + x * ux + y * vx,
                      origin[1] + x * uy + y * vy)
                     for x, y in ((left, -half), (right, -half),
                                  (right, half), (left, half)))

    board = BoardOutline(rectangle(n, -depth - margin, gap + depth + margin,
                                   half_width + margin))
    return PcbGeometry(
        model="pcb", outline=board,
        copper=[
            CopperPolygon("synthetic_negative", rectangle(n, -depth, 0., half_width), 0.),
            CopperPolygon("synthetic_positive", rectangle(p, 0., depth, half_width), 0.),
        ],
        substrate=Substrate(board, -config.substrate_thickness_m, 0.,
                            config.substrate_epsilon_r, config.substrate_loss_tangent),
        port=PcbPort("port_1", n, p, config.port_width_m),
        assumptions=["synthetic PCB placeholder geometry", "PEC top copper",
                     "Gerber geometry not loaded"],
    )


def prepare_pcb_placeholder(config_path) -> PcbWorkflowResult:
    """Load → synthetic geometry → validate → normalize; retain both frames."""
    config = load_pcb_config(config_path)
    source = make_synthetic_pcb_geometry(config)
    validate_pcb_geometry(source)
    normalized, transform = normalize_port_orientation(source)
    return PcbWorkflowResult(config, source, normalized, transform)
