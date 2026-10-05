"""PCB v0 data in SI units; no solver or antenna-model dependencies."""

from dataclasses import asdict, dataclass, field
from math import isfinite


@dataclass(frozen=True)
class BoardOutline:
    """Logically closed polygon; repeating the first vertex is optional."""

    vertices_xy_m: tuple[tuple[float, float], ...]

    def __post_init__(self):
        if any(len(p) != 2 or not all(isfinite(v) for v in p)
               for p in self.vertices_xy_m):
            raise ValueError("Board outline requires finite XY coordinates.")
        if len(set(self.vertices_xy_m)) < 3:
            raise ValueError("Board outline requires at least three unique vertices.")


@dataclass(frozen=True)
class CopperPolygon:
    id: str
    vertices_xy_m: tuple[tuple[float, float], ...]
    z_m: float


@dataclass(frozen=True)
class Substrate:
    outline: BoardOutline
    z_min_m: float
    z_max_m: float
    epsilon_r: float
    loss_tangent: float


@dataclass(frozen=True)
class PcbPort:
    id: str
    negative_xy_m: tuple[float, float]
    positive_xy_m: tuple[float, float]
    width_m: float


@dataclass(frozen=True)
class PcbTransform:
    """Metadata for translation followed by rotation in XY."""

    translation_xy_m: tuple[float, float]
    rotation_rad: float


@dataclass
class PcbGeometry:
    model: str
    outline: BoardOutline
    copper: list[CopperPolygon]
    substrate: Substrate
    port: PcbPort
    assumptions: list[str] = field(default_factory=list)

    @property
    def bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Material/board AABB, excluding air and the logical port region.

        Includes every copper polygon, even outside the board; validation is
        a separate step. PCB v0 board and port coordinates lie at z=0.
        """
        points = [(x, y, 0.0) for x, y in self.outline.vertices_xy_m]
        points.extend((x, y, z) for x, y in self.substrate.outline.vertices_xy_m
                      for z in (self.substrate.z_min_m, self.substrate.z_max_m))
        points.extend((x, y, polygon.z_m) for polygon in self.copper
                      for x, y in polygon.vertices_xy_m)
        return (tuple(min(p[i] for p in points) for i in range(3)),
                tuple(max(p[i] for p in points) for i in range(3)))

    def as_dict(self) -> dict:
        """Detached JSON-compatible snapshot, preserving supplied polygon order."""
        def json_value(value):
            if isinstance(value, dict):
                return {key: json_value(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [json_value(item) for item in value]
            return value

        return {
            "schema_version": 1,
            "units": "m",
            "coordinate_system": {"axes": "xyz", "handedness": "right",
                                  "board_top_z_m": 0.0},
            **json_value(asdict(self)),
        }
