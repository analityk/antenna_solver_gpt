"""Small source-only tests. No Gerber fixtures, native imports or FDTD."""
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.easyeda import parse_easyeda_source,metres,arc_center
from antenna_lab.pcb.easyeda_model import build_source_layout,source_layout_geometry
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.geometry_resolution import apply_geometry_resolution
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.reduced_control import run_reduced
from antenna_lab.solvers.reduced_pcb import build_reduced_model,solve_reduced_model


def records():
    return [
        ['DOCTYPE','PCB','1.8'],['HEAD',{'editorVersion':'2.2.47.7'}],['CANVAS',0,0,'mm'],
        ['LAYER',1,'TOP','Top',3],['LAYER',2,'BOTTOM','Bottom',3],
        ['LAYER',11,'OUTLINE','Board',3],['LAYER',361,'SUBSTRATE','Core',0],
        ['LAYER_PHYS',1,'',1.378,0,0,1],['LAYER_PHYS',361,'air',40,1,0,1],['LAYER_PHYS',2,'',1.378,0,0,1],
        ['NET','B'],['NET','A'],
        ['LINE','left',0,'B',1,-400,0,-100,0,10,0],
        ['LINE','right',0,'A',1,100,0,400,0,10,0],
        ['PAD','lp',0,'B',1,'1',-100,0,0,None,['RECT',40,40,0],[]],
        ['PAD','rp',0,'A',1,'2',100,0,0,None,['RECT',40,40,0],[]],
        ['POLY','board',0,'',11,1,['R',-500,500,1000,1000,0,0],0],
        ['POUR','ground',0,'B',2,.2,'GND',0,[['R',-500,500,1000,1000,0,0]],['SOLID',8],0,0],
        ['POURED','filled','ground',0,True,[[-50,50,'L',50,50,50,-50,-50,-50,-50,50]]],
    ]


def encoded(items):return ('\n'.join(json.dumps(r) for r in items)+'\n').encode()

def config():return dict(port=dict(mode='explicit',negative_mm=[-2.032,0],positive_mm=[2.032,0],width_mm=.508))


