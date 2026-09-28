"""Regressions for the Windows 512-stream failure, without running FDTD."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from antenna_lab.cli import _read_worker_log
from antenna_lab.solvers.native_io import _load_ucrt, configure_stdio, prepare_native_io


class LimitedCRT:
    def __init__(self, limit=512, open_capacity=None):
        self.limit = limit
        self.open_capacity = open_capacity
        self.handles = []
        self.set_calls = []
        self.open_calls = 0

    def _getmaxstdio(self):
        return self.limit

    def _setmaxstdio(self, value):
        self.set_calls.append(value)
        self.limit = value
        return value

    def fopen(self, name, mode):
        self.open_calls += 1
        available = self.limit - 3 if self.open_capacity is None else self.open_capacity
        if len(self.handles) >= available:
            return None
        handle = self.open_calls
        self.handles.append(handle)
        return handle

    def fclose(self, handle):
        self.handles.remove(handle)
        return 0


class NativeIOTests(unittest.TestCase):
    def test_945_probes_raise_512_limit_and_close_all_preflight_streams(self):
        crt = LimitedCRT()
        result = configure_stdio(crt, 945)
        self.assertEqual(crt.set_calls, [2048])
        self.assertEqual(result["limit_before"], 512)
        self.assertEqual(result["limit_after"], 2048)
        self.assertEqual(crt.open_calls, 945)
        self.assertEqual(crt.handles, [])

    def test_capacity_failure_closes_streams_and_does_not_claim_success(self):
        crt = LimitedCRT(open_capacity=509)
        with self.assertRaisesRegex(RuntimeError, "509 z 945"):
            configure_stdio(crt, 945)
        self.assertEqual(crt.handles, [])

    def test_cannot_silently_continue_when_limit_change_fails(self):
        crt = LimitedCRT()
        crt._setmaxstdio = Mock(return_value=-1)
        with self.assertRaisesRegex(RuntimeError, "Nie można zwiększyć"):
            configure_stdio(crt, 945)
        self.assertEqual(crt.open_calls, 0)

    def test_preserves_higher_limit_and_rejects_unsupported_capacity(self):
        crt = LimitedCRT(limit=4096)
        configure_stdio(crt, 945)
        self.assertEqual(crt.set_calls, [])
        self.assertEqual(crt.limit, 4096)
        with self.assertRaisesRegex(RuntimeError, "8192"):
            configure_stdio(crt, 8192)
        self.assertEqual(crt.set_calls, [])

    def test_windows_preflight_counts_saved_native_xml(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "model.xml"
            model.write_text('<openEMS><Properties>' + ''.join(
                f'<ProbeBox Name="probe_{i}"><Primitives><Box/></Primitives></ProbeBox>'
                for i in range(945)) + '</Properties></openEMS>', encoding="utf-8")
            crt = LimitedCRT()
            with patch("antenna_lab.solvers.native_io.sys.platform", "win32"), \
                    patch("antenna_lab.solvers.native_io._load_ucrt", return_value=crt), \
                    redirect_stdout(StringIO()) as output:
                result = prepare_native_io(model)
            self.assertEqual(result["probe_streams"], 945)
            self.assertIn("512 -> 2048", output.getvalue())

    def test_native_file_error_stops_worker_before_reading_further_output(self):
        process = Mock()
        process.poll.return_value = None
        process.stdout = StringIO("Running FDTD engine...\nCan't open file: power_edge_i_0253\n"
                                  "THIS MUST NOT BE READ\n")
        log = StringIO()
        with redirect_stdout(StringIO()), self.assertRaisesRegex(RuntimeError, "power_edge_i_0253"):
            _read_worker_log(process, log)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)
        self.assertTrue(process.stdout.closed)
        self.assertNotIn("THIS MUST NOT BE READ", log.getvalue())

    def test_unused_primitive_warning_does_not_stop_worker(self):
        process = Mock()
        process.stdout = StringIO("Warning: Unused primitive (type: Sphere) detected in property: radiator_PEC!\n")
        with redirect_stdout(StringIO()):
            _read_worker_log(process, StringIO())
        process.terminate.assert_not_called()
        self.assertTrue(process.stdout.closed)

    @unittest.skipUnless(sys.platform == "win32", "Real UCRT stream check requires Windows")
    def test_real_windows_ucrt_can_open_945_probe_streams(self):
        result = configure_stdio(_load_ucrt(), 945)
        self.assertEqual(result["simultaneous_probe_stream_check"], "passed")


if __name__ == "__main__":
    unittest.main()
