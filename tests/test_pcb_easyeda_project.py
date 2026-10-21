"""Small deterministic archive/footprint/contact tests. No native solver."""
import copy
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile, ZIP_DEFLATED
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.easyeda_project import (load_easyeda_project, resolve_project_components,
    materialize_project_source)
from antenna_lab.pcb.easyeda_footprints import instantiate_components, transform_xy
from antenna_lab.pcb.easyeda_model import build_source_layout, source_layout_geometry
from antenna_lab.pcb.reduced_control import run_reduced


def fixture():
    pcb=[['DOCTYPE','PCB','1.8'],['HEAD',{'editorVersion':'2.2.47.7'}],['CANVAS',0,0,'mm'],
        ['LAYER',1,'TOP','Top',3],['LAYER',2,'BOTTOM','Bottom',3],['LAYER',11,'OUTLINE','Board',3],
        ['LAYER',361,'SUBSTRATE','Core',0],['LAYER_PHYS',1,'',1,0,0,1],
        ['LAYER_PHYS',361,'air',40,1,0,1],['LAYER_PHYS',2,'',1,0,0,1],['NET','A'],['NET','B'],
        ['POLY','outline',0,'',11,1,['R',-500,500,1000,1000,0],0],
        ['POUR','ground',0,'B',2,.2,'GND',0,[['R',-500,500,1000,1000,0]],['SOLID',8],0,0],
        ['POURED','fill','ground',0,True,[[-50,50,'L',50,50,50,-50,-50,-50,-50,50]]],
        ['LINE','l',0,'A',1,-400,0,-100,0,10,0],['LINE','r',0,'B',1,100,0,400,0,10,0],
        ['COMPONENT','c',0,1,0,0,0,{'Value':'0'},0],
        ['ATTR','ref',0,'c',3,None,None,'Designator','CSRC'],
        ['ATTR','fp',0,'c',3,None,None,'Footprint','chosen'],
        ['ATTR','dev',0,'c',3,None,None,'Device','device'],
        ['PAD_NET','c','1','A','p1'],['PAD_NET','c','2','B','p2']]
    fp=[['DOCTYPE','FOOTPRINT','1.8'],['LAYER',1,'TOP','Top',3],['LAYER',2,'BOTTOM','Bottom',3],
        ['LAYER',12,'MULTI','All',3],[],
        ['PAD','p1',0,'',1,'1',-100,0,0,None,['RECT',40,40,0],[]],
        ['PAD','p2',0,'',1,'2',100,0,0,None,['RECT',40,40,0],[]]]
    p={'config':{'editorVersion':'2.2.47.7'},'pcbs':{'pcb':'Board'},
       'footprints':{'chosen':{'title':'R0603'},'device_default':{'title':'C0603'}},
       'devices':{'device':{'attributes':{'Footprint':'device_default','Value':'100nF'}}}}
    return p,pcb,fp


def write_project(root, values=None, extra=None):
    p,pcb,fp=values or fixture();path=Path(root)/'test.epro'
    encode=lambda rows:'\n'.join(json.dumps(r) for r in rows)+'\n'
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        z.writestr('project.json',json.dumps(p));z.writestr('PCB/pcb.epcb',encode(pcb))
        z.writestr('FOOTPRINT/chosen.efoo',encode(fp))
        for key,value in (extra or {}).items():z.writestr(key,value)
    return path


