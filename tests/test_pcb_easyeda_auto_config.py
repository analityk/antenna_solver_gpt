"""CAD-derived EasyEDA source-config contracts; small offline tests only."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.easyeda_auto_config import derive_source_config, main
from antenna_lab.pcb.easyeda_project import load_easyeda_project
from test_pcb_easyeda_project import write_project


class AutoSourceConfigTests(unittest.TestCase):
    def test_source_only_fixture_has_no_invented_passives_or_plating(self):
        with TemporaryDirectory() as tmp:
            project = load_easyeda_project(write_project(tmp))
            config, evidence = derive_source_config(project)
        self.assertEqual(config, {'port': {'mode': 'source', 'source_index': 0},
                                  'component_values': {}})
        self.assertNotIn('drills', config)
        self.assertEqual(evidence['source_designator'], 'CSRC')

    def test_instance_value_precedes_referenced_device_not_footprint(self):
        project = SimpleNamespace(data={'project': {'devices': {
            'r-device': {'attributes': {'Value': '49.9Ω'}}}}})
        src = {'role': 'source', 'designator': 'CSRC', 'source_index': 0}
        passive = {'role': 'component', 'designator': 'R1', 'device_id': 'r-device',
                   'attributes': {}, 'footprint_title': 'C0603'}
        result, evidence = derive_source_config(project, bindings=[src, passive])
        self.assertEqual(result['component_values']['R1'], {'kind':'R','value':'49.9Ω'})
        self.assertEqual(evidence['component_value_origins']['R1'],'referenced_device')
        passive['attributes']['Value']='56ohm'
        result, evidence = derive_source_config(project, bindings=[src, passive])
        self.assertEqual(result['component_values']['R1'], {'kind':'R','value':'56ohm'})
        self.assertEqual(evidence['component_value_origins']['R1'],'pcb_instance')

    def test_cad_conflicts_and_unsupported_values_fail_closed(self):
        project = SimpleNamespace(data={'project': {'devices': {}}})
        src = {'role':'source','designator':'CSRC','source_index':0}
        part = {'role':'component','designator':'C1','attributes':{'Value':'49.9Ω'},
                'device_id':None}
        with self.assertRaisesRegex(ConfigurationError,'conflict'):
            derive_source_config(project,bindings=[src,part])
        part['attributes']['Value']='10nF'
        result,_=derive_source_config(project,bindings=[src,part])
        self.assertEqual(result['component_values']['C1']['kind'],'C')
        part['attributes']['Value']='100'
        with self.assertRaisesRegex(ConfigurationError,'unique supported'):
            derive_source_config(project,bindings=[src,part])
        part['attributes'].clear()
        with self.assertRaisesRegex(ConfigurationError,'no unit-bearing Value'):
            derive_source_config(project,bindings=[src,part])
        with self.assertRaisesRegex(ConfigurationError,'exactly one'):
            derive_source_config(project,bindings=[part])

    def test_plating_is_explicit_only(self):
        with TemporaryDirectory() as tmp:
            project = load_easyeda_project(write_project(tmp))
            result,evidence=derive_source_config(project,pth_plating_um=25)
        self.assertEqual(result['drills'], {'pth_model':'solid_pec_equivalent',
                                            'pth_plating_um':25.})
        self.assertEqual(evidence['pth_plating_origin'],'explicit_user_option')
        with self.assertRaisesRegex(ConfigurationError,'plating'):
            derive_source_config(project,pth_plating_um=0)

    def test_standalone_generator_works_before_layout_and_refuses_overwrite(self):
        with TemporaryDirectory() as tmp:
            archive=write_project(tmp); target=Path(tmp)/'cfg.json'
            self.assertEqual(main(['--easyeda-project',str(archive),'--output',str(target)]),0)
            data=json.loads(target.read_text())
            self.assertEqual(data['port']['source_index'],0)
            before=target.read_bytes()
            self.assertEqual(main(['--easyeda-project',str(archive),'--output',str(target)]),1)
            self.assertEqual(target.read_bytes(),before)

    def test_real_spiral_library_value_if_archive_present(self):
        path=Path(__file__).resolve().parents[1]/'gerbs/emtest4/spirala.epro'
        if not path.is_file():self.skipTest('spirala archive not available')
        config,evidence=derive_source_config(load_easyeda_project(path))
        self.assertEqual(config['port'],{'mode':'source','source_index':0})
        self.assertEqual(config['component_values']['R1'],{'kind':'R','value':'49.9Ω'})
        self.assertEqual(evidence['component_value_origins']['R1'],'referenced_device')
        self.assertNotIn('drills',config)  # Fabrication assumption cannot be guessed.

    def test_fullwave_cli_no_longer_requires_source_config(self):
        from antenna_lab.pcb import easyeda_control as control
        with TemporaryDirectory() as tmp:
            destination=Path(tmp)/'dif400_001'
            args=['--easyeda-project','dif400.epro','--quality','preview','--prepare-only',
                  '--center-mhz','2000','--cutoff-mhz','1900',
                  '--sweep-start-mhz','1500','--sweep-stop-mhz','2500',
                  '--sweep-step-mhz','10']
            with patch.object(control,'allocate_output_dir',return_value=destination), \
                 patch.object(control,'run_easyeda_control',return_value={'status':'prepared'}) as run:
                self.assertEqual(control.main(args),0)
                self.assertIsNone(run.call_args.kwargs['source_config'])
                self.assertIsNone(run.call_args.kwargs['pth_plating_um'])
                self.assertEqual(control.main(args+['--pth-plating-um','25']),0)
                self.assertEqual(run.call_args.kwargs['pth_plating_um'],25.)
            

if __name__=='__main__':
    unittest.main()
