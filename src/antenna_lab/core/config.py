"""SI configuration loading; schemas are versioned in the editable checkout."""

from copy import deepcopy
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]


class ConfigurationError(ValueError):
    """Actionable input error, safe to display in the UI."""


def reject_nonfinite(value, location="config"):
    if isinstance(value, float) and not math.isfinite(value):
        raise ConfigurationError(f"{location}: wartość musi być skończona.")
    if isinstance(value, dict):
        for key, item in value.items():
            reject_nonfinite(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_nonfinite(item, f"{location}[{index}]")


def validate_schema(value, name):
    reject_nonfinite(value)
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        err = errors[0]
        path = ".".join(str(p) for p in err.absolute_path) or "config"
        raise ConfigurationError(f"{path}: {err.message}")


def validate_config(config):
    if config.get("schema_version") != 2:
        raise ConfigurationError("Wymagana konfiguracja v2 dla openEMS. Zaktualizuj repozytorium i plik parametrów.")
    validate_schema(config, "antenna-config.schema.json")
    freqs = config["simulation"]["frequency_hz"]
    if freqs != sorted(freqs):
        raise ConfigurationError("frequency_hz musi być uporządkowane rosnąco.")
    return config


def load_config(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return validate_config(json.load(stream))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def modified_config(config, dimensions_mm=None, frequency_mhz=None, reflector=None, scale_to_mhz=None):
    result = deepcopy(config)
    dimensions = result["antenna"]["parameters"]["dimensions_m"]
    if scale_to_mhz is not None:
        if not math.isfinite(scale_to_mhz) or scale_to_mhz <= 0:
            raise ConfigurationError("Częstotliwość skalowania musi być dodatnia i skończona.")
        if len(result["simulation"]["frequency_hz"]) != 1:
            raise ConfigurationError("Skalowanie wymaga jednej częstotliwości odniesienia.")
        old = result["simulation"]["frequency_hz"][0]
        new = scale_to_mhz * 1e6
        factor = old / new
        dimensions.update({k: v * factor for k, v in dimensions.items()})
        result["simulation"]["frequency_hz"] = [new]
        result["provenance"]["note"] += f" Explicit geometric scaling: {old:g} Hz to {new:g} Hz, factor {factor:.17g}."
        result["provenance"]["scaling_mode"] = "custom_dimensions"
    for key, value in (dimensions_mm or {}).items():
        if key not in dimensions:
            raise ConfigurationError(f"Nieznany wymiar: {key}")
        dimensions[key] = float(value) * 1e-3
    if dimensions_mm:
        result["provenance"]["scaling_mode"] = "custom_dimensions"
    if frequency_mhz is not None:
        result["simulation"]["frequency_hz"] = [float(frequency_mhz) * 1e6]
    if reflector is not None:
        result["simulation"]["reflector_model"] = "pec_plate" if reflector else "none"
    result["model_status"] = "unvalidated"
    return validate_config(result)
