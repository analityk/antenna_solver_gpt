"""Runtime profiles and CLI approval. Only local fakes; no native FDTD."""
import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.profiles import DEFAULT_CONFIG, load_profiles, resolve_profile, parse_override
from antenna_lab.solvers.runtime import native_engine_settings, native_boundaries
from antenna_lab.pcb.profile_cli import approve_profile, print_profile
from antenna_lab.pcb.gerber_quality import gerber_cost_preflight, require_excitation_fits
from antenna_lab.pcb import gerber_control
from antenna_lab.pcb.control import make_synthetic_control_case
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model, run_pcb_fdtd
from test_openems_pcb import CSX, XmlEngine
from test_pcb_control import Port
from test_pcb_edge_convergence import RunEngine


class ProfilesTests(unittest.TestCase):
    def test_exact_profiles_external_defaults(self):
        expected=[(10.,2,2,.10,6,1e-3,False),(15.,3,2,.15,6,1e-4,False),(20.,4,4,.25,8,1e-5,True)]
        for name, row in zip(('preview','design','verify'),expected):
            p=resolve_profile(name);s=p.settings;r=s.runtime
            self.assertEqual((s.cells_per_wavelength,s.min_substrate_cells_z,s.min_port_gap_cells,
                s.air_padding_wavelengths,s.pml_cells,s.end_criteria,r.exact_endcriteria),row)
            self.assertEqual(s.min_port_gap_cells,s.min_port_width_cells)
            self.assertEqual(s.max_timesteps,1_000_000_000)
            self.assertEqual((r.oversampling,r.time_step_s,r.time_step_factor,r.time_step_method),(4,0.,1.,3))
            self.assertEqual((s.threads,r.engine,r.verbose,r.dump_statistics,r.disable_dumps),(0,'fastest',0,True,False))
            self.assertEqual(r.report_phase_step_deg,15)
            self.assertEqual(p.field_frequency_hz,(s.excitation_center_hz,))
            self.assertEqual(native_boundaries(s),(f'PML_{s.pml_cells}',)*6)
        self.assertEqual(resolve_profile().name,'design')
        self.assertEqual(resolve_profile(),resolve_profile())

    def test_missing_invalid_schema_unknown_keys_and_profile(self):
        with self.assertRaises(ConfigurationError):load_profiles('/missing/profile.toml')
        with self.assertRaises(ConfigurationError):resolve_profile('unknown')
        with TemporaryDirectory() as d:
            path=Path(d)/'p.toml';text=DEFAULT_CONFIG.read_text()
            for bad in (text.replace('schema_version = 1','schema_version = 2'),
                        text+'\nmisspelled = 1\n', text.replace('max_cells = 20000000','max_cells = true'),
                        text.replace('time_step_factor = 1.0','time_step_factor = nan')):
                path.write_text(bad)
                with self.subTest(bad=bad[:40]),self.assertRaises(ConfigurationError):load_profiles(path)

    def test_validation_all_runtime_controls(self):
        invalid={'time_step_factor':[0,-1,1.1,float('nan'),True], 'time_step_s':[-1,float('inf')],
                 'max_time_s':[-1,1e-15], 'time_step_method':[0,2,True], 'oversampling':[0,2.2],
                 'verbose':[4,True], 'num_threads':[-1,False], 'dump_statistics':[1],
                 'disable_dumps':['false'], 'engine':['bogus'], 'report_phase_step_deg':[0,20],
                 'field_frequency_policy':['sweep'], 'boundary_conditions':[['PML']*5,['BAD']*6]}
        for key, values in invalid.items():
            for value in values:
                with self.subTest(key=key,value=value),self.assertRaises(ConfigurationError):
                    resolve_profile(cli_overrides={key:value})
        with self.assertRaisesRegex(ConfigurationError,'CFL'):
            resolve_profile(cli_overrides={'time_step_s':1e-15})

    def test_external_file_changes_defaults_and_hash_not_source(self):
        with TemporaryDirectory() as d:
            path=Path(d)/'profiles.toml';path.write_text(DEFAULT_CONFIG.read_text().replace('default_profile = "design"','default_profile = "preview"').replace('cells_per_wavelength = 10.0','cells_per_wavelength = 8.0'))
            p=resolve_profile(config_path=path)
            self.assertEqual(p.settings.cells_per_wavelength,8.)
            self.assertEqual(p.name,'preview')
            self.assertNotEqual(p.metadata['config_sha256'],resolve_profile().metadata['config_sha256'])

    def test_fields_default_explicit_optout_conflicts(self):
        experiment=dict(excitation_center_hz=2e9,excitation_cutoff_hz=1e9)
        self.assertEqual(resolve_profile(experiment=experiment).field_frequency_hz,(2e9,))
        self.assertEqual(resolve_profile(no_fields=True).field_frequency_hz,())
        self.assertEqual(resolve_profile(field_frequency_hz=(1.4e9,)).field_frequency_hz,(1.4e9,))
        self.assertEqual(resolve_profile(cli_overrides={'fields_default':False}).field_frequency_hz,())
        for kw in (dict(no_fields=True,field_frequency_hz=(1.4e9,)),dict(cli_overrides={'disable_dumps':True}),
                   dict(field_frequency_hz=(9e9,)),dict(field_frequency_hz=(1.4e9,1.4e9))):
            with self.assertRaises(ConfigurationError):resolve_profile(**kw)
        self.assertTrue(resolve_profile(no_fields=True,cli_overrides={'disable_dumps':True}).settings.runtime.disable_dumps)

    def test_override_types_precedence_and_metadata(self):
        cli=dict(parse_override(s) for s in ('cells_per_wavelength=8','engine=basic','result_frequency_hz=[1.3e9,1.5e9]'))
        p=resolve_profile('preview',cli_overrides=cli,interactive_overrides={'cells_per_wavelength':9})
        self.assertEqual(p.settings.cells_per_wavelength,9)
        self.assertEqual(p.settings.runtime.engine,'basic')
        self.assertEqual(p.settings.result_frequency_hz,(1.3e9,1.5e9))
        self.assertEqual(p.metadata['cli_overrides'],cli)
        self.assertEqual(p.metadata['interactive_overrides'],{'cells_per_wavelength':9})
        json.dumps(p.metadata,allow_nan=False)
        for text in ('unknown=2','max_cells=yes','cells_per_wavelength='):
            with self.assertRaises(ConfigurationError):parse_override(text)

    def test_y_n_e_and_file_unchanged(self):
        before=DEFAULT_CONFIG.read_bytes()
        with patch('sys.stdin.isatty',return_value=True),contextlib.redirect_stdout(io.StringIO()) as output:
            with patch('builtins.input',side_effect=['e','cells_per_wavelength','8','end_criteria','0.01','max_time_s','2e-8','','y']):
                p=approve_profile(dict(name='preview'))
            self.assertEqual(p.settings.cells_per_wavelength,8)
            self.assertEqual(p.settings.end_criteria,.01)
            self.assertEqual(p.settings.runtime.max_time_s,2e-8)
            self.assertEqual(p.metadata['confirmation_mode'],'interactive_yes')
            with patch('builtins.input',return_value='n'):
                self.assertIsNone(approve_profile({}))
        self.assertIn('physical simulated time',output.getvalue())
        self.assertIn('approximate df',output.getvalue())
        self.assertEqual(DEFAULT_CONFIG.read_bytes(),before)

    def test_invalid_edit_is_not_applied(self):
        with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',side_effect=['e','time_step_factor','2','','y']),contextlib.redirect_stdout(io.StringIO()):
            p=approve_profile({})
        self.assertEqual(p.settings.runtime.time_step_factor,1.)
        self.assertEqual(p.metadata['interactive_overrides'],{})

    def test_noninteractive_yes_prepare_and_library_never_prompt(self):
        with patch('sys.stdin.isatty',return_value=False),patch('builtins.input',side_effect=AssertionError('prompt')),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ConfigurationError,'--yes'):approve_profile({})
            self.assertEqual(approve_profile({},yes=True).metadata['confirmation_mode'],'yes_flag')
            self.assertEqual(approve_profile({},prepare_only=True).metadata['confirmation_mode'],'prepare_only')
            self.assertEqual(resolve_profile().metadata['confirmation_mode'],'library_api')

    def test_cli_cancel_and_no_tty_stop_before_pipeline(self):
        with patch.object(gerber_control,'run_gerber_control') as run,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',return_value='n'):
                self.assertEqual(gerber_control.main(['missing']),0)
            with patch('sys.stdin.isatty',return_value=False):self.assertEqual(gerber_control.main(['missing']),1)
            run.assert_not_called()

    def test_cli_yes_prepare_and_frequency_edits_reach_pipeline(self):
        with TemporaryDirectory() as d,patch.object(gerber_control,'run_gerber_control',return_value={'status':'prepared'}) as run,contextlib.redirect_stdout(io.StringIO()),patch('builtins.input',side_effect=AssertionError('prompt')):
            self.assertEqual(gerber_control.main(['missing','--output',d,'--prepare-only','--center-mhz','2000','--cutoff-mhz','1000',
                '--openems-set','end_criteria=0.01']),0)
            p=run.call_args.kwargs['resolved_profile'];self.assertEqual(p.field_frequency_hz,(2e9,));self.assertEqual(p.settings.end_criteria,.01)
            self.assertEqual(gerber_control.main(['missing','--output',d,'--yes','--no-fields']),0)
            self.assertEqual(run.call_args.kwargs['resolved_profile'].field_frequency_hz,())

    def test_cfl_max_time_and_explicit_nrts_preflight(self):
        g,_=make_synthetic_control_case();s=resolve_profile('preview',no_fields=True).settings
        mesh=make_pcb_domain_mesh(g,s);cost=gerber_cost_preflight(mesh,s)
        require_excitation_fits(cost,s)
        with self.assertRaises(ConfigurationError):require_excitation_fits(cost,replace(s,max_timesteps=1))
        fixed=replace(s,runtime=replace(s.runtime,time_step_method=1,time_step_s=cost['estimated_cfl_dt_s']/2,time_step_factor=.5,max_time_s=2e-8))
        options=native_engine_settings(fixed,mesh)
        self.assertEqual(options['TimeStep'],fixed.runtime.time_step_s)
        self.assertEqual(options['MaxTime'],2e-8)
        self.assertGreater(gerber_cost_preflight(mesh,fixed)['estimated_excitation_steps'],cost['estimated_excitation_steps'])
        with self.assertRaisesRegex(ConfigurationError,'stability'):
            native_engine_settings(replace(fixed,runtime=replace(fixed.runtime,time_step_s=1.)),mesh)
        self.assertNotIn('MaxTime',native_engine_settings(s,mesh))
        self.assertNotIn('TimeStep',native_engine_settings(s,mesh))

    def test_native_constructor_bc_runtime_and_no_mesh_change(self):
        g,_=make_synthetic_control_case();p=resolve_profile(no_fields=True,cli_overrides={'max_time_s':2e-8,'oversampling':8,
                'time_step_factor':.8,'time_step_method':1,'engine':'basic','num_threads':2,'verbose':2,
                'boundary_conditions':['PML','MUR','PEC','PMC','PML','PML'],'dump_statistics':False})
        s=p.settings;csx=CSX();engine=XmlEngine();constructor=[]
        def create(**kw):constructor.append(kw);return engine
        with TemporaryDirectory() as d,patch('antenna_lab.solvers.openems.native_modules',return_value=(SimpleNamespace(openEMS=create),SimpleNamespace(ContinuousStructure=lambda:csx))):
            _,_,_,mesh,_,meta=prepare_pcb_xml_model(g,s,Path(d)/'model.xml')
            self.assertEqual(constructor,[dict(NrTS=10**9,EndCriteria=1e-4,MaxTime=2e-8,OverSampling=8,TimeStepFactor=.8,TimeStepMethod=1)])
            self.assertEqual(meta['boundary_conditions']['values'],['PML_6','MUR','PEC','PMC','PML_6','PML_6'])
            self.assertEqual(meta['engine']['native_constructor'],constructor[0])
            self.assertEqual(mesh,make_pcb_domain_mesh(g,replace(s,runtime=None)))
            native=RunEngine();port=Port()
            result=run_pcb_fdtd(native,csx,port,mesh,s,d)
            self.assertEqual(len(native.calls),1)
            opts=native.calls[0][2]
            for key,value in dict(numThreads=2,engine='basic',verbose=2,dump_statistics=False,disable_dumps=False).items():self.assertEqual(opts[key],value)
            self.assertEqual(len(port.calls),1)

    def test_report_profile_metadata_and_phase_default_override(self):
        from antenna_lab.visualization.report import render_html
        # Rendering is tested using saved-file report fixtures elsewhere; here
        # intercept field presentation without producing thousands of images.
        from antenna_lab.visualization import report
        with TemporaryDirectory() as d:
            root=Path(d);(root/'fields').mkdir();(root/'fields/metadata.json').write_text('{}')
            data=dict(is_pcb=True,root=root,run_id='profile',reference=50,target_mhz=1420,
                      variant_name='profile',spectrum={'r':[50], 'x':[0], 'frequency_mhz':[1420], 'source':'fixture'},summary={'report_phase_step_deg':15},warnings=[],geometry={})
            with patch.object(report,'_pcb_geometry',return_value=''),patch.object(report,'_pcb_spectrum',return_value=''),patch.object(report,'_pcb_metadata',return_value=''),patch.object(report,'_pcb_diagnostics',return_value=''),patch('antenna_lab.visualization.pcb_stackup.stackup_section',return_value=''),patch('antenna_lab.visualization.pcb_drills.drill_section',return_value=''),patch('antenna_lab.visualization.pcb_components.component_section',return_value=''),patch('antenna_lab.visualization.fields.field_section',return_value='') as fields:
                render_html(data);self.assertEqual(fields.call_args.args[3],15)
                render_html(data,phase_step=30);self.assertEqual(fields.call_args.args[3],30)

    def test_default_fields_single_fake_solve_saved_metadata_and_report_phase(self):
        from test_pcb_gerber import GerberTests
        from test_pcb_fields import FieldCSX, FieldEngine
        fixture=GerberTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        csx=FieldCSX();engine=FieldEngine(csx)
        out=fixture.root/'profile_run'
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=lambda:csx))), \
                patch('antenna_lab.visualization.report.generate_report',return_value=out/'report.html') as report, \
                patch('builtins.input',side_effect=AssertionError('API must not prompt')), \
                contextlib.redirect_stdout(io.StringIO()):
            result=gerber_control.run_gerber_control(fixture.config_path,out,quality='preview')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['openems_profile']['resolved_settings']['max_timesteps'],10**9)
        self.assertEqual(result['openems_profile']['confirmation_mode'],'library_api')
        self.assertEqual(result['fields']['frequency_hz'],[1.42e9])
        self.assertEqual(len([c for c in engine.calls if c[0]=='Run']),1)
        self.assertEqual(len(engine.port.calls),1)
        self.assertEqual(report.call_args.kwargs['phase_step'],15)
        self.assertEqual(result,json.loads((out/'summary.json').read_text()))
        self.assertEqual(len(csx.dumps),6)
        self.assertTrue(all(d['frequency']==[1.42e9] for d in csx.dumps))
        from antenna_lab.visualization.report import _pcb_metadata
        html=_pcb_metadata(dict(summary=result,root=out,geometry=json.loads((out/'geometry.json').read_text()),warnings=[]))
        self.assertIn(result['openems_profile']['config_sha256'],html)
        self.assertIn('1000000000',html)

    def test_no_statistics_not_claimed_completed_and_max_time_cannot_fake_convergence(self):
        from test_pcb_gerber import GerberTests
        fixture=GerberTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        out=fixture.root/'no_stats';engine=RunEngine();csx=CSX()
        profile=resolve_profile('preview',no_fields=True,cli_overrides={'dump_statistics':False})
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=lambda:csx))), \
                patch('antenna_lab.visualization.report.generate_report',return_value=out/'report.html'), \
                contextlib.redirect_stdout(io.StringIO()):
            result=gerber_control.run_gerber_control(fixture.config_path,out,resolved_profile=profile)
        self.assertEqual(result['status'],'finished_unverified')
        self.assertEqual(result['termination_status'],'not_established_statistics_disabled')
        self.assertIsNone(result['actual_iterations'])
        self.assertFalse(result['run_options']['dump_statistics'])
        # Recorded physical duration at/near MaxTime must stop before CalcPort.
        g,_=make_synthetic_control_case()
        settings=resolve_profile(no_fields=True,cli_overrides={'max_time_s':2e-8}).settings
        mesh=make_pcb_domain_mesh(g,settings);port=Port()
        lines=dict(zip('xyz',(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)))
        csx=SimpleNamespace(GetGrid=lambda:SimpleNamespace(GetDeltaUnit=lambda:1.,GetLines=lambda a:lines[a]))
        with TemporaryDirectory() as d:
            (Path(d)/'model.xml').write_text('<model/>')
            with patch('antenna_lab.solvers.openems_pcb.read_pcb_native_statistics',return_value={
                    'number_of_iterations':20000,'fdtd_timestep_s':1e-12,'total_numerical_time_s':2e-8}):
                with self.assertRaisesRegex(ConfigurationError,'MaxTime'):
                    run_pcb_fdtd(RunEngine(),csx,port,mesh,settings,d)
        self.assertEqual(port.calls,[])


if __name__=='__main__':unittest.main()
