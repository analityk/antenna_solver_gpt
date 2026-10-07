"""Rigid XY normalization in metres; no rounding or coordinate snapping.

PcbTransform.translation_xy_m is added BEFORE rotation; rotation_rad is the
counter-clockwise angle: forward(p) = rotate(p + translation, angle).
Inverse order: inverse(p) = rotate(p, -angle) - translation.
"""

from dataclasses import replace
from math import atan2, cos, sin

from antenna_lab.pcb.model import PcbGeometry, PcbTransform
from antenna_lab.pcb.validation import validate_pcb_geometry


def _map_xy(geometry, point):
    def outline(value):
        return replace(value, vertices_xy_m=tuple(point(p) for p in value.vertices_xy_m))

    return replace(
        geometry,
        outline=outline(geometry.outline),
        substrate=replace(geometry.substrate, outline=outline(geometry.substrate.outline)),
        dielectric_layers=tuple(replace(d, outline=outline(d.outline)) for d in geometry.dielectric_layers),
        copper=[replace(copper, vertices_xy_m=tuple(point(p) for p in copper.vertices_xy_m))
                for copper in geometry.copper],
        port=replace(geometry.port, negative_xy_m=point(geometry.port.negative_xy_m),
                     positive_xy_m=point(geometry.port.positive_xy_m)),
        assumptions=list(geometry.assumptions),
    )


def normalize_port_orientation(geometry: PcbGeometry) -> tuple[PcbGeometry, PcbTransform]:
    """Return a new PCB centered on the port midpoint, directed along +X.

    Endpoints are symmetric about zero up to floating-point residue; they use
    exactly the same transform as all polygons, with no special correction.
    """
    validate_pcb_geometry(geometry)
    negative, positive = geometry.port.negative_xy_m, geometry.port.positive_xy_m
    translation = tuple(-(a / 2.0 + b / 2.0) for a, b in zip(negative, positive))
    angle = -atan2(positive[1] - negative[1], positive[0] - negative[0])
    transform = PcbTransform(translation, angle)
    c, s = cos(angle), sin(angle)

    def point(p):
        x, y = p[0] + translation[0], p[1] + translation[1]
        return c * x - s * y, s * x + c * y

    result = _map_xy(geometry, point)
    validate_pcb_geometry(result)
    return result, transform


def inverse_transform_geometry(geometry: PcbGeometry, transform: PcbTransform) -> PcbGeometry:
    """Undo normalization using its returned metadata, without mutating input."""
    validate_pcb_geometry(geometry)
    c, s = cos(transform.rotation_rad), sin(transform.rotation_rad)
    tx, ty = transform.translation_xy_m

    def point(p):
        x, y = p
        return c * x + s * y - tx, -s * x + c * y - ty

    result = _map_xy(geometry, point)
    validate_pcb_geometry(result)
    return result
