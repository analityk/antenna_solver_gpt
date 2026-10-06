"""Convergence infrastructure: synthetic spectra only, no native FDTD."""
import contextlib
from dataclasses import asdict
import io
import json
import csv
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import convergence as c
from antenna_lab.pcb.control import make_synthetic_control_case
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh

NAMES=('baseline','wavelength_fine','port_fine','substrate_z_fine','air_padding_wide',
       'pml_deep','time_strict','reference_fine')


class ConvergenceTests(unittest.TestCase):
    def test_variants_exact_diffs_validation_and_immutability(self):
        g,s=make_synthetic_control_case();before=asdict(s)
        with patch.object(c,'validate_pcb_simulation_settings',wraps=c.validate_pcb_simulation_settings) as validate:
            variants=c.make_convergence_variants(s)
        self.assertEqual(validate.call_count,8)
        self.assertEqual(tuple(n for n,_ in variants),NAMES)
        diffs=[{}, {'cells_per_wavelength':30}, {'min_port_gap_cells':4,'min_port_width_cells':4},
               {'min_substrate_cells_z':8}, {'air_padding_wavelengths':.5}, {'pml_cells':12},
               {'end_criteria':1e-6}]
        diffs.append({k:v for d in diffs[1:] for k,v in d.items()})
        for (_,variant),expected in zip(variants,diffs):
            self.assertEqual({k:v for k,v in asdict(variant).items() if v!=before[k]},expected)
        self.assertEqual(asdict(s),before)
        self.assertEqual(variants,c.make_convergence_variants(s))

    def test_comparison_independent_safe_denominators(self):
        ref=dict(frequency_hz=[1.,2.],reference_impedance_ohm=50.,resistance_ohm=[0.,3.],reactance_ohm=[1e-20,-4.])
        other={**ref,'resistance_ohm':[3.,6.],'reactance_ohm':[4.,0.]}
        rows=c.compare_impedance(other,ref)
        self.assertEqual(rows[0]['delta_R_ohm'],3.)
        self.assertEqual(rows[0]['delta_X_ohm'],4.)
        self.assertEqual(rows[0]['relative_R'],3.)
        self.assertEqual(rows[0]['relative_X'],4.)
        self.assertEqual(rows[0]['delta_Z_magnitude_ohm'],5.)
        self.assertEqual(rows[0]['relative_Z_magnitude'],.1)
        self.assertEqual(rows[1]['relative_R'],1.)
        self.assertEqual(rows[1]['relative_X'],1.)
        for row in c.compare_impedance(ref,ref):
            self.assertTrue(all(v==0 for k,v in row.items() if k!='frequency_hz'))
        with self.assertRaises(ConfigurationError): c.compare_impedance({**other,'frequency_hz':[3.]},ref)
        self.assertAlmostEqual(c.equivalent_capacitance(1e9,-100),1/(2*math.pi*1e11))
        self.assertIsNone(c.equivalent_capacitance(1e9,0))
        self.assertIsNone(c.equivalent_capacitance(1e9,5))

    def fake_run(self, geometry, settings, output):
        self.calls.append((geometry.as_dict(),asdict(settings),output))
        mesh=make_pcb_domain_mesh(geometry,settings)
        (output/'native').mkdir(parents=True)
        (output/'native/model.xml').write_text('<fake/>')
        i=len(self.calls)
        n=len(settings.result_frequency_hz)
        result=dict(frequency_hz=list(settings.result_frequency_hz), reference_impedance_ohm=50.,
                    resistance_ohm=[float(i)]*n,reactance_ohm=[-100.+i]*n,
                    s11_magnitude=[.99]*n,swr=[199.]*n,validation_status='unverified',
                    mesh={k:asdict(mesh)[k] for k in ('shape_cells','cell_count','pml_cells',
                          'min_step_m','max_step_m','worst_growth_ratio')})
        (output/'summary.json').write_text(json.dumps(result))
        (output/'impedance.csv').write_text('fake retained\n')
        return result

    def test_studies_bands_fixed_geometry_unique_paths_and_reports(self):
        for band in ({},dict(excitation_center_hz=2.45e9,excitation_cutoff_hz=.4e9,
                result_frequency_hz=(2.2e9,2.4e9,2.45e9,2.5e9,2.7e9),loss_reference_frequency_hz=2.4e9),
                dict(excitation_center_hz=.9e9,excitation_cutoff_hz=.15e9,result_frequency_hz=(.8e9,1e9))):
            with self.subTest(band=band),TemporaryDirectory() as directory:
                self.calls=[]
                with patch.object(c,'run_control_model',side_effect=self.fake_run),contextlib.redirect_stdout(io.StringIO()) as out:
                    study=c.run_convergence_study(directory,**band)
                self.assertEqual(study['status'],'diagnostic_pending_review')
                self.assertEqual(len(self.calls),8)
                self.assertEqual([p.name for _,_,p in self.calls],list(NAMES))
                self.assertEqual(len(set(p for _,_,p in self.calls)),8)
                g,s=make_synthetic_control_case(**band)
                for geometry,settings,path in self.calls:
                    self.assertEqual(geometry,g.as_dict())
                    for key in ('result_frequency_hz','excitation_center_hz','excitation_cutoff_hz','loss_reference_frequency_hz'):
                        self.assertEqual(settings[key],getattr(s,key))
                    self.assertTrue((path/'native/model.xml').exists())
                for ref,name in (('baseline','baseline'),('reference','reference_fine')):
                    rows=study['comparisons_to_'+ref][name]
                    self.assertEqual(len(rows),len(s.result_frequency_hz))
                    self.assertTrue(all(v==0 for row in rows for k,v in row.items() if k!='frequency_hz'))
                json.dumps(study,allow_nan=False)
                self.assertEqual(study,json.loads((Path(directory)/'convergence.json').read_text()))
                with (Path(directory)/'convergence.csv').open(newline='') as stream: rows=list(csv.DictReader(stream))
                self.assertEqual(len(rows),8*len(s.result_frequency_hz))
                self.assertEqual([float(r['frequency_hz']) for r in rows[:len(s.result_frequency_hz)]],list(s.result_frequency_hz))
                if s.excitation_center_hz not in s.result_frequency_hz:
                    self.assertIn('0.800 GHz: Z=',out.getvalue())
                with patch.object(c,'run_control_model') as runner:
                    with self.assertRaises(ConfigurationError): c.run_convergence_study(directory,**band)
                    runner.assert_not_called()

    def test_failed_or_interrupted_variant_preserves_completed(self):
        for error in (RuntimeError('native failed'),KeyboardInterrupt()):
            with TemporaryDirectory() as directory:
                self.calls=[]
                def fail(g,s,p):
                    if p.name=='port_fine': raise error
                    return self.fake_run(g,s,p)
                with patch.object(c,'run_control_model',side_effect=fail),contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(type(error)): c.run_convergence_study(directory)
                study=json.loads((Path(directory)/'convergence.json').read_text())
                self.assertEqual(study['status'],'failed')
                self.assertEqual(study['variants']['port_fine']['status'],'failed')
                self.assertEqual(study['variants']['reference_fine']['status'],'pending')
                self.assertEqual(study['variants']['baseline']['status'],'completed')
                self.assertTrue((Path(directory)/'baseline/native/model.xml').is_file())
                with (Path(directory)/'convergence.csv').open(newline='') as stream:
                    self.assertEqual(len(list(csv.DictReader(stream))),6)

    def test_cli_conversion_unique_default_and_errors(self):
        original=Path.cwd()
        with TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch.object(c,'run_convergence_study',return_value={}) as runner,contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(c.main([]),0)
                    self.assertEqual(c.main([]),0)
                    self.assertNotEqual(runner.call_args_list[0].args[0],runner.call_args_list[1].args[0])
                    self.assertEqual(c.main(['--output','custom','--center-mhz','2450','--cutoff-mhz','400',
                        '--frequencies-mhz','2200','2450','2700','--loss-reference-mhz','2400']),0)
                    self.assertEqual(runner.call_args.kwargs,dict(excitation_center_hz=2.45e9,
                        excitation_cutoff_hz=.4e9,result_frequency_hz=(2.2e9,2.45e9,2.7e9),loss_reference_frequency_hz=2.4e9))
                with patch.object(c,'run_control_model') as runner,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(c.main(['--center-mhz','0']),1)
                    runner.assert_not_called()
            finally: os.chdir(original)


if __name__=='__main__': unittest.main()
