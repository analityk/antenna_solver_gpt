"""Isolated replay contracts; all native boundaries are fakes, never FDTD."""
from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.control import make_synthetic_control_case, run_control_model
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from antenna_lab.pcb.postprocess import (save_preparation, load_preparation, recover_run,
    process_results, restore_inputs)
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh


from antenna_lab.solvers.openems_pcb import restore_pcb_port_reader as native_reader_factory


class ProbeReader:
    uf_tot = (50., 100., 50.+50j)
    if_tot = (1., 1., 1.)
    def __init__(self): self.calls = 0
    def CalcPort(self, *args, **kwargs): self.calls += 1


class PostprocessTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'arbitrary_input_041'; self.root.mkdir()
        self.native = self.root/'native'; self.native.mkdir()
        (self.native/'model.xml').write_text('<fake-xml/>')
        self.geometry,self.settings = make_synthetic_control_case()
        self.mesh = make_pcb_domain_mesh(self.geometry,self.settings)
        self.spec = resolve_pcb_lumped_port(self.geometry,self.mesh,self.settings)
        self.meta = {'port':asdict(self.spec)}
        self.manifest = save_preparation(self.root,self.geometry,self.settings,self.mesh,self.spec,self.meta)
        self.reader = ProbeReader()
        self.enterContext(patch('antenna_lab.solvers.openems_pcb.restore_pcb_port_reader',return_value=self.reader))
        self.enterContext(patch('antenna_lab.solvers.openems_pcb.execute_pcb_fdtd',side_effect=AssertionError('No Run permitted')))

    def raw_snapshot(self):
        return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*')
                if p.is_file() and 'postprocessed' not in p.parts}

    def test_missing_statistics_recovery_repeat_and_no_original_mutation(self):
        before=self.raw_snapshot()
        first,a=recover_run(self.root,render=False)
        second,b=recover_run(self.root,render=False)
        self.assertNotEqual(first,second)
        self.assertEqual(a,b)
        self.assertEqual(a['resistance_ohm'],[50.,100.,50.])
        self.assertEqual(a['termination_status'],'unconfirmed')
        self.assertEqual(a['stages']['engine']['status'],'not_recorded')
        self.assertEqual(a['stages']['port']['status'],'processed')
        self.assertEqual(before,self.raw_snapshot())
        self.assertFalse((self.native/'openEMS_stats.txt').exists())

    def test_statistics_limit_separate_from_port(self):
        for iterations,expected in ((10,'completed_before_limit'),(self.settings.max_timesteps,'max_timesteps_reached')):
            (self.native/'openEMS_stats.txt').write_text(f'{iterations}\t%number of iterations\n1e-12\t%timestep (s)\n{iterations*1e-12}\t%total numerical time (s)\n')
            _,result=recover_run(self.root,render=False)
            self.assertEqual(result['termination_status'],expected)
            self.assertEqual(result['stages']['port']['status'],'processed')
            if expected!='completed_before_limit':self.assertNotEqual(result['status'],'completed')

    def test_openems_layout_and_manifest_roundtrip(self):
        self.native.rename(self.root/'openems')
        manifest,native=load_preparation(self.root)
        geometry,settings,mesh,spec=restore_inputs(manifest)
        self.assertEqual(geometry.as_dict(),self.geometry.as_dict())
        self.assertEqual((settings,mesh,spec),(self.settings,self.mesh,self.spec))
        self.assertEqual(native.name,'openems')
        _,result=recover_run(self.root,render=False)
        self.assertEqual(result['stages']['port']['status'],'processed')

    def test_incomplete_raw_and_legacy_errors(self):
        with patch.object(self.reader,'CalcPort',side_effect=FileNotFoundError('port_it_1')):
            output,result=recover_run(self.root,render=False)
        self.assertIn('port_it_1',result['stages']['port']['reason'])
        self.assertFalse((output/'impedance.csv').exists())
        (self.root/'pcb-run.json').unlink()
        (self.root/'summary.json').write_text('{}')
        with self.assertRaisesRegex(ConfigurationError,'simulation_settings.*domain_mesh.*port.*preparation'):
            recover_run(self.root,render=False)

    def test_processed_reuse_does_not_recalculate_port(self):
        output,result=recover_run(self.root,render=False)
        calls=self.reader.calls
        with patch('antenna_lab.solvers.openems_pcb.restore_pcb_port_reader',side_effect=AssertionError('No native reader')):
            destination,reused=recover_run(output,render=False)
        self.assertEqual(self.reader.calls,calls)
        self.assertEqual(reused['stages']['postprocess']['status'],'reused')
        self.assertEqual((output/'impedance.csv').read_bytes(),(destination/'impedance.csv').read_bytes())

    def test_fields_failure_does_not_lose_spectrum_and_report_is_independent(self):
        manifest=dict(self.manifest,preparation=dict(self.meta,fields={'frequency_hz':[1.42e9],'planes':[{'name':'xy_air'}]}))
        with patch('antenna_lab.solvers.pcb_fields.finish_pcb_fields',side_effect=FileNotFoundError('fields_xy_air_E.h5')):
            result=process_results(manifest,self.native,self.root,port=self.reader)
        self.assertEqual(result['stages']['fields']['status'],'failed')
        self.assertTrue((self.root/'impedance.csv').exists())
        self.assertEqual(result['stages']['port']['status'],'processed')
        from antenna_lab.pcb.postprocess import render_report
        with patch('antenna_lab.visualization.report.generate_report',side_effect=RuntimeError('plot error')):
            render_report(self.root,result)
        self.assertEqual(result['stages']['report']['status'],'failed')
        self.assertTrue((self.root/'impedance.csv').exists())

    def test_normal_run_saves_contract_before_execution_and_shares_processing(self):
        target=Path(self.tmp.name)/'new_run'
        def prepare(g,s,xml,**kwargs):
            Path(xml).write_text('<fake-xml/>')
            return object(),object(),self.reader,self.mesh,self.spec,self.meta
        def execute(*args,**kwargs):
            saved=load_preparation(target)[0]
            self.assertEqual(saved['geometry'],self.geometry.as_dict())
            self.assertEqual(saved['domain_mesh'],json.loads(json.dumps(asdict(self.mesh))))
            return {'status':'returned'}
        with patch('antenna_lab.pcb.control.prepare_pcb_xml_model',side_effect=prepare), \
             patch('antenna_lab.pcb.control.execute_pcb_fdtd',side_effect=execute) as run:
            result=run_control_model(self.geometry,self.settings,target)
        self.assertEqual(run.call_count,1)
        self.assertEqual(self.reader.calls,1)
        self.assertEqual(result['stages']['engine']['status'],'returned')
        self.assertEqual(result['stages']['port']['status'],'processed')

    def test_modified_xml_and_ambiguous_native_directory_rejected(self):
        (self.native/'model.xml').write_text('<different/>')
        with self.assertRaisesRegex(ConfigurationError,'SHA256'):load_preparation(self.root)
        alternate=self.root/'openems';alternate.mkdir();(alternate/'model.xml').write_text('<fake/>')
        with self.assertRaisesRegex(ConfigurationError,'exactly one'):load_preparation(self.root)

    def test_successful_field_detachment_and_offline_reuse(self):
        import numpy as np
        from antenna_lab.solvers.pcb_fields import pcb_field_layout
        layout=pcb_field_layout(self.geometry,self.mesh,self.settings,(1.42e9,))
        manifest=dict(self.manifest,preparation=dict(self.meta,fields={'frequency_hz':[1.42e9],'planes':layout}))
        def surface(path,frequency):
            plane=next(p for p in layout if Path(path).name in p['native_files'].values())
            lines=[np.array([x for x in getattr(self.mesh,a+'_lines_m') if lo<=x<=hi])
                   for a,lo,hi in zip('xyz',plane['start_m'],plane['stop_m'])]
            return lines,np.ones((3,*(len(a) for a in lines)),dtype=complex)
        with patch('antenna_lab.solvers.pcb_fields._read_surface',side_effect=surface):
            result=process_results(manifest,self.native,self.root,port=self.reader)
        self.assertEqual(result['stages']['fields']['status'],'processed')
        for plane in layout:self.assertTrue((self.root/'fields'/(plane['name']+'.npz')).is_file())
        calls=self.reader.calls
        with patch('antenna_lab.solvers.openems_pcb.restore_pcb_port_reader',side_effect=AssertionError('No native')):
            output,reused=recover_run(self.root,render=False)
        self.assertEqual(self.reader.calls,calls)
        self.assertEqual(reused['stages']['postprocess']['status'],'reused')
        self.assertEqual((self.root/'fields/xy_air.npz').read_bytes(),(output/'fields/xy_air.npz').read_bytes())

    def test_legacy_complete_explicit_contract(self):
        from antenna_lab.pcb.postprocess import write_json
        (self.root/'pcb-run.json').unlink()
        write_json(self.root/'mesh.json',asdict(self.mesh))
        write_json(self.root/'summary.json',{'simulation_settings':asdict(self.settings),'preparation':self.meta})
        _,result=recover_run(self.root,render=False)
        self.assertEqual(result['stages']['port']['status'],'processed')

    def test_native_reader_factory_never_calls_run_or_writes_xml(self):
        from types import SimpleNamespace
        factory=native_reader_factory
        class Grid:
            def __init__(self):self.axes={}
            def SetDeltaUnit(self,v):self.unit=v
            def GetDeltaUnit(self):return self.unit
            def SetLines(self,a,v):self.axes[a]=v
            def GetLines(self,a):return self.axes[a]
        grid=Grid();csx=SimpleNamespace(GetGrid=lambda:grid)
        calls=[];reader=self.reader
        class Engine:
            def SetCSX(self,value):calls.append(('SetCSX',value))
            def AddLumpedPort(self,*args,**kwargs):calls.append(('port',args,kwargs));return reader
            def Run(self,*a,**k):raise AssertionError('FDTD forbidden')
            def Write2XML(self,*a,**k):raise AssertionError('XML modification forbidden')
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
            SimpleNamespace(openEMS=Engine),SimpleNamespace(ContinuousStructure=lambda:csx))):
            self.assertIs(factory(self.spec,self.mesh),reader)
        self.assertEqual([c[0] for c in calls],['SetCSX','port'])
        self.assertEqual(calls[1][1][2],list(self.spec.start_m))
        self.assertEqual(calls[1][1][3],list(self.spec.stop_m))
        for a in 'xyz':self.assertEqual(tuple(grid.axes[a]),getattr(self.mesh,a+'_lines_m'))

    def test_offline_report_includes_unconfirmed_execution_and_stage_status(self):
        output,result=recover_run(self.root,render=True)
        self.assertEqual(result['stages']['report']['status'],'generated')
        text=(output/'report.html').read_text()
        self.assertIn('Raport PCB',text)
        self.assertIn('unconfirmed',text)
        self.assertIn('temporal_completion',text)
        self.assertIn('not_recorded',text)
        self.assertTrue((output/'plots/impedance.png').is_file())
