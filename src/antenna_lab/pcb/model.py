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
    layer_role: str = "top"
    holes_xy_m: tuple[tuple[tuple[float, float], ...], ...] = ()


@dataclass(frozen=True)
class CopperImageStats:
    layer_role: str
    dark_primitive_count: int
    clear_primitive_count: int
    final_conductor_count: int
    final_hole_count: int


@dataclass(frozen=True)
class Substrate:
    outline: BoardOutline
    z_min_m: float
    z_max_m: float
    epsilon_r: float
    loss_tangent: float


@dataclass(frozen=True)
class DielectricLayer(Substrate):
    name: str = "substrate"


@dataclass(frozen=True)
class CopperLayer:
    role: str
    z_m: float
    model: str
    thickness_m: float
    conductivity_s_m: float
    source_sha256: str


@dataclass(frozen=True)
class PcbPort:
    id: str
    negative_xy_m: tuple[float, float]
    positive_xy_m: tuple[float, float]
    width_m: float


@dataclass(frozen=True)
class PcbTransform:
    """Translation then XY rotation; exact_orthogonal selects quarter-turn
    coefficients instead of trig. False preserves legacy/generic transforms.
    """

    translation_xy_m: tuple[float, float]
    rotation_rad: float
    exact_orthogonal: bool = False


@dataclass(frozen=True)
class PcbDrill:
    id: str
    x_m: float
    y_m: float
    drill_diameter_m: float
    plated: bool
    source_file_role: str
    source_tool: str
    source_file_sha256: str
    plating_thickness_m: float | None = None
    equivalent_outer_radius_m: float | None = None
    connected_layer_roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class PcbLumpedComponent:
    id: str
    kind: str
    value_si: float
    value_text: str
    pin1_net: str
    pin2_net: str
    pin1_xy_m: tuple[float, float]
    pin2_xy_m: tuple[float, float]
    layer: str
    axis: str
    gap_start_xy_m: tuple[float, float]
    gap_stop_xy_m: tuple[float, float]
    contact_window_xy_m: tuple[tuple[float, float], ...]
    source_sha256: str
    flying_probe_sha256: str


@dataclass(frozen=True)
class PcbSourceProvenance:
    source_refdes: str
    source_pin_nets: tuple[str, str]
    pin1_xy_m: tuple[float, float]
    pin2_xy_m: tuple[float, float]
    enet_sha256: str
    flying_probe_sha256: str


@dataclass
class PcbGeometry:
    model: str
    outline: BoardOutline
    copper: list[CopperPolygon]
    substrate: Substrate
    port: PcbPort
    assumptions: list[str] = field(default_factory=list)
    dielectric_layers: tuple[DielectricLayer, ...] = ()
    copper_layers: tuple[CopperLayer, ...] = ()
    copper_composition: tuple[CopperImageStats, ...] = ()
    drills: tuple[PcbDrill, ...] = ()
    components: tuple[PcbLumpedComponent, ...] = ()
    source_port: PcbSourceProvenance | None = None

    @property
    def dielectrics(self):
        """Actual materials; substrate is the legacy single/top-material view."""
        return self.dielectric_layers or (self.substrate,)

    @property
    def top_copper(self):
        return [c for c in self.copper if c.layer_role == 'top']

    @property
    def bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Material/board AABB, excluding air and the logical port region.

        Includes every copper polygon, even outside the board; validation is
        a separate step. PCB v0 board and port coordinates lie at z=0.
        """
        points = [(x, y, 0.0) for x, y in self.outline.vertices_xy_m]
        points.extend((x, y, z) for layer in self.dielectrics for x, y in layer.outline.vertices_xy_m
                      for z in (layer.z_min_m, layer.z_max_m))
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
            "schema_version": 2 if self.copper_layers else 1,
            "units": "m",
            "coordinate_system": {"axes": "xyz", "handedness": "right",
                                  "board_top_z_m": 0.0},
            **json_value(asdict(self)),
        }
