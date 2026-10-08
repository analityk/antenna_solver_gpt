"""Ideal netlist/placement contracts; native fakes only, never FDTD binaries."""
import contextlib
from copy import deepcopy
from dataclasses import replace, asdict, FrozenInstanceError
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.bundle import load_bundle_geometry
from antenna_lab.pcb.components import (ideal_value, read_netlist, read_placements,
    discover_component_sources, terminal_gap, IDEAL_NOTE)
from antenna_lab.pcb.gerber_control import run_gerber_control
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from antenna_lab.pcb.model import CopperPolygon, PcbDrill
from antenna_lab.pcb.regions import copper_shape
from antenna_lab.pcb.validation import TOLERANCE_M
from antenna_lab.pcb.geometry_resolution import apply_geometry_resolution
from antenna_lab.pcb.grid import PcbGrid
from shapely.geometry import LineString, Point
from antenna_lab.pcb.transform import normalize_port_orientation, inverse_transform_geometry
from antenna_lab.solvers.pcb_mesh import (make_pcb_domain_mesh, make_gerber_mesh_anchor_plan,
    make_pcb_mesh_anchor_plan)
from antenna_lab.solvers.pcb_components import resolve_component_boxes
from antenna_lab.solvers.openems_pcb import install_pcb_geometry, prepare_pcb_xml_model
from antenna_lab.solvers.pcb_fields import pcb_sample_mask
from antenna_lab.visualization.report import generate_report
from antenna_lab.visualization.pcb_components import component_paths
from test_pcb_bundle import bundle_fixture
from test_pcb_multilayer import physical_stack, solid_gerber, BAND
from test_pcb_drills import DrillCSX
from test_pcb_fields import FieldEngine
import test_pcb_copper


def component_fixture(root,vertical=False):
    directory=bundle_fixture(root/'gerbers')
    entries={};pins=[];lines=['%FSLAX45Y45*%','%MOMM*%']
    placements={'CSRC':((18,14),(20,14),(1.,2.),'0',('A','B')),
                'R1':((5,5),(7,5),(1.,2.),'49.9Ω',('A','n1')),
                'C1':((15,5),(15,7),(2.,1.),'100pF',('n1','n2')),
                'L1':((5,18),(7,18),(1.,2.),'18nH',('n2','B'))}
    def xy(p):return (25-p[1],p[0]) if vertical else p
    for i,(ref,(a,b,size,value,nets)) in enumerate(placements.items(),10):
        size=size[::-1] if vertical else size
        lines+= [f'%ADD{i}R,{size[0]}X{size[1]}*%',f'D{i}*']
        for pin,(p,net) in enumerate(zip((a,b),nets),1):
            x,y=xy(p);lines+=[f'X{round(x*100000)}Y{round(y*100000)}D03*']
            pins.append(dict(PIN_NAME=f'{ref}_{pin}',PIN_X=x,PIN_Y=y,LAYER='T',PIN_TYPE='SMD',NET_NAME=net,
                             PAD_SIZEX=size[0],PAD_SIZEY=size[1],PAD_ANGLE=0))
        entries['g'+ref]=dict(props=dict(Designator=ref,Value=value,Description='not electrical',DCR='100Ω'),pins=dict(zip(('1','2'),nets)))
    lines+=['M02*'];(directory/'Gerber_TopLayer.GTL').write_text('\n'.join(lines))
    (directory/'board-B_Cu.gbr').write_text(solid_gerber())
    enet=directory/'board.enet';enet.write_text(json.dumps(entries),encoding='utf8')
    fields=list(pins[0]);rows=[[p[k] for k in fields] for p in pins]
    pseudo=dict(pins[0],PIN_NAME='PAD1_1',PIN_TYPE='unsupported',NET_NAME='ignore')
    rows.append([pseudo[k] for k in fields])
    probe=directory/'FlyingProbeTesting.json';probe.write_text(json.dumps(dict(lengthUnit='mm',pins=dict(fields=fields,rows=rows))))
    config=root/'physical.json';config.write_text(json.dumps(physical_stack(2)))
    return directory,config,enet,probe


