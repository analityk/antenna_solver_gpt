"""D4 -> existing full-wave seams. No native modules or real FDTD execution."""
from contextlib import ExitStack, redirect_stdout
from dataclasses import asdict
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import easyeda_control as runner
from antenna_lab.pcb.easyeda_project import load_easyeda_project,materialize_project_source
from antenna_lab.pcb.easyeda_model import build_source_layout,source_layout_geometry
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.geometry_resolution import apply_geometry_resolution
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from antenna_lab.solvers.profiles import resolve_profile
from test_pcb_easyeda_project import write_project


class EasyEdaControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.project=write_project(self.root)
        self.config=self.root/'source.json'
        self.overrides={'port':{'mode':'source','source_index':0}}
        self.config.write_text(json.dumps(self.overrides))
        self.profile=resolve_profile('preview',no_fields=True)
        stack=self.enterContext(ExitStack())
        for target in ('gerbonara.rs274x.GerberFile.open','gerbonara.excellon.ExcellonFile.open',
                       'antenna_lab.pcb.bundle.load_bundle_geometry',
                       'antenna_lab.solvers.reduced_pcb.build_reduced_model',
                       'antenna_lab.solvers.reduced_pcb.solve_reduced_model',
                       'antenna_lab.solvers.openems.native_modules'):
            stack.enter_context(patch(target,side_effect=AssertionError('Forbidden path: '+target)))
        self.enterContext(redirect_stdout(StringIO()))

    def run_case(self,output='run',**kwargs):
        return runner.run_easyeda_control(self.project,self.root/output,source_config=self.config,
            resolved_profile=self.profile,**kwargs)

    @staticmethod
    def fake_prepare(geometry,settings,xml_path,**kwargs):
        # This XML is a seam marker, never claimed to be native CSXCAD output.
        if kwargs.get('gerber_quality')!='preview' or 'copper_config' in kwargs:
            raise AssertionError('Must keep feature-aware source-stackup path')
        mesh=make_pcb_domain_mesh(geometry,settings,gerber_quality='preview')
        Path(xml_path).write_text('<test-native-boundary/>')
        from antenna_lab.pcb.port import resolve_pcb_lumped_port
        from test_pcb_postprocess import ProbeReader
        spec=resolve_pcb_lumped_port(geometry,mesh,settings,gerber_quality='preview')
        return object(),object(),ProbeReader(),mesh,spec,{'port':asdict(spec),'xml':{'parse_status':'passed','test_fake':True}}

    def test_prepare_canonical_projection_profiles_and_provenance_without_gerbers(self):
        original=self.project.read_bytes()
        expected=source_layout_geometry(build_source_layout(materialize_project_source(load_easyeda_project(self.project))),self.overrides)
        normalized,_=normalize_port_orientation(expected)
        projected,_,_=apply_geometry_resolution(normalized,PcbGrid())
        with patch.object(runner,'prepare_pcb_xml_model',side_effect=self.fake_prepare) as prepare, \
             patch.object(runner,'run_control_model',side_effect=AssertionError('Run during prepare')):
            result=self.run_case(prepare_only=True)
        self.assertEqual(prepare.call_count,1)
        actual,settings,_=prepare.call_args.args
        self.assertEqual(actual.as_dict(),projected.as_dict())
        self.assertEqual(settings,self.profile.settings)
        self.assertEqual(result['design_source'],'easyeda_project')
        self.assertEqual(result['manufacturing_validation'],'not_requested')
        self.assertEqual(result['status'],'prepared');self.assertEqual(result['termination_status'],'not_run')
        self.assertEqual(result['mesh_anchor_policy']['name'],'feature_aware_copper_v3')
        root=self.root/'run'
        for name in ('project.source.json','component_bindings.json','source_ir.json','source_model.json',
                     'geometry.source.json','geometry.normalized_source.json','geometry.json','import.json','summary.json','native/model.xml'):
            self.assertTrue((root/name).is_file(),name)
        self.assertEqual(json.loads((root/'geometry.source.json').read_text()),json.loads(json.dumps(expected.as_dict())))
        self.assertEqual(result['import']['archive_sha256'],sha256(original).hexdigest())
        self.assertEqual(result['import']['source_config']['resolved'],self.overrides)
        self.assertEqual(self.project.read_bytes(),original)
        self.assertFalse((root/'impedance.csv').exists())
        json.dumps(result,allow_nan=False)

    def test_existing_run_controller_results_and_empty_directory_contract(self):
        def fake_run(engine,csx,port,mesh,settings,native,**kwargs):
            self.assertTrue((native/'model.xml').exists())
            self.assertTrue(kwargs['dump_statistics'])
            self.assertFalse(kwargs.get('exact_endcriteria',False))
            self.assertTrue((native.parent/'pcb-run.json').is_file())
            (native/'openEMS_stats.txt').write_text('100 %number of iterations\n1e-12 %timestep (s)\n1e-10 %total numerical time (s)\n')
            return {'status':'returned'}
        with patch('antenna_lab.pcb.control.prepare_pcb_xml_model',side_effect=self.fake_prepare), \
             patch('antenna_lab.pcb.control.execute_pcb_fdtd',side_effect=fake_run) as run, \
             patch('antenna_lab.visualization.report.generate_report',side_effect=RuntimeError('test report failure')):
            result=self.run_case()
        self.assertEqual(run.call_count,1)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['actual_iterations'],100)
        self.assertEqual(result['termination_status'],'completed_before_limit')
        self.assertIn('EasyEDA project',result['note']);self.assertNotIn('synthetic',result['note'])
        self.assertTrue((self.root/'run/impedance.csv').is_file())
        self.assertTrue(result['warnings'])

    def test_mesh_guard_saved_before_native_and_output_not_reused(self):
        with patch.object(runner,'make_pcb_domain_mesh',side_effect=ConfigurationError('test max_cells guard')), \
             patch.object(runner,'prepare_pcb_xml_model') as native:
            with self.assertRaisesRegex(ConfigurationError,'test max_cells'):
                self.run_case(prepare_only=True)
            native.assert_not_called()
        summary=json.loads((self.root/'run/summary.json').read_text())
        self.assertEqual(summary['status'],'failed');self.assertEqual(summary['failed_stage'],'feature_aware_mesh')
        self.assertTrue((self.root/'run/geometry.json').exists())
        before=(self.root/'run/summary.json').read_bytes()
        with self.assertRaisesRegex(ConfigurationError,'empty/new'):
            self.run_case(prepare_only=True)
        self.assertEqual((self.root/'run/summary.json').read_bytes(),before)

    def test_real_spiral_canonical_reaches_feature_mesh_boundary(self):
        path=Path(__file__).resolve().parents[1]/'gerbs/emtest4/spirala.epro'
        if not path.exists():self.skipTest('spirala.epro unavailable')
        original=path.read_bytes();self.project=path
        # Explicit test assumptions only, not library-derived production values.
        assumptions={'port':{'mode':'source','source_index':0},
            'drills':{'pth_model':'solid_pec_equivalent','pth_plating_um':25},
            'component_values':{'R1':{'kind':'R','value':'49.9ohm'}}}
        self.config.write_text(json.dumps(assumptions))
        expected=source_layout_geometry(build_source_layout(materialize_project_source(load_easyeda_project(path))),assumptions)
        normalized,_=normalize_port_orientation(expected)
        projected,_,_=apply_geometry_resolution(normalized,PcbGrid())
        def boundary(g,settings,quality):
            self.assertEqual(g.as_dict(),projected.as_dict())
            self.assertEqual(quality,'preview');self.assertEqual(settings,self.profile.settings)
            self.assertEqual(len(g.drills),2);self.assertEqual([c.id for c in g.components],['R1'])
            raise ConfigurationError('intentional non-native mesh boundary')
        with patch.object(runner,'make_gerber_mesh_anchor_plan',side_effect=boundary) as seam, \
             patch.object(runner,'prepare_pcb_xml_model') as native:
            with self.assertRaisesRegex(ConfigurationError,'intentional non-native mesh boundary'):
                self.run_case(prepare_only=True)
            seam.assert_called_once();native.assert_not_called()
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(json.loads((self.root/'run/import.json').read_text())['design_source'],'easyeda_project')
        for missing,message in (('port','excitation undefined'),('drills','plating'),('component_values','component_values required')):
            config=dict(assumptions);config.pop(missing);self.config.write_text(json.dumps(config))
            with self.subTest(missing=missing),patch.object(runner,'make_pcb_domain_mesh') as mesh:
                with self.assertRaisesRegex(ConfigurationError,message):self.run_case(output='missing_'+missing,prepare_only=True)
                mesh.assert_not_called()

    def test_cli_shared_profile_and_frequencies_explicit_and_default_output(self):
        with patch.object(runner,'run_easyeda_control',return_value={'status':'prepared'}) as run, \
             patch.object(runner,'allocate_output_dir',return_value=self.root/'spirala_001') as allocate:
            args=['--easyeda-project','spirala.epro','--source-config',str(self.config),'--quality','preview',
                  '--prepare-only','--center-mhz','2000','--cutoff-mhz','1900',
                  '--sweep-start-mhz','1500','--sweep-stop-mhz','2500','--sweep-step-mhz','10']
            self.assertEqual(runner.main(args),0)
            allocate.assert_called_once_with(Path('spirala.epro'),Path('outcomes/pcb_easyeda'))
            profile=run.call_args.kwargs['resolved_profile']
            self.assertEqual(len(profile.settings.result_frequency_hz),101)
            self.assertEqual(profile.field_frequency_hz,(2e9,))
            self.assertEqual(profile.settings.cells_per_wavelength,resolve_profile('preview').settings.cells_per_wavelength)
            allocate.reset_mock()
            self.assertEqual(runner.main(args+['--output',str(self.root/'chosen')]),0)
            allocate.assert_not_called();self.assertEqual(run.call_args.args[1],self.root/'chosen')
            run.reset_mock()
            self.assertEqual(runner.main(args+['--frequencies-mhz','2000']),1)
            run.assert_not_called()
