"""Targeted EasyEDA source stackup tests. No solver, mesh, native or PSU."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.easyeda import parse_easyeda_source
from antenna_lab.pcb.easyeda_stackup import (
    source_physical_stackup, describe_source_stackup,
    parse_source_dielectric_materials,
)


def sample():
    layers = [
        dict(id=1,type='TOP',name='TOP'),
        dict(id=361,type='SUBSTRATE',name='Core A'),
        dict(id=15,type='SIGNAL',name='Inner1'),
        dict(id=362,type='SUBSTRATE',name='Core B'),
        dict(id=16,type='SIGNAL',name='Inner2'),
        dict(id=363,type='SUBSTRATE',name='Core C'),
        dict(id=2,type='BOTTOM',name='BOTTOM'),
        dict(id=3,type='TOP_SILK',name='Top Silk'),
        dict(id=5,type='TOP_SOLDER_MASK',name='Top Mask'),
        dict(id=7,type='TOP_PASTE_MASK',name='Top Paste'),
    ]
    kind={v['id']:v['type'] for v in layers}
    ids=[3,5,7,1,361,15,362,16,363,2]
    thickness={1:.000035,15:.000035,16:.000035,2:.000035,
               361:.0002,362:.0002,363:.0002}
    phys=[dict(layer_id=i,material='CAD',thickness_m=thickness.get(i,0),
               epsilon_r=0,loss_tangent=0,record_index=k)
          for k,i in enumerate(ids,1)]
    return dict(layers=layers,layer_physics=phys)


class EasyEdaStackupTests(unittest.TestCase):
    def test_filters_editor_layers_and_preserves_physical_order(self):
        s=source_physical_stackup(sample())
        self.assertEqual(list(s['role_by_layer_id'].values()),
                         ['top','inner1','inner2','bottom'])
        self.assertEqual([p['layer_id'] for p in s['records']],
                         [1,361,15,362,16,363,2])
        self.assertEqual([p['layer_id'] for p in s['ignored_layers']],[3,5,7])

    def test_real_stack_requires_explicit_epsilon_but_inspection_survives(self):
        info=describe_source_stackup(sample(),'sha')
        self.assertEqual([p['role'] for p in info['copper_layers']],
                         ['top','inner1','inner2','bottom'])
        self.assertEqual([p['z_m'] for p in info['copper_layers']],
                         [0,-.0002,-.0004,-.0006])
        self.assertEqual(len(info['missing_materials']),3)
        self.assertIn('omitted',info['soldermask_model'])
        with self.assertRaisesRegex(ConfigurationError,'361, 362, 363'):
            describe_source_stackup(sample(),'sha',require_materials=True)

    def test_user_dielectric_values_do_not_change_source_thickness_or_z(self):
        requested=parse_source_dielectric_materials([
            '361:4.25:0.016','362:4.12:0.013','363:4.25:0.016'])
        stack=describe_source_stackup(sample(),'sha',requested,require_materials=True)
        self.assertEqual(len(stack['missing_materials']),0)
        self.assertEqual([d['epsilon_r'] for d in stack['dielectric_layers']],
                         [4.25,4.12,4.25])
        self.assertEqual(stack['dielectric_layers'][0]['epsilon_origin'],
                         'explicit_user_override')
        self.assertEqual([d['z_min_m'] for d in stack['dielectric_layers']],
                         [-.0002,-.0004,-.0006])
        self.assertNotIn('drills',stack)

    def test_bad_physical_order_and_unknown_non_em_kind_fail(self):
        d=sample()
        d['layer_physics']=[x for x in d['layer_physics'] if x['layer_id']!=362]
        with self.assertRaisesRegex(ConfigurationError,'alternate'):
            source_physical_stackup(d)
        d=sample();d['layers'][0]['type']='WILDCARD'
        with self.assertRaisesRegex(ConfigurationError,'unknown physical layer kind'):
            source_physical_stackup(d)
        d=sample();d['layer_physics'][5]['epsilon_r']=float('nan')
        with self.assertRaisesRegex(ConfigurationError,'invalid material parameter'):
            describe_source_stackup(d,'sha')

    def test_invalid_material_override_and_duplicate_ids_fail(self):
        for values in (['361:0:0'],['361:4.2:-0.01'],
                       ['361:4.2:0','361:4.3:0'],['361:4.2'],['foo']):
            with self.subTest(values=values),self.assertRaises(ConfigurationError):
                parse_source_dielectric_materials(values)
        with self.assertRaisesRegex(ConfigurationError,'unknown/non-dielectric'):
            describe_source_stackup(sample(),'sha',{'3':dict(epsilon_r=4.3)})
        with self.assertRaisesRegex(ConfigurationError,'unknown/non-dielectric'):
            describe_source_stackup(sample(),'sha',{'99':dict(epsilon_r=4.3)})

    def test_real_stripline_stack_and_missing_material_provenance(self):
        import zipfile
        from antenna_lab.pcb.easyeda_project import load_easyeda_project,materialize_project_source
        from antenna_lab.pcb.easyeda_model import build_source_layout
        path=Path(__file__).resolve().parents[1]/'gerbs/stripline1/stripline1.epro'
        if not path.is_file():self.skipTest('Real stripline1 epro not installed')
        src=materialize_project_source(load_easyeda_project(path))
        stack=describe_source_stackup(src.semantics,src.source_sha256)
        self.assertEqual([c['layer_id'] for c in stack['copper_layers']],[1,15,16,2])
        self.assertEqual([d['layer_id'] for d in stack['dielectric_layers']],[361,362,363])
        self.assertEqual({d['layer_id'] for d in stack['missing_materials']},{361,362,363})
        self.assertEqual(len(stack['ignored_layers']),6)
        # End-to-end physical source inspection; no solver or FDTD.
        layout=build_source_layout(src)
        self.assertEqual(len(layout['dielectric_layers']),3)
        self.assertIn('inner2', {c['layer_role'] for c in layout['copper']})
        self.assertGreater(len(layout['feature_owners']),0)


if __name__=='__main__':
    unittest.main()
