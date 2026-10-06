"""Spatial ladder tests: no native modules or real FDTD."""
import contextlib
import csv
from dataclasses import asdict
import io
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import spatial_convergence as s
from antenna_lab.pcb.control import make_synthetic_control_case


class SpatialTests(unittest.TestCase):
    def test_exact_levels_validation_frozen_settings(self):
        g,base=make_synthetic_control_case()
        before=asdict(base)
        with patch.object(s,'validate_pcb_simulation_settings',wraps=s.validate_pcb_simulation_settings) as validator:
            levels=s.make_spatial_levels(base)
        self.assertEqual(validator.call_count,4)
        self.assertEqual(tuple(n for n,_ in levels),('L0_baseline','L1_medium','L2_fine','L3_extra_fine'))
        keys=('cells_per_wavelength','min_port_gap_cells','min_port_width_cells','min_substrate_cells_z')
        for (_,settings),expected in zip(levels,((20,2,2,4),(30,4,4,8),(40,6,6,12),(50,8,8,16))):
            self.assertEqual(tuple(getattr(settings,k) for k in keys),expected)
            self.assertEqual({k:v for k,v in asdict(settings).items() if k not in keys},
                             {k:v for k,v in before.items() if k not in keys})
        self.assertEqual(asdict(base),before)
        self.assertEqual(levels,s.make_spatial_levels(base))

    def result(self,r,x,frequencies=(1e9,)):
        return dict(frequency_hz=list(frequencies),resistance_ohm=[r]*len(frequencies),
                    reactance_ohm=[x]*len(frequencies),reference_impedance_ohm=50.)

    def test_comparison_capacitance_and_safe_denominators(self):
        old=self.result(0,-4)
        new=self.result(3,-8)
        row=s.compare_spatial_results(new,old)[0]
        self.assertEqual(row['delta_R_ohm'],3)
        self.assertEqual(row['delta_X_ohm'],-4)
        self.assertEqual(row['delta_Z_magnitude_ohm'],5)
        self.assertEqual(row['relative_Z_magnitude'],.1)
        self.assertEqual(row['relative_R'],3)
        self.assertEqual(row['relative_X'],1)
        self.assertAlmostEqual(row['delta_equivalent_capacitance_f'],-1/(16*math.pi*1e9),delta=1e-25)
        self.assertAlmostEqual(row['relative_equivalent_capacitance'],.5)
        self.assertEqual(s.compare_spatial_results(new,self.result(1e-20,-4))[0]['relative_R'],3)
        for x in (0,1):
            row=s.compare_spatial_results(self.result(3,x),old)[0]
            self.assertIsNone(row['delta_equivalent_capacitance_f'])
            self.assertIsNone(row['relative_equivalent_capacitance'])
        floor=s.compare_spatial_results(self.result(0,-2e20),self.result(0,-1e20))[0]
        self.assertAlmostEqual(floor['relative_equivalent_capacitance'],abs(floor['delta_equivalent_capacitance_f'])/1e-18)

    def test_gate_inclusive_boundaries_every_frequency(self):
        boundary=dict(relative_Z_magnitude=.01,relative_X=.01,relative_R=.05)
        self.assertTrue(s.engineering_gate([boundary,boundary]))
        self.assertFalse(s.engineering_gate([]))
        for key,value in boundary.items():
            self.assertFalse(s.engineering_gate([boundary,{**boundary,key:math.nextafter(value,math.inf)}]))
        # Nonmonotonicity is recorded, not a gate condition.
        pairs={name:[dict(frequency_hz=1e9,delta_Z_magnitude_ohm=v)]
               for name,v in zip(s.LEVEL_NAMES[1:],(5,2,3))}
        self.assertEqual(s.convergence_trend(pairs),[dict(frequency_hz=1e9,
            L2_change_smaller_than_L1=True,L3_change_smaller_than_L2=False)])

    def setUp(self):
        self.events=[]
        self.geometry=[]
        self.settings=[]
        self.paths=[]
        self.meshes={}
        self.reactances=(-100.,-110.,-114.,-114.5)

    def fake_mesh(self,g,settings):
        index=settings.min_port_gap_cells//2-1
        self.events.append(('mesh',index))
        mesh=SimpleNamespace(shape_cells=(10+index,20,30),cell_count=(10+index)*600,pml_cells=8,
                             min_step_m=.0001/(index+1),max_step_m=.005,worst_growth_ratio=1.4)
        self.meshes[index]=mesh
        return mesh

    def fake_run(self,g,settings,path):
        index=settings.min_port_gap_cells//2-1
        self.assertEqual(self.events[-1],('mesh',index))
        self.events.append(('run',index))
        self.geometry.append(g.as_dict());self.settings.append(asdict(settings));self.paths.append(path)
        (path/'native').mkdir(parents=True)
        (path/'native/model.xml').write_text('<fake/>')
        result=self.result(5.,self.reactances[index],settings.result_frequency_hz)
        result.update(s11_magnitude=[.99]*len(settings.result_frequency_hz),swr=[199.]*len(settings.result_frequency_hz),
                      mesh=vars(self.meshes[index]).copy())
        (path/'summary.json').write_text(json.dumps(result))
        (path/'impedance.csv').write_text('retained fake result')
        return result

    def test_study_reports_order_geometry_band_and_trend(self):
        bands=({},dict(excitation_center_hz=2.45e9,excitation_cutoff_hz=.4e9,
             result_frequency_hz=(2.2e9,2.45e9,2.7e9),loss_reference_frequency_hz=2.4e9),
             dict(excitation_center_hz=.9e9,excitation_cutoff_hz=.15e9,result_frequency_hz=(.8e9,.9e9,1e9)))
        for band in bands:
            self.setUp()
            with self.subTest(band=band),TemporaryDirectory() as directory:
                with patch.object(s,'make_pcb_domain_mesh',side_effect=self.fake_mesh),patch.object(s,'run_control_model',side_effect=self.fake_run),contextlib.redirect_stdout(io.StringIO()) as console:
                    study=s.run_spatial_study(directory,**band)
                self.assertEqual(self.events,[(stage,i) for i in range(4) for stage in ('mesh','run')])
                self.assertEqual(len(set(self.paths)),4)
                self.assertEqual([p.name for p in self.paths],list(s.LEVEL_NAMES))
                geometry,settings=make_synthetic_control_case(**band)
                self.assertTrue(all(g==geometry.as_dict() for g in self.geometry))
                for values in self.settings:
                    for key in ('result_frequency_hz','excitation_center_hz','excitation_cutoff_hz','loss_reference_frequency_hz'):
                        self.assertEqual(values[key],getattr(settings,key))
                self.assertTrue(study['candidate_spatially_converged'])
                self.assertEqual(study['status'],'diagnostic_candidate_converged')
                self.assertEqual(len(study['pairwise_comparisons']),3)
                for row in study['comparisons_to_finest']['L3_extra_fine']:
                    self.assertTrue(all(v==0 for k,v in row.items() if k!='frequency_hz'))
                self.assertTrue(all(row['L2_change_smaller_than_L1'] and row['L3_change_smaller_than_L2'] for row in study['convergence_trend']))
                self.assertEqual(study,json.loads((Path(directory)/'spatial_convergence.json').read_text()))
                json.dumps(study,allow_nan=False)
                with (Path(directory)/'spatial_convergence.csv').open(newline='') as stream: rows=list(csv.DictReader(stream))
                self.assertEqual(len(rows),4*len(settings.result_frequency_hz))
                self.assertEqual(rows[0]['delta_R_ohm_vs_previous'],'')
                self.assertIn('mesh: shape=',console.getvalue())
                self.assertIn('candidate spatial convergence: YES',console.getvalue())
                self.assertEqual(study['levels']['L2_fine']['impedance_ohm'][0],{'real':5.,'imag':-114.})
                with patch.object(s,'run_control_model') as runner:
                    with self.assertRaises(ConfigurationError): s.run_spatial_study(directory)
                    runner.assert_not_called()

    def test_not_converged_stops_at_four_and_nonmonotonic_is_not_error(self):
        self.reactances=(-100.,-110.,-114.,-150.)
        with TemporaryDirectory() as directory,patch.object(s,'make_pcb_domain_mesh',side_effect=self.fake_mesh),patch.object(s,'run_control_model',side_effect=self.fake_run),contextlib.redirect_stdout(io.StringIO()):
            study=s.run_spatial_study(directory)
        self.assertFalse(study['candidate_spatially_converged'])
        self.assertEqual(study['status'],'diagnostic_not_converged')
        self.assertFalse(study['convergence_trend'][0]['L3_change_smaller_than_L2'])
        self.assertEqual(len(self.paths),4)

    def test_resource_failure_before_native_preserves_earlier(self):
        for fail_at in (2,3):
            self.setUp()
            def preflight(g,settings):
                if settings.min_port_gap_cells==2*(fail_at+1):
                    raise ConfigurationError('cell_count exceeds max_cells')
                return self.fake_mesh(g,settings)
            with TemporaryDirectory() as directory,patch.object(s,'make_pcb_domain_mesh',side_effect=preflight),patch.object(s,'run_control_model',side_effect=self.fake_run),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ConfigurationError,'before native execution.*max_cells=20000000'):
                    s.run_spatial_study(directory)
                study=json.loads((Path(directory)/'spatial_convergence.json').read_text())
                self.assertEqual(study['status'],'failed')
                self.assertEqual(len(self.paths),fail_at)
                self.assertEqual(study['levels'][s.LEVEL_NAMES[fail_at]]['status'],'failed')
                for path in self.paths: self.assertTrue((path/'native/model.xml').exists())
                with (Path(directory)/'spatial_convergence.csv').open(newline='') as stream:
                    self.assertEqual(len(list(csv.DictReader(stream))),fail_at*3)

    def test_native_failure_interrupt_and_geometry_mutation(self):
        for fault in ('native','interrupt','geometry'):
            self.setUp()
            def runner(g,settings,path):
                if path.name=='L2_fine':
                    if fault=='native': raise RuntimeError('native failure')
                    if fault=='interrupt': raise KeyboardInterrupt()
                    g.assumptions.append('unexpected mutation')
                return self.fake_run(g,settings,path)
            with TemporaryDirectory() as directory,patch.object(s,'make_pcb_domain_mesh',side_effect=self.fake_mesh),patch.object(s,'run_control_model',side_effect=runner),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises((RuntimeError,KeyboardInterrupt,ConfigurationError)): s.run_spatial_study(directory)
                study=json.loads((Path(directory)/'spatial_convergence.json').read_text())
                self.assertEqual(study['status'],'failed')
                self.assertEqual(study['levels']['L1_medium']['status'],'completed')
                self.assertEqual(study['levels']['L3_extra_fine']['status'],'pending')

    def test_cli_unique_directories_hz_and_errors(self):
        cwd=Path.cwd()
        with TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch.object(s,'run_spatial_study',return_value={'status':'diagnostic_not_converged'}) as runner,contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(s.main([]),0)
                    self.assertEqual(s.main([]),0)
                    self.assertNotEqual(runner.call_args_list[0].args[0],runner.call_args_list[1].args[0])
                    self.assertEqual(s.main(['--output','custom','--center-mhz','2450','--cutoff-mhz','400',
                        '--frequencies-mhz','2200','2450','2700','--loss-reference-mhz','2400']),0)
                    self.assertEqual(runner.call_args.kwargs,dict(excitation_center_hz=2.45e9,
                        excitation_cutoff_hz=.4e9,result_frequency_hz=(2.2e9,2.45e9,2.7e9),loss_reference_frequency_hz=2.4e9))
                with patch.object(s,'run_control_model') as native,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(s.main(['--center-mhz','0']),1)
                    native.assert_not_called()
            finally: os.chdir(cwd)


if __name__=='__main__': unittest.main()