class ProjectTests(unittest.TestCase):
    def test_archive_to_real_canonical_pads_and_unchanged_bytes(self):
        with TemporaryDirectory() as tmp:
            path=write_project(tmp);before=path.read_bytes()
            project=load_easyeda_project(path);source=materialize_project_source(project)
            layout=build_source_layout(source)
            self.assertFalse(layout['missing_dependencies']);self.assertEqual(len(layout['pads']),2)
            self.assertEqual(layout['resolved_components'][0]['footprint_title'],'R0603')
            self.assertEqual(layout['resolved_components'][0]['source_index'],0)
            self.assertEqual(layout['contact_audit']['status'],'passed')
            self.assertTrue(all(p['physical_contacts'] for p in layout['contact_audit']['pads']))
            g=source_layout_geometry(layout,{'port':{'mode':'explicit','negative_mm':[-2.032,0],
                'positive_mm':[2.032,0],'width_mm':.508}})
            self.assertEqual(len(g.source_pads),2);self.assertEqual(g.source_pads[0].net,'A')
            self.assertEqual(path.read_bytes(),before);self.assertEqual(project.archive_sha256,sha256(before).hexdigest())
            self.assertEqual(load_easyeda_project(path),project)

    def test_identity_and_missing_pad_fail_closed(self):
        changes=[(lambda p,b,f:b[19].__setitem__(8,'missing'),'missing/ambiguous'),
                 (lambda p,b,f:b[-1].__setitem__(4,'p1'),'number/ID mismatch'),
                 (lambda p,b,f:b[-1].__setitem__(2,'9'),'number/ID mismatch'),
                 (lambda p,b,f:b.pop(),'unmapped footprint pads')]
        for change,message in changes:
            with self.subTest(message=message),TemporaryDirectory() as tmp:
                p,b,f=fixture();change(p,b,f)
                with self.assertRaisesRegex(ConfigurationError,message):
                    resolve_project_components(load_easyeda_project(write_project(tmp,(p,b,f))))

    def test_device_fallback_only_without_explicit_pcb_choice(self):
        with TemporaryDirectory() as tmp:
            p,b,f=fixture();b=[r for r in b if not (r[0]=='ATTR' and r[7]=='Footprint')]
            p['devices']['device']['attributes']['Footprint']='chosen'
            result=resolve_project_components(load_easyeda_project(write_project(tmp,(p,b,f))))
            self.assertEqual(result[0]['footprint_resolution'],'device_fallback')

    def test_embedded_footprint_uuid(self):
        with TemporaryDirectory() as tmp:
            p,b,f=fixture();embedded=copy.deepcopy(f);embedded.insert(1,['HEAD',{'uuid':'embedded','source':'chosen','editorVersion':'2.2.40.8'}])
            b[19][8]='embedded'
            result=resolve_project_components(load_easyeda_project(write_project(tmp,(p,embedded+b,f))))
            self.assertEqual(result[0]['footprint_key'],'embedded')

    def test_rotation_bottom_reflection_and_no_device_geometry(self):
        self.assertEqual(transform_xy((2,3),(10,20),90),(7,22))
        self.assertEqual(transform_xy((2,3),(10,20),90,True),(13,22))
        with TemporaryDirectory() as tmp:
            p,b,f=fixture();b[17][3]=2;b[17][4:7]=[20,30,90]
            project=load_easyeda_project(write_project(tmp,(p,b,f)))
            rs=resolve_project_components(project)
            instances,pads,drills=instantiate_components(rs,[{'id':1,'type':'TOP'},{'id':2,'type':'BOTTOM'}],['A','B'])
            self.assertEqual([p['layer_id'] for p in pads],[2,2])
            self.assertAlmostEqual(pads[0]['centre_xy_m'][0],.000508)
            self.assertAlmostEqual(pads[0]['centre_xy_m'][1],-.001778)
            self.assertEqual(instances[0]['footprint_key'],'chosen')

    def test_source_is_explicit_not_capacitor_value(self):
        with TemporaryDirectory() as tmp:
            p,b,f=fixture();b[18][8]='C1'
            resolved=resolve_project_components(load_easyeda_project(write_project(tmp,(p,b,f))))
            self.assertIsNone(resolved[0]['source_index']);self.assertEqual(resolved[0]['role'],'component')

    def test_short_bad_transform_and_unsupported_shape(self):
        cases=[(lambda p,b,f:f[-1].__setitem__(6,-100),'source short'),
               (lambda p,b,f:b[17].__setitem__(6,float('nan')),'strict JSON'),
               (lambda p,b,f:f[-1].__setitem__(10,['RECT',40,40,20]),'unsupported PAD shape')]
        for change,msg in cases:
            with self.subTest(msg=msg),TemporaryDirectory() as tmp:
                p,b,f=fixture();change(p,b,f)
                with self.assertRaisesRegex(ConfigurationError,msg):
                    build_source_layout(materialize_project_source(load_easyeda_project(write_project(tmp,(p,b,f)))))

    def test_round_tht_metadata_and_plating_not_guessed(self):
        with TemporaryDirectory() as tmp:
            p,b,f=fixture()
            # Both through pads use B to avoid intentional short to full bottom B plane.
            b[-2][3]='B';b[15][3]='B'
            for pad in f[-2:]:
                pad[4]=12;pad[9]=['ROUND',10,10];pad.extend([0,0,0,1])
            source=materialize_project_source(load_easyeda_project(write_project(tmp,(p,b,f))))
            layout=build_source_layout(source)
            self.assertEqual(len(layout['footprint_drills']),2);self.assertEqual(len(layout['pads']),4)
            self.assertTrue(all(p['holes_xy_m'] for p in layout['pads']))
            cfg={'port':{'mode':'explicit','negative_mm':[-2.032,0],'positive_mm':[2.032,0],'width_mm':.508}}
            with self.assertRaisesRegex(ConfigurationError,'barrel plating'):source_layout_geometry(layout,cfg)

    def test_archive_security_and_selection(self):
        for name in ('../escape','/absolute','FOOTPRINT\\escape','project.JSON'):
            with self.subTest(name=name),TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ConfigurationError,'unsafe/duplicate'):
                    load_easyeda_project(write_project(tmp,extra={name:'x'}))
        with TemporaryDirectory() as tmp:
            p,b,f=fixture();p['pcbs']['other']='Other'
            path=write_project(tmp,(p,b,f))
            with self.assertRaisesRegex(ConfigurationError,'ambiguous PCB'):load_easyeda_project(path)
            self.assertEqual(load_easyeda_project(path,pcb_id='pcb').pcb_id,'pcb')
            with patch('antenna_lab.pcb.easyeda_project.MAX_TOTAL_BYTES',1):
                with self.assertRaisesRegex(ConfigurationError,'limit'):load_easyeda_project(path)

    def test_project_cli_inspection_without_gerber(self):
        with TemporaryDirectory() as tmp:
            path=write_project(tmp)
            with patch('antenna_lab.pcb.bundle.load_bundle_geometry',side_effect=AssertionError('Gerber')):
                result=run_reduced(None,Path(tmp)/'out',easyeda_project=path,inspect_source=True)
            self.assertEqual(result['status'],'source_inspected')
            self.assertEqual(result['provenance']['contact_audit']['status'],'passed')
            self.assertFalse((Path(tmp)/'out'/'impedance.csv').exists())

    def test_real_spiral_pad_geometry_and_contacts(self):
        path=Path(__file__).resolve().parents[1]/'gerbs/emtest4/spirala.epro'
        if not path.exists():self.skipTest('user spiral archive not present')
        project=load_easyeda_project(path);source=materialize_project_source(project);layout=build_source_layout(source)
        self.assertEqual(len(layout['resolved_components']),2);self.assertEqual(len(layout['pads']),4)
        self.assertEqual(len(source.routes),13);self.assertEqual(len(source.vias),2)
        self.assertEqual({c['footprint_title'] for c in layout['resolved_components']},{'R0603'})
        c=next(c for c in layout['resolved_components'] if c['designator']=='CSRC')
        self.assertEqual(c['source_index'],0)
        self.assertEqual([(b['pad_number'],b['pad_id'],b['net']) for b in c['bindings']],[('2','e7','B'),('1','e8','A')])
        pads=source.semantics['pads'];p=next(p for p in pads if p['component_id']==c['component_id'] and p['pad_number']=='1')
        self.assertAlmostEqual(p['centre_xy_m'][0],.002921,places=12)
        self.assertAlmostEqual(p['centre_xy_m'][1],.012962636,places=12)
        self.assertTrue(all(p['physical_contacts'] for p in layout['contact_audit']['pads']))

if __name__=='__main__':unittest.main()
