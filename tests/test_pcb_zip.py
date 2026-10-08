"""Direct ZIP/source hierarchy contracts. No extraction and no native FDTD."""
import contextlib
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import shutil
import stat
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings
from zipfile import ZipFile, ZipInfo

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.experiment import resolve_experiment, load_experiment_geometry, _resolve_resource
from antenna_lab.pcb.easyeda_stackup import normalize_stackup
from antenna_lab.pcb import sources
from antenna_lab.pcb.bundle_multilayer import load_multilayer_bundle
from antenna_lab.pcb.gerber_control import run_gerber_control, main
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.geometry_resolution import apply_geometry_resolution
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.gerber_quality import gerber_quality_settings, gerber_cost_preflight, require_excitation_fits
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from antenna_lab.solvers.pcb_components import resolve_component_boxes
from test_pcb_components import component_fixture, ComponentCSX
from test_pcb_edge_convergence import RunEngine
from test_pcb_drills import drill_text
from test_pcb_multilayer import physical_stack

ROOT=Path(__file__).resolve().parents[1]
BAND=dict(excitation_center_hz=2e9,excitation_cutoff_hz=1e9,
          result_frequency_hz=tuple(f*1e6 for f in range(1500,2501,10)))


def archive(path, files, prefix=''):
    with ZipFile(path,'w') as z:
        for name,content in files.items():z.writestr(prefix+name,content)


def easyeda():
    types=['TOP','SUBSTRATE','BOTTOM'];rows=[];management=[]
    for i,kind in enumerate(types,1):
        name='Dielectric1' if kind=='SUBSTRATE' else kind
        rows.append(dict(values={'Layer Id':i,'Layer':name,'Layer Type':kind,
            'Type':'Substrate' if kind=='SUBSTRATE' else 'Copper',
            'Thickness':.2 if kind=='SUBSTRATE' else .035,
            'Permittivity':4.5 if kind=='SUBSTRATE' else 0,'Loss Tangent':0}))
        management.append(dict(values=dict(layerId=i,layerType=kind,status=1)))
    return dict(layerManagement=management,physicalStacking=rows)


class ResourceResolutionTests(unittest.TestCase):
    def test_independent_local_parent_matrix_and_no_grandparent(self):
        for kind in ('netlist','stackup'):
            for local_count,parent_count,scope in ((1,0,'local'),(0,1,'parent'),(1,1,'local'),
                                                   (1,2,'local'),(2,1,None),(0,2,None),(0,0,None)):
                with self.subTest(kind=kind,counts=(local_count,parent_count)),TemporaryDirectory() as t:
                    parent=Path(t)/'family';local=parent/'variant';local.mkdir(parents=True)
                    suffix='.ENET' if kind=='netlist' else '.json'
                    content='{}' if kind=='netlist' else json.dumps(physical_stack(2))
                    for directory,count in ((local,local_count),(parent,parent_count)):
                        for i in range(count):(directory/f'{i}{suffix}').write_text(content)
                    (Path(t)/('grandparent'+suffix)).write_text(content)
                    (local/'unrelated.json').write_text('{"report":true}')
                    (local/'FlyingProbeTesting.json').write_text('{"pins":[]}')
                    if scope:
                        selected=_resolve_resource(local,kind)
                        self.assertEqual(selected.scope,scope)
                        self.assertEqual(selected.source_directory,local if scope=='local' else parent)
                        self.assertEqual(selected.source_sha256,sha256(content.encode()).hexdigest())
                        with self.assertRaises(FrozenInstanceError): selected.scope='changed'
                    else:
                        with self.assertRaises(ConfigurationError) as error:_resolve_resource(local,kind)
                        self.assertIn(kind,str(error.exception))
                        if local_count>1:self.assertIn('ambiguous in local',str(error.exception))
                        elif parent_count>1:self.assertIn('ambiguous in parent',str(error.exception))
                        else:self.assertIn('local:',str(error.exception));self.assertIn('parent:',str(error.exception))

    def test_malformed_selected_stackup_does_not_fall_back(self):
        with TemporaryDirectory() as t:
            family=Path(t);local=family/'variant';local.mkdir()
            (family/'good.json').write_text(json.dumps(easyeda()))
            bad=easyeda();bad['physicalStacking'][1]['values']['Permittivity']=0
            (local/'bad.json').write_text(json.dumps(bad))
            selected=_resolve_resource(local,'stackup');self.assertEqual(selected.scope,'local')
            with self.assertRaisesRegex(ConfigurationError,'Permittivity=0'):
                normalize_stackup(json.loads(selected.source_path.read_text()))


