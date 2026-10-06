"""Saved PCB reports share the antenna renderer; never reparse or solve."""
import contextlib
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.pcb.gerber_control import run_gerber_control
from antenna_lab.visualization.report import generate_report
from antenna_lab.visualization.report_data import load_report_data
from antenna_lab.cli import main
from test_pcb_bundle import bundle_fixture
from test_pcb_edge_convergence import RunEngine
from test_openems_pcb import CSX


class PcbReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.bundle=bundle_fixture(self.root/'gerbers',vertical=True,loop=True)
        self.out=self.root/'run';engine=RunEngine()
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=CSX))),contextlib.redirect_stdout(io.StringIO()) as console:
            self.result=run_gerber_control(self.bundle,self.out,quality='preview')
        self.console=console.getvalue()

    def test_automatic_offline_report_plots_and_metadata(self):
        html=(self.out/'report.html').read_text(encoding='utf-8')
        self.assertIn('Raport HTML:',self.console)
        for name in ('geometry','impedance','s11','swr'):
            path=self.out/'plots'/f'{name}.png'
            self.assertGreater(path.stat().st_size,1000)
            self.assertEqual(path.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
        for text in ('Raport PCB','PCB pod lupą','preview','completed_before_limit','unverified',
                     'documented defaults','soldermask','silkscreen','paste','SHA256',
                     'S11 [dB]','Minimum próbkowane SWR','Optimum na granicy sweepu'):
            self.assertIn(text,html)
        self.assertNotIn('Raport anteny',html)
        self.assertNotIn('<h2>Bilans mocy</h2>',html)
        self.assertNotIn('<h2>Kierunkowość i zysk</h2>',html)
        self.assertIn('data:image/png;base64,',html)
        self.assertNotIn('<script src=',html);self.assertNotIn('<link ',html)
        self.assertNotRegex(html,r'(?:src|href)=[\"\']https?://')
        for record in self.result['import']['discovered_files']:
            self.assertIn(record['name'],html);self.assertIn(record['sha256'],html)

    def test_regenerate_saved_files_without_native_or_gerbers_and_cli_open(self):
        for path in self.bundle.iterdir():path.unlink()
        before={str(p.relative_to(self.out)):sha256(p.read_bytes()).hexdigest() for p in self.out.rglob('*') if p.is_file()}
        with patch('antenna_lab.solvers.openems.native_modules',side_effect=AssertionError('native forbidden')),\
             patch('gerbonara.GerberFile.open',side_effect=AssertionError('Gerbers forbidden')),\
             patch('subprocess.Popen',side_effect=AssertionError('process forbidden')):
            report=generate_report(self.out,self.root/'regenerated.html')
            data=load_report_data(self.out)
            self.assertTrue(data['is_pcb']);self.assertEqual(data['spectrum']['source'],'impedance.csv')
            self.assertEqual(data['execution_status'],'completed')
            with patch('webbrowser.open',return_value=True) as browser,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['report',str(self.out),'--output',str(self.root/'cli.html'),'--open']),0)
                browser.assert_called_once_with((self.root/'cli.html').as_uri())
        after={str(p.relative_to(self.out)):sha256(p.read_bytes()).hexdigest() for p in self.out.rglob('*') if p.is_file()}
        self.assertEqual(before,after);self.assertIn('Raport PCB',report.read_text())

    def test_geometry_and_note_are_escaped(self):
        path=self.out/'summary.json';value=json.loads(path.read_text());value['note']='<script>alert(1)</script>'
        value['import']['source_directory']='<script>directory</script>';path.write_text(json.dumps(value))
        report=generate_report(self.out,self.root/'escaped.html');html=report.read_text()
        self.assertNotIn('<script>alert',html);self.assertIn('&lt;script&gt;alert',html)
        self.assertNotIn('<script>directory',html)


if __name__=='__main__':unittest.main()
