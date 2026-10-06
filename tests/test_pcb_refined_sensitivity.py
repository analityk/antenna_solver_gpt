"""Refined experiment tests: real Python pipeline, fake native binaries only."""
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

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import refined_sensitivity as r
from antenna_lab.pcb.control import make_synthetic_control_case
from test_openems_pcb import CSX
from test_pcb_edge_convergence import RunEngine


class RefinedTests(unittest.TestCase):
    def result(self, z, frequencies=(1e9,)):
        z = complex(z)
        return dict(frequency_hz=list(frequencies), reference_impedance_ohm=50.,
                    resistance_ohm=[z.real]*len(frequencies), reactance_ohm=[z.imag]*len(frequencies))

    def decomposition(self, dw, dp, ds, dc):
        base = self.result(10-100j)
        comparisons = {name: r.compare_to_reference(self.result(10-100j+delta), base)
                      for name, delta in zip(r.VARIANT_NAMES[1:], (dw, dp, ds, dc))}
        rows, overall = r.decompose_comparisons(comparisons)
        return rows[0], overall

    def test_exact_variants_only_one_factor_settings_and_no_mutation(self):
        _, base = make_synthetic_control_case()
        before = asdict(base)
        variants = r.make_refined_variants(base)
        self.assertEqual([name for name, _ in variants], list(r.VARIANT_NAMES))
        reference = asdict(variants[0][1])
        self.assertEqual((reference['cells_per_wavelength'], reference['min_port_gap_cells'],
                          reference['min_port_width_cells'], reference['min_substrate_cells_z']), (40,6,6,12))
        expected = ({}, {'cells_per_wavelength':50}, {'min_port_gap_cells':8, 'min_port_width_cells':8},
                    {'min_substrate_cells_z':16}, {'cells_per_wavelength':50, 'min_port_gap_cells':8,
                                                  'min_port_width_cells':8, 'min_substrate_cells_z':16})
        for (_, settings), change in zip(variants, expected):
            self.assertEqual({k:v for k,v in asdict(settings).items() if v != reference[k]}, change)
            for k in ('air_padding_wavelengths', 'pml_cells', 'end_criteria', 'max_timesteps',
                      'growth_ratio_target', 'growth_ratio_limit', 'reference_impedance_ohm', 'max_cells'):
                self.assertEqual(getattr(settings,k), getattr(base,k))
        self.assertEqual(variants, r.make_refined_variants(base))
        self.assertEqual(before, asdict(base))
        limited = replace(base, max_cells=1234)
        self.assertTrue(all(s.max_cells == 1234 for _,s in r.make_refined_variants(limited)))

    def test_complex_comparison_safe_denominators_and_capacitance(self):
        row = r.compare_to_reference(self.result(3-8j), self.result(-4j))[0]
        self.assertEqual(row['delta_Z_ohm'], {'real':3.,'imag':-4.})
        self.assertEqual(row['delta_Z_magnitude_ohm'],5.)
        self.assertEqual((row['relative_R'],row['relative_X'],row['relative_Z_magnitude']),(3.,1.,.1))
        self.assertAlmostEqual(row['delta_equivalent_capacitance_f'],-1/(16*math.pi*1e9),delta=1e-25)
        for x in (0,1):
            self.assertIsNone(r.compare_to_reference(self.result(3+x*1j),self.result(-4j))[0]['delta_equivalent_capacitance_f'])
        with self.assertRaises(ValueError):
            r.compare_to_reference(self.result(complex(float('nan'),0)),self.result(1))

    def test_vector_sum_interaction_and_unforced_fractions(self):
        row, _ = self.decomposition(3+4j, -2-3j, 1-1j, 4+2j)
        self.assertEqual(row['dZ_linear_sum_ohm'], {'real':2.,'imag':0.})
        self.assertEqual(row['interaction_residual_ohm'], {'real':2.,'imag':2.})
        self.assertAlmostEqual(row['relative_interaction_residual'],math.sqrt(8/20))
        self.assertEqual(row['abs_dZ_wave_ohm'],5.)
        row, _ = self.decomposition(10, -9, 1, 2)
        self.assertEqual(row['abs_interaction_residual_ohm'],0.)
        self.assertEqual(row['wave_fraction_of_combined']+row['port_fraction_of_combined']+
                         row['substrate_fraction_of_combined'],10.)
        row, label = self.decomposition(.25, 0, 0, .25)
        self.assertEqual(row['diagnostic_denominator_ohm'],1.)
        self.assertEqual(row['wave_fraction_of_combined'],.25)
        self.assertEqual(label,'wavelength_dominated')
        row, label = self.decomposition(0,0,0,0)
        self.assertEqual(label,'mixed')
        self.assertEqual(row['relative_interaction_residual'],0.)

    def test_classifications_and_strict_thresholds(self):
        for increments, expected in (((4,1,1,6),'wavelength_dominated'),
                                     ((1,4,1,6),'port_dominated'),
                                     ((1,1,4,6),'substrate_z_dominated'),
                                     ((10,9.5,0,19.5),'mixed'),
                                     ((1,4,1,1),'strong_interaction')):
            with self.subTest(expected=expected):
                self.assertEqual(self.decomposition(*increments)[1],expected)
        self.assertEqual(self.decomposition(10,9,0,19)[1],'wavelength_dominated')  # exactly 10%
        row, _ = self.decomposition(1,0,0,2)  # exactly 50%: not strong
        self.assertFalse(row['strong_interaction'])
        self.assertTrue(self.decomposition(.1,0,0,0)[0]['strong_interaction'])
        self.assertTrue(self.decomposition(.1,0,0,.3)[0]['strong_interaction'])  # no 1-ohm floor here
        base = self.result(10-100j, (1e9,2e9))
        comparisons = {}
        for name, values in zip(r.VARIANT_NAMES[1:], ((4,1),(1,4),(1,1),(6,6))):
            value = self.result(10-100j, (1e9,2e9))
            value['resistance_ohm'] = [10+d for d in values]
            comparisons[name] = r.compare_to_reference(value,base)
        self.assertEqual(r.decompose_comparisons(comparisons)[1],'mixed')
        comparisons[r.VARIANT_NAMES[-1]][1]['delta_R_ohm']=.1
        self.assertEqual(r.decompose_comparisons(comparisons)[1],'strong_interaction')

    @contextlib.contextmanager
    def fake_native(self, factory=None):
        self.engines = []
        self.structures = []
        def engine_factory(**kw):
            index = len(self.engines)
            engine = (factory(index,kw) if factory else
                      RunEngine(reactance=(-500,-501,-505,-502,-508)[index], **kw))
            self.engines.append(engine)
            return engine
        def csx_factory():
            csx = CSX()
            self.structures.append(csx)
            return csx
        with patch('antenna_lab.solvers.openems.native_modules', return_value=(
                SimpleNamespace(openEMS=engine_factory), SimpleNamespace(ContinuousStructure=csx_factory))),\
                contextlib.redirect_stdout(io.StringIO()):
            yield

    def test_full_pipeline_metadata_frequencies_geometry_and_csv(self):
        for band in ({}, dict(excitation_center_hz=2.45e9, excitation_cutoff_hz=.4e9,
                             result_frequency_hz=(2.2e9,2.45e9,2.7e9),loss_reference_frequency_hz=2.4e9)):
            geometry, baseline = make_synthetic_control_case(**band)
            identity = geometry.as_dict()
            seen = []
            real = r.run_control_model
            def run(g,s,path,**kw):
                self.assertIs(g,geometry)
                self.assertEqual(g.as_dict(),identity)
                self.assertEqual(kw,dict(port_edge_mode='thirds',exact_endcriteria=True,dump_statistics=True))
                seen.append(path.name)
                return real(g,s,path,**kw)
            with TemporaryDirectory() as d, self.fake_native(),\
                    patch.object(r,'make_synthetic_control_case',return_value=(geometry,baseline)) as make,\
                    patch.object(r,'run_control_model',side_effect=run):
                study = r.run_refined_study(d,**band)
                make.assert_called_once_with(**band)
                self.assertEqual(seen,list(r.VARIANT_NAMES))
                self.assertEqual(len(self.engines),5)
                self.assertEqual(geometry.as_dict(),identity)
                self.assertEqual(study['status'],'diagnostic_pending_review')
                self.assertEqual(study['overall_classification'],'port_dominated')
                self.assertEqual(len(study['dominant_factor_by_frequency']),3)
                self.assertEqual(len(study['interaction_strength_by_frequency']),3)
                self.assertEqual(study['vector_decomposition'][0]['abs_interaction_residual_ohm'],0.)
                self.assertEqual(study['combined_comparison'][0]['delta_X_ohm'],-8.)
                for i,(name,variant) in enumerate(study['variants'].items()):
                    self.assertEqual(variant['edge_mode'],'thirds')
                    self.assertEqual(variant['edge_policy']['mode'],'thirds')
                    self.assertTrue(all(k in variant['edge_policy'] for k in ('edge_resolution_x','edge_resolution_y',
                        'physical_x_edges','physical_y_edges','x_hints','y_hints')))
                    self.assertGreater(variant['mesh']['cell_count'],0)
                    for key in r.PORT_KEYS:
                        self.assertEqual(variant['port'][key],variant['result']['preparation']['port'][key])
                        self.assertGreater(variant['port'][key],0)
                    self.assertEqual(variant['result']['frequency_hz'],list(baseline.result_frequency_hz))
                    for key in r.FREQUENCY_KEYS:
                        self.assertEqual(variant['settings'][key],study['frequency_configuration'][key])
                    engine = self.engines[i]
                    run_calls = [c for c in engine.calls if c[0]=='Run']
                    self.assertEqual(len(run_calls),1)
                    self.assertEqual(run_calls[0][2],dict(cleanup=False,numThreads=0,exact_endcriteria=True,dump_statistics=True))
                    self.assertEqual(engine.port.calls[0][1].tolist(),list(baseline.result_frequency_hz))
                    # Unsupported field/NF2FF/power calls fail in these narrow native fakes.
                    self.assertTrue(all(c[0] in ('SetCSX','AddLumpedPort','SetGaussExcite','SetBoundaryCond','Write2XML','Run')
                                        for c in engine.calls))
                    self.assertTrue((Path(d)/name/'native/openEMS_stats.txt').is_file())
                    self.assertTrue((Path(d)/name/'summary.json').is_file())
                self.assertTrue(all(c.metals[0][1].polygons==self.structures[0].metals[0][1].polygons for c in self.structures))
                saved = (Path(d)/'refined_sensitivity.json').read_text()
                self.assertEqual(study,json.loads(saved,parse_constant=lambda s:self.fail(s)))
                json.dumps(study,allow_nan=False)
                with (Path(d)/'refined_sensitivity.csv').open(newline='') as stream:
                    rows=list(csv.DictReader(stream))
                self.assertEqual(len(rows),15)
                self.assertEqual(rows[-1]['number_of_iterations'],'12345')
                self.assertEqual(rows[-1]['delta_X_vs_L2'],'-8.0')
                self.assertEqual(json.loads(rows[-1]['delta_Z_vs_L2']),{'real':0.,'imag':-8.})
                self.assertEqual(float(rows[0]['delta_R_vs_L2']),0.)
                self.assertEqual(float(rows[0]['equivalent_capacitance_f']),1/(2*math.pi*baseline.result_frequency_hz[0]*500))
                with patch.object(r,'run_control_model') as native:
                    with self.assertRaises(ConfigurationError): r.run_refined_study(d)
                    native.assert_not_called()

    def test_preflight_failure_never_calls_native(self):
        for target in ('make_pcb_domain_mesh','resolve_pcb_lumped_port'):
            with TemporaryDirectory() as d, patch.object(r,target,side_effect=ConfigurationError('preflight failed')),\
                    patch.object(r,'run_control_model') as native, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ConfigurationError,'preflight failed'): r.run_refined_study(d)
                native.assert_not_called()
                study=json.loads((Path(d)/'refined_sensitivity.json').read_text())
                self.assertEqual(study['status'],'failed')
                self.assertEqual(study['variants'][r.VARIANT_NAMES[0]]['status'],'failed')

    def test_temporal_failure_preserves_prior_results_and_no_comparison(self):
        def factory(i,kw):
            return RunEngine(iterations=100000 if i==2 else 12345,**kw)
        with TemporaryDirectory() as d, self.fake_native(factory):
            with self.assertRaisesRegex(ConfigurationError,'temporal termination'): r.run_refined_study(d)
            study=json.loads((Path(d)/'refined_sensitivity.json').read_text())
            self.assertEqual(study['status'],'failed')
            self.assertEqual(len(self.engines),3)
            self.assertEqual(self.engines[2].port.calls,[])
            self.assertNotIn(r.VARIANT_NAMES[2],study['comparisons_to_L2'])
            self.assertEqual(study['vector_decomposition'],[])
            self.assertEqual(study['variants'][r.VARIANT_NAMES[1]]['status'],'completed')
            self.assertEqual(study['variants'][r.VARIANT_NAMES[3]]['status'],'pending')
            self.assertTrue((Path(d)/r.VARIANT_NAMES[0]/'summary.json').is_file())
            self.assertTrue((Path(d)/r.VARIANT_NAMES[2]/'native/openEMS_stats.txt').is_file())
            with (Path(d)/'refined_sensitivity.csv').open(newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))),6)

    def test_native_failure_and_mutation_or_metadata_mismatch_preserve_results(self):
        real=r.run_control_model
        for fault in ('native','geometry','mesh','port','settings','nan','flags','statistics','nonfinite_metadata'):
            def runner(g,s,path,**kw):
                if path.name==r.VARIANT_NAMES[2] and fault=='native':
                    (path/'native').mkdir(parents=True)
                    (path/'native/retained.txt').write_text('partial native output')
                    raise RuntimeError('native failure')
                result=real(g,s,path,**kw)
                if path.name==r.VARIANT_NAMES[2]:
                    if fault=='geometry': g.assumptions.append('unexpected mutation')
                    elif fault=='mesh': result['mesh']['cell_count']+=1
                    elif fault=='port': result['preparation']['port']['x_cell_count']+=1
                    elif fault=='settings': result['simulation_settings']['reference_impedance_ohm']=75.
                    elif fault=='nan': result['resistance_ohm'][0]=float('nan')
                    elif fault=='flags': result['run_options']['exact_endcriteria']=False
                    elif fault=='statistics': del result['native_statistics']
                    elif fault=='nonfinite_metadata': result['extra']=float('inf')
                return result
            with self.subTest(fault=fault), TemporaryDirectory() as d, self.fake_native(),patch.object(r,'run_control_model',side_effect=runner):
                with self.assertRaises((RuntimeError,ConfigurationError,KeyError,ValueError)): r.run_refined_study(d)
                study=json.loads((Path(d)/'refined_sensitivity.json').read_text(),parse_constant=lambda s:self.fail(s))
                self.assertEqual(study['status'],'failed')
                self.assertEqual(study['variants'][r.VARIANT_NAMES[2]]['status'],'failed')
                self.assertEqual(study['variants'][r.VARIANT_NAMES[1]]['status'],'completed')
                self.assertIsNone(study['overall_classification'])
                self.assertEqual(len(study['comparisons_to_L2']),2)
                self.assertTrue((Path(d)/r.VARIANT_NAMES[1]/'summary.json').exists())
                self.assertTrue((Path(d)/r.VARIANT_NAMES[2]/'native').exists())

    def test_real_resource_guard_and_statistics_are_mandatory(self):
        g,base=make_synthetic_control_case()
        with TemporaryDirectory() as d, patch.object(r,'make_synthetic_control_case',return_value=(g,replace(base,max_cells=1))),\
                patch.object(r,'run_control_model') as native,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ConfigurationError): r.run_refined_study(d)
            native.assert_not_called()
        class BadStatisticsEngine(RunEngine):
            def Run(self,path,**kw):
                value=super().Run(path,**kw)
                stats=Path(path)/'openEMS_stats.txt'
                stats.write_text(stats.read_text().replace('12345\t','0\t'))
                return value
        with TemporaryDirectory() as d,self.fake_native(lambda i,kw:BadStatisticsEngine(**kw)):
            with self.assertRaisesRegex(ConfigurationError,'temporal termination'): r.run_refined_study(d)
            self.assertEqual(len(self.engines),1)
            self.assertEqual(self.engines[0].port.calls,[])
            study=json.loads((Path(d)/'refined_sensitivity.json').read_text())
            self.assertEqual(study['comparisons_to_L2'],{})
            self.assertEqual(study['status'],'failed')

    def test_cli_unique_directories_frequency_conversion_and_failure(self):
        cwd=Path.cwd()
        with TemporaryDirectory() as d:
            try:
                os.chdir(d)
                with patch.object(r,'run_refined_study',return_value=dict(status='diagnostic_pending_review',overall_classification='mixed')) as run,contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(r.main([]),0)
                    self.assertEqual(r.main([]),0)
                    self.assertNotEqual(run.call_args_list[0].args[0],run.call_args_list[1].args[0])
                    self.assertEqual(run.call_args.args[0].parent,Path('outcomes/pcb_refined_sensitivity').resolve())
                    self.assertEqual(r.main(['--output','other','--center-mhz','900','--cutoff-mhz','150',
                        '--frequencies-mhz','800','900','1000','--loss-reference-mhz','850']),0)
                    self.assertEqual(run.call_args.kwargs,dict(excitation_center_hz=.9e9,excitation_cutoff_hz=.15e9,
                        result_frequency_hz=(.8e9,.9e9,1e9),loss_reference_frequency_hz=.85e9))
                with patch.object(r,'run_control_model') as native,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(r.main(['--center-mhz','0']),1)
                    native.assert_not_called()
            finally:
                os.chdir(cwd)


if __name__=='__main__':
    unittest.main()
