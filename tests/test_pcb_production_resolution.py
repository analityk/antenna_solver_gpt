"""Production geometry identity/provenance and fake-native acceptance; no FDTD binaries."""
import contextlib
from dataclasses import replace
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import gerber_control as control
from antenna_lab.pcb import geometry_resolution as projection
from antenna_lab.pcb import control as shared_control
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.solvers import pcb_fields
from antenna_lab.visualization.report import generate_report
import test_pcb_gerber as gerber_fixtures
from test_pcb_components import ComponentCSX
from test_pcb_fields import FieldCSX, FieldEngine
from test_pcb_edge_convergence import RunEngine

ROOT=Path(__file__).resolve().parents[1]
BAND=dict(excitation_center_hz=2e9,excitation_cutoff_hz=1e9,
          result_frequency_hz=tuple(f*1e6 for f in range(1500,2501,10)))


class ProductionResolutionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=gerber_fixtures.GerberTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root

    @contextlib.contextmanager
    def native(self,csx=None,engine=None):
        csx=csx or ComponentCSX();engine=engine or RunEngine()
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
             SimpleNamespace(openEMS=lambda **kw:engine),
             SimpleNamespace(ContinuousStructure=lambda:csx))),contextlib.redirect_stdout(io.StringIO()):
            yield csx,engine

    def test_cli_choices_default_help_and_programmatic_rejection(self):
        for arg,value in (([],10),(['100'],100),(['10'],10),(['1'],1),(['0.1'],.1)):
            with patch.object(control,'run_gerber_control',return_value={'status':'prepared'}) as run,contextlib.redirect_stdout(io.StringIO()):
                options=['--geometry-resolution-um',*arg] if arg else []
                self.assertEqual(control.main([str(self.fixture.config_path),'--output',str(self.root/'cli'),
                    '--prepare-only',*options]),0)
                self.assertEqual(run.call_args.kwargs['geometry_resolution_um'],value)
        with contextlib.redirect_stdout(io.StringIO()) as text,self.assertRaises(SystemExit):
            control.main(['--help'])
        self.assertIn('geometry resolution',text.getvalue())
        for value in ('0','-1','5','25','0.5','nan','inf','oops'):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                control.main(['unused','--geometry-resolution-um',value])
        for value in (True,False,None,'10',0,-1,5,25,.5,float('nan'),float('inf')):
            with patch.object(control,'load_pcb_config') as load,self.assertRaises(ConfigurationError):
                control.run_gerber_control('unused',self.root/'invalid',geometry_resolution_um=value)
            load.assert_not_called()

    def test_prepare_legacy_identity_once_provenance_and_exact_native_mesh(self):
        out=self.root/'prepare'
        with self.native(),patch.object(control,'normalize_port_orientation',wraps=control.normalize_port_orientation) as norm,\
             patch.object(projection,'materialize_quantized_geometry',wraps=projection.materialize_quantized_geometry) as materialize,\
             patch.object(control,'make_pcb_domain_mesh',wraps=control.make_pcb_domain_mesh) as mesh,\
             patch.object(control,'prepare_pcb_xml_model',wraps=control.prepare_pcb_xml_model) as native:
            result=control.run_gerber_control(self.fixture.config_path,out,prepare_only=True,quality='preview')
        norm.assert_called_once();materialize.assert_called_once();native.assert_called_once()
        modeled=mesh.call_args.args[0]
        self.assertIs(native.call_args.args[0],modeled)
        for name in ('geometry.source.json','geometry.normalized_source.json','geometry.json','import.json','summary.json','native/model.xml'):
            self.assertTrue((out/name).is_file(),name)
        raw=json.loads((out/'geometry.source.json').read_text())
        normal=json.loads((out/'geometry.normalized_source.json').read_text())
        saved=json.loads((out/'geometry.json').read_text())
        self.assertNotEqual(raw,normal);self.assertNotEqual(normal,saved)
        self.assertEqual(saved,modeled.as_dict())
        self.assertEqual(saved['port']['width_m'],.00086)
        self.assertEqual(normal['port']['width_m'],.00086401)
        audit=result['geometry_resolution']
        self.assertEqual(audit,result['import']['geometry_resolution'])
        self.assertEqual(audit['requested_um'],10);self.assertEqual(audit['topology_status'],'PASS')

    def test_mesh_mismatch_rejected_before_run_in_both_paths(self):
        real=control.prepare_pcb_xml_model
        def wrong(*args,**kwargs):
            parts=list(real(*args,**kwargs))
            parts[3]=replace(parts[3],cell_count=parts[3].cell_count+1)
            return tuple(parts)
        for prepare in (True,False):
            target=control if prepare else shared_control
            with self.native() as (_,engine),patch.object(target,'prepare_pcb_xml_model',side_effect=wrong):
                with self.assertRaisesRegex(ConfigurationError,'differs.*preflight'):
                    control.run_gerber_control(self.fixture.config_path,self.root/str(prepare),prepare_only=prepare)
            self.assertFalse(any(c[0]=='Run' for c in engine.calls))

    def test_full_fields_path_same_modeled_geometry_single_run_and_calcport(self):
        out=self.root/'fields';csx=FieldCSX();engine=FieldEngine(csx)
        with self.native(csx,engine),\
             patch.object(control,'make_pcb_domain_mesh',wraps=control.make_pcb_domain_mesh) as mesh,\
             patch.object(control,'run_control_model',wraps=control.run_control_model) as run,\
             patch.object(shared_control,'prepare_pcb_xml_model',wraps=shared_control.prepare_pcb_xml_model) as native,\
             patch.object(pcb_fields,'pcb_field_layout',wraps=pcb_fields.pcb_field_layout) as layout,\
             patch.object(pcb_fields,'finish_pcb_fields',wraps=pcb_fields.finish_pcb_fields) as finish:
            result=control.run_gerber_control(self.fixture.config_path,out,quality='preview',
                       field_frequency_hz=(1.41e9,1.43e9))
        modeled=mesh.call_args.args[0]
        self.assertIs(run.call_args.args[0],modeled)
        self.assertIs(native.call_args.args[0],modeled)
        self.assertIs(finish.call_args.args[0],modeled)
        for call in layout.call_args_list:self.assertIs(call.args[0],modeled)
        self.assertEqual(sum(c[0]=='Run' for c in engine.calls),1)
        self.assertEqual(len(engine.port.calls),1)
        self.assertEqual(result['fields']['frequency_hz'],[1.41e9,1.43e9])
        self.assertEqual(json.loads((out/'geometry.json').read_text()),modeled.as_dict())

    def test_offline_report_resolution_and_modeled_width(self):
        out=self.root/'report'
        with self.native():
            control.run_gerber_control(self.fixture.config_path,out,quality='preview')
        for p in (self.fixture.top,self.fixture.outline):p.unlink()
        with patch('antenna_lab.solvers.openems.native_modules',side_effect=AssertionError('no native')):
            report=generate_report(out,self.root/'offline.html')
        html=report.read_text()
        for text in ('Geometry resolution','10 um','Geometry topology','PASS','Adjusted spatial values','0.86 mm'):
            self.assertIn(text,html)
        self.assertNotIn('<script src=',html)


