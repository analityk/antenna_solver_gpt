"""Immutable per-run folders, source snapshots and honest completion states."""

from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
import zipfile

from antenna_lab import __version__
from .config import ROOT, write_json


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_revision():
    try:
        def git(*args):
            return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()
        return {"version": __version__, "commit_sha": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"version": __version__, "commit_sha": None, "dirty": None}


class RunRecord:
    @classmethod
    def open(cls, path):
        record = object.__new__(cls)
        record.path = Path(path).resolve()
        record.manifest = json.loads((record.path / "manifest.json").read_text(encoding="utf-8"))
        return record

    def __init__(self, root, stage, config, geometry, validation):
        stamp = datetime.now(timezone.utc)
        run_id = stamp.strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:10]
        self.path = Path(root).resolve() / run_id
        self.path.mkdir(parents=True, exist_ok=False)
        resolved = deepcopy(config)
        resolved["$schema"] = "schemas/antenna-config.schema.json"
        resolved["antenna"]["parameter_schema"] = "schemas/" + Path(config["antenna"]["parameter_schema"]).name
        for schema in (ROOT / "schemas").glob("*.json"):
            write_json(self.path / "schemas" / schema.name, json.loads(schema.read_text(encoding="utf-8")))
        write_json(self.path / "parameters.resolved.json", resolved)
        write_json(self.path / "geometry.json", geometry.as_dict())
        write_json(self.path / "validation.json", validation)
        # Allowlisted project sources only; never copy local environments or account settings.
        with zipfile.ZipFile(self.path / "source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for folder, pattern in (("src", "*.py"), ("schemas", "*.json"), ("parameters/reference", "*.json")):
                for item in sorted((ROOT / folder).rglob(pattern)):
                    archive.write(item, item.relative_to(ROOT).as_posix())
            archive.write(ROOT / "pyproject.toml", "pyproject.toml")
        self.manifest = {"schema_version": 2, "run_id": run_id, "stage": stage, "status": "running",
                         "created_at": stamp.isoformat(), "code": code_revision(),
                         "configuration_sha256": sha256(self.path / "parameters.resolved.json"),
                         "frequency_hz": config["simulation"]["frequency_hz"], "solver": None,
                         "coordinates": {"cartesian": "x horizontal, y long antenna axis, z forward",
                                         "spherical": "theta from +z, phi from +x towards +y, angles in degrees",
                                         "polarization_basis": "E_theta along increasing theta, E_phi along increasing phi"},
                         "normalization": {"accepted_power_w": config["simulation"]["accepted_power_w"],
                                           "amplitude_convention": "peak", "phase_reference": "positive port voltage",
                                           "phasor_convention": config["simulation"]["phasor_convention"], "applied": False},
                         "validation_status": "unverified", "artifacts": [], "error": None,
                         "warnings": list(validation["warnings"])}
        self.save()

    def save(self):
        write_json(self.path / "manifest.json", self.manifest)

    def finish(self, status, error=None):
        self.manifest["status"] = status
        self.manifest["error"] = str(error) if error is not None else None
        self.manifest["artifacts"] = [
            {"path": p.relative_to(self.path).as_posix(), "sha256": sha256(p)}
            for p in sorted(self.path.rglob("*")) if p.is_file() and p.name != "manifest.json"
        ]
        self.save()
