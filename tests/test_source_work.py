"""Check source-work signs, spatial pairing and native probe index contracts."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import numpy as np

from antenna_lab.antennas import build_model
from antenna_lab.core.config import ROOT, load_config
from antenna_lab.solvers.mesh import make_mesh
from antenna_lab.solvers.power import monitor_layout
from antenna_lab.solvers.source_work import (check_aggregation, check_probe_indices,
                                             edge_probe_layout, edge_work)


class SourceWorkTests(unittest.TestCase):
    def test_source_control_preserves_model_and_covers_each_edge_once(self):
        base = load_config(ROOT / "parameters/quados8_1420mhz_power_audit.json")
        control = load_config(ROOT / "parameters/quados8_1420mhz_source_work.json")
        stripped = deepcopy(control)
        del stripped["solver"]["power_diagnostics"]["source_edge_work"]
        for key in ("antenna", "simulation", "solver", "requested_outputs"):
            self.assertEqual(base[key], stripped[key])
        geometry = build_model(control)
        axes, meta = make_mesh(geometry, control)
        base_axes, base_meta = make_mesh(build_model(base), base)
        self.assertEqual(geometry.as_dict(), build_model(base).as_dict())
        self.assertEqual(meta, base_meta)
        layout = monitor_layout(geometry, axes, meta, control["solver"]["power_diagnostics"])
        work = edge_probe_layout(axes, layout["voltage_probes"])
        self.assertEqual(work["shape"], [18, 5, 5])
        self.assertEqual(len(work["edges"]), 450)
        self.assertEqual(len({tuple(e["index"]) for e in work["edges"]}), 450)
        for axis in "xyz":
            np.testing.assert_array_equal(axes[axis], base_axes[axis])
        # The requested H contours lie strictly inside the two dual boundaries,
        # on opposite sides of one primary E edge: native outward snapping is
        # unambiguous even after coordinate serialization/rounding.
        for edge in work["edges"]:
            for n, axis in ((1, "y"), (2, "z")):
                j = edge["index"][n]
                a = axes[axis]
                lower, upper = (a[j - 1] + a[j]) / 2, (a[j] + a[j + 1]) / 2
                self.assertLess(lower, edge["current"]["start_m"][n])
                self.assertLess(edge["current"]["start_m"][n], a[j])
                self.assertLess(a[j], edge["current"]["stop_m"][n])
                self.assertLess(edge["current"]["stop_m"][n], upper)

    def test_work_matches_analytic_poynting_flux_on_nonuniform_grid(self):
        # E=(-1,0,0), H=(0,0,y): div(0.5 Re(E x H*))=0.5.
        # Paired U=dx and I=dual area yield half the physical box volume.
        # An imaginary displacement-current term contributes no active work.
        dx = np.array([.1, .15, .25])
        dy = np.array([.2, .3])
        dz = np.array([.4, .1])
        u = np.broadcast_to(dx[:, None, None], (3, 2, 2)).ravel()[None, :].astype(complex)
        i = np.broadcast_to(dy[None, :, None] * dz[None, None, :], (3, 2, 2)).ravel()[None, :]
        i = i * (1 + 3j)
        expected = .5 * dx.sum() * dy.sum() * dz.sum()
        self.assertAlmostEqual(edge_work(u, i, [1], 1).sum(), expected)
        self.assertAlmostEqual(edge_work(u, -i, [1], 1).sum(), -expected)
        self.assertAlmostEqual(edge_work(u, i, [2], 3).sum(), 1.5 * expected)

    def test_local_products_cannot_be_replaced_by_average_voltage(self):
        # Two parallel paths: the first returns energy. Net work is 9 W;
        # an average voltage times total current would give 4.5 W.
        u = np.array([[2, 4]], complex)
        i = np.array([[-1, 2]], complex) * 3
        work = edge_work(u, i, [1], 1)
        np.testing.assert_array_equal(work, [[-3, 12]])
        self.assertEqual(float(work.sum()), 9)
        self.assertNotEqual(float(work.sum()), .5 * np.real(u.mean() * i.sum().conjugate()))

    def test_aggregation_detects_missing_or_wrongly_signed_probe(self):
        shape = (2, 2, 1)
        u = np.array([[1 + 2j, 3 + 4j, 5 + 6j, 7 + 8j]])
        i = np.array([[.2 + .1j, .3 + .2j, .4 + .3j, .5 + .4j]])
        # Independently specified line totals and contour sums.
        expected_u = np.array([[6 + 8j, 10 + 12j]])
        expected_i = np.array([[.5 + .3j, .9 + .7j]])
        check_aggregation(u, i, shape, expected_u, expected_i)
        broken = i.copy()
        broken[0, 2] *= -1
        with self.assertRaisesRegex(RuntimeError, "nie odtwarza"):
            check_aggregation(u, broken, shape, expected_u, expected_i)

    def test_native_index_headers_reject_shifted_contour(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "probe"
            path.write_text("% openEMS\n% start-coordinates: (0,0,0) m -> [73,568,48]\n"
                            "% stop-coordinates: (0,0,0) m -> [73,569,49]\n% t/s current\n",
                            encoding="utf-8")
            probe = {"start_index": [73, 568, 48], "stop_index": [73, 569, 49]}
            check_probe_indices(path, probe)
            probe["stop_index"][1] += 1
            with self.assertRaisesRegex(RuntimeError, "nieoczekiwanych"):
                check_probe_indices(path, probe)


if __name__ == "__main__":
    unittest.main()
