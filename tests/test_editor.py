"""Editing regressions: no work per keystroke, atomic apply and distinct saves."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from antenna_lab.app.editor import EditorState
from antenna_lab.core.config import ROOT, ConfigurationError, load_config

CONFIG = ROOT / "parameters" / "quados8_1420mhz.json"


class EditorStateTests(unittest.TestCase):
    def test_noop_and_frequency_keep_full_precision_and_do_not_rebuild(self):
        state = EditorState(load_config(CONFIG))
        original = deepcopy(state.config)
        geometry = state.geometry
        with patch("antenna_lab.app.editor.build_model", side_effect=AssertionError("unneeded rebuild")):
            self.assertFalse(state.apply(state.fields, state.frequency, state.reflector))
            self.assertEqual(state.config, original)
            self.assertFalse(state.apply(state.fields, "1500", state.reflector))
        self.assertIs(state.geometry, geometry)
        self.assertEqual(state.config["antenna"], original["antenna"])
        self.assertEqual(state.config["simulation"]["frequency_hz"], [1500000000.0])

    def test_invalid_pending_text_never_partially_commits_other_fields(self):
        state = EditorState(load_config(CONFIG))
        original = deepcopy(state.config)
        geometry = state.geometry
        for invalid in ("", "-", "2e", "nan", "0"):
            fields = dict(state.fields, C="75", G=invalid)
            with self.assertRaises((ConfigurationError, ValueError)):
                state.apply(fields, state.frequency, state.reflector)
            self.assertEqual(state.config, original)
            self.assertIs(state.geometry, geometry)
        self.assertTrue(state.apply(dict(state.fields, C="75,5"), state.frequency, state.reflector))
        self.assertAlmostEqual(state.config["antenna"]["parameters"]["dimensions_m"]["C"], 0.0755)


class NativeEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.destroy()
            cls.tk = tk
        except (ImportError, RuntimeError) as exc:
            raise unittest.SkipTest(f"Tk GUI unavailable: {exc}") from exc
        except Exception as exc:
            # TclError covers missing display in headless CI.
            if type(exc).__name__ != "TclError":
                raise
            raise unittest.SkipTest(f"Tk display unavailable: {exc}") from exc

    def setUp(self):
        from antenna_lab.app.editor import GeometryEditor
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.tk.Tk()
        self.ui = GeometryEditor(self.root, load_config(CONFIG), Path(self.temp.name) / "runs")
        self.root.update()
        self.root.update_idletasks()

    def tearDown(self):
        self.root.update_idletasks()
        self.root.destroy()
        self.temp.cleanup()

    def test_typing_and_tab_do_not_draw_or_rebuild_enter_applies_once(self):
        from antenna_lab.app.editor import build_model
        original = deepcopy(self.ui.state.config)
        with patch.object(self.ui.canvas, "draw", wraps=self.ui.canvas.draw) as draw, \
             patch("antenna_lab.app.editor.build_model", wraps=build_model) as build:
            entry = self.ui.entries["C"]
            entry.focus_force()
            entry.delete(0, "end")
            for character in "75,5":
                entry.insert("end", character)
                self.root.update()
            entry.event_generate("<Tab>")
            self.root.update()
            self.assertEqual(self.ui.state.config, original)
            self.assertTrue(self.ui.dirty)
            draw.assert_not_called()
            build.assert_not_called()
            entry.focus_force()
            entry.event_generate("<Return>")
            self.root.update()
            self.assertEqual(build.call_count, 1)
            self.assertEqual(draw.call_count, 1)
            self.assertFalse(self.ui.dirty)
            self.assertAlmostEqual(self.ui.state.config["antenna"]["parameters"]["dimensions_m"]["C"], 0.0755)

    def test_save_parameters_and_export_capture_pending_edits_in_different_artifacts(self):
        from matplotlib import pyplot as plt
        from tkinter import filedialog
        parameter_file = Path(self.temp.name) / "variant.json"
        self.ui.fields["C"].set("75")
        with patch.object(filedialog, "asksaveasfilename", return_value=str(parameter_file)):
            self.ui.save_button.invoke()
        saved = load_config(parameter_file)
        self.assertAlmostEqual(saved["antenna"]["parameters"]["dimensions_m"]["C"], 0.075)
        self.assertFalse((Path(self.temp.name) / "runs").exists())
        self.ui.fields["D"].set("80")
        figures = plt.get_fignums()
        self.ui.export_button.invoke()
        self.root.update()
        self.assertEqual(plt.get_fignums(), figures)
        runs = list((Path(self.temp.name) / "runs").iterdir())
        self.assertEqual(len(runs), 1)
        run = runs[0]
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["stage"], manifest["status"]), ("geometry", "completed"))
        resolved = load_config(run / "parameters.resolved.json")
        self.assertAlmostEqual(resolved["antenna"]["parameters"]["dimensions_m"]["D"], 0.080)
        self.assertTrue((run / "geometry.json").exists())
        self.assertTrue((run / "plots" / "geometry.png").exists())
        self.assertFalse((run / "openems").exists())

    def test_loading_biquad_and_quados_rebuilds_parameter_fields(self):
        from tkinter import filedialog
        for path, model, present, absent in (
                (ROOT / "parameters/biquad_1420mhz.json", "biquad", "S", "A"),
                (CONFIG, "quados8", "A", "S")):
            with patch.object(filedialog, "askopenfilename", return_value=str(path)):
                self.ui.load_button.invoke()
            self.root.update()
            self.assertEqual(self.ui.state.geometry.model, model)
            self.assertIn(present, self.ui.fields)
            self.assertNotIn(absent, self.ui.fields)
            self.assertFalse(self.ui.dirty)
            self.assertIn(model[:3].lower(), self.root.title().lower())

    def test_biquad_invalid_feed_explains_unchanged_preview_then_recovers(self):
        from tkinter import filedialog
        from antenna_lab.app.editor import APPLY_HINT
        with patch.object(filedialog, "askopenfilename", return_value=str(ROOT / "parameters/biquad_1420mhz.json")):
            self.ui.load_button.invoke()
        original = self.ui.state.geometry
        for key, value in {"S": "60", "G": "2", "wire_diameter": "2"}.items():
            self.ui.fields[key].set(value)
        self.ui.apply_button.invoke()
        self.assertIs(self.ui.state.geometry, original)
        self.assertIn("poprzedni model", self.ui.apply_hint.cget("text"))
        self.assertIn("prześwit 0 mm", self.ui.apply_hint.cget("text"))
        self.ui.fields["G"].set("4")
        self.ui.apply_button.invoke()
        self.assertAlmostEqual(self.ui.state.geometry.wires[0].length_m, .060)
        self.assertEqual(self.ui.apply_hint.cget("text"), APPLY_HINT)


if __name__ == "__main__":
    unittest.main()
