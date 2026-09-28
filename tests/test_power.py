"""Analytical integration, timestamp and experiment-isolation checks, not benchmarks."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import h5py
import numpy as np

from antenna_lab.antennas import build_model
from antenna_lab.core.config import ROOT, ConfigurationError, load_config
from antenna_lab.solvers.mesh import make_mesh
from antenna_lab.solvers.power import integrate_box, monitor_layout, probe_spectrum


class PowerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make_analytic_box(self):
        # E=(0,1,0), H=(0,0,2x) gives S=(x,0,0), div(S)=1.
        # Divergence theorem: net signed flux is the box's volume, exactly 12.
        base = [np.array([-1, -.7, 0, .8, 2]), np.array([-.5, -.1, .5]), np.array([-2, -1, .2, 2])]
        for face in range(6):
            axis, side = divmod(face, 2)
            mesh = [a.copy() for a in base]
            mesh[axis] = mesh[axis][[0 if side == 0 else -1]]
            xyz = np.meshgrid(*mesh, indexing="ij")
            for kind in "EH":
                field = np.zeros((3, *(len(a) for a in mesh)), complex)
                if kind == "E":
                    field[1] = 1
                else:
                    field[2] = 2 * xyz[0]
                with h5py.File(self.path / f"test_{kind}_{face}.h5", "w") as h5:
                    group = h5.create_group("Mesh")
                    group.attrs["mesh_type"] = 0
                    for name, values in zip("xyz", mesh):
                        group[name] = values
                    fd = h5.create_group("FieldData/FD")
                    fd.attrs["frequency"] = [1e9]
                    dataset = fd.create_dataset("f0", data=field)
                    dataset.attrs["d_order"] = "NXYZ"
                    dataset.attrs["frequency"] = 1e9
        return [-1, -.5, -2], [2, .5, 2]

    def test_flux_matches_divergence_theorem_on_nonuniform_mesh(self):
        start, stop = self.make_analytic_box()
        result = integrate_box(self.path, "test", 1e9, start, stop, 1)
        self.assertAlmostEqual(result["active_flux_w"], 12, places=12)
        self.assertAlmostEqual(result["faces"][0]["active_flux_w"], 4, places=12)
        self.assertAlmostEqual(result["faces"][1]["active_flux_w"], 8, places=12)
        normalized = integrate_box(self.path, "test", 1e9, start, stop, 3, target_power=2)
        self.assertAlmostEqual(normalized["active_flux_w"], 8, places=12)

    def test_missing_wall_and_misaligned_e_h_are_errors(self):
        start, stop = self.make_analytic_box()
        with h5py.File(self.path / "test_H_0.h5", "r+") as h5:
            h5["Mesh/z"][1] += .01
        with self.assertRaisesRegex(RuntimeError, "Siatki E/H"):
            integrate_box(self.path, "test", 1e9, start, stop, 1)
        (self.path / "test_H_3.h5").unlink()
        with self.assertRaisesRegex(RuntimeError, "Niekompletna"):
            integrate_box(self.path, "test", 1e9, start, stop, 1)

    def test_dft_respects_separate_staggered_timestamps(self):
        frequency = 1e9
        step = 1 / (64 * frequency)
        for name, shift, amplitude in (("u", 0, 50), ("i", step / 2, 1)):
            t = np.arange(256) * step + shift
            np.savetxt(self.path / name, np.c_[t, amplitude * np.cos(2 * np.pi * frequency * t + .31)])
        voltage = probe_spectrum(self.path / "u", [frequency])[0]
        current = probe_spectrum(self.path / "i", [frequency])[0]
        self.assertAlmostEqual((voltage / current).real, 50, places=10)
        self.assertAlmostEqual((voltage / current).imag, 0, places=10)

    def test_audit_configuration_changes_only_passive_measurements(self):
        base = load_config(ROOT / "parameters/quados8_1420mhz.json")
        audit = load_config(ROOT / "parameters/quados8_1420mhz_power_audit.json")
        settings = audit["solver"]["power_diagnostics"]
        a = deepcopy(audit)
        del a["solver"]["power_diagnostics"]
        for key in ("antenna", "simulation", "solver", "requested_outputs"):
            self.assertEqual(base[key], a[key])
        geometry = build_model(audit)
        self.assertEqual(geometry.as_dict(), build_model(base).as_dict())
        mesh, meta = make_mesh(geometry, audit)
        base_mesh, base_meta = make_mesh(build_model(base), base)
        self.assertEqual(meta, base_meta)
        for axis in "xyz":
            np.testing.assert_array_equal(mesh[axis], base_mesh[axis])
        original = {a: m.copy() for a, m in mesh.items()}
        layout = monitor_layout(geometry, mesh, meta, settings)
        for axis in "xyz":
            np.testing.assert_array_equal(mesh[axis], original[axis])
        for box in layout["boxes"]:
            for axis, lower, upper in zip("xyz", box["start_m"], box["stop_m"]):
                self.assertIn(lower, mesh[axis])
                self.assertIn(upper, mesh[axis])
                self.assertLess(lower, upper)
        self.assertGreater(len(layout["voltage_probes"]), 1)
        self.assertGreater(len(layout["current_probes"]), 1)
        bad = deepcopy(settings)
        bad["port_spectrum_hz"]["stop"] = 1.9e9
        with self.assertRaisesRegex(ConfigurationError, "poza deklarowane pasmo"):
            monitor_layout(geometry, mesh, meta, bad)


if __name__ == "__main__":
    unittest.main()
