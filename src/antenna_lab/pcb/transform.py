"""Rigid XY normalization in metres; no rounding or coordinate snapping.

PcbTransform.translation_xy_m is added BEFORE rotation; rotation_rad is the
counter-clockwise angle: forward(p) = rotate(p + translation, angle).
Inverse order: inverse(p) = rotate(p, -angle) - translation.
Exact axial sources set exact_orthogonal; forward/inverse then use only
-1/0/+1 coefficients. Oblique sources retain ordinary double-precision trig.
"""

from dataclasses import replace
from math import atan2, cos, sin, pi

from antenna_lab.pcb.model import PcbGeometry, PcbTransform
from antenna_lab.pcb.validation import validate_pcb_geometry


def _rotation_coefficients(transform):
    # The flag distinguishes an exactly axial source from an oblique source
    # whose atan2 could round to the same stored quarter-turn angle.
    if transform.exact_orthogonal:
        return {0.0: (1, 0), pi: (-1, 0), -pi: (-1, 0),
                pi/2: (0, 1), -pi/2: (0, -1)}[transform.rotation_rad]
    return cos(transform.rotation_rad), sin(transform.rotation_rad)


def _map_xy(geometry, point):
    def outline(value):
        return replace(value, vertices_xy_m=tuple(point(p) for p in value.vertices_xy_m))

    def drill(value):
        x,y=point((value.x_m,value.y_m))
        return replace(value,x_m=x,y_m=y)

    return replace(
        geometry,
        outline=outline(geometry.outline),
        substrate=replace(geometry.substrate, outline=outline(geometry.substrate.outline)),
        dielectric_layers=tuple(replace(d, outline=outline(d.outline)) for d in geometry.dielectric_layers),
        copper=[replace(copper, vertices_xy_m=tuple(point(p) for p in copper.vertices_xy_m),
                        holes_xy_m=tuple(tuple(point(p) for p in ring) for ring in copper.holes_xy_m))
                for copper in geometry.copper],
        port=replace(geometry.port, negative_xy_m=point(geometry.port.negative_xy_m),
                     positive_xy_m=point(geometry.port.positive_xy_m)),
        drills=tuple(drill(d) for d in geometry.drills),
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
    dx,dy = positive[0]-negative[0],positive[1]-negative[1]
    angle = -atan2(dy,dx)
    # Exact comparisons only: no tolerance, rounding or snapping.
    transform = PcbTransform(translation, angle, exact_orthogonal=(dx == 0 or dy == 0))
    c, s = _rotation_coefficients(transform)

    def point(p):
        x, y = p[0] + translation[0], p[1] + translation[1]
        return c * x - s * y, s * x + c * y

    result = _map_xy(geometry, point)
    validate_pcb_geometry(result)
    return result, transform


def inverse_transform_geometry(geometry: PcbGeometry, transform: PcbTransform) -> PcbGeometry:
    """Undo normalization using its returned metadata, without mutating input."""
    validate_pcb_geometry(geometry)
    c, s = _rotation_coefficients(transform)
    tx, ty = transform.translation_xy_m

    def point(p):
        x, y = p
        return c * x + s * y - tx, -s * x + c * y - ty

    result = _map_xy(geometry, point)
    validate_pcb_geometry(result)
    return result
