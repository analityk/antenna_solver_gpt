"""Small output allocation regressions; no native solver or real output files."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from antenna_lab.pcb.output import allocate_output_dir
from antenna_lab.pcb.reduced_control import main


class PcbOutputTests(TestCase):
    def test_monotonic_and_parallel(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'spirala_001').mkdir();(root/'spirala_004').mkdir()
            (root/'other_999').mkdir()
            with ThreadPoolExecutor(max_workers=4) as pool:
                paths=list(pool.map(lambda _: allocate_output_dir('spirala.epro',root), range(4)))
            self.assertEqual({p.name for p in paths},{f'spirala_{n:03d}' for n in range(5,9)})
            self.assertTrue(all(p.is_dir() for p in paths))

    def test_directory_input(self):
        with TemporaryDirectory() as tmp:
            source=Path(tmp)/'board';source.mkdir()
            self.assertEqual(allocate_output_dir(source,Path(tmp)/'runs').name,'board_001')

    def test_inspect_source_and_explicit_override(self):
        result={'status':'source_inspected','provenance':{'missing_source_dependencies':[]}}
        with patch('antenna_lab.pcb.reduced_control.run_reduced',return_value=result) as run, \
             patch('antenna_lab.pcb.reduced_control.allocate_output_dir',return_value=Path('spirala_001')) as allocate:
            self.assertEqual(main(['--easyeda-project','spirala.epro','--inspect-source']),0)
            allocate.assert_called_once_with(Path('spirala.epro'),Path('outcomes/pcb_reduced'))
            self.assertEqual(run.call_args.args[1],Path('spirala_001'))
            allocate.reset_mock()
            self.assertEqual(main(['--easyeda-project','spirala.epro','--inspect-source','--output','chosen']),0)
            allocate.assert_not_called()
            self.assertEqual(run.call_args.args[1],Path('chosen'))
