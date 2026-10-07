"""Real Gerber constructs and native fakes: no native FDTD execution."""
import contextlib
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.bundle import load_bundle_geometry, load_physical_config, audit_physical_feed
from antenna_lab.pcb.bundle_multilayer import discover_stackup_bundle
from antenna_lab.pcb.gerber_control import run_gerber_control
from antenna_lab.pcb.gerber_quality import gerber_quality_settings, gerber_cost_preflight
from antenna_lab.pcb.model import CopperPolygon
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from antenna_lab.pcb.transform import normalize_port_orientation, inverse_transform_geometry
from antenna_lab.pcb.validation import validate_pcb_geometry
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh, make_pcb_mesh_anchor_plan
from antenna_lab.solvers.pcb_fields import pcb_sample_mask, pcb_field_layout
from antenna_lab.visualization.pcb_fields import overlays
from antenna_lab.visualization.report import generate_report
from test_pcb_bundle import bundle_fixture
from test_pcb_copper import CopperCSX
import test_pcb_copper
from test_pcb_fields import FieldEngine

BAND = dict(excitation_center_hz=2e9, excitation_cutoff_hz=625e6,
            result_frequency_hz=(1.5e9,2e9,2.5e9))


def physical_stack(count=4):
    roles = ['top', *[f'inner{i}' for i in range(1,count-1)], 'bottom']
    layers = []
    for i, role in enumerate(roles):
        layers.append(dict(type='copper', role=role, model='conducting_sheet',
            thickness_um=35 if role in ('top','bottom') else 18,
            conductivity_s_m=58e6-i*1e6))
        if i < count-1:
            layers.append(dict(type='dielectric', name=f'dielectric_{i}',
                thickness_mm=1.6 if count==2 else (1.20 if i==1 else .18),
                epsilon_r=4.2+i*.1, loss_tangent=.018+i*.001))
    return dict(schema_version=2, stackup=layers, port=dict(mode='auto', layer='top'))


def solid_gerber(physical_number=None, role='Inr'):
    metadata = f'%TF.FileFunction,Copper,L{physical_number},{role}*%\n' if physical_number else ''
    # A region and overlapping flashed pad, one union per layer.
    return ('%FSLAX45Y45*%\n%MOMM*%\n'+metadata+'%ADD10R,1X1*%\nG01*\nG36*\n'
            'X100000Y100000D02*\nX2400000Y100000D01*\nX2400000Y2400000D01*\n'
            'X100000Y2400000D01*\nX100000Y100000D01*\nG37*\nD10*\nX1250000Y1250000D03*\nM02*')


class MultilayerTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def fixture(self, count=4, metadata=False, vertical=False):
        directory=bundle_fixture(self.root/f'gerbers{count}', loop=True, vertical=vertical)
        for i in range(1,count-1):
            (directory/f'board-In{i}_Cu.gbr').write_text(solid_gerber(i+1 if metadata else None))
        (directory/'board-B_Cu.gbr').write_text(solid_gerber(count if metadata else None,'Bot'))
        path=self.root/f'physical{count}.json';path.write_text(json.dumps(physical_stack(count)))
        return directory,path

    def loaded(self, count=4):
        directory,path=self.fixture(count)
        config,source,metadata=load_bundle_geometry(directory,path)
        geometry,_=normalize_port_orientation(source)
        settings,_=gerber_quality_settings('preview',**BAND)
        return directory,path,config,source,geometry,settings,metadata

    def test_discovery_metadata_order_and_easyeda_names(self):
        directory,path=self.fixture(metadata=True)
        roles=['top','inner1','inner2','bottom']
        first=discover_stackup_bundle(directory,roles)
        self.assertEqual(first,discover_stackup_bundle(directory,roles))
        self.assertEqual(list(first[0]),[*roles,'outline'])
        for i in (1,2):
            old=directory/f'board-In{i}_Cu.gbr';old.rename(directory/f'Gerber_InnerLayer{i}.G{i}')
        self.assertEqual(list(discover_stackup_bundle(directory,roles)[0]),[*roles,'outline'])
        config,source,meta=load_bundle_geometry(directory,path)
        self.assertEqual([c.role for c in source.copper_layers],roles)
        self.assertEqual(len([r for r in meta['discovered_files'] if r['disposition']=='omitted']),3)

    def test_two_and_four_layer_geometry_z_union_normalization(self):
        for count in (2,4):
            directory,path,config,source,g,s,meta=self.loaded(count)
            self.assertEqual(config.schema_version,2)
            expected=[0,-.0016] if count==2 else [0,-.00018,-.00138,-.00156]
            np.testing.assert_allclose([c.z_m for c in g.copper_layers],expected,rtol=0,atol=1e-18)
            self.assertEqual(len(g.copper),count)  # loop top + solid independently unioned inner/bottom
            self.assertEqual(len({p.id for p in g.copper}),count)
            for layer in g.copper_layers:
                polys=[c for c in g.copper if c.layer_role==layer.role]
                self.assertEqual(len(polys),1);self.assertEqual(polys[0].z_m,layer.z_m)
                record=next(r for r in meta['discovered_files'] if r['role']==layer.role)
                self.assertEqual(layer.source_sha256,sha256(Path(record['path']).read_bytes()).hexdigest())
            self.assertEqual(g.bounds[0][2],g.dielectric_layers[-1].z_min_m)
            self.assertEqual(g.port.negative_xy_m[1],g.port.positive_xy_m[1])
            self.assertLess(g.port.negative_xy_m[0],0);self.assertGreater(g.port.positive_xy_m[0],0)
            before=source.as_dict();normalized,t=normalize_port_orientation(source)
            inverse=inverse_transform_geometry(normalized,t)
            for a,b in zip(source.copper,inverse.copper):np.testing.assert_allclose(a.vertices_xy_m,b.vertices_xy_m,atol=1e-16,rtol=0)
            self.assertEqual(before,source.as_dict());self.assertEqual(source.copper_layers,inverse.copper_layers)
            validate_pcb_geometry(g);audit_physical_feed(g)

    def test_native_layers_exact_intervals_materials_and_thickness_independent_mesh(self):
        _,_,config,_,g,s,_=self.loaded()
        original=g.as_dict();outputs=[]
        for scale in (1,10):
            changed=replace(g,copper_layers=tuple(replace(c,thickness_m=c.thickness_m*scale) for c in g.copper_layers))
            csx=CopperCSX();engine=FieldEngine(csx)
            with test_pcb_copper.CopperTests.natives(self,csx,engine):
                _,_,_,mesh,spec,metadata=prepare_pcb_xml_model(changed,s,self.root/f'{scale}.xml',
                    gerber_quality='preview',copper_config=config,field_frequency_hz=(2e9,))
            outputs.append(mesh)
            self.assertEqual(len(csx.materials),3);self.assertEqual(len(csx.copper_calls),4)
            for native,layer in zip(csx.materials,g.dielectrics):
                _,params,material=native
                self.assertEqual(params['epsilon'],layer.epsilon_r)
                self.assertAlmostEqual(params['kappa'],2*np.pi*2e9*8.8541878128e-12*layer.epsilon_r*layer.loss_tangent,delta=1e-16)
                primitive=material.polygons[0]
                self.assertEqual(primitive['elevation'],layer.z_min_m)
                self.assertEqual(primitive['length'],layer.z_max_m-layer.z_min_m)
            for call,(_,prop),layer in zip(csx.copper_calls,csx.metals,changed.copper_layers):
                self.assertEqual(call,('AddConductingSheet','pcb_copper_'+layer.role,
                    dict(conductivity=layer.conductivity_s_m,thickness=layer.thickness_m)))
                self.assertEqual(prop.polygons[0]['elevation'],layer.z_m)
                self.assertIn(layer.z_m,mesh.z_lines_m)
            for d in g.dielectrics:
                self.assertIn(d.z_min_m,mesh.z_lines_m);self.assertIn(d.z_max_m,mesh.z_lines_m)
            self.assertGreater(spec.active_ex_edge_count,0)
            self.assertEqual(metadata['geometry']['resolved_stackup']['layers'][0]['source_sha256'],g.copper_layers[0].source_sha256)
            self.assertFalse(any(c[0]=='Run' for c in engine.calls))
        self.assertEqual(outputs[0],outputs[1]);self.assertEqual(g.as_dict(),original)
        thin=g.dielectric_layers[0]
        self.assertFalse(any(thin.z_min_m < z < thin.z_max_m for z in outputs[0].z_lines_m))
        cost=gerber_cost_preflight(outputs[0],s)
        self.assertEqual(cost['min_axis_steps_m']['z'],min(np.diff(outputs[0].z_lines_m)))
        mixed=replace(g,copper_layers=tuple(replace(c,model='pec') if c.role=='inner1' else c for c in g.copper_layers))
        csx=CopperCSX();engine=FieldEngine(csx)
        with test_pcb_copper.CopperTests.natives(self,csx,engine):
            mixed_result=prepare_pcb_xml_model(mixed,s,self.root/'mixed.xml',gerber_quality='preview')
        self.assertEqual(mixed_result[3],outputs[0])
        self.assertEqual(csx.copper_calls[1][0],'AddMetal')

    def test_top_port_ignores_buried_copper_but_rejects_top_gap_copper(self):
        *_,g,s,meta=self.loaded()
        mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        spec=resolve_pcb_lumped_port(g,mesh,s,gerber_quality='preview')
        self.assertEqual(spec.negative_copper_id,spec.positive_copper_id)
        self.assertTrue(spec.negative_copper_id.startswith('top:'))
        n,p=g.port.negative_xy_m,g.port.positive_xy_m
        x=(n[0]+p[0])/2;y=(n[1]+p[1])/2;w=(p[0]-n[0])/8
        bad=replace(g,copper=[*g.copper,CopperPolygon('sliver',((x-w,y-w),(x+w,y-w),(x+w,y+w),(x-w,y+w)),0.)])
        validate_pcb_geometry(bad)
        with self.assertRaisesRegex(ConfigurationError,'gap contains copper'):audit_physical_feed(bad)
        with self.assertRaisesRegex(ConfigurationError,'szczeliny'):
            resolve_pcb_lumped_port(bad,make_pcb_domain_mesh(bad,s,gerber_quality='preview'),s,gerber_quality='preview')

    def test_fields_mask_actual_planes_and_vertical_interfaces(self):
        *_,g,s,meta=self.loaded()
        mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        axes=[np.asarray(getattr(mesh,a+'_lines_m')) for a in 'xyz']
        n,p=g.port.negative_xy_m,g.port.positive_xy_m
        x=(n[0]+p[0])/2;y=(n[1]+p[1])/2
        def mask(z):return int(pcb_sample_mask([np.array([x]),np.array([y]),np.array([z])],axes,g).item())
        self.assertFalse(mask(0)&1)  # Clear top feed despite buried full metal.
        for c in g.copper_layers[1:]:self.assertTrue(mask(c.z_m)&1)
        self.assertFalse(mask(.01)&1)
        layout=pcb_field_layout(g,mesh,s,(2e9,))
        self.assertEqual(layout[0]['actual_position_m'],next(z for z in mesh.z_lines_m if z>0))
        for plane in layout[1:]:
            paths=overlays(g.as_dict(),plane)
            z={point[1] for path in paths for point in path['points']}
            for d in g.dielectrics:
                self.assertIn(d.z_min_m*1000,z);self.assertIn(d.z_max_m*1000,z)

    def test_strict_config_missing_extra_ambiguous_drills_and_order(self):
        directory,path=self.fixture()
        original=json.loads(path.read_text())
        bads=[]
        for key,value in [('layer','bottom'),('mode','guess')]:
            v=deepcopy(original);v['port'][key]=value;bads.append(v)
        v=deepcopy(original);v['files']={};bads.append(v)
        v=deepcopy(original);v['stackup'][2]['role']='inner2';bads.append(v)
        v=deepcopy(original);v['stackup'][1]['thickness_mm']=0;bads.append(v)
        v=deepcopy(original);v['stackup'][3]['name']=v['stackup'][1]['name'];bads.append(v)
        v=deepcopy(original);v['stackup'].pop(1);bads.append(v)
        for v in bads:
            path.write_text(json.dumps(v))
            with self.assertRaises(ConfigurationError):load_physical_config(path)
        path.write_text(json.dumps(original))
        roles=['top','inner1','inner2','bottom']
        inner=directory/'board-In1_Cu.gbr';saved=inner.read_text();inner.unlink()
        with self.assertRaisesRegex(ConfigurationError,'inner1.*candidates'):load_bundle_geometry(directory,path)
        inner.write_text(saved)
        duplicate=directory/'duplicate.G1';duplicate.write_text(saved)
        with self.assertRaisesRegex(ConfigurationError,'board-In1_Cu.gbr.*duplicate.G1'):load_bundle_geometry(directory,path)
        duplicate.unlink()
        extra=directory/'extra.G3';extra.write_text(saved)
        with self.assertRaisesRegex(ConfigurationError,'Extra copper.*extra.G3'):load_bundle_geometry(directory,path)
        extra.unlink()
        inner.write_text(solid_gerber(3))
        with self.assertRaisesRegex(ConfigurationError,'ordering'):load_bundle_geometry(directory,path)
        inner.write_text(saved)
        drill=directory/'holes.drl';drill.write_text('M48\nMETRIC\n%\nM30\n')
        with self.assertRaisesRegex(ConfigurationError,'empty drill source'):
            load_bundle_geometry(directory,path)
        drill.unlink()
        drill=directory/'fabrication.gbr'
        drill.write_text(solid_gerber().replace('%MOMM*%', '%MOMM*%\n%TF.FileFunction,Plated,1,4,PTH*%'))
        with self.assertRaisesRegex(ConfigurationError,'unsupported/invalid Excellon'):
            load_bundle_geometry(directory,path)
        drill.unlink()
        # Extra bottom copper remains unsupported in v1, never silently included.
        with self.assertRaisesRegex(ConfigurationError,'Unsupported'):load_bundle_geometry(directory)

    def test_adjacent_dielectrics_keep_distinct_material_interface(self):
        directory,path=self.fixture(2)
        v=json.loads(path.read_text())
        v['stackup'][1]['thickness_mm']=.18
        v['stackup'].insert(2,dict(type='dielectric',name='core',thickness_mm=1.2,epsilon_r=5.1,loss_tangent=.02))
        path.write_text(json.dumps(v))
        config,g,_=load_bundle_geometry(directory,path);g,_=normalize_port_orientation(g)
        s,_=gerber_quality_settings('preview',**BAND)
        csx=CopperCSX();engine=FieldEngine(csx)
        with test_pcb_copper.CopperTests.natives(self,csx,engine):
            _,_,_,mesh,_,metadata=prepare_pcb_xml_model(g,s,self.root/'adjacent.xml',gerber_quality='preview')
        self.assertEqual(len(csx.materials),2)
        self.assertIn(g.dielectric_layers[0].z_min_m,mesh.z_lines_m)
        self.assertEqual([l['type'] for l in metadata['geometry']['resolved_stackup']['layers']],
                         ['copper','dielectric','dielectric','copper'])
        self.assertEqual(csx.materials[1][1]['epsilon'],5.1)

    def test_invalid_stackup_geometry_stops_before_native_materials(self):
        *_,g,s,meta=self.loaded()
        mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        from antenna_lab.solvers.openems_pcb import install_pcb_geometry
        invalids=[replace(g,dielectric_layers=()),
                  replace(g,copper=[replace(g.copper[0],z_m=5e-11),*g.copper[1:]]),
                  replace(g,copper_layers=tuple(replace(c,model='volume') for c in g.copper_layers))]
        for bad in invalids:
            csx=CopperCSX()
            with self.assertRaises(ConfigurationError):
                install_pcb_geometry(csx,bad,mesh,s,gerber_quality='preview')
            self.assertEqual(csx.grid_accesses,0)
            self.assertEqual(csx.copper_calls,[])

    def test_thin_stackup_cost_aborts_before_native_loading(self):
        directory,path=self.fixture(4);v=json.loads(path.read_text())
        v['stackup'][1]['thickness_mm']=.001
        path.write_text(json.dumps(v))
        from unittest.mock import patch
        with patch('antenna_lab.solvers.openems.native_modules') as native, contextlib.redirect_stdout(io.StringIO()) as console:
            with self.assertRaises(ConfigurationError):
                run_gerber_control(directory,self.root/'too_costly',pcb_config=path,quality='preview',**BAND)
            native.assert_not_called()
        self.assertIn('Estimated excitation:',console.getvalue())
        failed=json.loads((self.root/'too_costly/summary.json').read_text())
        self.assertEqual(failed['status'],'failed')
        self.assertGreater(failed['estimated_excitation_steps'],50000)

    def test_thin_unresolvable_dielectric_not_merged(self):
        directory,path=self.fixture(2);v=json.loads(path.read_text());v['stackup'][1]['thickness_mm']=5e-8
        path.write_text(json.dumps(v));_,g,_=load_bundle_geometry(directory,path);g,_=normalize_port_orientation(g)
        with self.assertRaisesRegex(ConfigurationError,'unresolved dielectric'):make_pcb_mesh_anchor_plan(g)

    def test_full_fake_run_fields_stackup_report_offline(self):
        directory,path=self.fixture(4,vertical=True)
        csx=CopperCSX();engine=FieldEngine(csx);out=self.root/'run'
        with test_pcb_copper.CopperTests.natives(self,csx,engine),contextlib.redirect_stdout(io.StringIO()) as console:
            result=run_gerber_control(directory,out,pcb_config=path,quality='preview',field_frequency_hz=(2e9,),**BAND)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len([c for c in engine.calls if c[0]=='Run']),1)
        self.assertEqual(len(engine.port.calls),1)
        self.assertIn('Minimum steps:',console.getvalue())
        self.assertIn('Estimated excitation:',console.getvalue())
        stack=result['resolved_stackup'];self.assertEqual(len(stack['layers']),7)
        self.assertAlmostEqual(stack['total_dielectric_thickness_m'],.00156,delta=1e-18)
        self.assertEqual(stack,result['preparation']['geometry']['resolved_stackup'])
        self.assertTrue((out/'plots/stackup.png').is_file())
        html=re.sub(r'data:image/[^"\s]+','',(out/'report.html').read_text())
        self.assertIn('<h2>Stackup</h2>',html);self.assertIn('inner2',html);self.assertIn('symbolicznie',html)
        self.assertIn('Pola E/H',html);self.assertNotIn('Copper model</td><td>PEC',html)
        for p in directory.iterdir():p.unlink()
        path.unlink()
        from unittest.mock import patch
        with patch('antenna_lab.solvers.openems.native_modules',side_effect=AssertionError('offline')):
            report=generate_report(out,self.root/'offline.html')
        self.assertTrue(report.is_file())
        json.loads((out/'summary.json').read_text(),parse_constant=lambda s:self.fail(s))


if __name__=='__main__':unittest.main()
