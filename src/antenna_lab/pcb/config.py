"""Standalone PCB inputs; unit conversion happens only in this loader."""

from dataclasses import dataclass
import json
from pathlib import Path

from antenna_lab.core.config import ConfigurationError, validate_schema


@dataclass(frozen=True)
class ResolvedPcbConfig:
    schema_version: int
    model: str
    copper_top_path: Path
    board_outline_path: Path
    copper_thickness_m: float
    copper_conductivity_s_m: float
    copper_model: str
    substrate_thickness_m: float
    substrate_epsilon_r: float
    substrate_loss_tangent: float
    port_negative_xy_m: tuple[float, float]
    port_positive_xy_m: tuple[float, float]
    port_width_m: float


def validate_pcb_config(value: dict) -> dict:
    """Validate external units without modifying input or accessing Gerbers."""
    validate_schema(value, "pcb-config.schema.json")
    for name, path in value["files"].items():
        if not path.strip():
            raise ConfigurationError(f"files.{name}: ścieżka nie może być pusta.")
    if value["port"]["negative_mm"] == value["port"]["positive_mm"]:
        raise ConfigurationError("port: końce muszą być różne.")
    return value


def load_pcb_config(path) -> ResolvedPcbConfig:
    """Load UTF-8/BOM JSON and resolve paths relative to its directory.

    Gerber existence and contents are intentionally unchecked. resolve(strict=False)
    permits missing targets; no Gerber is opened. Copper thickness/conductivity
    are metadata for v0 PEC, not a request to construct finite-thickness copper.
    """
    path = Path(path).resolve()
    with path.open(encoding="utf-8-sig") as stream:
        value = validate_pcb_config(json.load(stream))
    copper, substrate, port = value["copper"], value["substrate"], value["port"]
    return ResolvedPcbConfig(
        schema_version=value["schema_version"], model=value["model"],
        copper_top_path=(path.parent / value["files"]["copper_top"]).resolve(strict=False),
        board_outline_path=(path.parent / value["files"]["board_outline"]).resolve(strict=False),
        copper_thickness_m=copper["thickness_um"] * 1e-6,
        copper_conductivity_s_m=copper["conductivity_s_m"], copper_model=copper["model"],
        substrate_thickness_m=substrate["thickness_mm"] * 1e-3,
        substrate_epsilon_r=substrate["epsilon_r"], substrate_loss_tangent=substrate["loss_tangent"],
        port_negative_xy_m=tuple(v * 1e-3 for v in port["negative_mm"]),
        port_positive_xy_m=tuple(v * 1e-3 for v in port["positive_mm"]),
        port_width_m=port["width_mm"] * 1e-3,
    )
