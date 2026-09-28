"""Name runs and locate saved geometries without importing a solver."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .config import ConfigurationError


def variant_slug(name):
    ascii_name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_name).strip("_")[:40] or "antenna"


def geometry_key(config):
    """Ignore labels/provenance/schema paths; SI lengths rounded to 1 pm."""
    def canonical(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return round(float(value), 12)
        if isinstance(value, dict):
            return {key: canonical(item) for key, item in value.items()}
        if isinstance(value, list):
            return [canonical(item) for item in value]
        return value

    antenna, simulation = config["antenna"], config["simulation"]
    identity = {"model": antenna["model"], "parameters": antenna["parameters"],
                "physical_model": {key: simulation[key] for key in
                                   ("medium", "conductor_model", "reflector_model", "feed_model")}}
    encoded = json.dumps(canonical(identity), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def completed_simulations(runs_path):
    results = []
    for file in Path(runs_path).glob("*/manifest.json"):
        try:
            manifest = json.loads(file.read_text(encoding="utf-8-sig"))
            if manifest.get("stage") != "simulation" or manifest.get("status") != "completed":
                continue
            if not (file.parent / "summary.json").is_file():
                continue
            created = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            results.append((created.timestamp(), file.parent.name, file.parent))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(results, reverse=True)


def find_geometry_run(config, runs_path):
    """Resolve old and new folders by snapshot contents, never by filename alone.

    Prefer matching simulation/solver settings, then the newest completion
    of the same geometry and requested frequencies, with an explicit warning
    supplied by the caller when settings differ.
    """
    target = geometry_key(config)
    matching, exact = [], []
    for _, _, path in completed_simulations(runs_path):
        try:
            saved = json.loads((path / "parameters.resolved.json").read_text(encoding="utf-8-sig"))
            if (geometry_key(saved) != target
                    or saved["simulation"]["frequency_hz"] != config["simulation"]["frequency_hz"]):
                continue
            matching.append(path)
            if saved["simulation"] == config["simulation"] and saved.get("solver") == config.get("solver"):
                exact.append(path)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not matching:
        raise ConfigurationError("Brak ukończonej symulacji tej geometrii i częstotliwości. "
                                 "Sprawdź plik wariantu: po zmianie wymiarów nie pasuje już do wcześniejszych wyników.")
    return (exact or matching)[0], len(matching), bool(exact)
