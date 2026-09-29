"""Synthetic wave and adapter I/O checks; these are not solved antenna data."""

from copy import deepcopy
from contextlib import redirect_stderr
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import h5py
import numpy as np

from antenna_lab.antennas import build_model
from antenna_lab.cli import main
from antenna_lab.core.config import ConfigurationError, ROOT, load_config, write_json
from antenna_lab.solvers.feed import resolve_feed
from antenna_lab.solvers.fields import field_layout, install_fields, finish_fields, sample_mask
from antenna_lab.solvers.mesh import make_mesh
from antenna_lab.solvers.openems import port_quantities
from antenna_lab.visualization.fields import load_plane, phase_values, phase_figure
from antenna_lab.visualization.report import generate_report
from test_report import fixture


def synthetic_dump(path, lines, frequency, field):
    with h5py.File(path, "w") as out:
        mesh = out.create_group("Mesh")
        mesh.attrs["mesh_type"] = 0
        for a, values in zip("xyz", lines):
            mesh[a] = values
        group = out.create_group("FieldData/FD")
        group.attrs["frequency"] = frequency
        for i, f in enumerate(frequency):
            data = group.create_dataset(f"f{i}", data=field, compression="gzip")
            data.attrs["frequency"] = f
            data.attrs["d_order"] = "NXYZ"


class FieldTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "parameters/biquad_1420mhz.json")
        self.config["requested_outputs"]["field_planes"] = ["xy_front", "xz", "yz"]
        self.geometry = build_model(self.config)
        self.axes, self.mesh = make_mesh(self.geometry, self.config)
        self.layout = field_layout(self.geometry, self.axes, self.mesh, self.config)

    def test_both_models_use_existing_nodes_and_correct_native_dump_modes(self):
        for filename in ("biquad_1420mhz", "quados8_1420mhz_aligned_feed"):
            config = load_config(ROOT / "parameters" / f"{filename}.json")
            config["requested_outputs"]["field_planes"] = ["xy_front", "xz", "yz"]
            geometry = build_model(config)
            axes, mesh = make_mesh(geometry, config)
            before = {a: x.copy() for a, x in axes.items()}
            layout = field_layout(geometry, axes, mesh, config)
            for a in axes:
                np.testing.assert_array_equal(before[a], axes[a])
            for plane in layout:
                self.assertEqual(plane["shape_xyz"].count(1), 1)
                for n, a in enumerate("xyz"):
                    self.assertIn(plane["start_m"][n], axes[a])
                    self.assertIn(plane["stop_m"][n], axes[a])
            with tempfile.TemporaryDirectory() as directory:
                csx = Mock()
                install_fields(csx, layout, config, SimpleNamespace(path=Path(directory)))
                self.assertEqual(csx.AddDump.call_count, 6)
                self.assertEqual([call.kwargs["dump_type"] for call in csx.AddDump.call_args_list], [10, 11] * 3)
                self.assertTrue(all(call.kwargs["dump_mode"] == 1 and call.kwargs["file_type"] == 1
                                    for call in csx.AddDump.call_args_list))

    def test_phase_sign_half_period_and_impedance_normalization(self):
        f = 1.42e9
        position = np.array([0., .01, .1])
        v, current = np.array([.002 * np.exp(.7j)]), np.array([.002 / 50 * np.exp(.7j)])
        *_, scale = port_quantities(v, current, 50, 1.)
        electric = np.exp(1j * (.7 - 2 * np.pi * f / 299792458 * position)) * scale[0]
        magnetic = electric / 376.730313668
        np.testing.assert_allclose(phase_values(electric, 180), -phase_values(electric, 0), atol=1e-10)
        np.testing.assert_allclose(phase_values(electric, 90), -electric.imag, atol=1e-10)
        self.assertAlmostEqual(electric[0].imag, 0., places=10)
        np.testing.assert_allclose(electric / magnetic, 376.730313668)
        np.testing.assert_allclose(phase_values(electric, 30), abs(scale[0]) * np.cos(np.deg2rad(30) - 2*np.pi*f/299792458*position))

    def test_front_plane_outside_domain_is_rejected_before_native_solve(self):
        self.config["requested_outputs"]["field_front_offset_m"] = 10
        with self.assertRaisesRegex(ConfigurationError, "poza obszarem"):
            field_layout(self.geometry, self.axes, self.mesh, self.config)

    def test_cli_enables_planes_without_changing_geometry_and_rejects_bad_offset(self):
        path = ROOT / "parameters/biquad_1420mhz.json"
        with patch("antenna_lab.cli._native_job", return_value=0) as job, redirect_stderr(StringIO()):
            self.assertEqual(main(["run", "--config", str(path), "--fields", "--front-offset-mm", "10"]), 0)
            used = job.call_args.args[0]
            self.assertEqual(used["requested_outputs"]["field_planes"], ["xy_front", "xz", "yz"])
            self.assertEqual(used["requested_outputs"]["field_front_offset_m"], .01)
            self.assertEqual(used["antenna"], self.config["antenna"])
            job.reset_mock()
            self.assertEqual(main(["run", "--config", str(path), "--front-offset-mm", "nan"]), 1)
            job.assert_not_called()

    def test_mask_covers_metal_source_halo_but_leaves_air(self):
        feed = resolve_feed(self.geometry.port, self.axes, "mesh_anchors")
        plate_z = self.axes["z"][np.argmin(abs(self.axes["z"]))]
        mask = sample_mask([np.array([0.]), np.array([0.]), np.array([plate_z])], self.axes, self.geometry, feed)
        self.assertTrue(mask.item() & 1)
        center_z = self.axes["z"][np.argmin(abs(self.axes["z"] - self.geometry.port.positive[2]))]
        mask = sample_mask([np.array([0.]), np.array([0.]), np.array([center_z])], self.axes, self.geometry, feed)
        self.assertTrue(mask.item() & 4)
        plane = self.layout[0]
        lines = [a[(a >= plane["start_m"][n]) & (a <= plane["stop_m"][n])] for n, a in enumerate(self.axes.values())]
        mask = sample_mask(lines, self.axes, self.geometry, feed)
        self.assertEqual(np.count_nonzero(mask), 0)

    def test_native_complex_read_normalization_export_and_offline_report(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = fixture(parent / "run")
            (root / "openems").mkdir()
            config = deepcopy(self.config)
            config["requested_outputs"]["field_planes"] = ["xy_front"]
            config["requested_outputs"]["phase_degrees"] = [0, 90, 180]
            write_json(root / "parameters.resolved.json", config)
            write_json(root / "geometry.json", self.geometry.as_dict())
            np.savez(root / "mesh.npz", **self.axes)
            layout = self.layout[:1]
            write_json(root / "field_layout.json", {"planes": layout})
            p = layout[0]
            lines = [a[(a >= p["start_m"][n]) & (a <= p["stop_m"][n])] for n, a in enumerate(self.axes.values())]
            shape = tuple(map(len, lines))
            raw = np.zeros((3, *shape), dtype=complex)
            raw[0] = 2 + 3j
            frequency = np.array(config["simulation"]["frequency_hz"])
            for kind in "EH":
                synthetic_dump(root / "openems" / p["native_files"][kind], lines, frequency, raw)
            run = SimpleNamespace(path=root)
            self.assertEqual(finish_fields(self.geometry, config, run, frequency, np.array([2j])), ["xy_front"])
            data = load_plane(root / "fields/xy_front.npz", p, frequency)
            np.testing.assert_allclose(data["E_v_per_m"][0, 0], -6 + 4j)
            fig = phase_figure(data, p, self.geometry.as_dict(), [0, 90, 180])
            norms = [ax.collections[0].norm for ax in fig.axes[:6]]
            self.assertIs(norms[0], norms[2])
            self.assertIs(norms[2], norms[4])
            fig.clear()
            before = {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
            with patch("subprocess.Popen", side_effect=AssertionError("No native solve in report")):
                output = generate_report(root, parent / "fields.html", phase_step=30)
            after = {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertIn("Pobierz diagram PNG", output.read_text(encoding="utf-8"))
            self.assertIn("7 faz", output.read_text(encoding="utf-8"))
            broken = dict(p, actual_position_m=1.)
            with self.assertRaisesRegex(ValueError, "Położenie"):
                load_plane(root / "fields/xy_front.npz", broken, frequency)
            with self.assertRaisesRegex(ValueError, "Częstotliwości"):
                load_plane(root / "fields/xy_front.npz", p, frequency * 2)
            import shutil
            shutil.rmtree(root / "fields")
            path = root / "openems" / p["native_files"]["H"]
            with h5py.File(path, "a") as out:
                out["Mesh/x"][0] += .00001
            with self.assertRaisesRegex(RuntimeError, "Siatki E/H"):
                finish_fields(self.geometry, config, run, frequency, np.array([2j]))
            path.unlink()
            from antenna_lab.solvers.power import _read_surface
            with self.assertRaises(OSError):
                _read_surface(path, frequency[0])


if __name__ == "__main__":
    unittest.main()