class EasyedaStackTests(unittest.TestCase):
    def test_real_stackup_units_assumptions_and_zero_loss(self):
        data=json.loads((ROOT/'gerbs/realpcb_microstrip/stacup.json').read_text())
        result,meta=normalize_stackup(data)
        self.assertEqual([l['type'] for l in result['stackup']],['copper','dielectric','copper'])
        for layer in (result['stackup'][0],result['stackup'][2]):
            self.assertEqual(layer['thickness_um'],35);self.assertEqual(layer['conductivity_s_m'],58e6)
            self.assertEqual(layer['model'],'conducting_sheet')
        self.assertEqual(result['stackup'][1],dict(type='dielectric',name='Dielectric1',thickness_mm=.2,epsilon_r=4.5,loss_tangent=0))
        self.assertEqual(len(meta['omitted_layers']),6);self.assertTrue(meta['assumptions'])
        self.assertEqual(result['drills']['pth_plating_um'],25)
        for name in ('stacdef4.json','stacdef4a.json'):
            with self.assertRaisesRegex(ConfigurationError,'Permittivity=0.*not inferred'):
                normalize_stackup(json.loads((ROOT/'gerbs'/name).read_text()))

    def test_invalid_sequence_types_em_and_order(self):
        cases=[]
        bad=easyeda();bad['physicalStacking']='wrong';cases.append(bad)
        bad=easyeda();bad['physicalStacking'].pop(1);cases.append(bad)
        bad=easyeda();bad['physicalStacking'][1]['values']['Layer Id']=[];cases.append(bad)
        bad=easyeda();bad['physicalStacking'].reverse();cases.append(bad)
        for key,value in (('Thickness',0),('Permittivity',None),('Permittivity',float('nan')),('Loss Tangent',-1)):
            bad=easyeda();bad['physicalStacking'][1]['values'][key]=value;cases.append(bad)
        bad=easyeda();bad['layerManagement'][0]['values']['status']=0;cases.append(bad)
        for bad in cases:
            with self.subTest(data=bad),self.assertRaises(ConfigurationError):normalize_stackup(bad)


class ZipInputTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.directory,self.config,self.enet,self.probe=component_fixture(self.root)
        self.files={p.name:p.read_bytes() for p in self.directory.iterdir() if p.suffix!='.enet'}
        self.family=self.root/'family';self.local=self.family/'variant';self.local.mkdir(parents=True)
        self.zip=self.local/'board.ZIP';archive(self.zip,self.files)
        (self.family/'common.enet').write_bytes(self.enet.read_bytes())
        (self.family/'stackup.json').write_bytes(self.config.read_bytes())

    def test_root_wrapper_overrides_explicit_and_cwd_independence(self):
        initial=resolve_experiment(self.zip)
        self.assertEqual((initial.stackup.scope,initial.netlist.scope),('parent','parent'))
        self.assertEqual(initial,resolve_experiment(self.zip))
        for stack_local,net_local in ((True,False),(False,True),(True,True)):
            stack=self.local/'local.json';net=self.local/'circuit.enet'
            if stack_local:stack.write_bytes(self.config.read_bytes())
            else:stack.unlink(missing_ok=True)
            if net_local:net.write_bytes(self.enet.read_bytes())
            else:net.unlink(missing_ok=True)
            e=resolve_experiment(self.zip)
            self.assertEqual(e.stackup.scope,'local' if stack_local else 'parent')
            self.assertEqual(e.netlist.scope,'local' if net_local else 'parent')
        # Even locally ambiguous stackups are bypassed by explicit selection.
        (self.local/'second.json').write_bytes(self.config.read_bytes())
        explicit=resolve_experiment(self.zip,self.config)
        self.assertEqual(explicit.stackup.scope,'explicit_cli')
        self.assertEqual(explicit.netlist.source_directory,self.local)
        original=load_experiment_geometry(explicit)[1].as_dict()
        archive(self.zip,self.files,'project/')
        wrapped=resolve_experiment(self.zip,self.config)
        self.assertEqual(wrapped.logical_bundle_root,'project')
        self.assertEqual(load_experiment_geometry(wrapped)[1].as_dict(),original)
        old=Path.cwd()
        try:
            os.chdir(self.root)
            self.assertEqual(resolve_experiment(self.zip,self.config),wrapped)
        finally:os.chdir(old)

    def test_no_extraction_or_path_parser_and_fake_native_prepare(self):
        out=self.root/'out';csx=ComponentCSX();engine=RunEngine()
        with patch.object(ZipFile,'extract',side_effect=AssertionError('no extract')),\
             patch.object(ZipFile,'extractall',side_effect=AssertionError('no extractall')),\
             patch('gerbonara.GerberFile.open',side_effect=AssertionError('text parsing required')),\
             patch('gerbonara.ExcellonFile.open',side_effect=AssertionError('text parsing required')),\
             patch('antenna_lab.solvers.openems.native_modules',return_value=(
                 SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=lambda:csx))),\
             contextlib.redirect_stdout(io.StringIO()):
            result=run_gerber_control(self.zip,out,prepare_only=True,quality='preview',**BAND)
        self.assertEqual(result['status'],'prepared');self.assertFalse(any(c[0]=='Run' for c in engine.calls))
        info=result['import']['experiment_input'];self.assertEqual(info['netlist']['scope'],'parent')
        self.assertEqual(info['gerber_archive']['sha256'],sha256(self.zip.read_bytes()).hexdigest())
        for record in result['import']['discovered_files']:
            self.assertIn('.ZIP::',record['path'])
            self.assertEqual(record['sha256'],sha256(self.files[record['name']]).hexdigest())
        self.assertEqual(sorted(p.name for p in self.local.iterdir()),['board.ZIP'])
        self.assertFalse(any(p.suffix.lower() in ('.gtl','.gbl','.drl') for p in out.rglob('*')))
        self.assertTrue((out/'native/model.xml').is_file())

    def test_missing_roles_probe_internal_netlist_and_two_roots(self):
        for name in ('Gerber_TopLayer.GTL','board-B_Cu.gbr','Gerber_BoardOutlineLayer.GKO','FlyingProbeTesting.json'):
            files=dict(self.files);files.pop(name)
            archive(self.zip,files)
            with self.subTest(name=name),self.assertRaises(ConfigurationError):
                load_experiment_geometry(resolve_experiment(self.zip))
        archive(self.zip,{**self.files,'x.enet':b'{}'})
        with self.assertRaisesRegex(ConfigurationError,'internal .enet'):resolve_experiment(self.zip)
        archive(self.zip,{**{'one/'+k:v for k,v in self.files.items()},**{'two/'+k:v for k,v in self.files.items()}})
        with self.assertRaisesRegex(ConfigurationError,'candidates: one, two'):resolve_experiment(self.zip)

    def test_required_external_netlist_no_auto_feed_fallback_and_zero_epsilon(self):
        (self.family/'common.enet').unlink()
        with patch('antenna_lab.solvers.openems.native_modules') as native:
            with self.assertRaisesRegex(ConfigurationError,'netlist not found'):
                run_gerber_control(self.zip,self.root/'missing',prepare_only=True)
            native.assert_not_called()
        (self.family/'common.enet').write_bytes(self.enet.read_bytes())
        bad=easyeda();bad['physicalStacking'][1]['values']['Permittivity']=0
        (self.local/'bad.json').write_text(json.dumps(bad))
        with patch('antenna_lab.pcb.gerber_control.make_pcb_domain_mesh') as mesh:
            with self.assertRaisesRegex(ConfigurationError,'Permittivity=0'):
                run_gerber_control(self.zip,self.root/'bad',prepare_only=True)
            mesh.assert_not_called()

    def test_drill_members_g90_and_provenance(self):
        # Add an isolated NPTH, keeping the strict Excellon warning whitelist.
        files=dict(self.files);files['Drill_NPTH_Through.DRL']=drill_text(10,10,.3).replace('%\n','%\nG90\n').encode()
        archive(self.zip,files)
        _,g,meta=load_experiment_geometry(resolve_experiment(self.zip))
        self.assertEqual(len(g.drills),1);self.assertFalse(g.drills[0].plated)
        d=meta['drill_sources'][0]
        self.assertIn('board.ZIP::Drill_NPTH',d['path'])
        self.assertEqual(d['sha256'],sha256(files['Drill_NPTH_Through.DRL']).hexdigest())
        self.assertEqual(d['compatibility_warnings'][0]['disposition'],'accepted_gerbonara_compatibility_warning')

    def test_security_names_duplicates_special_encryption_corruption_limits(self):
        for name in ('../a.gtl','/a.gtl','C:/a.gtl','\\\\server\\a.gtl','x\\..\\a.gtl','a//b.gtl','./a.gtl'):
            archive(self.zip,{name:b'text'})
            with self.subTest(name=name),self.assertRaises(ConfigurationError):sources.zip_members(self.zip)
        for names in (('a.gtl','a.gtl'),('X/a.gtl','X\\a.gtl'),('a.gtl','A.GTL')):
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                with ZipFile(self.zip,'w') as z:
                    for n in names:z.writestr(n,'x')
            with self.assertRaisesRegex(ConfigurationError,'Duplicate'):sources.zip_members(self.zip)
        info=ZipInfo('link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        with ZipFile(self.zip,'w') as z:z.writestr(info,'target')
        with self.assertRaisesRegex(ConfigurationError,'special'):sources.zip_members(self.zip)
        self.zip.write_bytes(b'not a zip')
        with self.assertRaisesRegex(ConfigurationError,'Invalid PCB ZIP'):sources.zip_members(self.zip)
        archive(self.zip,{'a':'12345','b':'12345'})
        for setting,limit in (('MAX_ARCHIVE_MEMBERS',1),('MAX_MEMBER_BYTES',4),('MAX_TOTAL_BYTES',9),('MAX_ARCHIVE_BYTES',1)):
            with patch.object(sources,setting,limit),self.assertRaises(ConfigurationError):sources.zip_members(self.zip)
        real=ZipFile.infolist
        def encrypted(z):
            entries=real(z);entries[0].flag_bits|=1;return entries
        with patch.object(ZipFile,'infolist',encrypted),self.assertRaisesRegex(ConfigurationError,'Encrypted'):
            sources.zip_members(self.zip)


class RealZipAcceptance(unittest.TestCase):
    def test_local_parent_and_directory_oracle_equivalence(self):
        real=ROOT/'gerbs/realpcb_microstrip/test1.zip'
        selected=resolve_experiment(real)
        self.assertEqual((selected.stackup.scope,selected.netlist.scope),('local','local'))
        _,local,meta=load_experiment_geometry(selected)
        with TemporaryDirectory() as t:
            family=Path(t);variant=family/'variant';variant.mkdir()
            for name in ('test1.enet','stacup.json'):(family/name).write_bytes((real.parent/name).read_bytes())
            copied=variant/'test1.zip';copied.write_bytes(real.read_bytes())
            parent=resolve_experiment(copied)
            self.assertEqual((parent.stackup.scope,parent.netlist.scope),('parent','parent'))
            _,inherited,_=load_experiment_geometry(parent)
            self.assertEqual(local.as_dict(),inherited.as_dict())
            # Oracle exists before cleanup; after cleanup build a TEST-ONLY directory from members.
            oracle=real.with_suffix('')
            if not oracle.is_dir():
                oracle=family/'oracle';oracle.mkdir()
                for m in selected.members:(oracle/m.name).write_bytes(m.read_bytes())
            with ZipFile(real) as z:
                for n in z.namelist():self.assertEqual(z.read(n),(oracle/n).read_bytes())
            _,old,_=load_multilayer_bundle(oracle,json.loads(selected.physical_json),
                       component_sources=(selected.netlist.source_path,oracle/'FlyingProbeTesting.json'))
            old.assumptions.extend(json.loads(selected.stackup_audit_json)['assumptions'])
            self.assertEqual(old.as_dict(),local.as_dict())
            s,_=gerber_quality_settings('preview',**BAND);results=[]
            for geometry in (local,inherited,old):
                normalized,transform=normalize_port_orientation(geometry)
                modeled,_,audit=apply_geometry_resolution(normalized,PcbGrid())
                mesh=make_pcb_domain_mesh(modeled,s,gerber_quality='preview')
                cost=gerber_cost_preflight(mesh,s)
                results.append((normalized.as_dict(),modeled.as_dict(),mesh,cost))
                self.assertEqual(audit['topology_status'],'PASS')
                self.assertTrue(transform.exact_orthogonal)
                self.assertEqual(modeled.source_port.source_refdes,'CSRC')
                self.assertEqual([(c.id,c.value_si) for c in modeled.components],[('R1',49.9)])
                self.assertEqual(len(modeled.drills),2)
                self.assertTrue(all(set(d.connected_layer_roles)=={'top','bottom'} for d in modeled.drills))
                specs=resolve_component_boxes(modeled,(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m))
                self.assertEqual([(c.id,c.value_si) for c in specs],[('R1',49.9)])
                # Downstream excitation budget remains an independent guard.
                with self.assertRaisesRegex(ConfigurationError,'excitation needs at least'):
                    require_excitation_fits(cost,s)
            self.assertEqual(results[0],results[1]);self.assertEqual(results[0],results[2])
            # Both production profiles must get beyond component resolution.
            # The known excitation budget failure must occur before native work.
            for quality in ('preview','design'):
                s,_=gerber_quality_settings(quality,**BAND)
                normalized,_=normalize_port_orientation(local)
                modeled,_,_=apply_geometry_resolution(normalized,PcbGrid())
                before=modeled.as_dict()
                mesh=make_pcb_domain_mesh(modeled,s,gerber_quality=quality)
                specs=resolve_component_boxes(modeled,(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m))
                self.assertEqual([(c.id,c.kind,c.value_si) for c in specs],[('R1','R',49.9)])
                self.assertEqual(modeled.as_dict(),before)
                c=modeled.components[0];spec=specs[0]
                self.assertGreaterEqual(spec.start_m[1],min(p[1] for p in c.contact_window_xy_m))
                self.assertLessEqual(spec.stop_m[1],max(p[1] for p in c.contact_window_xy_m))
                # The previous sparse transverse mesh is still rightly rejected.
                lo=min(p[1] for p in c.contact_window_xy_m)
                hi=max(p[1] for p in c.contact_window_xy_m)
                damaged=tuple(y for y in mesh.y_lines_m if not lo<=y<=hi)
                with self.assertRaisesRegex(ConfigurationError,'explicit EM mesh-contact policy'):
                    resolve_component_boxes(modeled,(mesh.x_lines_m,damaged,mesh.z_lines_m))
                output=io.StringIO()
                with patch('antenna_lab.solvers.openems.native_modules') as native,contextlib.redirect_stdout(output):
                    with self.assertRaisesRegex(ConfigurationError,'excitation needs at least'):
                        run_gerber_control(copied,family/quality,prepare_only=True,quality=quality,**BAND)
                native.assert_not_called()
                self.assertIn('Cost indicator:',output.getvalue())
                self.assertNotIn('no legal existing transverse cell',output.getvalue())



if __name__=='__main__':unittest.main()
