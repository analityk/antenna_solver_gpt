import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from antenna_lab.antennas import build_model
from antenna_lab.core.config import ROOT, load_config, validate_schema
from antenna_lab.core.geometry import check_geometry
from antenna_lab.core.runs import RunRecord, sha256


class RecordTests(unittest.TestCase):
    def test_geometry_records_are_unique_replayable_and_not_em_results(self):
        config = load_config(ROOT / "parameters/quados8_1420mhz.json")
        geometry = build_model(config)
        with tempfile.TemporaryDirectory() as folder:
            a = RunRecord(folder, "geometry", config, geometry, check_geometry(geometry))
            b = RunRecord(folder, "geometry", config, geometry, check_geometry(geometry))
            self.assertNotEqual(a.path, b.path)
            a.finish("completed")
            manifest = json.loads((a.path / "manifest.json").read_text(encoding="utf-8"))
            validate_schema(manifest, "run-manifest.schema.json")
            self.assertEqual(manifest["validation_status"], "unverified")
            self.assertIsNone(manifest["solver"])
            self.assertFalse(manifest["normalization"]["applied"])
            for item in manifest["artifacts"]:
                self.assertEqual(item["sha256"], sha256(a.path / item["path"]))
            resolved = load_config(a.path / "parameters.resolved.json")
            self.assertTrue((a.path / resolved["$schema"]).is_file())
            self.assertEqual(build_model(resolved).as_dict(), geometry.as_dict())
            with zipfile.ZipFile(a.path / "source.zip") as source:
                self.assertIn("src/antenna_lab/antennas/quados8/model.py", source.namelist())
                self.assertFalse(any(".venv" in name for name in source.namelist()))
            b.finish("failed", "test failure")
            self.assertEqual(RunRecord.open(b.path).manifest["error"], "test failure")


if __name__ == "__main__":
    unittest.main()
