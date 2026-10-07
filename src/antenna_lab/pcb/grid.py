"""Integer PCB geometry lattice; independent of the float FDTD mesh.

Input numbers are metres. Decimal/string input is exact. For float inputs,
only a two-ULP neighbourhood of integer/half ticks is canonicalized at the
projection boundary, preventing ordinary binary arithmetic residue from
changing a decimal tie. This is not a geometry/topology merge tolerance.
"""
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING, localcontext
import json
from math import ulp

from antenna_lab.core.config import ConfigurationError


@dataclass(frozen=True)
class PcbGrid:
    quantum_nm: int = 10000

    def __post_init__(self):
        if type(self.quantum_nm) is not int or self.quantum_nm not in (100000,10000,1000,100):
            raise ConfigurationError('PCB lattice quantum must be 100, 10, 1 or 0.1 um.')

    @property
    def quantum_decimal_m(self):
        return Decimal(self.quantum_nm)*Decimal('1e-9')

    @property
    def quantum_m(self):
        return float(self.quantum_decimal_m)

    @property
    def quantum_um(self):
        return self.quantum_nm/1000

    def _ticks_decimal(self, value, halves=False):
        if isinstance(value,bool): raise ConfigurationError('PCB lattice requires finite spatial numbers, not bool.')
        try: number=Decimal(str(value))
        except (InvalidOperation,ValueError) as exc: raise ConfigurationError('PCB lattice: invalid spatial number.') from exc
        if not number.is_finite(): raise ConfigurationError('PCB lattice: finite spatial number required.')
        with localcontext() as context:
            context.prec=max(60,len(number.as_tuple().digits)+abs(number.adjusted())+20)
            ticks=number/self.quantum_decimal_m
            if isinstance(value,float):
                factor=2 if halves else 1
                target=(ticks*factor).to_integral_value(rounding=ROUND_HALF_UP)/factor
                residue=Decimal(str(ulp(value)))*2/self.quantum_decimal_m
                if abs(ticks-target)<=residue: ticks=target
            return ticks

    def nearest_tick(self, metres):
        return int(self._ticks_decimal(metres,True).to_integral_value(rounding=ROUND_HALF_UP))

    def floor_tick(self, metres):
        return int(self._ticks_decimal(metres).to_integral_value(rounding=ROUND_FLOOR))

    def ceil_tick(self, metres):
        return int(self._ticks_decimal(metres).to_integral_value(rounding=ROUND_CEILING))

    def to_metres(self, tick):
        if type(tick) is not int: raise ConfigurationError('PCB lattice export requires an integer tick.')
        return float(Decimal(tick)*self.quantum_decimal_m)


XY = tuple[int, int]
Ring = tuple[XY, ...]


@dataclass(frozen=True)
class TickCopper:
    id: str
    layer_role: str
    z: int
    outer: Ring
    holes: tuple[Ring, ...]


@dataclass(frozen=True)
class TickDielectric:
    name: str
    outline: Ring
    bottom: int
    top: int
    thickness: int
    epsilon_r: float
    loss_tangent: float


@dataclass(frozen=True)
class TickCopperLayer:
    role: str
    z: int
    model: str
    material_thickness_m: float  # Not a geometric extrusion; never quantized.
    conductivity_s_m: float
    source_sha256: str


@dataclass(frozen=True)
class TickPort:
    id: str
    negative: XY
    positive: XY
    width: int


@dataclass(frozen=True)
class TickDrill:
    id: str
    centre: XY
    radius: int
    diameter: int  # Exactly 2*radius; radius is the native circle parameter.
    plated: bool
    outer_radius: int | None
    connected_layer_roles: tuple[str, ...]
    source_file_role: str
    source_tool: str
    source_file_sha256: str
    plating_thickness_m: float | None  # Provenance only, not a mesh thickness.


@dataclass(frozen=True)
class TickComponent:
    id: str
    kind: str
    value_si: float
    value_text: str
    pin1_net: str
    pin2_net: str
    pin1: XY
    pin2: XY
    layer: str
    axis: str
    gap_start: XY
    gap_stop: XY
    contact_window: Ring
    source_sha256: str
    flying_probe_sha256: str


@dataclass(frozen=True)
class TickSource:
    refdes: str
    pin_nets: tuple[str, str]
    pin1: XY
    pin2: XY
    enet_sha256: str
    flying_probe_sha256: str


@dataclass(frozen=True)
class QuantizedPcbGeometry:
    """All authoritative spatial values are ticks; no native/export integration.

    source_json is an immutable provenance snapshot, not solver geometry.
    No PML/domain/mesh exists here yet; future modules must use the same grid.
    """
    grid: PcbGrid
    model: str
    outline: Ring
    copper: tuple[TickCopper, ...]
    dielectrics: tuple[TickDielectric, ...]
    copper_layers: tuple[TickCopperLayer, ...]
    port: TickPort
    drills: tuple[TickDrill, ...]
    components: tuple[TickComponent, ...]
    source_port: TickSource | None
    assumptions: tuple[str, ...]
    source_json: str

    @property
    def provenance(self):
        return json.loads(self.source_json)

    def as_dict(self):
        value=asdict(self)
        value['source_geometry']=json.loads(value.pop('source_json'))
        value['coordinate_units']='integer_ticks'
        return json.loads(json.dumps(value,allow_nan=False))
