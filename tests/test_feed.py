"""Regression: rounded mesh bounds must not remove excitation edge layers."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from antenna_lab.antennas import build_model
from antenna_lab.core.config import ROOT, ConfigurationError, load_config, validate_config
from antenna_lab.solvers.feed import resolve_feed
from antenna_lab.solvers.mesh import make_mesh
from antenna_lab.solvers.openems import prepare
from antenna_lab.solvers.power import monitor_layout
from antenna_lab.solvers.source_work import edge_probe_layout


class FeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = load_config(ROOT / "parameters/quados8_1420mhz_source_work.json")
        cls.new = load_config(ROOT / "parameters/quados8_1420mhz_aligned_feed.json")
        cls.geometry = build_model(cls.new)
        cls.axes, cls.mesh = make_mesh(cls.geometry, cls.new)

    def test_legacy_reproduces_two_unexcited_y_layers(self):
        feed = resolve_feed(self.geometry.port, self.axes)
        self.assertEqual(feed["edge_shape"], [18, 5, 5])
        self.assertEqual(feed["resistor_edge_count"], 450)
        self.assertEqual(feed["excitation_box_edge_count"], 270)
        self.assertEqual(feed["excluded_axis_indices"], {"x": [], "y": [569, 573], "z": []})
        self.assertEqual(feed["start_m"], feed["nominal_start_m"])
        self.assertEqual(feed["stop_m"], feed["nominal_stop_m"])
        self.assertEqual(feed["max_coordinate_adjustment_m"], 0)

    def test_alignment_covers_all_edges_without_changing_model_or_mesh(self):
        stripped = deepcopy(self.new)
        del stripped["solver"]["port_mesh_alignment"]
        for key in ("antenna", "simulation", "solver", "requested_outputs"):
            self.assertEqual(self.old[key], stripped[key])
        old_geometry = build_model(self.old)
        old_axes, old_mesh = make_mesh(old_geometry, self.old)
        self.assertEqual(old_geometry.as_dict(), self.geometry.as_dict())
        self.assertEqual(old_mesh, self.mesh)
        feed = resolve_feed(self.geometry.port, self.axes, "mesh_anchors")
        self.assertEqual(feed["resistor_edge_count"], 450)
        self.assertEqual(feed["excitation_box_edge_count"], 450)
        self.assertEqual(feed["excluded_edge_count"], 0)
        self.assertLess(feed["max_coordinate_adjustment_m"], .5e-12)
        for n, a in enumerate("xyz"):
            np.testing.assert_array_equal(self.axes[a], old_axes[a])
            self.assertEqual(feed["start_m"][n], old_axes[a][feed["mesh_start_index"][n]])
            self.assertEqual(feed["stop_m"][n], old_axes[a][feed["mesh_stop_index"][n]])
        settings = self.new["solver"]["power_diagnostics"]
        before = monitor_layout(self.geometry, old_axes, old_mesh, settings)
        after = monitor_layout(self.geometry, self.axes, self.mesh, settings, feed)
        # The original 450 local measurements keep exactly the same grid edges.
        self.assertEqual(edge_probe_layout(old_axes, before["voltage_probes"]),
                         edge_probe_layout(self.axes, after["voltage_probes"]))
        self.assertEqual(before["boxes"], after["boxes"])

    def test_rejects_missing_anchor_instead_of_moving_physical_feed(self):
        axes = {a: v.copy() for a, v in self.axes.items()}
        axes["y"][569] -= 1e-8  # Far smaller than a cell, but not rounding noise.
        with self.assertRaisesRegex(ConfigurationError, "nie są kotwicami"):
            resolve_feed(self.geometry.port, axes, "mesh_anchors")
        with self.assertRaisesRegex(ConfigurationError, "Nieznany tryb"):
            resolve_feed(self.geometry.port, self.axes, "silent_snap")
        bad = deepcopy(self.new)
        bad["solver"]["port_mesh_alignment"] = "silent_snap"
        with self.assertRaises(ConfigurationError):
            validate_config(bad)

    def test_adapter_passes_audited_bounds_to_native_port(self):
        # A fake API only verifies the adapter boundary, not native EM physics.
        engine, csx = Mock(), Mock()
        modules = (SimpleNamespace(openEMS=Mock(return_value=engine), __version__="test"),
                   SimpleNamespace(ContinuousStructure=Mock(return_value=csx)))
        engine.Write2XML.side_effect = lambda path: Path(path).write_text("<test/>", encoding="utf-8")
        config = deepcopy(self.new)
        del config["solver"]["power_diagnostics"]
        with tempfile.TemporaryDirectory() as folder:
            run = SimpleNamespace(path=Path(folder), manifest={"warnings": []}, save=Mock())
            with patch("antenna_lab.solvers.openems.native_modules", return_value=modules), \
                    patch("antenna_lab.solvers.openems.importlib.metadata.version", return_value="test"), \
                    redirect_stdout(io.StringIO()):
                prepare(self.geometry, config, run)
            audit = json.loads((run.path / "feed_grid_coverage.json").read_text())
            args = engine.AddLumpedPort.call_args.args
            self.assertEqual(args[1], 200.0)
            self.assertEqual(args[2:4], (audit["start_m"], audit["stop_m"]))
            self.assertEqual(audit["excitation_box_edge_count"], 450)
            self.assertEqual(run.manifest["solver"]["feed"], audit)
            self.assertFalse(engine.Run.called)


if __name__ == "__main__":
    unittest.main()
