"""Folder inputs, physical feed topology and native-free production import."""
import contextlib
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.bundle import (discover_bundle,load_bundle_geometry,load_physical_config,
                                   DEFAULT_PHYSICAL,audit_physical_feed)
from antenna_lab.pcb import gerber_control
from antenna_lab.pcb.model import CopperPolygon
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from test_pcb_edge_convergence import RunEngine
from test_openems_pcb import CSX


def bundle_fixture(root, *, vertical=False, loop=False, stroke=False):
    """Authored Gerbers: matching pads, two regions and optional remote bridge."""
    root.mkdir(parents=True,exist_ok=True)
    def xy(x,y): return (25-y,x) if vertical else (x,y)
    def command(x,y,d):
        x,y=xy(x,y);return f'X{round(x*100000)}Y{round(y*100000)}D{d:02d}*'
    lines=['%FSLAX45Y45*%','%MOMM*%', '%ADD10R,'+('0.86401X0.80648' if vertical else '0.80648X0.86401')+'*%',
           '%ADD11C,0.2*%','G01*']
    polygons=[[(2,6),(12.0904,6),(12.0904,19),(2,19)],
              [(12.9686,6),(22,6),(22,19),(12.9686,19)]]
    if loop:polygons.append([(10,18),(15,18),(15,20),(10,20)])
    for points in polygons:
        lines+=['G36*',command(*points[0],2)]
        lines += [command(*v,1) for v in points[1:]+points[:1]]
        lines+=['G37*']
    if stroke:lines+=['D11*',command(12.9686,6,2),command(12.9686,19,1)]
    lines+=['D10*',command(11.81964,12.573,3),command(13.32636,12.573,3),'M02*']
    (root/'Gerber_TopLayer.GTL').write_text('\n'.join(lines))
    outline=Path(__file__).parent/'fixtures/pcb-gerber/outline.gko'
    (root/'Gerber_BoardOutlineLayer.GKO').write_bytes(outline.read_bytes())
    for name in ('TopSolderMaskLayer.GTS','TopPasteMaskLayer.GTP','TopSilkscreenLayer.GTO'):
        (root/('Gerber_'+name)).write_text('%FSLAX45Y45*%\n%MOMM*%\n%ADD10C,1*%\nD10*\nX100000Y100000D03*\nM02*')
    return root


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.bundle=bundle_fixture(self.root/'gerbers')

    def test_discovery_hashes_and_omissions(self):
        selected,files=discover_bundle(self.bundle)
        self.assertEqual(set(selected),{'top_copper','outline'})
        self.assertEqual({f['role'] for f in files},{'top_copper','outline','soldermask','paste','silkscreen'})
        for f in files:
            self.assertEqual(f['sha256'],sha256(Path(f['path']).read_bytes()).hexdigest())
            self.assertEqual(f['disposition'],'modeled' if f['role'] in selected else 'omitted')
        self.assertEqual((selected,files),discover_bundle(self.bundle))

    def test_ambiguous_candidates_and_unsupported(self):
        for role,name in (('top_copper','second.GTL'),('outline','second.GKO')):
            paths,_=discover_bundle(self.bundle);target=self.bundle/name;target.write_bytes(paths[role].read_bytes())
            with self.assertRaisesRegex(ConfigurationError,name):discover_bundle(self.bundle)
            target.unlink()
        for name in ('bottom.GBL','inner.G1','holes.txt','mystery.gbr'):
            path=self.bundle/name
            path.write_text('M48\nMETRIC\n%\nM30' if name=='holes.txt' else (self.bundle/'Gerber_TopLayer.GTL').read_text())
            with self.assertRaisesRegex(ConfigurationError,'Unsupported'):discover_bundle(self.bundle)
            path.unlink()

    def test_x2_metadata_roles_and_conflicting_extension(self):
        old=self.bundle/'Gerber_TopLayer.GTL';text=old.read_text();old.unlink()
        path=self.bundle/'unconventional.gbr';path.write_text('%TF.FileFunction,Copper,L1,Top*%\n'+text)
        self.assertEqual(discover_bundle(self.bundle)[0]['top_copper'],path)
        path.rename(self.bundle/'conflict.GBL')
        with self.assertRaisesRegex(ConfigurationError,'conflicts'):discover_bundle(self.bundle)

    def test_physical_config_no_files_defaults_and_override(self):
        c,g,m=load_bundle_geometry(self.bundle)
        self.assertEqual(c.substrate_thickness_m,.0016)
        self.assertIn('assumptions/unverified',m['physical_config_source'])
        self.assertTrue(any('documented defaults' in a for a in g.assumptions))
        path=self.root/'physical.json';value=deepcopy(DEFAULT_PHYSICAL)
        value['files']={'copper_top':'other.gtl'};path.write_text(json.dumps(value))
        with self.assertRaises(ConfigurationError):load_physical_config(path)
        value.pop('files');value['substrate']['epsilon_r']=3.8
        value['port']=dict(mode='explicit',negative_mm=[12.22288,12.573],positive_mm=[12.92312,12.573],width_mm=.86401)
        path.write_text(json.dumps(value));c,g,m=load_bundle_geometry(self.bundle,path)
        self.assertEqual(c.substrate_epsilon_r,3.8);self.assertEqual(m['feed_detection']['mode'],'explicit')

    def test_horizontal_vertical_loop_and_true_union_gap(self):
        for vertical,loop,stroke in ((False,False,False),(True,True,False),(False,False,True)):
            path=bundle_fixture(self.root/f'b{vertical}{loop}{stroke}',vertical=vertical,loop=loop,stroke=stroke)
            c,g,m=load_bundle_geometry(path)
            self.assertEqual(m['feed_detection']['axis'],'y' if vertical else 'x')
            expected=(12.8686 if stroke else 12.92312)-12.22288
            self.assertAlmostEqual(m['feed_detection']['gap_m'],expected*1e-3,places=13)
            self.assertAlmostEqual(g.port.width_m,.86401e-3,places=13)
            normalized,_=normalize_port_orientation(g)
            self.assertLess(normalized.port.negative_xy_m[0],0)
            self.assertGreater(normalized.port.positive_xy_m[0],0)
            s,_=gerber_quality_settings('preview')
            mesh=make_pcb_domain_mesh(normalized,s,gerber_quality='preview')
            port=resolve_pcb_lumped_port(normalized,mesh,s,gerber_quality='preview')
            self.assertEqual(port.negative_copper_id==port.positive_copper_id,loop)

    def test_ambiguous_auto_feed_and_occupied_gap(self):
        top=self.bundle/'Gerber_TopLayer.GTL';source=top.read_text()
        top.write_text(source.replace('M02*','X1800000Y1500000D03*\nM02*'))
        with self.assertRaisesRegex(ConfigurationError,'exactly two'):load_bundle_geometry(self.bundle)
        top.write_text(source);_,g,_=load_bundle_geometry(self.bundle)
        n,p=g.port.negative_xy_m,g.port.positive_xy_m;mid=(n[0]+p[0])/2
        g.copper.append(CopperPolygon('sliver',((mid-1e-6,n[1]+1e-4),(mid+1e-6,n[1]+1e-4),
            (mid+1e-6,n[1]+2e-4),(mid-1e-6,n[1]+2e-4)),0.))
        with self.assertRaisesRegex(ConfigurationError,'gap contains copper'):audit_physical_feed(g)
        g,_=normalize_port_orientation(g);s,_=gerber_quality_settings('preview')
        mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        with self.assertRaisesRegex(ConfigurationError,'szczeliny'):resolve_pcb_lumped_port(g,mesh,s,gerber_quality='preview')

    def test_tracked_production_import_no_native(self):
        root=Path(__file__).resolve().parents[1]/'gerbs'
        for name,gap,axis,count in (('emstest',.64412,'x',2),('emstest2',.70024,'y',1)):
            if not (root/name).exists():self.skipTest('Tracked production bundle unavailable in source archive')
            _,g,m=load_bundle_geometry(root/name)
            self.assertAlmostEqual(m['feed_detection']['gap_m'],gap*1e-3,places=12)
            self.assertEqual(m['feed_detection']['axis'],axis);self.assertEqual(len(g.copper),count)
            g,_=normalize_port_orientation(g);s,_=gerber_quality_settings('preview')
            resolve_pcb_lumped_port(g,make_pcb_domain_mesh(g,s,gerber_quality='preview'),s,gerber_quality='preview')

    def test_cli_folder_physical_config_and_best_effort_report(self):
        engine=RunEngine();out=self.root/'run'
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=CSX))),\
             patch('antenna_lab.visualization.report.generate_report',side_effect=RuntimeError('report unavailable')),\
             contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            result=gerber_control.run_gerber_control(self.bundle,out,quality='preview')
        self.assertEqual(result['status'],'completed');self.assertEqual(result['termination_status'],'completed_before_limit')
        self.assertTrue((out/'impedance.csv').exists());self.assertIn('report unavailable',result['warnings'][0])
        self.assertEqual(json.loads((out/'summary.json').read_text()),result)
        self.assertEqual(json.loads((out/'import.json').read_text())['discovered_files'],result['import']['discovered_files'])
        with patch.object(gerber_control,'run_gerber_control',return_value={'status':'prepared'}) as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gerber_control.main([str(self.bundle),'--pcb-config','material.json','--output',str(out),'--prepare-only']),0)
            self.assertEqual(run.call_args.kwargs['pcb_config'],Path('material.json'))


if __name__=='__main__':unittest.main()
