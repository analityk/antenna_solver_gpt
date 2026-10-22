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
        manifest=dict(self.manifest,preparation=dict(self.meta,fields={'frequency_hz':[1.42e9],'planes':[]}))
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
