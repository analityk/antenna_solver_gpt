from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.config import ResolvedPcbConfig, load_pcb_config, validate_pcb_config


def config():
    return {
        "schema_version": 1, "model": "pcb",
        "files": {"copper_top": "gerbers/top.gbr", "board_outline": "gerbers/edge.gbr"},
        "copper": {"thickness_um": 35, "conductivity_s_m": 58000000, "model": "pec"},
        "substrate": {"thickness_mm": 1.6, "epsilon_r": 4.3, "loss_tangent": .018},
        "port": {"negative_mm": [9., 10.], "positive_mm": [11., 10.], "width_mm": 1.},
    }


class PcbConfigTests(unittest.TestCase):
    def test_valid_load_all_fields_units_immutable_deterministic_bom(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "pcb.json"
            path.write_text(json.dumps(config()), encoding="utf-8-sig")
            result = load_pcb_config(path)
            self.assertIsInstance(result, ResolvedPcbConfig)
            self.assertEqual(result, load_pcb_config(path))
            self.assertEqual(result.schema_version, 1)
            self.assertEqual(result.model, "pcb")
            self.assertEqual(result.copper_top_path, root / "gerbers/top.gbr")
            self.assertEqual(result.board_outline_path, root / "gerbers/edge.gbr")
            self.assertAlmostEqual(result.copper_thickness_m, 35e-6, delta=1e-20)
            self.assertEqual(result.copper_conductivity_s_m, 58000000)
            self.assertEqual(result.copper_model, "pec")
            self.assertAlmostEqual(result.substrate_thickness_m, 1.6e-3, delta=1e-18)
            self.assertEqual(result.substrate_epsilon_r, 4.3)
            self.assertEqual(result.substrate_loss_tangent, .018)
            for actual, expected in zip(result.port_negative_xy_m + result.port_positive_xy_m,
                                        (.009, .010, .011, .010)):
                self.assertAlmostEqual(actual, expected, delta=1e-17)
            self.assertIsInstance(result.port_negative_xy_m, tuple)
            self.assertIsInstance(result.port_positive_xy_m, tuple)
            self.assertAlmostEqual(result.port_width_m, .001, delta=1e-18)
            with self.assertRaises(FrozenInstanceError):
                result.model = "other"

    def test_validation_returns_same_object_without_mutation(self):
        value = config()
        before = deepcopy(value)
        self.assertIs(validate_pcb_config(value), value)
        self.assertEqual(before, value)

    def test_relative_paths_missing_files_and_cwd_independence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "project"
            project.mkdir()
            path = project / "pcb.json"
            value = config()
            value["files"] = {"copper_top": "missing_top.gbr", "board_outline": "missing_edge.gbr"}
            path.write_text(json.dumps(value), encoding="utf-8")
            first = load_pcb_config(path)
            old_cwd = Path.cwd()
            try:
                os.chdir(root)
                second = load_pcb_config(Path("project/pcb.json"))
            finally:
                os.chdir(old_cwd)
            self.assertEqual(first, second)
            self.assertEqual(first.copper_top_path, project / "missing_top.gbr")
            self.assertEqual(first.board_outline_path, project / "missing_edge.gbr")

    def test_no_gerber_open_or_existence_requirement(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "pcb.json"
            path.write_text(json.dumps(config()), encoding="utf-8")
            original_open = Path.open

            def guarded_open(target, *args, **kwargs):
                self.assertNotEqual(target.suffix, ".gbr")
                return original_open(target, *args, **kwargs)

            with patch.object(Path, "open", guarded_open), patch.object(
                    Path, "exists", side_effect=AssertionError("No existence checks")):
                load_pcb_config(path)

    def test_versions_and_models(self):
        for key, values in (("schema_version", (0, 2, "1", True)), ("model", ("antenna", "PCB", ""))):
            for value in values:
                data = config()
                data[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ConfigurationError):
                    validate_pcb_config(data)
        for model in ("conducting_sheet", "copper"):
            data = config()
            data["copper"]["model"] = model
            with self.assertRaises(ConfigurationError):
                validate_pcb_config(data)

    def test_invalid_physical_values(self):
        fields = (("copper", "thickness_um", (0, -1)),
                  ("copper", "conductivity_s_m", (0, -1)),
                  ("substrate", "thickness_mm", (0, -1)),
                  ("substrate", "epsilon_r", (.99,)),
                  ("substrate", "loss_tangent", (-.01,)),
                  ("port", "width_mm", (0, -1)))
        for section, key, values in fields:
            for value in values:
                data = config()
                data[section][key] = value
                with self.subTest(section=section, key=key, value=value), self.assertRaises(ConfigurationError):
                    validate_pcb_config(data)

    def test_port_arrays_and_coincident_endpoints(self):
        for key in ("negative_mm", "positive_mm"):
            for value in ([], [1], [1, 2, 3], ["1", 2], [True, 2], "1,2"):
                data = config()
                data["port"][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ConfigurationError):
                    validate_pcb_config(data)
        data = config()
        data["port"]["positive_mm"] = [9, 10]
        with self.assertRaisesRegex(ConfigurationError, "końce"):
            validate_pcb_config(data)

    def test_nonfinite_all_physical_fields(self):
        for section in ("copper", "substrate", "port"):
            for key, current in config()[section].items():
                if isinstance(current, str):
                    continue
                for value in (float("nan"), float("inf"), -float("inf")):
                    data = config()
                    data[section][key] = [value, 10.] if isinstance(current, list) else value
                    with self.subTest(section=section, key=key, value=value), self.assertRaises(ConfigurationError):
                        validate_pcb_config(data)

    def test_missing_required_fields(self):
        for section in config():
            data = config()
            del data[section]
            with self.subTest(section=section), self.assertRaises(ConfigurationError):
                validate_pcb_config(data)
        for section in ("files", "copper", "substrate", "port"):
            for key in config()[section]:
                data = config()
                del data[section][key]
                with self.subTest(section=section, key=key), self.assertRaises(ConfigurationError):
                    validate_pcb_config(data)

    def test_unknown_fields(self):
        for section in (None, "files", "copper", "substrate", "port"):
            data = config()
            (data if section is None else data[section])["unexpected"] = 1
            with self.subTest(section=section), self.assertRaises(ConfigurationError):
                validate_pcb_config(data)

    def test_empty_or_whitespace_paths(self):
        for key in ("copper_top", "board_outline"):
            for value in ("", " \t\n"):
                data = config()
                data["files"][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ConfigurationError):
                    validate_pcb_config(data)


if __name__ == "__main__":
    unittest.main()
