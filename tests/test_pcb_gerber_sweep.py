"""Dense Gerber spectra through fake native objects; no FDTD execution."""
import contextlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import gerber_control as control
from antenna_lab.pcb.gerber_sweep import sweep_frequencies_hz, sampled_diagnostics
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from antenna_lab.pcb.gerber import load_pcb_geometry
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from test_pcb_edge_convergence import RunEngine
from test_openems_pcb import CSX
import test_pcb_gerber as fixtures


class SweepTests(unittest.TestCase):
    def test_regular_inclusive_deterministic_and_nondivisible(self):
        values=sweep_frequencies_hz(1260,1580,5)
        self.assertEqual(values,tuple(1260e6+i*5e6 for i in range(65)))
        self.assertEqual(values,sweep_frequencies_hz(1260,1580,5))
        self.assertEqual(sweep_frequencies_hz(1,2,.3),(1e6,1.3e6,1.6e6,1.9e6))
        self.assertEqual(sweep_frequencies_hz(1,1.3,.1),(1e6,1.1e6,1.2e6,1.3e6))

    def test_invalid_values(self):
        for args in ((0,2,1),(-1,2,1),(2,2,1),(3,2,1),(1,2,0),(1,2,-1),(1,2,3)):
            with self.subTest(args=args),self.assertRaises(ConfigurationError):sweep_frequencies_hz(*args)
        for i in range(3):
            for value in (float('nan'),float('inf'),-float('inf')):
                args=[1,2,.1];args[i]=value
                with self.assertRaises(ConfigurationError):sweep_frequencies_hz(*args)

    def test_cli_selection_defaults_conflicts_and_band(self):
        common=['unused.json','--output','unused','--prepare-only']
        sweep=['--sweep-start-mhz','1260','--sweep-stop-mhz','1580','--sweep-step-mhz','5']
        for args,expected in (([],(1.3e9,1.42e9,1.5e9)),
                              (['--frequencies-mhz','1300','1400'],(1.3e9,1.4e9)),
                              (sweep,sweep_frequencies_hz(1260,1580,5))):
            with patch.object(control,'run_gerber_control',return_value={'status':'prepared'}) as run,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(control.main(common+args),0)
                self.assertEqual(run.call_args.kwargs['resolved_profile'].settings.result_frequency_hz,expected)
        for args in (sweep+['--frequencies-mhz','1300','1420','1500'],sweep[:-2],
                     ['--sweep-start-mhz','1000','--sweep-stop-mhz','1580','--sweep-step-mhz','5']):
            with patch.object(control,'run_gerber_control') as run,contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(control.main(common+args),1)
                run.assert_not_called()

    def test_sample_minima_crossings_and_strict_json(self):
        result=dict(frequency_hz=[1.,2.,3.,4.,5.],resistance_ohm=[50.]*5,
                    reactance_ohm=[-3.,2.,0.,0.,-1.],s11_magnitude=[.3,.2,0.,0.,.1],
                    s11_db=[-10.,-14.,None,None,-20.],swr=[2.,1.5,1.,1.,1.2])
        before=json.dumps(result,allow_nan=False)
        d=sampled_diagnostics(result)
        self.assertEqual(d['minimum_s11'],dict(frequency_hz=3.,s11_magnitude=0.,s11_db=None,
            swr=1.,resistance_ohm=50.,reactance_ohm=0.))
        self.assertEqual(d['minimum_swr'],dict(frequency_hz=3.,swr=1.))
        self.assertEqual(d['minimum_abs_reactance'],dict(frequency_hz=3.,resistance_ohm=50.,reactance_ohm=0.))
        self.assertEqual(d['reactance_crossings'],[
            dict(frequency_low_hz=float(i+1),frequency_high_hz=float(i+2),x_low_ohm=a,x_high_ohm=b)
            for i,(a,b) in enumerate(zip(result['reactance_ohm'],result['reactance_ohm'][1:]))])
        json.dumps(d,allow_nan=False)
        self.assertEqual(before,json.dumps(result,allow_nan=False))
        result['reactance_ohm']=[1.,2.,3.,4.,5.]
        self.assertEqual(sampled_diagnostics(result)['reactance_crossings'],[])

    def test_dense_single_run_calcport_all_profiles_and_mesh_independence(self):
        fixture=fixtures.GerberTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        geometry,_=normalize_port_orientation(load_pcb_geometry(fixture.config))
        frequencies=sweep_frequencies_hz(1260,1580,5)
        for quality in ('preview','design','verify'):
            sparse,_=gerber_quality_settings(quality,result_frequency_hz=(frequencies[0],frequencies[-1]))
            dense,_=gerber_quality_settings(quality,result_frequency_hz=frequencies)
            self.assertEqual(make_pcb_domain_mesh(geometry,sparse,gerber_quality=quality),
                             make_pcb_domain_mesh(geometry,dense,gerber_quality=quality))
            engine=RunEngine(n=65);csx=CSX();out=fixture.root/quality
            with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                    SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=lambda:csx))),contextlib.redirect_stdout(io.StringIO()) as console:
                result=control.run_gerber_control(fixture.config_path,out,quality=quality,
                    result_frequency_hz=frequencies,sweep_request=(1260,1580,5),field_frequency_hz=())
            self.assertEqual(len([c for c in engine.calls if c[0]=='Run']),1)
            self.assertEqual(len(engine.port.calls),1)
            self.assertEqual(tuple(engine.port.calls[0][1]),frequencies)
            self.assertEqual(result['sweep']['point_count'],65)
            self.assertEqual(result['sweep']['requested_step_hz'],5e6)
            self.assertEqual(result,json.loads((out/'summary.json').read_text(),parse_constant=lambda x:self.fail(x)))
            self.assertNotIn('synthetic',result['note'])
            self.assertEqual([p.name for p in out.glob('*.csv')],['impedance.csv'])
            self.assertEqual(len((out/'impedance.csv').read_text().splitlines()),66)
            self.assertIn('Sweep: 1260–1580 MHz, step 5 MHz, 65 points',console.getvalue())
            for text in ('Best |S11|:','Minimum SWR:','Nearest X=0:','Reactance crossings:'):
                self.assertIn(text,console.getvalue())


if __name__=='__main__':unittest.main()
