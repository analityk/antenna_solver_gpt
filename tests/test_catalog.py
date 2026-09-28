"""Geometry selection must not confuse labels, edited variants or partial runs."""

from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from antenna_lab.antennas import build_model
from antenna_lab.cli import main
from antenna_lab.core.catalog import find_geometry_run, geometry_key
from antenna_lab.core.config import ConfigurationError, ROOT, load_config, write_json, validate_schema
from antenna_lab.core.geometry import check_geometry
from antenna_lab.core.runs import RunRecord, sha256


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runs = self.root / "runs"
        self.config = load_config(ROOT / "parameters/quados8_1420mhz_aligned_feed.json")

    def saved(self, name, config=None, day=28, status="completed", stage="simulation"):
        folder = self.runs / name
        write_json(folder / "parameters.resolved.json", config or self.config)
        write_json(folder / "manifest.json", {"created_at": f"2026-09-{day:02}T12:00:00Z",
                                             "run_id": name, "status": status, "stage": stage})
        write_json(folder / "summary.json", {"frequency_hz": [1.42e9], "resistance_ohm": [50],
                                             "reactance_ohm": [0], "reference_impedance_ohm": 50,
                                             "accepted_power_w": 1, "validation_status": "unverified"})
        return folder

    def test_legacy_selection_uses_dimensions_not_shared_id_or_latest_folder(self):
        target = self.saved("20260928_old_opaque")
        other = deepcopy(self.config)
        other["antenna"]["parameters"]["dimensions_m"]["H"] = .04
        self.saved("20260929_new_opaque", other, day=29)
        self.saved("20260930_failed", day=30, status="failed")
        self.saved("20260930_geometry", day=30, stage="geometry")
        before = {str(p): sha256(p) for p in self.runs.rglob("*") if p.is_file()}
        found, count, exact = find_geometry_run(self.config, self.runs)
        self.assertEqual(found, target)
        self.assertEqual(count, 1)
        self.assertTrue(exact)
        self.assertEqual(before, {str(p): sha256(p) for p in self.runs.rglob("*") if p.is_file()})

    def test_schema_locations_provenance_and_labels_do_not_change_geometry(self):
        copied = deepcopy(self.config)
        copied["$schema"] = "schemas/antenna-config.schema.json"
        copied["antenna"]["parameter_schema"] = "schemas/quados8-parameters.schema.json"
        copied["id"] = "renamed_variant"
        copied["provenance"]["note"] = "different note"
        copied["antenna"]["parameters"]["dimensions_m"]["H"] += 1e-15
        self.assertEqual(geometry_key(copied), geometry_key(self.config))
        copied["simulation"]["reflector_model"] = "none"
        self.assertNotEqual(geometry_key(copied), geometry_key(self.config))

    def test_exact_solver_settings_preferred_and_fallback_is_explicit(self):
        old = self.saved("old")
        changed = deepcopy(self.config)
        changed["solver"]["cells_per_wire_diameter"] = 2
        new = self.saved("new", changed, day=29)
        self.assertEqual(find_geometry_run(self.config, self.runs), (old, 2, True))
        (old / "manifest.json").unlink()
        self.assertEqual(find_geometry_run(self.config, self.runs), (new, 1, False))

    def test_different_frequency_or_edited_geometry_is_not_silently_selected(self):
        self.saved("old")
        for section, key, value in (("frequency", "frequency_hz", [1.5e9]), ("dimensions", "C", .075)):
            requested = deepcopy(self.config)
            if section == "frequency":
                requested["simulation"][key] = value
            else:
                requested["antenna"]["parameters"]["dimensions_m"][key] = value
            with self.assertRaisesRegex(ConfigurationError, "Brak ukończonej"):
                find_geometry_run(requested, self.runs)

    def test_named_records_remain_unique_and_valid(self):
        geometry = build_model(self.config)
        validation = check_geometry(geometry)
        a = RunRecord(self.runs, "simulation", self.config, geometry, validation, variant_name="quados8_variant_sz4")
        b = RunRecord(self.runs, "simulation", self.config, geometry, validation, variant_name="quados8_variant_sz4")
        self.assertTrue(a.path.name.startswith("quados8_variant_sz4__"))
        self.assertNotEqual(a.path, b.path)
        self.assertEqual(a.manifest["variant_name"], "quados8_variant_sz4")
        self.assertEqual(a.manifest["geometry_sha256"], geometry_key(self.config))
        validate_schema(a.manifest, "run-manifest.schema.json")
        a.finish("failed", "synthetic test, no solver")
        b.finish("failed", "synthetic test, no solver")

    def test_cli_accepts_variant_basename_from_parameters_and_labels_old_report(self):
        self.saved("old_opaque")
        write_json(self.root / "parameters" / "quados8_variant_sz4.json", self.config)
        output = self.root / "report.html"
        stream = StringIO()
        with patch("antenna_lab.cli.ROOT", self.root), redirect_stdout(stream):
            code = main(["report", "quados8_variant_sz4.json", "--runs-dir", str(self.runs), "--output", str(output)])
        self.assertEqual(code, 0)
        self.assertIn("quados8_variant_sz4", stream.getvalue())
        html = output.read_text(encoding="utf-8")
        self.assertIn("Wariant: <strong>quados8_variant_sz4</strong>", html)
        self.assertIn("old_opaque", html)


if __name__ == "__main__":
    unittest.main()