class EasyEdaTests(unittest.TestCase):
    def test_parse_units_provenance_and_determinism(self):
        raw=encoded(records());a=parse_easyeda_source(raw);b=parse_easyeda_source(raw)
        self.assertEqual(a,b);self.assertEqual(a.source_sha256,sha256(raw).hexdigest())
        self.assertEqual(a.format_version,'1.8');self.assertEqual(a.editor_version,'2.2.47.7')
        self.assertEqual(a.canvas_display_unit,'mm');self.assertEqual(a.semantics['nets'],['B','A'])
        self.assertEqual(a.routes[1].start_xy_m,(.00254,0.))
        self.assertEqual(a.routes[1].width_m,.000254)
        self.assertEqual(a.routes[1].layer_role,'top');self.assertEqual(a.routes[1].record_index,14)
        self.assertAlmostEqual(metres(984.252,'board'),.0250000008)
        self.assertEqual(metres(10,'poured',poured=True),metres(100,'pcb'))
        self.assertEqual(a.records[0]['data'],records()[0])
        snapshot=a.as_dict();json.dumps(snapshot,allow_nan=False)
        snapshot['records'][0]['data'][1]='changed';self.assertEqual(a.records[0]['data'][1],'PCB')

    def test_arc_signed_sweep_and_center_not_tessellation(self):
        items=records()
        for i,angle in enumerate((59.0156,-104.918,180,-180,52.916)):
            items.append(['ARC',f'a{i}',0,'A',1,100,0,200,0,angle,10,0])
        source=parse_easyeda_source(encoded(items));arcs=source.routes[2:]
        self.assertEqual([r.signed_sweep_deg for r in arcs],[59.0156,-104.918,180,-180,52.916])
        self.assertGreater(arcs[0].center_xy_m[1],0)
        self.assertLess(arcs[1].center_xy_m[1],0)
        self.assertEqual(arcs[2].center_xy_m,arcs[3].center_xy_m)
        self.assertEqual(arc_center((0,0),(2,0),180,'test'),(1.,0.))

    def test_via_pad_net_and_raw_materials(self):
        items=records()+[['VIA','v1',0,'B','',-350,0,10,20,0,None,None,0,[]],
                         ['PAD_NET','comp','1','A','pad'],['META_NOTE',{'anything':42}]]
        src=parse_easyeda_source(encoded(items));v=src.vias[0]
        self.assertEqual(v.drill_diameter_m,.000254);self.assertEqual(v.pad_diameter_m,.000508)
        self.assertEqual(src.semantics['pad_nets'][0]['net'],'A')
        self.assertFalse(src.semantics['unsupported_records'])
        layout=build_source_layout(src)
        override=config();override['drills']=dict(pth_model='solid_pec_equivalent',pth_plating_um=25)
        g=source_layout_geometry(layout,override)
        self.assertEqual(g.drills[0].connected_layer_roles,('top','bottom'))
        self.assertEqual(g.drills[0].equivalent_outer_radius_m,.000254/2+25e-6)
        with self.assertRaisesRegex(ConfigurationError,'barrel plating'):
            source_layout_geometry(layout,config())

    def test_unusual_dielectric_is_legal(self):
        items=records();items[8][3]=25000/25.4
        src=parse_easyeda_source(encoded(items));layout=build_source_layout(src)
        self.assertAlmostEqual(layout['dielectric']['z_min_m'],-.025)
        self.assertEqual(layout['dielectric']['epsilon_r'],1)

    def test_bad_inputs_fail_closed(self):
        for change,pattern in [
            (lambda r:r[0].__setitem__(2,'9.0'),'version'),
            (lambda r:r[1][1].__setitem__('editorVersion','3.0'),'units unresolved'),
            (lambda r:r[12].__setitem__(9,float('nan')),'strict JSON'),
            (lambda r:r[12].pop(),'field count'),
            (lambda r:r[16].__setitem__(6,['BEZIER',1,2]),'polygon subtype'),
        ]:
            with self.subTest(pattern=pattern):
                r=records();change(r)
                with self.assertRaisesRegex(ConfigurationError,pattern):parse_easyeda_source(encoded(r))
        src=parse_easyeda_source(encoded(records()+[['FILL','unsupported',0,'A',1]]))
        with self.assertRaisesRegex(ConfigurationError,'FILL unsupported'):build_source_layout(src)

    def test_pour_boundary_is_not_filled_without_poured(self):
        src=parse_easyeda_source(encoded(records()[:-1]))
        with self.assertRaisesRegex(ConfigurationError,'materialized POURED geometry unavailable'):
            build_source_layout(src)

    def test_missing_footprint_precise_dependency(self):
        items=records()+[
            ['COMPONENT','c1',0,1,10,10,90,{},0],
            ['ATTR','c1attr',0,'c1',3,None,None,'Footprint','unavailable_hash'],
            ['PAD_NET','c1','1','A','pad1']]
        src=parse_easyeda_source(encoded(items));layout=build_source_layout(src)
        self.assertEqual(layout['missing_dependencies'][0]['footprint_id'],'unavailable_hash')
        with self.assertRaisesRegex(ConfigurationError,'source component.*footprint pad geometry unavailable') as err:
            source_layout_geometry(layout,config())
        self.assertNotIn('Gerber required',str(err.exception))

    def test_source_only_fast_without_manufacturing_files(self):
        src=parse_easyeda_source(encoded(records()));layout=build_source_layout(src)
        self.assertEqual(layout['manufacturing_validation'],'not_requested')
        g=source_layout_geometry(layout,config());before=g.as_dict()
        normalized,_=normalize_port_orientation(g)
        modeled,_,audit=apply_geometry_resolution(normalized,PcbGrid())
        self.assertEqual(audit['topology_status'],'PASS')
        self.assertEqual(g.as_dict(),before)
        self.assertEqual([(r.id,r.net,r.signed_sweep_deg) for r in modeled.source_routes],
                         [(r.id,r.net,r.signed_sweep_deg) for r in src.routes])
        model=build_reduced_model(modeled)
        self.assertEqual(model['extraction_method'],'easyeda_source_routes')
        self.assertEqual(len(model['line_sections']),2)
        self.assertEqual(len(solve_reduced_model(model,[1.42e9],50)),1)

    def test_source_only_cli_and_inspection(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'source.epcb';path.write_bytes(encoded(records()))
            overrides=root/'source-config.json';overrides.write_text(json.dumps(config()))
            # Prove no accidental manufacturing loader invocation.
            with patch('antenna_lab.pcb.bundle.load_bundle_geometry',side_effect=AssertionError('Gerber called')):
                result=run_reduced(None,root/'solve',easyeda_source=path,source_config=overrides)
                self.assertEqual(result['status'],'completed')
                self.assertEqual(result['manufacturing_validation'],'not_requested')
                inspect=run_reduced(None,root/'inspect',easyeda_source=path,inspect_source=True)
                self.assertEqual(inspect['status'],'source_inspected')
                self.assertFalse((root/'inspect'/'impedance.csv').exists())
                self.assertTrue((root/'inspect'/'source_model.json').exists())

    def test_source_arc_survives_projection_but_physics_remains_guarded(self):
        r=records();r[13]=['ARC','right',0,'A',1,100,0,400,0,180,10,0]
        src=parse_easyeda_source(encoded(r));g=source_layout_geometry(build_source_layout(src),config())
        n,_=normalize_port_orientation(g);g,_,_=apply_geometry_resolution(n,PcbGrid())
        self.assertEqual(g.source_routes[1].signed_sweep_deg,180)
        with self.assertRaisesRegex(ConfigurationError,'EasyEDA source ARC unsupported.*right'):
            build_reduced_model(g)

    def test_source_short_and_unknown_layers_not_ignored(self):
        items=records()+[['LINE','short',0,'A',1,-400,0,-100,0,10,0]]
        with self.assertRaisesRegex(ConfigurationError,'source short'):
            build_source_layout(parse_easyeda_source(encoded(items)))
        items=records();items[12][4]=999
        with self.assertRaisesRegex(ConfigurationError,'unresolved LAYER'):
            parse_easyeda_source(encoded(items))


if __name__=='__main__':unittest.main()
