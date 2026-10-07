"""Ordered real Gerber fixtures, holes and native-priority fakes; never native FDTD."""
import contextlib
from dataclasses import asdict, replace
import io
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
from shapely.geometry import Point, Polygon
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.gerber import _copper, _read, CURVE_ERROR_M
from antenna_lab.pcb.bundle import load_bundle_geometry, audit_physical_feed
from antenna_lab.pcb.model import CopperPolygon
from antenna_lab.pcb.validation import validate_pcb_geometry, _contains_copper
from antenna_lab.pcb.regions import copper_shape
from antenna_lab.pcb.transform import normalize_port_orientation, inverse_transform_geometry
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from antenna_lab.pcb.gerber_control import run_gerber_control
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from antenna_lab.solvers.pcb_fields import pcb_sample_mask
from antenna_lab.solvers.pcb_clearances import copper_priority_plan
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from antenna_lab.visualization.pcb_regions import copper_patch
from antenna_lab.visualization.pcb_fields import overlays
from antenna_lab.visualization.report import generate_report
from test_pcb_bundle import bundle_fixture
from test_pcb_copper import CopperCSX
import test_pcb_copper
from test_pcb_fields import FieldEngine
from test_openems_pcb import Material
from test_pcb_multilayer import physical_stack, solid_gerber, BAND


HEADER='%FSLAX45Y45*%\n%MOMM*%\n%ADD10C,4*%\n%ADD11C,1*%\n%ADD12R,2X30*%\nG01*\n'
PLANE='G36*\nX200000Y200000D02*\nX2200000Y200000D01*\nX2200000Y2200000D01*\nX200000Y2200000D01*\nX200000Y200000D01*\nG37*\n'
HOLE='%LPC*%\nD10*\nX500000Y1200000D03*\n'
RESTORE='%LPD*%\nD11*\nX500000Y1200000D03*\n'


class AirMaterial(Material):
    def AddPolygon(self, **kwargs): self.polygons.append(kwargs)


class ClearanceCSX(CopperCSX):
    def AddMaterial(self, name, **kwargs):
        if name != 'pcb_copper_clearance_air':return super().AddMaterial(name,**kwargs)
        material=AirMaterial();self.materials.append((name,kwargs,material));return material


class ClearanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def image(self, body):
        file=self.root/'image.gtl';file.write_text(HEADER+body+'M02*\n')
        stats={};copper=_copper(_read(file,'top copper'),stats)
        return copper,stats

    def bundle(self, clear=True, restore=False):
        directory=bundle_fixture(self.root/'gerbers',loop=True)
        top=directory/'Gerber_TopLayer.GTL'
        if clear:
            top.write_text(top.read_text().replace('M02*','%ADD14C,4*%\n%ADD15C,1*%\n%LPC*%\nD14*\nX500000Y1200000D03*\n'+
                ('%LPD*%\nD15*\nX500000Y1200000D03*\n' if restore else '')+'M02*'))
        return directory

    def config(self, model='pec'):
        from antenna_lab.pcb.bundle import DEFAULT_PHYSICAL
        value=json.loads(json.dumps(DEFAULT_PHYSICAL));value['copper']['model']=model
        path=self.root/(model+'.json');path.write_text(json.dumps(value));return path

    def test_ordered_solid_circular_multiple_restore_notch_and_disconnect(self):
        cases=[(PLANE,1,0,1,0),
               (PLANE+HOLE,1,1,1,1),
               (PLANE+HOLE+'X1500000Y1200000D03*\n',1,2,1,2),
               (PLANE+HOLE+RESTORE,2,1,2,1),
               (PLANE+'%LPC*%\nD10*\nX200000Y1200000D03*\n',1,0,1,1),
               (PLANE+'%LPC*%\nD12*\nX1200000Y1200000D03*\n',2,0,1,1)]
        for body,n,holes,dark,clear in cases:
            with self.subTest(n=n,holes=holes,dark=dark,clear=clear):
                polygons,stats=self.image(body)
                self.assertEqual(len(polygons),n);self.assertEqual(sum(len(c.holes_xy_m) for c in polygons),holes)
                self.assertEqual(stats,dict(dark_primitive_count=dark,clear_primitive_count=clear,final_conductor_count=n,final_hole_count=holes))
                self.assertEqual((polygons,stats),self.image(body))
                self.assertTrue(all(copper_shape(c).is_valid for c in polygons))
        c,_=self.image(PLANE+HOLE)
        expected=.020**2-np.pi*.002**2
        self.assertAlmostEqual(copper_shape(c[0]).area,expected,delta=2*np.pi*.002*CURVE_ERROR_M)
        restored,_=self.image(PLANE+HOLE+RESTORE)
        self.assertTrue(any(_contains_copper((.005,.012),c) for c in restored))
        self.assertFalse(any(_contains_copper((.006,.012),c) for c in restored))
        reversed_order,_=self.image(PLANE+RESTORE+HOLE)
        self.assertFalse(any(_contains_copper((.005,.012),c) for c in reversed_order))
        # Full later dark restore removes the hole, rather than retaining all clears.
        filled,_=self.image(PLANE+HOLE+'%LPD*%\nD10*\nX500000Y1200000D03*\n')
        self.assertEqual(filled[0].holes_xy_m,())
        with self.assertRaises(ConfigurationError):self.image(PLANE+'%LPC*%\n'+PLANE)

    def test_positive_ring_and_aperture_clear_primitive_keep_holes(self):
        # Former blanket rejection of a positive closed arc/ring is removed.
        ring='%ADD13C,0.1*%\nD13*\nG75*\nG01X100000Y100000D02*\nG02X100000Y100000I50000J0D01*\nG01*\n'
        copper,stats=self.image(ring)
        self.assertEqual(len(copper),1);self.assertEqual(len(copper[0].holes_xy_m),1)
        self.assertEqual(stats['clear_primitive_count'],0)
        # Gerbonara expands an aperture hole into a clear graphic primitive.
        copper,stats=self.image('%ADD13C,4X2*%\nD13*\nX1000000Y1000000D03*\n')
        self.assertEqual(stats['dark_primitive_count'],1);self.assertEqual(stats['clear_primitive_count'],1)
        self.assertFalse(_contains_copper((.01,.01),copper[0]))
        self.assertEqual(len(copper[0].holes_xy_m),1)

    def test_membership_validation_normalization_and_real_hole_edge_feed(self):
        bundle=self.bundle();_,g,_=load_bundle_geometry(bundle)
        c=g.copper[0]
        self.assertTrue(c.holes_xy_m)
        self.assertFalse(_contains_copper((.005,.012),c))
        self.assertTrue(_contains_copper((.008,.012),c))
        self.assertTrue(_contains_copper(c.holes_xy_m[0][0],c))
        snapshot=g.as_dict();n,t=normalize_port_orientation(g);restored=inverse_transform_geometry(n,t)
        self.assertEqual(g.as_dict(),snapshot)
        for old,new in zip(g.copper,restored.copper):
            for a,b in zip(old.holes_xy_m,new.holes_xy_m):np.testing.assert_allclose(a,b,atol=1e-16,rtol=0)
        s,_=gerber_quality_settings('preview',**BAND)
        resolve_pcb_lumped_port(n,make_pcb_domain_mesh(n,s,gerber_quality='preview'),s,gerber_quality='preview')
        for hole in (((.04,.04),(.05,.04),(.05,.05),(.04,.05)),
                     ((.004,.011),(.006,.013),(.006,.011),(.004,.013))):
            bad=replace(g,copper=[replace(c,holes_xy_m=(hole,))])
            with self.assertRaises(ConfigurationError):validate_pcb_geometry(bad)
        hole= ((.010,.010),(.014,.010),(.014,.014),(.010,.014))
        plane=CopperPolygon('plane',((.002,.002),(.022,.002),(.022,.022),(.002,.022)),0.,holes_xy_m=(hole,))
        gap=replace(g,copper=[plane],port=replace(g.port,negative_xy_m=(.010,.012),positive_xy_m=(.014,.012),width_m=.001))
        validate_pcb_geometry(gap);audit_physical_feed(gap)
        normalized,_=normalize_port_orientation(gap)
        resolve_pcb_lumped_port(normalized,make_pcb_domain_mesh(normalized,s,gerber_quality='preview'),s,gerber_quality='preview')
        intruder=CopperPolygon('intruder',((.011,.011),(.013,.011),(.013,.013),(.011,.013)),0.)
        with self.assertRaisesRegex(ConfigurationError,'gap contains copper'):
            audit_physical_feed(replace(gap,copper=[plane,intruder]))

    def test_native_priorities_nested_restore_and_models_frozen_mesh(self):
        bundle=self.bundle(restore=True);results=[]
        for model in ('pec','conducting_sheet'):
            config,g,_=load_bundle_geometry(bundle,self.config(model));g,_=normalize_port_orientation(g)
            s,_=gerber_quality_settings('preview',**BAND);mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
            before=(g.as_dict(),asdict(mesh));csx=ClearanceCSX();engine=FieldEngine(csx)
            with test_pcb_copper.CopperTests.natives(self,csx,engine):
                *_,native_mesh,spec,metadata=prepare_pcb_xml_model(g,s,self.root/(model+'.xml'),gerber_quality='preview',copper_config=config)
            self.assertEqual(mesh,native_mesh);self.assertEqual(before,(g.as_dict(),asdict(mesh)))
            name,air,primitive=next(v for v in csx.materials if v[0]=='pcb_copper_clearance_air')
            self.assertEqual(air,dict(epsilon=1.,kappa=0.))
            self.assertEqual(len(primitive.polygons),1);clearance=primitive.polygons[0]
            self.assertEqual(clearance['elevation'],0.);self.assertEqual(clearance['norm_dir'],'z')
            self.assertNotIn('length',clearance)
            priorities=metadata['geometry']['copper_clearances']['priorities']
            self.assertEqual(sorted(p['copper_priority'] for p in priorities),[10,12])
            self.assertEqual(clearance['priority'],11)
            self.assertEqual(csx.copper_calls[0][0],'AddMetal' if model=='pec' else 'AddConductingSheet')
            self.assertFalse(any(v[0]=='Run' for v in engine.calls))
            results.append((mesh,csx.metals[0][1].polygons,primitive.polygons))
            # Evaluate native primitive priority at restored island and remaining air.
            source_point=np.mean(np.asarray(g.copper[1].vertices_xy_m),axis=0)
            all_native=[(p,'metal') for p in csx.metals[0][1].polygons]+[(p,'air') for p in primitive.polygons]
            def winner(point):
                candidates=[(p['priority'],kind) for p,kind in all_native if Polygon(np.asarray(p['points']).T).covers(Point(point))]
                return max(candidates)[1]
            self.assertEqual(winner(source_point),'metal')
            self.assertEqual(winner(source_point+np.array([.001,0])),'air')
            self.assertEqual(metadata['geometry']['copper_composition'][0]['final_hole_count'],1)
        self.assertEqual(results[0],results[1])
        # A hole in an existing conductor adds no mesh anchors itself.
        config,base,_=load_bundle_geometry(self.bundle(clear=False),self.config())
        plain,_=normalize_port_orientation(base)
        config,cut,_=load_bundle_geometry(self.bundle(clear=True),self.config())
        cut,_=normalize_port_orientation(cut)
        self.assertEqual(make_pcb_domain_mesh(plain,s,gerber_quality='preview'),make_pcb_domain_mesh(cut,s,gerber_quality='preview'))

    def test_multilayer_independence_mask_and_clearance_grid_audit(self):
        bundle=self.bundle(clear=False)
        # Top stays solid at this XY; inner1 and bottom have independent clears.
        for role in ('In1','In2','B'):
            image=solid_gerber()
            if role in ('In1','B'):
                image=image.replace('M02*','%ADD14C,4*%\n%LPC*%\nD14*\nX500000Y1200000D03*\nM02*')
            (bundle/f'board-{role}_Cu.gbr').write_text(image)
        configfile=self.root/'stack.json';configfile.write_text(json.dumps(physical_stack()))
        config,g,_=load_bundle_geometry(bundle,configfile)
        counts={c.layer_role:len(c.holes_xy_m) for c in g.copper}
        self.assertEqual(counts,dict(top=0,inner1=1,inner2=0,bottom=1))
        paths=overlays(g.as_dict(),dict(name='xz_feed',actual_position_m=.012))
        for layer in g.copper_layers:
            spans=[path['points'] for path in paths if path['color']=='#725018'
                   and all(p[1]==layer.z_m*1e3 for p in path['points'])]
            covers=any(min(p[0] for p in line)<5<max(p[0] for p in line) for line in spans)
            self.assertEqual(covers,layer.role in ('top','inner2'))
        axes=[np.arange(0,.0251,.0001),np.arange(0,.0251,.0001),np.arange(-.002,.0011,.00001)]
        for layer in g.copper_layers:
            mask=pcb_sample_mask([np.array([.005]),np.array([.012]),np.array([layer.z_m])],axes,g).item()
            self.assertEqual(bool(mask&1),layer.role in ('top','inner2'))
        n,_=normalize_port_orientation(g);s,_=gerber_quality_settings('preview',**BAND)
        csx=ClearanceCSX();engine=FieldEngine(csx)
        with test_pcb_copper.CopperTests.natives(self,csx,engine):
            *_,mesh,spec,metadata=prepare_pcb_xml_model(n,s,self.root/'multi.xml',gerber_quality='preview',copper_config=config)
        clear=next(m for name,_,m in csx.materials if name=='pcb_copper_clearance_air')
        self.assertEqual({p['elevation'] for p in clear.polygons},{g.copper_layers[1].z_m,g.copper_layers[3].z_m})
        for p in clear.polygons:self.assertIn(p['elevation'],mesh.z_lines_m)
        self.assertEqual(len(metadata['geometry']['copper_composition']),4)
        # Tampered native material insertion cannot change the frozen axes.
        bad=ClearanceCSX();original=bad.AddMaterial
        def mutate(name,**kw):
            result=original(name,**kw)
            if name=='pcb_copper_clearance_air':bad.grid.lines['z']=bad.grid.lines['z'][1:]
            return result
        bad.AddMaterial=mutate;engine=FieldEngine(bad)
        with test_pcb_copper.CopperTests.natives(self,bad,engine),self.assertRaisesRegex(ConfigurationError,'frozen grid'):
            prepare_pcb_xml_model(n,s,self.root/'bad.xml',gerber_quality='preview',copper_config=config)

    def test_field_hole_open_space_and_top_vertical_rendering(self):
        bundle=self.bundle();_,g,_=load_bundle_geometry(bundle)
        axes=[np.arange(0,.0251,.0001),np.arange(0,.0251,.0001),np.arange(-.002,.0011,.0001)]
        for z in (0.,.0001):
            m=pcb_sample_mask([np.array([.005]),np.array([.012]),np.array([z])],axes,g).item()
            self.assertEqual(m,0)  # Open antipad is larger than the conservative halo.
        mask=pcb_sample_mask([np.array([.008]),np.array([.012]),np.array([0.])],axes,g).item()
        self.assertTrue(mask&1)
        plane=dict(name='xz_feed',actual_position_m=.012)
        paths=overlays(g.as_dict(),plane)
        segments=[p['points'] for p in paths if p['color']=='#725018']
        self.assertFalse(any(min(p[0] for p in line)<5<max(p[0] for p in line) for line in segments))
        copper,_=self.image(PLANE+HOLE+RESTORE)
        fig=Figure(figsize=(5,5),dpi=100);canvas=FigureCanvasAgg(fig);ax=fig.subplots()
        for c in copper:ax.add_patch(copper_patch(asdict(c),facecolor='#cc8833',edgecolor='none'))
        ax.set(xlim=(0,25),ylim=(0,25));canvas.draw();pixels=np.asarray(canvas.buffer_rgba())
        def sample(x,y):
            px,py=ax.transData.transform((x,y));return pixels[pixels.shape[0]-int(py),int(px),:3]
        np.testing.assert_equal(sample(6,12),[255,255,255])
        self.assertFalse(np.array_equal(sample(5,12),[255,255,255]))
        self.assertFalse(np.array_equal(sample(8,12),[255,255,255]))
        fig.clear()

    def test_one_fake_run_offline_report_and_detached_holes(self):
        bundle=self.bundle();csx=ClearanceCSX();engine=FieldEngine(csx);out=self.root/'run'
        with test_pcb_copper.CopperTests.natives(self,csx,engine),contextlib.redirect_stdout(io.StringIO()):
            result=run_gerber_control(bundle,out,pcb_config=self.config('conducting_sheet'),quality='preview',field_frequency_hz=(2e9,),**BAND)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len([c for c in engine.calls if c[0]=='Run']),1)
        self.assertEqual(len(engine.port.calls),1)
        geometry=json.loads((out/'geometry.json').read_text())
        self.assertEqual(len(geometry['copper'][0]['holes_xy_m']),1)
        self.assertEqual(geometry['copper'][0]['layer_role'],'top')
        self.assertEqual(result['import']['copper_composition'][0]['clear_primitive_count'],1)
        self.assertEqual(result['import']['copper_composition'][0]['final_hole_count'],1)
        for p in bundle.iterdir():p.unlink()
        with patch('antenna_lab.solvers.openems.native_modules',side_effect=AssertionError('offline')):
            path=generate_report(out,self.root/'offline.html')
        self.assertTrue(path.is_file());self.assertTrue((out/'plots/geometry.png').is_file())
        json.loads((out/'summary.json').read_text(),parse_constant=lambda value:self.fail(value))


if __name__=='__main__':unittest.main()
