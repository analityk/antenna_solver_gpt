"""Gerbonara round drills, physical connectivity, native fakes and saved reports."""
from copy import deepcopy
from dataclasses import replace, asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import contextlib
import io
import json
import unittest
from unittest.mock import patch
import numpy as np

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.bundle import load_bundle_geometry, load_physical_config
from antenna_lab.pcb.drills import read_drill_source, connected_layers, validate_drills
from antenna_lab.pcb.transform import normalize_port_orientation, inverse_transform_geometry
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from antenna_lab.pcb.gerber_control import run_gerber_control
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh, make_pcb_mesh_anchor_plan
from antenna_lab.solvers.openems_pcb import install_pcb_geometry
from antenna_lab.solvers.pcb_fields import pcb_sample_mask
from antenna_lab.visualization.pcb_drills import drill_paths
from antenna_lab.visualization.report import generate_report
from test_pcb_bundle import bundle_fixture
from test_pcb_multilayer import physical_stack, solid_gerber, BAND
from test_pcb_clearances import ClearanceCSX
from test_pcb_fields import FieldEngine
import test_pcb_copper


def drill_text(x=5,y=10,diameter=.3,comment='',body=None):
    return f'M48\n{comment}\nMETRIC,TZ\nT01C{diameter:.6f}\n%\nT01\n'+(body or f'X{x:.6f}Y{y:.6f}\n')+'M30\n'


class DrillCSX(ClearanceCSX):
    def __init__(self):super().__init__();self.cylinders=[];self.mutate=False
    def cylinder_property(self,prop,name):
        def cylinder(**kw):
            self.cylinders.append((name,kw))
            if self.mutate:self.grid.lines['x']=self.grid.lines['x'][:-1]
        prop.AddCylinder=cylinder
        return prop
    def AddMetal(self,name):return self.cylinder_property(super().AddMetal(name),name)
    def AddMaterial(self,name,**kw):return self.cylinder_property(super().AddMaterial(name,**kw),name)


class DrillTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def fixture(self,*,vertical=False,antipad=True,drills=True):
        directory=bundle_fixture(self.root/'gerbers',loop=True,vertical=vertical)
        for i in (1,2):
            text=solid_gerber()
            if i==1 and antipad:
                text=text.replace('M02*','%LPC*%\n%ADD11C,1*%\nD11*\nX500000Y1000000D03*\nM02*')
            (directory/f'board-In{i}_Cu.gbr').write_text(text)
        (directory/'board-B_Cu.gbr').write_text(solid_gerber())
        if drills:
            (directory/'Drill_PTH.drl').write_text(drill_text())
            (directory/'Drill_NPTH.drl').write_text(drill_text(8,9,.5))
        value=physical_stack();value['drills']=dict(pth_plating_um=25,pth_model='solid_pec_equivalent')
        config=self.root/'physical.json';config.write_text(json.dumps(value))
        return directory,config
    def loaded(self,**kw):
        directory,config=self.fixture(**kw);cfg,source,meta=load_bundle_geometry(directory,config)
        geometry,transform=normalize_port_orientation(source)
        settings,_=gerber_quality_settings('preview',**BAND)
        return directory,config,cfg,source,geometry,transform,settings,meta

    def test_parser_classification_units_tools_metadata_and_rejections(self):
        for name,comment,expected in [('part-PTH.drl','',True),('part-NPTH.drl','',False),
            ('unknown.drl',';TYPE=PLATED',True),('unknown.drl',';Layer: Drill NPTH',False),
            ('unknown.drl','; #@! TF.FileFunction,Plated,1,4,PTH*',True)]:
            with self.subTest(name=name,comment=comment):
                p=self.root/name;p.write_text(drill_text(comment=comment));holes,meta=read_drill_source(p,4)
                self.assertEqual(meta['classification'],'PTH' if expected else 'NPTH')
                self.assertEqual(holes,[(.005,.010,.0003,'T01')]);self.assertEqual(meta['tool_diameters_m'],{'T01':.0003})
                self.assertEqual(len(meta['sha256']),64)
        p=self.root/'inch-PTH.drl';p.write_text('M48\nINCH,TZ,00.0000\nT02C0.010\n%\nT02\nX0.100Y0.200\nM30\n')
        holes,_=read_drill_source(p,4);np.testing.assert_allclose(holes[0][:3],(.00254,.00508,.000254),atol=1e-18,rtol=0)
        for name,text,reason in [('unknown.drl',drill_text(),'Ambiguous'),
            ('part-PTH.drl',drill_text(comment=';TYPE=NON_PLATED'),'Ambiguous'),
            ('part-PTH-L1-L2.drl',drill_text(),'span'),
            ('part-PTH.drl',drill_text(comment='; #@! TF.FileFunction,Plated,2,4,PTH*'),'span'),
            ('part-PTH.drl',drill_text(comment=';Contents: Blind / Drill / Plated'),'unsupported'),
            ('part-PTH.drl',drill_text(body='X5.0Y10.0G85X6.0Y10.0\n'),'slot'),
            ('part-PTH.drl',drill_text(body='G00X5.0Y10.0\nM15\nG01X6.0Y10.0\nM16\n'),'slot')]:
            p=self.root/name;p.write_text(text)
            with self.subTest(name=name,text=text),self.assertRaisesRegex(ConfigurationError,reason):read_drill_source(p,4)

    def test_import_connectivity_normalization_and_config(self):
        _,path,_,source,g,t,_,meta=self.loaded(vertical=True)
        self.assertEqual(len(source.drills),2)
        pth=next(d for d in source.drills if d.plated)
        self.assertAlmostEqual(pth.equivalent_outer_radius_m,.000175,delta=1e-19)
        self.assertEqual(pth.connected_layer_roles,('top','inner2','bottom'))
        self.assertEqual(next(d for d in source.drills if not d.plated).connected_layer_roles,())
        self.assertEqual({r['classification'] for r in meta['drill_sources']},{'PTH','NPTH'})
        before=source.as_dict();normal,_=normalize_port_orientation(source)
        restored=inverse_transform_geometry(normal,t)
        for a,b in zip(source.drills,restored.drills):
            np.testing.assert_allclose((a.x_m,a.y_m),(b.x_m,b.y_m),atol=1e-17,rtol=0)
        self.assertEqual(source.as_dict(),before);self.assertEqual(normal.as_dict(),g.as_dict())
        v=json.loads(path.read_text())
        for bad in (0,-1,float('nan'),float('inf'),True,'25'):
            changed=deepcopy(v);changed['drills']['pth_plating_um']=bad;path.write_text(json.dumps(changed))
            with self.assertRaises(ConfigurationError):load_physical_config(path)
        changed=deepcopy(v);changed['drills']['pth_model']='shell';path.write_text(json.dumps(changed))
        with self.assertRaises(ConfigurationError):load_physical_config(path)

    def test_contact_without_antipad_orphan_and_feed_intrusion(self):
        directory,path,_,source,_,_,_,_=self.loaded(antipad=False)
        self.assertEqual(next(d for d in source.drills if d.plated).connected_layer_roles,('top','inner1','inner2','bottom'))
        # Same legal drill disk no longer has sufficient physical copper contacts.
        source.copper=[replace(c,vertices_xy_m=tuple((x+1,y+1) for x,y in c.vertices_xy_m)) if c.layer_role!='top' else c for c in source.copper]
        with self.assertRaisesRegex(ConfigurationError,'orphan'):validate_drills(source)
        (directory/'Drill_PTH.drl').write_text(drill_text(12.57,12.573))
        with self.assertRaisesRegex(ConfigurationError,'port gap'):load_bundle_geometry(directory,path)

    def test_exact_centres_plating_independent_mesh_and_native_priorities(self):
        _,_,cfg,_,g,_,s,_=self.loaded();original=g.as_dict();meshes=[]
        for thickness in (25e-6,50e-6):
            changed=replace(g,drills=tuple(replace(d,plating_thickness_m=thickness,
                equivalent_outer_radius_m=d.drill_diameter_m/2+thickness) if d.plated else d for d in g.drills))
            mesh=make_pcb_domain_mesh(changed,s,gerber_quality='preview');meshes.append(mesh)
            plan=make_pcb_mesh_anchor_plan(changed)
            for d in changed.drills:
                self.assertIn(d.x_m,mesh.x_lines_m);self.assertIn(d.y_m,mesh.y_lines_m)
                self.assertIn((d.x_m,d.y_m),mesh.drill_centres_xy_m)
                self.assertIn(d.x_m,plan.x_required_m);self.assertIn(d.y_m,plan.y_required_m)
            csx=DrillCSX();m=install_pcb_geometry(csx,changed,mesh,s,copper_config=cfg,gerber_quality='preview')
            self.assertEqual(len(csx.cylinders),2)
            self.assertEqual(tuple(csx.grid.lines[a] for a in 'xyz'),(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m))
            highest=max(p['clearance_priority'] or p['copper_priority'] for p in m['copper_clearances']['priorities'])
            for name,k in csx.cylinders:
                d=next(d for d in changed.drills if d.plated==('pth_solid' in name))
                self.assertEqual(k['start'],[d.x_m,d.y_m,0]);self.assertEqual(k['stop'],[d.x_m,d.y_m,g.bounds[0][2]])
                self.assertEqual(k['radius'],d.equivalent_outer_radius_m if d.plated else d.drill_diameter_m/2)
                self.assertGreater(k['priority'],highest)
            self.assertTrue(any(call[:2]==('AddMetal','pcb_pth_solid_PEC') for call in csx.copper_calls))
            self.assertIn(('pcb_npth_air',{'epsilon':1.,'kappa':0.}),[(a,b) for a,b,_ in csx.materials])
        self.assertEqual(meshes[0],meshes[1]);self.assertEqual(g.as_dict(),original)
        csx=DrillCSX();csx.mutate=True
        with self.assertRaisesRegex(ConfigurationError,'grid|siatk'):install_pcb_geometry(csx,g,meshes[0],s,copper_config=cfg,gerber_quality='preview')

    def test_mask_and_vertical_and_top_paths(self):
        _,_,_,_,g,_,_,_=self.loaded()
        for d in g.drills:
            lines=([d.x_m],[d.y_m],[-.0005])
            axes=([d.x_m-.00001,d.x_m,d.x_m+.00001],[d.y_m-.00001,d.y_m,d.y_m+.00001],[-.00051,-.0005,-.00049])
            mask=pcb_sample_mask(lines,axes,g).item()
            self.assertEqual(bool(mask&1),d.plated)
            self.assertEqual(bool(mask&2),d.plated)
            paths=drill_paths(g.as_dict(),dict(name='xz_feed',actual_position_m=d.y_m))
            self.assertTrue(paths);self.assertTrue(any(any(p[1]<0 for p in path['points']) for path in paths))
        # NPTH also removes accidentally overlapping planar copper at top.
        d=next(d for d in g.drills if not d.plated)
        self.assertEqual(pcb_sample_mask(([d.x_m],[d.y_m],[0]),
            ([d.x_m-1e-5,d.x_m,d.x_m+1e-5],[d.y_m-1e-5,d.y_m,d.y_m+1e-5],[-1e-5,0,1e-5]),g).item(),0)
        self.assertEqual(len(drill_paths(g.as_dict(),dict(name='xy_air',actual_position_m=.0001))),2)

    def test_v1_and_no_drill_compatibility_missing_plating(self):
        directory,path=self.fixture(drills=False)
        cfg,g,meta=load_bundle_geometry(directory,path)
        self.assertEqual(g.drills,());self.assertEqual(meta['drill_sources'],[])
        (directory/'Drill_PTH.drl').write_text(drill_text())
        v=json.loads(path.read_text());v.pop('drills');path.write_text(json.dumps(v))
        with self.assertRaisesRegex(ConfigurationError,'explicit v2 drills'):load_bundle_geometry(directory,path)
        with self.assertRaisesRegex(ConfigurationError,'Unsupported'):load_bundle_geometry(directory)
        (directory/'Drill_PTH.drl').unlink();(directory/'Drill_NPTH.drl').write_text(drill_text(8,9,.5))
        self.assertEqual(len(load_bundle_geometry(directory,path)[1].drills),1)

    def test_close_distinct_centres_never_suppressed_and_budget_fails(self):
        from antenna_lab.solvers.pcb_mesh import make_gerber_mesh_anchor_plan
        directory,path=self.fixture()
        (directory/'Drill_PTH.drl').write_text(drill_text(body='X5.000Y10.000\nX5.030Y17.000\n'))
        _,source,_=load_bundle_geometry(directory,path);g,_=normalize_port_orientation(source)
        settings,_=gerber_quality_settings('preview',**BAND)
        for quality in ('preview','design','verify'):
            plan,metadata=make_gerber_mesh_anchor_plan(g,settings,quality)
            for d in g.drills:
                self.assertIn(d.x_m,plan.x_required_m);self.assertIn(d.y_m,plan.y_required_m)
            self.assertEqual(metadata['drill_centres_xy_m'],tuple((d.x_m,d.y_m) for d in g.drills))
        with patch('antenna_lab.solvers.openems.native_modules',side_effect=AssertionError('must stop before native')):
            with self.assertRaisesRegex(ConfigurationError,'max_cells'):
                make_pcb_domain_mesh(g,replace(settings,max_cells=10),gerber_quality='preview')

    def test_fake_single_run_and_offline_report(self):
        directory,path=self.fixture();csx=DrillCSX();engine=FieldEngine(csx);out=self.root/'run'
        with test_pcb_copper.CopperTests.natives(self,csx,engine),contextlib.redirect_stdout(io.StringIO()):
            result=run_gerber_control(directory,out,pcb_config=path,quality='preview',**BAND)
        self.assertEqual(result['status'],'completed');self.assertEqual(sum(c[0]=='Run' for c in engine.calls),1)
        saved=json.loads((out/'geometry.json').read_text());self.assertEqual(len(saved['drills']),2)
        self.assertEqual(len(result['import']['drill_sources']),2)
        self.assertEqual(len(result['import']['drills']),2)
        for file in directory.iterdir():file.unlink()
        with patch('antenna_lab.solvers.openems.native_modules',side_effect=AssertionError('offline')):
            report=generate_report(out,self.root/'offline.html')
        text=report.read_text();self.assertIn('Drills / vias',text);self.assertIn('solid PEC equivalent cylinder',text)
        self.assertIn('inner2',text);self.assertTrue((out/'plots/geometry.png').exists())
        json.dumps(result,allow_nan=False)


if __name__=='__main__':unittest.main()