@unittest.skipUnless((ROOT/'gerbs/emtest3').exists() and (ROOT/'gerbs/emtest4').exists(),
                     'Production Gerber bundles not available')
class ProductionBundleAcceptance(unittest.TestCase):
    def test_real_production_prepare_and_failure_provenance(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for name,shape,count,updates in (
                ('emtest3',(60,49,35),102900,357886200),
                ('emtest4',(69,89,35),214935,6543911010)):
                bundle=ROOT/'gerbs'/name
                hashes={p:sha256(p.read_bytes()).hexdigest() for p in bundle.iterdir() if p.is_file()}
                csx=ComponentCSX();engine=RunEngine();out=root/name
                with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                     SimpleNamespace(openEMS=lambda **kw:engine),
                     SimpleNamespace(ContinuousStructure=lambda:csx))),contextlib.redirect_stdout(io.StringIO()):
                    result=control.run_gerber_control(bundle,out,prepare_only=True,quality='preview',
                          pcb_config=ROOT/'parameters/pcb_fr4_2layer_pth.json',**BAND)
                self.assertEqual(tuple(result['mesh']['shape_cells']),shape)
                self.assertEqual(result['mesh']['cell_count'],count)
                self.assertEqual(result['estimated_cell_updates'],updates)
                self.assertEqual(result['geometry_resolution']['topology_status'],'PASS')
                self.assertFalse(any(c[0]=='Run' for c in engine.calls))
                geometry=json.loads((out/'geometry.json').read_text())
                self.assertEqual(geometry['port']['negative_xy_m'],[-.00035,0])
                self.assertEqual(geometry['port']['positive_xy_m'],[.00035,0])
                self.assertEqual(geometry['port']['width_m'],.00086)
                self.assertEqual(len(geometry['drills']),1)
                drill=geometry['drills'][0]
                self.assertEqual(set(drill['connected_layer_roles']),{'top','bottom'})
                self.assertEqual(drill['drill_diameter_m'],.0003)
                self.assertEqual(drill['equivalent_outer_radius_m'],.00018)
                self.assertAlmostEqual(drill['plating_thickness_m'],.000025,delta=1e-19)
                self.assertEqual(drill['source_drill_diameter_m'],.000305)
                info=result['preparation']['geometry']['drills']
                self.assertEqual(info['pth_count'],1);self.assertEqual(info['npth_count'],0)
                self.assertEqual(len(info['records']),1)
                from antenna_lab.visualization.report import _pcb_metadata
                html=_pcb_metadata(dict(summary=result,root=out,geometry=geometry,warnings=[]))
                self.assertIn('PTH: 1; NPTH: 0',html)
                self.assertNotIn('9 drills',html)
                if name=='emtest4':
                    self.assertEqual(len(geometry['components']),3)
                    self.assertEqual(geometry['source_port']['source_refdes'],'CSRC')
                    self.assertEqual(result['estimated_excitation_steps'],30446)
                    values={c['id']:c['value_si'] for c in geometry['components']}
                    self.assertAlmostEqual(values['C1'],100e-12,delta=1e-24)
                    self.assertAlmostEqual(values['L1'],18e-9,delta=1e-22)
                    self.assertEqual(values['R1'],49.9)
                    self.assertEqual(len(csx.lumped),3)
                    self.assertEqual(sum(c[0]=='AddLumpedPort' for c in engine.calls),1)
                self.assertEqual(hashes,{p:sha256(p.read_bytes()).hexdigest() for p in hashes})
            out=root/'coarse'
            with patch.object(control,'make_pcb_domain_mesh') as mesh,\
                 patch('antenna_lab.solvers.openems.native_modules') as native,contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ConfigurationError,'100 um.*full-width contact.*finer'):
                    control.run_gerber_control(ROOT/'gerbs/emtest4',out,prepare_only=True,quality='preview',
                        geometry_resolution_um=100,pcb_config=ROOT/'parameters/pcb_fr4_2layer_pth.json',**BAND)
            mesh.assert_not_called();native.assert_not_called()
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['geometry_resolution']['topology_status'],'FAIL')
            self.assertFalse((out/'geometry.json').exists())
            for file in ('geometry.source.json','geometry.normalized_source.json','import.json'):
                self.assertTrue((out/file).exists())
