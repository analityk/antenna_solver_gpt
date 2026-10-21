"""Neutral source CAD semantics. No Gerber, native solver or mesh dependency."""
from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class SourceRoutePrimitive:
    id: str
    record_index: int
    kind: str
    net: str
    layer_id: int
    layer_role: str
    start_xy_m: tuple[float, float]
    stop_xy_m: tuple[float, float]
    width_m: float
    signed_sweep_deg: float | None
    center_xy_m: tuple[float, float] | None
    source_file: str
    source_sha256: str
    conductor_id: str | None = None


@dataclass(frozen=True)
class SourceVia:
    id: str
    record_index: int
    net: str
    centre_xy_m: tuple[float, float]
    drill_diameter_m: float
    pad_diameter_m: float
    span_rule: str
    source_file: str
    source_sha256: str


@dataclass(frozen=True)
class EasyEdaSource:
    source_file: str
    source_sha256: str
    format_version: str
    editor_version: str
    canvas_display_unit: str
    routes: tuple[SourceRoutePrimitive, ...]
    vias: tuple[SourceVia, ...]
    # Immutable strict JSON snapshots; raw records retain all unknown fields.
    records_json: str
    semantic_json: str

    @property
    def records(self):
        return json.loads(self.records_json)

    @property
    def semantics(self):
        return json.loads(self.semantic_json)

    def as_dict(self):
        result=asdict(self)
        result['records']=json.loads(result.pop('records_json'))
        result['semantics']=json.loads(result.pop('semantic_json'))
        return json.loads(json.dumps(result,allow_nan=False))
