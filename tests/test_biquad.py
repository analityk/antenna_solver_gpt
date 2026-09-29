"""Biquad topology and compatibility; no native solve or performance tests."""

from copy import deepcopy
import math
import unittest

import numpy as np

from antenna_lab.antennas import build_model
from antenna_lab.app.editor import EditorState
from antenna_lab.core.config import ConfigurationError, ROOT, load_config, modified_config
from antenna_lab.core.geometry import check_geometry
from antenna_lab.solvers.feed import resolve_feed
from antenna_lab.solvers.mesh import make_mesh
from antenna_lab.solvers.power import monitor_layout
from antenna_lab.solvers.source_work import edge_probe_layout


class BiquadTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "parameters/biquad_1420mhz.json")

    def test_two_equal_four_side_paths_symmetry_and_open_feed_gap(self):
        geometry = build_model(self.config)
        d = self.config["antenna"]["parameters"]["dimensions_m"]
        check = check_geometry(geometry)
        self.assertEqual((check["wire_count"], check["node_count"]), (8, 8))
        self.assertEqual(check["warnings"], [])
        for length in check["branch_lengths_m"].values():
            self.assertAlmostEqual(length, 4 * d["S"], places=13)
        for wire in geometry.wires:
            self.assertAlmostEqual(wire.length_m, d["S"], places=13)
            self.assertNotEqual({wire.start, wire.stop}, {geometry.port.negative, geometry.port.positive})
        nodes = {tuple(round(v, 12) for v in p) for p in geometry.nodes}
        for x, y, z in nodes:
            self.assertIn((-x, y, z), nodes)
            self.assertIn((x, -y, z), nodes)
        self.assertAlmostEqual(math.dist(geometry.port.negative, geometry.port.positive), d["G"])

    def test_invalid_gap_clearance_and_closure_are_rejected(self):
        for key, value in (("G", .003), ("G", .05), ("H", .001), ("S", .001)):
            config = deepcopy(self.config)
            config["antenna"]["parameters"]["dimensions_m"][key] = value
            with self.assertRaises(ConfigurationError):
                build_model(config)

    def test_reflector_switch_and_uniform_scaling_preserve_radiator_topology(self):
        geometry = build_model(self.config)
        bare = build_model(modified_config(self.config, reflector=False))
        self.assertEqual(bare.wires, geometry.wires)
        self.assertEqual(bare.plates, [])
        scaled = build_model(modified_config(self.config, scale_to_mhz=710))
        for original, doubled in zip(geometry.wires, scaled.wires):
            np.testing.assert_allclose(doubled.start, np.array(original.start) * 2)
            self.assertAlmostEqual(doubled.length_m, 2 * original.length_m)

    def test_existing_mesh_port_and_diagnostics_accept_biquad(self):
        geometry = build_model(self.config)
        axes, mesh = make_mesh(geometry, self.config)
        self.assertLess(mesh["cell_count"], self.config["solver"]["max_cells"])
        feed = resolve_feed(geometry.port, axes, "mesh_anchors")
        self.assertEqual(feed["excluded_edge_count"], 0)
        self.assertGreater(feed["excitation_box_edge_count"], 0)
        layout = monitor_layout(geometry, axes, mesh, self.config["solver"]["power_diagnostics"], feed=feed)
        edges = edge_probe_layout(axes, layout["voltage_probes"])["edges"]
        self.assertEqual(len(edges), feed["excitation_box_edge_count"])
        self.assertEqual(len({tuple(edge["index"]) for edge in edges}), len(edges))

    def test_editor_uses_biquad_fields_without_rounding_untouched_dimensions(self):
        state = EditorState(self.config)
        self.assertIn("S", state.fields)
        self.assertNotIn("A", state.fields)
        saved = deepcopy(state.config)
        self.assertFalse(state.apply(state.fields, state.frequency, state.reflector))
        self.assertEqual(saved, state.config)
        self.assertTrue(state.apply(dict(state.fields, S="54"), state.frequency, state.reflector))
        self.assertAlmostEqual(state.geometry.wires[0].length_m, .054)


if __name__ == "__main__":
    unittest.main()