class ComponentCSX(DrillCSX):
    def __init__(self):super().__init__();self.lumped=[];self.component_mutation=False
    def AddLumpedElement(self,name,**parameters):
        assert self.metals or self.copper_calls, 'copper must be installed first'
        calls=[];self.lumped.append((name,parameters,calls))
        def add_box(**kw):
            calls.append(kw)
            if self.component_mutation:self.grid.lines['x']=self.grid.lines['x'][:-1]
        return SimpleNamespace(AddBox=add_box)


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.directory,self.config,self.enet,self.probe=component_fixture(self.root)

    def loaded(self):
        config,source,meta=load_bundle_geometry(self.directory,self.config)
        geometry,transform=normalize_port_orientation(source)
        settings,_=gerber_quality_settings('preview',**BAND)
        return config,source,geometry,transform,settings,meta

    def test_discovery_and_legacy_without_netlist(self):
        cfg,source,g,t,s,meta=self.loaded()
        selected=[r for r in meta['discovered_files'] if r['role'] in ('enet','flying_probe')]
        self.assertEqual(len(selected),2)
        for r in selected:self.assertEqual(r['disposition'],'modeled');self.assertEqual(len(r['sha256']),64)
        self.assertEqual(source.source_port.source_refdes,'CSRC')
        self.assertEqual(source.source_port.source_pin_nets,('A','B'))
        self.assertEqual({c.id for c in g.components},{'R1','C1','L1'})
        self.probe.unlink()
        with self.assertRaisesRegex(ConfigurationError,'FlyingProbe'):discover_component_sources(self.directory)
        self.enet.unlink();self.assertIsNone(discover_component_sources(self.directory))
        # No ENET: the old two-pad feed path and geometry still work unchanged.
        bundle_fixture(self.directory)
        cfg,source,meta=load_bundle_geometry(self.directory,self.config)
        self.assertEqual(source.components,());self.assertIsNone(source.source_port)
        self.assertEqual(meta['feed_detection']['mode'],'auto')

    def test_duplicate_sources_and_ambiguous_probe(self):
        second=self.directory/'other.enet';second.write_bytes(self.enet.read_bytes())
        with self.assertRaisesRegex(ConfigurationError,'exactly one'):discover_component_sources(self.directory)
        second.unlink();second=self.directory/'FLYINGPROBETESTING.JSON';second.write_bytes(self.probe.read_bytes())
        # Explicit listing also exercises the ambiguity on case-insensitive Windows.
        with patch.object(Path,'iterdir',return_value=iter((self.enet,self.probe,second))):
            with self.assertRaises(ConfigurationError):discover_component_sources(self.directory)

    def test_values_units_and_strict_source_rules(self):
        for kind,text,expected in [('R','49.9Ω',49.9),('R','1ohm',1),('R','2R',2),('R','3mΩ',.003),
            ('R','4kΩ',4000),('R','5MΩ',5e6),('C','100pF',1e-10),('C','1µF',1e-6),('C','2uF',2e-6),
            ('C','2nF',2e-9),('C','1F',1),('L','1H',1),('L','2pH',2e-12),('L','18nH',18e-9),
            ('L','1µH',1e-6),('L','1uH',1e-6),('L','2mH',.002)]:
            with self.subTest(text=text):self.assertAlmostEqual(ideal_value(kind,text)/expected,1,places=14)
        for kind,text in [('R','0Ω'),('C','-1pF'),('L','NaNH'),('R','infΩ'),('C','1e400F'),('R','49.9'),('L','18nH ±5%')]:
            with self.subTest(text=text),self.assertRaises(ConfigurationError):ideal_value(kind,text)
        original=json.loads(self.enet.read_text())
        entries=read_netlist(self.enet)
        self.assertEqual(entries['CSRC'][:2],('SOURCE',0));self.assertEqual(entries['R1'][1],49.9)
        for change in ('zero','bad_source','duplicate','unsupported','three_pins','missing_source'):
            changed=deepcopy(original)
            if change=='zero':changed['gR1']['props']['Value']='0Ω'
            if change=='bad_source':changed['gCSRC']['props']['Value']='0F'
            if change=='duplicate':changed['duplicate']=deepcopy(changed['gCSRC'])
            if change=='unsupported':changed['gR1']['props']['Designator']='U1'
            if change=='three_pins':changed['gR1']['pins']['3']='extra'
            if change=='missing_source':del changed['gCSRC']
            self.enet.write_text(json.dumps(changed))
            with self.subTest(change=change),self.assertRaises(ConfigurationError):read_netlist(self.enet)

    def test_placement_rejections_nets_layer_pin_count_axis(self):
        original=json.loads(self.probe.read_text());fields=original['pins']['fields']
        for key,value in [('NET_NAME','wrong'),('LAYER','B'),('PIN_TYPE','THT'),('PIN_X',float('inf')),('PAD_ANGLE',45)]:
            changed=deepcopy(original);changed['pins']['rows'][0][fields.index(key)]=value
            self.probe.write_text(json.dumps(changed))
            with self.subTest(key=key),self.assertRaises(ConfigurationError):self.loaded()
        for duplicate in (True,False):
            changed=deepcopy(original)
            if duplicate:changed['pins']['rows'].append(changed['pins']['rows'][0])
            else:changed['pins']['rows'].pop(0)
            self.probe.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ConfigurationError,'missing/ambiguous'):self.loaded()
        self.probe.write_text(json.dumps(original));_,_,g,_,_,_=self.loaded()
        with self.assertRaisesRegex(ConfigurationError,'axis-aligned'):
            terminal_gap('bad',(((0.,0.),(.1,.1)),((.001,.001),(.1,.1))),
                [CopperPolygon('a',((-.1,-.1),(.1,-.1),(.1,.1),(-.1,.1)),0.)])

    def test_physical_gap_holes_and_transform_roundtrip(self):
        config,source,g,t,s,meta=self.loaded()
        self.assertEqual({c.axis for c in source.components},{'x','y'})
        for c in source.components:
            self.assertAlmostEqual(np.linalg.norm(np.subtract(c.gap_stop_xy_m,c.gap_start_xy_m)),.001,delta=1e-17)
        # A new copper extension changes actual gap, even with unchanged pad metadata.
        c=next(c for c in source.components if c.id=='R1')
        owner=next(p for p in source.top_copper if min(v[0] for v in p.vertices_xy_m)<.005<max(v[0] for v in p.vertices_xy_m) and min(v[1] for v in p.vertices_xy_m)<.005<max(v[1] for v in p.vertices_xy_m))
        extended=replace(owner,vertices_xy_m=tuple((x+.0002 if x>.005 else x,y) for x,y in owner.vertices_xy_m))
        copper=[extended if p.id==owner.id else p for p in source.copper]
        gap=terminal_gap('R1',((c.pin1_xy_m,(.001,.002)),(c.pin2_xy_m,(.001,.002))),copper)
        self.assertAlmostEqual(abs(gap[2][0]-gap[1][0]),.0008,delta=1e-17)
        before=source.as_dict();restored=inverse_transform_geometry(g,t)
        for a,b in zip(source.components,restored.components):
            for attr in ('pin1_xy_m','pin2_xy_m','gap_start_xy_m','gap_stop_xy_m','contact_window_xy_m'):
                np.testing.assert_allclose(getattr(a,attr),getattr(b,attr),rtol=0,atol=1e-17)
        self.assertEqual(source.as_dict(),before)
        np.testing.assert_allclose(restored.source_port.pin1_xy_m,source.source_port.pin1_xy_m,rtol=0,atol=1e-17)
        other=self.root/'vertical';other.mkdir();directory,config,_,_=component_fixture(other,vertical=True)
        _,source,_=load_bundle_geometry(directory,config);normal,t=normalize_port_orientation(source)
        self.assertTrue(t.exact_orthogonal)
        restored=inverse_transform_geometry(normal,t)
        for original,back in zip(source.components,restored.components):
            self.assertEqual(original.axis,back.axis)
            np.testing.assert_allclose(original.contact_window_xy_m,back.contact_window_xy_m,rtol=0,atol=1e-17)
            np.testing.assert_allclose(original.pin1_xy_m,back.pin1_xy_m,rtol=0,atol=1e-17)
        self.assertEqual(normal.port.negative_xy_m[1],0.)
        self.assertEqual(normal.port.positive_xy_m[1],0.)
        self.assertLess(normal.port.negative_xy_m[0],0);self.assertGreater(normal.port.positive_xy_m[0],0)
        for c in normal.components:
            axis='xy'.index(c.axis);self.assertEqual(c.gap_start_xy_m[1-axis],c.gap_stop_xy_m[1-axis])

    def test_mesh_values_no_z_refinement_exact_faces_and_frozen_install(self):
        cfg,source,g,t,s,meta=self.loaded();before=g.as_dict()
        mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview');axes=(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)
        changed=replace(g,components=tuple(replace(c,value_si=c.value_si*10) for c in g.components))
        self.assertEqual(mesh,make_pcb_domain_mesh(changed,s,gerber_quality='preview'))
        no_components=make_pcb_domain_mesh(replace(g,components=()),s,gerber_quality='preview')
        self.assertEqual(mesh.z_lines_m,no_components.z_lines_m)
        for c in g.components:
            i='xy'.index(c.axis)
            for p in (c.gap_start_xy_m,c.gap_stop_xy_m):self.assertIn(p[i],axes[i])
        specs=resolve_component_boxes(g,axes);self.assertEqual(len(specs),3)
        with self.assertRaises(FrozenInstanceError):specs[0].value_si=1
        csx=ComponentCSX();metadata=install_pcb_geometry(csx,g,mesh,s,copper_config=cfg,gerber_quality='preview')
        self.assertEqual(tuple(csx.grid.lines[a] for a in 'xyz'),axes)
        self.assertEqual(len(csx.lumped),3);self.assertEqual(g.as_dict(),before)
        for name,params,boxes in csx.lumped:
            spec=next(v for v in specs if name.endswith(v.id))
            self.assertEqual(params,dict(ny='xyz'.index(spec.direction),caps=True,LEtype=1,**{spec.kind:spec.value_si}))
            self.assertEqual(boxes,[dict(start=list(spec.start_m),stop=list(spec.stop_m),priority=5)])
            self.assertIn(spec.stop_m[2],mesh.z_lines_m)
        self.assertEqual(len(metadata['ideal_components']),3)
        csx=ComponentCSX();csx.component_mutation=True
        with self.assertRaisesRegex(ConfigurationError,'grid audit'):install_pcb_geometry(csx,g,mesh,s,copper_config=cfg,gerber_quality='preview')

    def test_modeled_xy_contact_bounds_are_critical_in_every_policy(self):
        _,_,g,_,_,_=self.loaded()
        g,_,_=apply_geometry_resolution(g,PcbGrid())
        # Narrow windows strictly inside the physical pads: copper bounding boxes
        # alone cannot supply these transverse anchors (X and Y components).
        components=[]
        for c in g.components:
            trans=1-'xy'.index(c.axis);centre=c.gap_start_xy_m[trans]
            window=tuple(tuple(centre + (-.00037 if p[i]<centre else .00037)
                               if i==trans else p[i] for i in range(2))
                         for p in c.contact_window_xy_m)
            components.append(replace(c,contact_window_xy_m=window))
        g=replace(g,components=tuple(components));before=g.as_dict()
        self.assertEqual({c.axis for c in g.components},{'x','y'})
        for quality in ('preview','design','verify'):
            settings,_=gerber_quality_settings(quality,**BAND)
            plan,meta=make_gerber_mesh_anchor_plan(g,settings,quality)
            ordinary=make_pcb_mesh_anchor_plan(g)
            mesh=make_pcb_domain_mesh(g,settings,gerber_quality=quality)
            axes=(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)
            specs=resolve_component_boxes(g,axes)
            for c,spec in zip(g.components,specs):
                axis='xy'.index(c.axis);trans=1-axis
                lo=min(p[trans] for p in c.contact_window_xy_m)
                hi=max(p[trans] for p in c.contact_window_xy_m)
                for i,values in ((axis,(c.gap_start_xy_m[axis],c.gap_stop_xy_m[axis])),(trans,(lo,hi))):
                    for value in values:
                        self.assertIn(value,(plan.x_required_m,plan.y_required_m)[i])
                        self.assertIn(value,(ordinary.x_required_m,ordinary.y_required_m)[i])
                        self.assertIn(value,meta['component_terminal_anchors_m']['xy'[i]])
                        self.assertIn(value,axes[i])
                        self.assertFalse(any(r['axis']=='xy'[i] and r['coordinate_m']==value
                                             for r in meta['suppressed_noncritical_anchors']))
                self.assertGreaterEqual(spec.start_m[trans],lo)
                self.assertLessEqual(spec.stop_m[trans],hi)
                for pin,terminal in ((c.pin1_xy_m,c.gap_start_xy_m),(c.pin2_xy_m,c.gap_stop_xy_m)):
                    owner=[copper_shape(p) for p in g.top_copper
                           if copper_shape(p).buffer(TOLERANCE_M).covers(Point(pin))]
                    self.assertEqual(len(owner),1)
                    a=list(spec.start_m[:2]);b=list(spec.stop_m[:2])
                    a[axis]=b[axis]=terminal[axis]
                    self.assertTrue(owner[0].buffer(TOLERANCE_M).covers(LineString((a,b))))
            changed=replace(g,components=tuple(replace(c,value_si={'R':100.,'C':1e-9,'L':100e-9}[c.kind])
                                               for c in g.components))
            self.assertEqual(mesh,make_pcb_domain_mesh(changed,settings,gerber_quality=quality))
            without=make_pcb_domain_mesh(replace(g,components=()),settings,gerber_quality=quality)
            self.assertEqual(mesh.z_lines_m,without.z_lines_m)
        self.assertEqual(g.as_dict(),before)

    def test_contact_audit_keeps_collision_and_ownership_protections(self):
        _,_,g,_,s,_=self.loaded()
        c=next(c for c in g.components if c.id=='R1')
        g=replace(g,components=(c,))
        mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        axes=(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)
        spec,=resolve_component_boxes(g,axes)
        x0,y0=spec.start_m[:2];x1,y1=spec.stop_m[:2]
        # Exactly one candidate cell, so collisions cannot be evaded by choosing
        # another row in the same pad. No production mesh is altered.
        c=replace(c,contact_window_xy_m=((x0,y0),(x1,y0),(x1,y1),(x0,y1)))
        g=replace(g,components=(c,))
        owner=next(p for p in g.top_copper if copper_shape(p).covers(Point(c.pin1_xy_m)))
        mx,my=(x0+x1)/2,(y0+y1)/2
        intruder=CopperPolygon('intruder',((mx-.00001,y0),(mx+.00001,y0),
                                         (mx+.00001,y1),(mx-.00001,y1)),0.)
        drill=PcbDrill('hole',mx,my,.0001,False,'NPTH','1','0'*64)
        cases={
            'ambiguous ownership':replace(g,copper=g.copper+[replace(owner,id='duplicate')]),
            'missing ownership':replace(g,copper=[p for p in g.copper if p.id!=owner.id]),
            'gap intrusion':replace(g,copper=g.copper+[intruder]),
            'source overlap':replace(g,port=replace(g.port,negative_xy_m=(x0,my),positive_xy_m=(x1,my),width_m=y1-y0)),
            'component overlap':replace(g,components=(c,replace(c,id='R2'))),
            'drill overlap':replace(g,drills=(drill,)),
            'wrong layer':replace(g,components=(replace(c,layer='bottom'),)),
            'invalid value':replace(g,components=(replace(c,value_si=0.),)),
        }
        # Partial pad contact: keep the pin and gap centre, but remove the
        # transverse ends of its contact face. Endpoint ownership still passes.
        centre=c.pin1_xy_m[1]
        narrow=replace(owner,vertices_xy_m=tuple((x,centre+(y-centre)*.001) for x,y in owner.vertices_xy_m))
        cases['incomplete face']=replace(g,copper=[narrow if p.id==owner.id else p for p in g.copper])
        for reason,invalid in cases.items():
            with self.subTest(reason=reason),self.assertRaises(ConfigurationError):
                resolve_component_boxes(invalid,axes)

    def test_box_rejects_no_transverse_cell_copper_intrusion_and_missing_faces(self):
        _,_,g,_,s,_=self.loaded();mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        axes=(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)
        c=g.components[0];axis='xy'.index(c.axis)
        damaged=list(axes);damaged[axis]=tuple(v for v in axes[axis] if v!=c.gap_start_xy_m[axis])
        with self.assertRaisesRegex(ConfigurationError,'exact longitudinal'):resolve_component_boxes(g,damaged)
        damaged=list(axes);damaged[1-axis]=(axes[1-axis][0],axes[1-axis][-1])
        with self.assertRaisesRegex(ConfigurationError,'no legal'):resolve_component_boxes(g,damaged)
        a,b=c.gap_start_xy_m,c.gap_stop_xy_m;xy=(np.asarray(a)+b)/2
        intruder=CopperPolygon('intruder',tuple((xy[0]+dx,xy[1]+dy) for dx,dy in ((-.001,-.001),(.001,-.001),(.001,.001),(-.001,.001))),0.)
        with self.assertRaisesRegex(ConfigurationError,'no legal|ambiguous'):resolve_component_boxes(replace(g,copper=g.copper+[intruder]),axes)

    def test_single_run_source_fields_masks_and_offline_report(self):
        csx=ComponentCSX();engine=FieldEngine(csx);out=self.root/'run'
        with test_pcb_copper.CopperTests.natives(self,csx,engine),contextlib.redirect_stdout(io.StringIO()):
            result=run_gerber_control(self.directory,out,pcb_config=self.config,quality='preview',field_frequency_hz=(2e9,),**BAND)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(sum(c[0]=='Run' for c in engine.calls),1)
        self.assertEqual(sum(c[0]=='AddLumpedPort' for c in engine.calls),1)
        self.assertEqual(len(csx.lumped),3)
        self.assertEqual(len(engine.port.calls),1)
        self.assertEqual(sum(c[0]=='SetGaussExcite' for c in engine.calls),1)
        self.assertFalse(any(name.endswith('CSRC') for name,_,_ in csx.lumped))
        field=json.loads((out/'fields/metadata.json').read_text());self.assertIn('8',field['mask_bits'])
        self.assertEqual(len(field['component_regions']),3)
        _,_,g,_,s,_=self.loaded();mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        axes=(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m);spec=resolve_component_boxes(g,axes)[0]
        centre=(np.asarray(spec.start_m)+spec.stop_m)/2
        mask=pcb_sample_mask(tuple([v] for v in centre),axes,g).item();self.assertTrue(mask&8)
        plane=dict(name='xz_feed',actual_position_m=centre[1])
        self.assertTrue(component_paths(g.as_dict(),plane,field['component_regions']))
        json.dumps(result,allow_nan=False)
        for path in self.directory.iterdir():path.unlink()
        with patch('antenna_lab.solvers.openems.native_modules',side_effect=AssertionError('offline')):
            report=generate_report(out,self.root/'offline.html')
        text=report.read_text();self.assertIn('Ideal components',text);self.assertIn(IDEAL_NOTE,text)
        for ref in ('CSRC','R1','C1','L1'):self.assertIn(ref,text)
        self.assertIn('50-ohm reference port',text)
        self.assertTrue((out/'plots/geometry.png').exists())


if __name__=='__main__':unittest.main()
