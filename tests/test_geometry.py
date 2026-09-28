"""Physical geometry invariants independent of rendering and native openEMS."""

from copy import deepcopy
import math
import unittest

import numpy as np

from antenna_lab.antennas import build_model
from antenna_lab.core.config import ConfigurationError, ROOT, load_config, modified_config
from antenna_lab.core.geometry import Geometry, Port, Wire, check_geometry, segment_distance
from antenna_lab.solvers.mesh import make_mesh
from antenna_lab.solvers.openems import check_capabilities, port_quantities


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "parameters/quados8_1420mhz.json")

    def test_reference_lengths_topology_and_symmetry(self):
        geometry = build_model(self.config)
        result = check_geometry(geometry)
        expected = 449.6e-3 * 2450 / 1420  # independently specified source branch length
        self.assertEqual(result["wire_count"], 48)
        self.assertEqual(result["node_count"], 48)
        for length in result["branch_lengths_m"].values():
            self.assertAlmostEqual(length, expected, places=12)
        points = {tuple(round(v, 12) for v in p) for p in geometry.nodes}
        for x, y, z in points:
            self.assertIn((-x, y, z), points)
            self.assertIn((x, -y, z), points)
        self.assertEqual(geometry.port.negative[0], -geometry.port.positive[0])
        self.assertEqual(geometry.plates[0].stop[2], 0)
        self.assertLess(geometry.plates[0].start[2], 0)

    def test_dimension_edit_keeps_radiators_and_changes_branch_length(self):
        before = build_model(self.config)
        d = self.config["antenna"]["parameters"]["dimensions_m"]
        changed = modified_config(self.config, {"C": d["C"] * 1000 + 5})
        after = build_model(changed)
        for a, b in zip(before.wires, after.wires):
            if a.label != "C":
                self.assertAlmostEqual(a.length_m, b.length_m, places=12)
        lengths = check_geometry(after)["branch_lengths_m"]
        self.assertAlmostEqual(lengths["RU"], check_geometry(before)["branch_lengths_m"]["RU"] + 0.005, places=12)
        np.testing.assert_allclose(after.port.positive, before.port.positive)

    def test_frequency_change_and_explicit_scaling_are_distinct(self):
        original = build_model(self.config)
        unchanged = build_model(modified_config(self.config, frequency_mhz=2840))
        self.assertEqual(original.as_dict(), unchanged.as_dict())
        scaled = build_model(modified_config(self.config, scale_to_mhz=2840))
        for a, b in zip(original.wires, scaled.wires):
            np.testing.assert_allclose(np.array(a.start) / 2, b.start, atol=1e-14)
            self.assertAlmostEqual(a.radius_m / 2, b.radius_m)

    def test_impossible_closure_and_colliding_feed_are_rejected(self):
        for edits in ({"F": 10}, {"G": 1}, {"H": 0.5}):
            with self.assertRaises(ConfigurationError):
                build_model(modified_config(self.config, edits))

    def test_nonfinite_and_old_schema_are_rejected(self):
        with self.assertRaises(ConfigurationError):
            modified_config(self.config, {"C": math.nan})
        old = deepcopy(self.config)
        old["schema_version"] = 1
        with self.assertRaises(ConfigurationError):
            modified_config(old)

    def test_reflector_toggle_does_not_change_radiator(self):
        with_plate = build_model(self.config)
        without = build_model(modified_config(self.config, reflector=False))
        self.assertEqual(with_plate.wires, without.wires)
        self.assertFalse(without.plates)

    def test_segment_distance_parallel_skew_and_crossing(self):
        self.assertAlmostEqual(segment_distance((0,0,0),(1,0,0),(0,2,0),(1,2,0)), 2)
        self.assertAlmostEqual(segment_distance((0,0,0),(1,0,0),(.5,-1,3),(.5,1,3)), 3)
        self.assertAlmostEqual(segment_distance((0,0,0),(1,0,0),(.5,-1,0),(.5,1,0)), 0)
        self.assertAlmostEqual(segment_distance((0,0,0),(1,0,0),(2,0,0),(3,0,0)), 1)

    def test_disconnected_and_crossing_wires_fail_validation(self):
        a = Wire("a", (0,0,0), (1,0,0), .01, "a", "a")
        b = Wire("b", (.5,-1,0), (.5,1,0), .01, "b", "b")
        c = Wire("c", (1,0,0), (.5,1,0), .01, "c", "c")
        port = Port("p", a.start, a.stop, .02)
        with self.assertRaisesRegex(ConfigurationError, "odłączony"):
            check_geometry(Geometry("test", [a,b], [], port))
        with self.assertRaisesRegex(ConfigurationError, "zetknięcie"):
            check_geometry(Geometry("test", [a,b,c], [], port))

    def test_mesh_preserves_port_encloses_objects_and_has_uniform_pml(self):
        geometry = build_model(self.config)
        axes, meta = make_mesh(geometry, self.config)
        for axis in axes.values():
            self.assertTrue(np.all(np.diff(axis) > 0))
            np.testing.assert_allclose(np.diff(axis[:9]), meta["max_step_target_m"])
            np.testing.assert_allclose(np.diff(axis[-9:]), meta["max_step_target_m"])
        self.assertTrue(np.any(np.isclose(axes["z"], geometry.port.positive[2], atol=1e-12)))
        low, high = geometry.bounds
        self.assertTrue(np.all(np.array(meta["nf2ff_start_m"]) < low))
        self.assertTrue(np.all(np.array(meta["nf2ff_stop_m"]) > high))
        self.assertEqual(meta["cell_count"], math.prod(len(a)-1 for a in axes.values()))
        limited = deepcopy(self.config)
        limited["solver"]["max_cells"] = 1000
        with self.assertRaisesRegex(ConfigurationError, "limit"):
            make_mesh(geometry, limited)

    def test_unsupported_field_request_is_not_silently_ignored(self):
        config = deepcopy(self.config)
        config["requested_outputs"]["field_planes"] = ["xz"]
        with self.assertRaisesRegex(ConfigurationError, "M3"):
            check_capabilities(config)

    def test_port_normalization_known_resistive_and_reactive_loads(self):
        z_expected = np.array([50+0j, 100+50j])
        current = np.array([.001+0.002j, .003-0.001j])
        voltage = current * z_expected
        z, rho, swr, power, factor = port_quantities(voltage, current, 50, 1)
        np.testing.assert_allclose(z, z_expected)
        self.assertAlmostEqual(abs(rho[0]), 0)
        self.assertAlmostEqual(swr[0], 1)
        np.testing.assert_allclose(.5*np.real(voltage*factor*np.conj(current*factor)), 1)
        np.testing.assert_allclose(np.imag(voltage*factor), 0, atol=1e-14)
        with self.assertRaises(RuntimeError):
            port_quantities([1], [-1], 50, 1)


if __name__ == "__main__":
    unittest.main()
