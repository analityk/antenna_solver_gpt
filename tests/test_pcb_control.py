"""Control solve contract using fakes only; never executes native FDTD."""
import contextlib
import csv
from dataclasses import asdict, replace
import io
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import control
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from antenna_lab.solvers.openems_pcb import run_pcb_fdtd, write_pcb_port_results


class Engine:
    def __init__(self, status=None, error=None):
        self.calls = []
        self.status, self.error = status, error

    def Run(self, path, **kwargs):
        self.calls.append((path, kwargs))
        os.chdir(path)
        if self.error:
            raise self.error
        return self.status
    # All preparation/field/NF2FF methods are intentionally absent.


class Port:
    def __init__(self, voltage=(50, 100, 50+50j), current=(1, 1, 1)):
        self.uf_tot, self.if_tot = voltage, current
        self.calls = []

    def CalcPort(self, path, frequencies, **kwargs):
        self.calls.append((path, frequencies.copy(), kwargs))


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.native = Path(self.temp.name)/'native'
        self.native.mkdir()
        (self.native/'model.xml').write_text('<model/>')
        self.geometry, self.settings = control.make_synthetic_control_case()
        self.mesh = make_pcb_domain_mesh(self.geometry, self.settings)
        self.lines = dict(zip('xyz', (self.mesh.x_lines_m,self.mesh.y_lines_m,self.mesh.z_lines_m)))
        self.grid = SimpleNamespace(GetDeltaUnit=lambda:1., GetLines=lambda axis:self.lines[axis])
        self.csx = SimpleNamespace(GetGrid=lambda:self.grid)

    def solve(self, port=None, engine=None, settings=None):
        return run_pcb_fdtd(engine or Engine(), self.csx, port or Port(), self.mesh,
                            settings or self.settings, self.native)

    def test_exact_calls_math_order_and_detachment(self):
        engine, port = Engine(), Port()
        before = (self.geometry.as_dict(), asdict(self.settings), asdict(self.mesh))
        result = self.solve(port, engine)
        self.assertEqual(engine.calls, [(str(self.native), dict(cleanup=False,numThreads=0))])
        self.assertEqual(len(port.calls),1)
        path, frequencies, kwargs = port.calls[0]
        self.assertEqual(path,str(self.native))
        self.assertEqual(frequencies.tolist(),list(self.settings.result_frequency_hz))
        self.assertEqual(kwargs,dict(ref_impedance=50.))
        self.assertEqual(result['resistance_ohm'],[50.,100.,50.])
        self.assertEqual(result['reactance_ohm'],[0.,0.,50.])
        np.testing.assert_allclose(result['s11_real'],[0,1/3,.2])
        np.testing.assert_allclose(result['s11_imag'],[0,0,.4])
        np.testing.assert_allclose(result['s11_magnitude'],[0,1/3,math.sqrt(.2)])
        self.assertIsNone(result['s11_db'][0])
        self.assertAlmostEqual(result['s11_db'][1],-9.542425094393248)
        self.assertAlmostEqual(result['s11_db'][2],-6.9897000433601875)
        np.testing.assert_allclose(result['swr'],[1,2,(1+math.sqrt(.2))/(1-math.sqrt(.2))])
        self.assertEqual(result['frequency_hz'],list(self.settings.result_frequency_hz))
        json.dumps(result,allow_nan=False)
        result['mesh']['shape_cells'].clear()
        self.assertEqual(before,(self.geometry.as_dict(),asdict(self.settings),asdict(self.mesh)))

    def test_configured_reference_threads_and_safe_vector_reshape(self):
        settings = replace(self.settings,reference_impedance_ohm=75.,threads=3)
        port = Port([[75],[75],[75]],[[1,1,1]])
        engine = Engine()
        result = self.solve(port,engine,settings)
        self.assertEqual(result['s11_magnitude'],[0,0,0])
        self.assertEqual(port.calls[0][2],{'ref_impedance':75.})
        self.assertEqual(engine.calls[0][1]['numThreads'],3)

    def test_return_codes_and_cwd_on_all_exits(self):
        original = Path.cwd()
        for status, error in ((None,None),(0,None),(7,None),(None,RuntimeError('native failed'))):
            with self.subTest(status=status,error=error):
                port, engine = Port(), Engine(status,error)
                if error or status == 7:
                    with self.assertRaises(RuntimeError): self.solve(port,engine)
                    self.assertEqual(port.calls,[])
                else:
                    self.solve(port,engine)
                self.assertEqual(Path.cwd(),original)

    def test_bad_native_spectra(self):
        cases = [([1,2,3],[1,0,1]), ([1,2],[1,1,1]),
                 ([[1,2],[3,4]],[1,1,1]), ([1,2,3],[1,1]),
                 (['bad',1,1],[1,1,1])]
        for bad in (float('nan'),float('inf'),complex(1,float('inf'))):
            cases.extend([([bad,1,1],[1,1,1]),([1,1,1],[1,bad,1])])
        for voltage,current in cases:
            with self.subTest(voltage=voltage,current=current), self.assertRaises(ConfigurationError):
                self.solve(Port(voltage,current))
        port=Port();del port.uf_tot
        with self.assertRaisesRegex(ConfigurationError,'uf_tot'): self.solve(port)

    def test_invalid_impedance_denominator_and_nonpassivity(self):
        for voltage,current,reason in (([-50]*3,[1]*3,'mianownik'),
                ([1e308]*3,[1e-308]*3,'mianownik'),
                ([0]*3,[1]*3,'non-passive'), ([-1]*3,[1]*3,'non-passive')):
            with self.subTest(voltage=voltage), self.assertRaisesRegex(ConfigurationError,reason):
                self.solve(Port(voltage,current))

    def test_prerun_failures_do_not_run(self):
        engine = Engine()
        self.lines['x'] = self.lines['x'][1:]
        with self.assertRaisesRegex(ConfigurationError,'before Run'): self.solve(engine=engine)
        self.assertEqual(engine.calls,[])
        self.lines['x'] = self.mesh.x_lines_m
        self.grid.GetDeltaUnit=lambda:.001
        with self.assertRaises(ConfigurationError): self.solve(engine=engine)
        self.grid.GetDeltaUnit=lambda:1.
        for mode in ('empty','missing','missing_dir'):
            xml=self.native/'model.xml'
            if mode=='empty': xml.write_text('')
            elif mode=='missing': xml.unlink()
            else: self.native.rmdir()
            with self.subTest(mode=mode), self.assertRaisesRegex(ConfigurationError,'model.xml'):
                self.solve(engine=engine)
            self.assertEqual(engine.calls,[])

    def test_csv_strict_json(self):
        result=self.solve()
        directory=Path(self.temp.name)/'results'
        written=write_pcb_port_results(result,directory)
        self.assertEqual(set(p.name for p in directory.iterdir()),{'impedance.csv','summary.json'})
        with (directory/'impedance.csv').open(newline='') as stream: rows=list(csv.reader(stream))
        self.assertEqual(rows[0],['frequency_hz','resistance_ohm','reactance_ohm','reference_ohm',
                                 's11_real','s11_imag','s11_magnitude','s11_db','swr'])
        self.assertEqual(len(rows),4)
        self.assertEqual([float(r[0]) for r in rows[1:]],list(self.settings.result_frequency_hz))
        self.assertEqual(rows[1][7],'')
        loaded=json.loads((directory/'summary.json').read_text())
        self.assertEqual(loaded,result)
        self.assertEqual(loaded['validation_status'],'unverified')
        json.dumps(loaded,allow_nan=False)
        written['frequency_hz'].clear()
        self.assertEqual(len(result['frequency_hz']),3)
        bad=dict(result,swr=[float('nan')]*3)
        with self.assertRaises(ValueError): write_pcb_port_results(bad,directory)
        with self.assertRaises(ConfigurationError): write_pcb_port_results(dict(result,swr=[]),directory)

    def test_control_geometry_single_normalization(self):
        with patch.object(control,'normalize_port_orientation',wraps=control.normalize_port_orientation) as norm:
            geometry,settings=control.make_synthetic_control_case()
        self.assertEqual(norm.call_count,1)
        self.assertEqual(len(geometry.copper),2)
        self.assertEqual(geometry.substrate.z_min_m,-.0016)
        self.assertEqual(geometry.substrate.epsilon_r,4.3)
        self.assertEqual(geometry.substrate.loss_tangent,.018)
        self.assertAlmostEqual(math.dist(geometry.port.negative_xy_m,geometry.port.positive_xy_m),.001)
        self.assertEqual(geometry.port.width_m,.002)
        self.assertEqual(settings.reference_impedance_ohm,50.)
        spec=resolve_pcb_lumped_port(geometry,make_pcb_domain_mesh(geometry,settings),settings)
        self.assertEqual(spec.active_ex_edge_count,6)

    def test_high_level_prepares_once_and_retains_native(self):
        output=Path(self.temp.name)/'run'
        engine,port=Engine(),Port()
        calls=[]
        def prepare(g,s,path):
            calls.append(path)
            path.write_text('<model/>')
            return engine,self.csx,port,self.mesh,None,{'test':'preparation'}
        with patch.object(control,'prepare_pcb_xml_model',side_effect=prepare):
            result=control.run_synthetic_control(output)
        self.assertEqual(calls,[output/'native/model.xml'])
        self.assertEqual(len(engine.calls),1)
        self.assertTrue(calls[0].is_file())
        self.assertEqual(result['preparation'],{'test':'preparation'})
        self.assertEqual(result['simulation_settings']['threads'],0)
        with patch.object(control,'prepare_pcb_xml_model') as prep:
            with self.assertRaisesRegex(ConfigurationError,'pusty'): control.run_synthetic_control(output)
            prep.assert_not_called()

    def test_cli_unique_outputs_and_known_unexpected_errors(self):
        cwd=Path.cwd()
        result=self.solve()
        try:
            os.chdir(self.temp.name)
            with patch.object(control,'run_synthetic_control',return_value=result) as run, contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(control.main([]),0)
                self.assertEqual(control.main([]),0)
                first,second=[call.args[0] for call in run.call_args_list]
                self.assertNotEqual(first,second)
                self.assertTrue(first.is_dir() and second.is_dir())
                self.assertIn('Status: UNVERIFIED',stdout.getvalue())
            for error in (ConfigurationError('bad'),RuntimeError('bad'),OSError('bad'),ValueError('bad')):
                with patch.object(control,'run_synthetic_control',side_effect=error), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(control.main(['--output','explicit']),1)
            with patch.object(control,'run_synthetic_control',side_effect=AssertionError('programmer')), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(AssertionError): control.main(['--output','explicit'])
        finally:
            os.chdir(cwd)


if __name__ == '__main__':
    unittest.main()
