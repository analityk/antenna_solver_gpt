"""Reports must preserve results, expose missing evidence and stay offline."""

from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from antenna_lab.cli import main, _write_run_report
from antenna_lab.visualization.report import generate_report, power_comparisons
from antenna_lab.visualization.report_data import latest_run, load_report_data


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def fixture(root, *, date="2026-09-28T00:00:00+00:00", status="completed", stage="simulation"):
    """Synthetic I/O fixture, not a solved antenna or validation reference."""
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "manifest.json", {"run_id": root.name, "created_at": date, "stage": stage,
                                       "status": status, "warnings": []})
    write_json(root / "summary.json", {"frequency_hz": [1.42e9], "resistance_ohm": [50],
                                       "reactance_ohm": [0], "reference_impedance_ohm": 50,
                                       "accepted_power_w": 1, "validation_status": "unverified"})
    return root


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = fixture(self.root / "run")

    def test_report_is_offline_escaped_and_does_not_touch_sources(self):
        summary = json.loads((self.run / "summary.json").read_text())
        summary["note"] = '</script><script>alert("injected")</script>'
        write_json(self.run / "summary.json", summary)
        before = {p.name: sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        output = self.root / "portable.html"
        with patch("subprocess.Popen", side_effect=AssertionError("A report must not launch a solver")):
            generate_report(self.run, output)
        after = {p.name: sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        self.assertEqual(before, after)
        html = output.read_text(encoding="utf-8")
        self.assertNotIn('<script>alert("injected")', html)
        self.assertIn('&lt;script&gt;alert', html)
        self.assertIn('data:image/png;base64,', html)
        self.assertNotIn('<script src=', html)
        self.assertNotIn('<link ', html)
        self.assertIn('Brak far_field.npz', html)
        self.assertIn('Brak niezależnego bilansu', html)

    def test_completed_run_and_existing_output_are_protected(self):
        with self.assertRaisesRegex(ValueError, "niezmienny"):
            generate_report(self.run, self.run / "new.html")
        path = self.root / "existing.html"
        path.write_text("keep")
        with self.assertRaisesRegex(ValueError, "już istnieje"):
            generate_report(self.run, path)
        self.assertEqual(path.read_text(), "keep")
        with self.assertRaisesRegex(ValueError, "przed zamknięciem"):
            generate_report(self.run, automatic=True)

    def test_latest_selects_completed_simulation_not_recent_prepare_or_failure(self):
        fixture(self.root / "later-failed", date="2026-09-29T00:00:00Z", status="failed")
        fixture(self.root / "later-running", date="2026-09-29T00:00:00Z", status="running")
        fixture(self.root / "later-geometry", date="2026-09-29T00:00:00Z", stage="geometry")
        fixture(self.root / "later-prepare", date="2026-09-29T00:00:00Z", status="prepared", stage="openems_input")
        incomplete = fixture(self.root / "incomplete", date="2026-09-30T00:00:00Z")
        (incomplete / "summary.json").unlink()
        self.assertEqual(latest_run(self.root), self.run)

    def test_latest_errors_when_no_successful_simulation_exists(self):
        (self.run / "manifest.json").unlink()
        with self.assertRaisesRegex(ValueError, "Brak ukończonej"):
            latest_run(self.root)

    def test_dense_csv_order_and_nonpassive_points_are_preserved(self):
        (self.run / "impedance_dense.csv").write_text(
            "frequency_hz,resistance_ohm,reactance_ohm\n1421000000,-3,4\n1420000000,51,2\n")
        data = load_report_data(self.run)
        self.assertEqual(data["spectrum"]["frequency_mhz"], [1420, 1421])
        self.assertEqual(data["spectrum"]["r"], [51, -3])
        self.assertTrue(any("R ≤ 0" in message for message in data["warnings"]))

    def test_duplicate_or_nonfinite_csv_data_are_rejected(self):
        path = self.run / "impedance_dense.csv"
        for rows in ("1420000000,50,0\n1420000000,51,0\n", "1420000000,nan,0\n"):
            path.write_text("frequency_hz,resistance_ohm,reactance_ohm\n" + rows)
            with self.assertRaises(ValueError):
                load_report_data(self.run)

    def test_partial_and_archived_results_do_not_claim_completion(self):
        (self.run / "manifest.json").unlink()
        path = generate_report(self.run, self.root / "archive.html")
        self.assertIn("Brak potwierdzenia ukończenia", path.read_text(encoding="utf-8"))

    def test_two_power_denominators_and_signed_edge_work(self):
        # Reduced diagnostic fixture captures the distinction which matters:
        # 1 W port; 0.9 W work; 0.899 W outgoing flux; one negative edge.
        write_json(self.run / "power_balance.json", {
            "accepted_power_w": 1,
            "boxes": [{"name": "nf2ff", "frequency_hz": 1.42e9, "active_flux_w": .899}],
            "source_edge_work": {"frequencies": [{"frequency_hz": 1.42e9, "net_active_work_w": .9}]}})
        np.savez(self.run / "source_work_spectra.npz", frequency_hz=[1.42e9],
                 edge_active_work_w=[[1, -.1]], net_active_work_w=[.9])
        row = power_comparisons(load_report_data(self.run))[0]
        self.assertAlmostEqual(row["port_work_difference_percent"], 10)
        self.assertAlmostEqual(row["outer_work_difference_percent"], 100 / 900)
        self.assertEqual((row["counts"]["positive"], row["counts"]["negative"]), (1, 1))
        np.savez(self.run / "source_work_spectra.npz", frequency_hz=[1.42e9],
                 edge_active_work_w=[[1, -.1]], net_active_work_w=[1])
        with self.assertRaisesRegex(ValueError, "Niespójna suma"):
            power_comparisons(load_report_data(self.run))

    def test_power_surface_at_other_frequency_is_not_compared(self):
        write_json(self.run / "power_balance.json", {
            "accepted_power_w": 1,
            "boxes": [{"name": "nf2ff", "frequency_hz": 1.43e9, "active_flux_w": .899}],
            "source_edge_work": {"frequencies": [{"frequency_hz": 1.42e9, "net_active_work_w": .9}]}})
        row = power_comparisons(load_report_data(self.run))[0]
        self.assertIsNone(row["outer_work_difference_percent"])

    def test_explicit_spectrum_requires_raw_data_and_a_complete_range(self):
        with self.assertRaisesRegex(ValueError, "Podaj razem"):
            load_report_data(self.run, start_mhz=1400)
        with self.assertRaisesRegex(ValueError, "port_ut_1"):
            load_report_data(self.run, start_mhz=1400, stop_mhz=1440, step_mhz=.25)

    def test_dft_uses_separate_probe_times_and_keeps_band_limits(self):
        # Synthetic analytic waveform, not a simulated antenna. I is sampled
        # half a step later; equal timestamps would introduce a false phase.
        native = self.run / "openems"
        native.mkdir()
        write_json(self.run / "mesh.json", {"excitation_center_hz": 1e6, "excitation_bandwidth_hz": .2e6})
        t = np.arange(1000) / 100e6
        ti = t + .5 / 100e6
        np.savetxt(native / "port_ut_1", np.c_[t, 50 * np.cos(2*np.pi*1e6*t)])
        np.savetxt(native / "port_it_1", np.c_[ti, np.cos(2*np.pi*1e6*ti)])
        data = load_report_data(self.run, start_mhz=1, stop_mhz=1, step_mhz=.01)
        self.assertAlmostEqual(data["spectrum"]["r"][0], 50, places=8)
        self.assertAlmostEqual(data["spectrum"]["x"][0], 0, places=8)
        with self.assertRaisesRegex(ValueError, "pasmo"):
            load_report_data(self.run, start_mhz=.1, stop_mhz=1, step_mhz=.01)
        with self.assertRaisesRegex(ValueError, "10001"):
            load_report_data(self.run, start_mhz=.9, stop_mhz=1.1, step_mhz=.000001)

    def test_report_failure_leaves_simulation_status_for_normal_finalization(self):
        record = SimpleNamespace(path=self.run, manifest={"status": "running", "warnings": []})
        with patch("antenna_lab.visualization.report.generate_report", side_effect=OSError("disk error")):
            with redirect_stderr(StringIO()):
                _write_run_report(record)
        self.assertEqual(record.manifest["status"], "running")
        self.assertIn("Wyniki FDTD są zachowane", record.manifest["warnings"][0])

    def test_cli_latest_and_open_use_a_local_uri_without_subprocess(self):
        output = self.root / "from-cli.html"
        with patch("webbrowser.open", return_value=True) as browser, patch("subprocess.Popen", side_effect=AssertionError("no FDTD")):
            with redirect_stdout(StringIO()):
                code = main(["report", "--latest", "--runs-dir", str(self.root), "--output", str(output), "--open"])
        self.assertEqual(code, 0)
        browser.assert_called_once_with(output.as_uri())
        with redirect_stderr(StringIO()):
            self.assertEqual(main(["report"]), 1)
            self.assertEqual(main(["report", str(self.run), "--latest"]), 1)

    def test_automatic_report_is_inside_unfinished_run(self):
        fixture(self.run, status="running")
        path = generate_report(self.run, automatic=True)
        self.assertEqual(path, self.run / "report.html")
        self.assertTrue((self.run / "plots" / "impedance.png").is_file())
        self.assertIn("completed", path.read_text(encoding="utf-8"))
        self.assertEqual(json.loads((self.run / "manifest.json").read_text())["status"], "running")


if __name__ == "__main__":
    unittest.main()
