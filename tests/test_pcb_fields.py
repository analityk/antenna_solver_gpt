"""PCB fields through native fakes and real HDF5 reader; no native FDTD."""
from dataclasses import asdict,replace
from hashlib import sha256
import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import h5py
import numpy as np

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import gerber_control
from antenna_lab.pcb.bundle import load_bundle_geometry
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from antenna_lab.solvers.pcb_fields import (validate_field_frequencies,pcb_field_layout,
    pcb_sample_mask,voltage_scale,finish_pcb_fields,install_pcb_fields)
from antenna_lab.visualization.fields import phase_values,load_plane
from antenna_lab.visualization.pcb_fields import view_fields,viewer_payload,pcb_phase_figure,overlays
from antenna_lab.visualization.report import generate_report
from test_pcb_bundle import bundle_fixture
from test_pcb_edge_convergence import RunEngine
from test_openems_pcb import CSX


class FieldCSX(CSX):
    def __init__(self):super().__init__();self.dumps=[]
    def AddDump(self,name,**kwargs):
        entry=dict(name=name,**kwargs);self.dumps.append(entry)
        return SimpleNamespace(AddBox=lambda **box:entry.update(box))


class FieldPort:
    def __init__(self):self.calls=[]
    def CalcPort(self,path,frequencies,**kw):
        self.calls.append((path,frequencies.copy(),kw))
        self.uf_tot=(2+3j)*frequencies/1e9
        self.if_tot=self.uf_tot/(50+20j)


class FieldEngine(RunEngine):
    def __init__(self,csx):super().__init__();self.port=FieldPort();self.csx_fields=csx
    def Run(self,path,**kw):
        result=super().Run(path,**kw)
        for dump in self.csx_fields.dumps:
            lines=[np.asarray(self.csx_fields.grid.lines[a]) for a in 'xyz']
            lines=[a[(a>=lo)&(a<=hi)] for a,lo,hi in zip(lines,dump['start'],dump['stop'])]
            with h5py.File(Path(path)/(dump['name']+'.h5'),'w') as out:
                mesh=out.create_group('Mesh');mesh.attrs['mesh_type']=0
                for a,v in zip('xyz',lines):mesh[a]=v
                fd=out.create_group('FieldData/FD');fd.attrs['frequency']=dump['frequency']
                for i,f in enumerate(dump['frequency']):
                    raw=np.ones((3,*map(len,lines)),complex)*(2+3j)*f/1e9
                    raw[1]*=1j;raw[2]*=(2-1j)
                    field=fd.create_dataset(f'f{i}',data=raw)
                    field.attrs['frequency']=f;field.attrs['d_order']='NXYZ'
        self.raw_hashes={p.name:sha256(p.read_bytes()).hexdigest() for p in Path(path).glob('*.h5')}
        return result


class PcbFieldTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.bundle=bundle_fixture(self.root/'gerbers',loop=True)
        _,g,_=load_bundle_geometry(self.bundle);self.g,_=normalize_port_orientation(g)
        self.s,_=gerber_quality_settings('preview');self.mesh=make_pcb_domain_mesh(self.g,self.s,gerber_quality='preview')

    def run_fields(self,frequencies=(1.41e9,)):
        csx=FieldCSX();engine=FieldEngine(csx);out=self.root/'run'
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=lambda:csx))),\
                contextlib.redirect_stdout(io.StringIO()) as console:
            result=gerber_control.run_gerber_control(self.bundle,out,quality='preview',field_frequency_hz=frequencies)
        return out,result,csx,engine,console.getvalue()

    def test_frequency_validation_and_cli_preflight(self):
        self.assertEqual(validate_field_frequencies((1.5e9,1.4e9),self.s),(1.4e9,1.5e9))
        self.assertEqual(len(validate_field_frequencies((1.3e9,1.4e9,1.5e9),self.s)),3)
        for values in ((0,),(-1,), (float('nan'),),(float('inf'),),(True,),
                       (1.4e9,1.4e9),(1.1e9,),(1.63e9,),(1.3e9,1.4e9,1.5e9,1.6e9)):
            with self.subTest(values=values),self.assertRaises(ConfigurationError):validate_field_frequencies(values,self.s)
        with patch.object(gerber_control,'run_gerber_control') as run,contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(gerber_control.main([str(self.bundle),'--output',str(self.root/'x'),'--fields-mhz','1900']),1)
            run.assert_not_called()
        with patch.object(gerber_control,'run_gerber_control',return_value={'status':'prepared'}) as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gerber_control.main([str(self.bundle),'--output',str(self.root/'x'),'--prepare-only','--fields-mhz','1411','1501']),0)
            self.assertEqual(run.call_args.kwargs['field_frequency_hz'],(1.411e9,1.501e9))

    def test_layout_first_air_feed_centres_pml_limit_no_mutation(self):
        before=(self.g.as_dict(),asdict(self.mesh),asdict(self.s))
        layout=pcb_field_layout(self.g,self.mesh,self.s,(1.4e9,1.5e9))
        self.assertEqual([p['name'] for p in layout],['xy_air','xz_feed','yz_feed'])
        positive=next(z for z in self.mesh.z_lines_m if 0<z<self.mesh.pml_start_max_m[2])
        self.assertEqual(layout[0]['actual_position_m'],positive)
        for p in layout:
            for i in range(3):
                self.assertGreater(p['start_m'][i],self.mesh.pml_start_min_m[i])
                self.assertLess(p['stop_m'][i],self.mesh.pml_start_max_m[i])
            normal='xyz'.index(p['normal_axis'])
            self.assertEqual(p['shape_xyz'][normal],1)
            if normal!=2:
                midpoint=(self.g.port.negative_xy_m[normal]+self.g.port.positive_xy_m[normal])/2
                self.assertEqual(p['requested_position_m'],midpoint)
                self.assertEqual(p['actual_position_m'],midpoint)
        with patch('antenna_lab.solvers.pcb_fields.MAX_FIELD_POINTS',1):
            with self.assertRaisesRegex(ConfigurationError,'exceeds'):pcb_field_layout(self.g,self.mesh,self.s,(1.4e9,))
        self.assertEqual(before,(self.g.as_dict(),asdict(self.mesh),asdict(self.s)))

    def test_native_dump_grid_mutation_is_rejected(self):
        from antenna_lab.solvers.openems_pcb import prepare_pcb_native_model
        csx=FieldCSX();engine=FieldEngine(csx)
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=lambda:csx))):
            _,_,_,mesh,_,_=prepare_pcb_native_model(self.g,self.s,gerber_quality='preview')
        original=csx.AddDump
        def mutate(*args,**kwargs):
            dump=original(*args,**kwargs)
            csx.grid.lines['x']=csx.grid.lines['x'][1:]
            return dump
        csx.AddDump=mutate
        with self.assertRaises(ConfigurationError):install_pcb_fields(csx,self.g,mesh,self.s,(1.4e9,))

    def test_mask_copper_source_halo_substrate_and_air(self):
        axes=[np.asarray(getattr(self.mesh,a+'_lines_m')) for a in 'xyz']
        def mask(x,y,z):return int(pcb_sample_mask([np.array([v]) for v in (x,y,z)],axes,self.g).item())
        n=self.g.port.negative_xy_m
        self.assertTrue(mask(n[0]-.001,n[1],0)&1)
        self.assertTrue(mask(0,0,0)&4)
        first=next(z for z in self.mesh.z_lines_m if z>0)
        self.assertTrue(mask(n[0]-.001,n[1],first)&2)
        # Outside copper and source halo, even within substrate: no material mask.
        self.assertEqual(mask(0,-.01,-.0008),0)
        self.assertEqual(mask(.04,.04,.01),0)

    def test_voltage_normalization_and_phase_math(self):
        v=np.array([2+3j,-4j]);scale=voltage_scale(v)
        np.testing.assert_allclose(v*scale,1,rtol=1e-15)
        for bad in ([0j],[complex(float('nan'),0)],[complex(float('inf'),0)]):
            with self.assertRaises(ConfigurationError):voltage_scale(bad)
        field=np.array([2+3j,-1+4j])
        np.testing.assert_allclose(phase_values(field,180),-phase_values(field,0),atol=1e-14)
        np.testing.assert_allclose(phase_values(field,360),phase_values(field,0),atol=1e-14)

    def test_single_run_single_calcport_selected_dumps_full_export_and_report(self):
        out,result,csx,engine,console=self.run_fields((1.411e9,1.501e9))
        self.assertEqual(len([c for c in engine.calls if c[0]=='Run']),1)
        self.assertEqual(len(engine.port.calls),1)
        self.assertEqual(tuple(engine.port.calls[0][1]),(1.3e9,1.411e9,1.42e9,1.5e9,1.501e9))
        self.assertEqual(result['frequency_hz'],[1.3e9,1.42e9,1.5e9])
        for a in 'xyz':self.assertEqual(csx.grid.lines[a],getattr(self.mesh,a+'_lines_m'))
        self.assertEqual(len(csx.dumps),6)
        self.assertEqual([d['dump_type'] for d in csx.dumps],[10,11]*3)
        for d in csx.dumps:
            self.assertEqual(d['frequency'],[1.411e9,1.501e9]);self.assertEqual(d['dump_mode'],1);self.assertEqual(d['file_type'],1)
        self.assertIn('Mesh changed by fields: no',console);self.assertIn('Additional FDTD runs: 0',console)
        metadata=json.loads((out/'fields/metadata.json').read_text(),parse_constant=lambda x:self.fail(x))
        self.assertEqual(metadata['reference_voltage_v'],1.);self.assertFalse(metadata['mesh_changed'])
        self.assertIn('not accepted-power',metadata['normalization'])
        before={p.name:sha256(p.read_bytes()).hexdigest() for p in (out/'native').glob('*.h5')}
        self.assertEqual(before,engine.raw_hashes)
        for p in metadata['planes']:
            data=load_plane(out/'fields'/f'{p["name"]}.npz',p,metadata['frequency_hz'])
            self.assertEqual(data['E_v_per_m'].shape,(2,3,*p['shape_xyz']))
            self.assertNotIn('reference_power_w',data)
            valid=data['mask']==0
            np.testing.assert_allclose(data['E_v_per_m'][:,0,valid],1,atol=1e-14)
            np.testing.assert_allclose(data['E_v_per_m'][:,1,valid],1j,atol=1e-14)
            self.assertTrue(np.isnan(data['E_v_per_m'][:,:,~valid]).all())
            for i in range(2):self.assertTrue((out/'plots'/f'fields_{p["name"]}_{i}.png').exists())
        html=(out/'report.html').read_text()
        self.assertIn('Pola E/H — przebieg jednego okresu',html)
        for marker in ('pcb-field-player','setInterval','Pause','%d.phases.length','/360/d.frequency_hz*1e9'):
            self.assertIn(marker,html)
        self.assertNotIn('<script src=',html)
        for path in self.bundle.iterdir():path.unlink()
        with patch('antenna_lab.solvers.openems.native_modules',side_effect=AssertionError('native forbidden')):
            generate_report(out,self.root/'manual.html',phase_step=15)
        self.assertEqual(before,{p.name:sha256(p.read_bytes()).hexdigest() for p in (out/'native').glob('*.h5')})

    def test_fixed_scales_display_only_subsampling_and_strict_loader(self):
        out,result,_,_,_=self.run_fields()
        metadata=result['fields'];p=metadata['planes'][0]
        data=load_plane(out/'fields/xy_air.npz',p,metadata['frequency_hz']);snapshot=data['E_v_per_m'].copy()
        view=view_fields(data,p,0);paths=overlays(self.g.as_dict(),p)
        fig=pcb_phase_figure(view,paths,p)
        norms=[a.collections[0].norm for a in fig.axes[:8]]
        self.assertIs(norms[0],norms[2]);self.assertIs(norms[0],norms[6])
        self.assertEqual(norms[0].vmin,-norms[0].vmax)
        payload=viewer_payload(view,paths,list(range(0,360,30)))
        self.assertEqual(payload['phases'],list(range(0,360,30)))
        self.assertLessEqual(len(payload['u']),80);json.dumps(payload,allow_nan=False)
        np.testing.assert_equal(snapshot,data['E_v_per_m']);fig.clear()
        with np.load(out/'fields/xy_air.npz') as archive:bad=dict(archive)
        bad['E_v_per_m']=bad['E_v_per_m'][:,0];np.savez(self.root/'bad.npz',**bad)
        with self.assertRaisesRegex(ValueError,'próbki'):load_plane(self.root/'bad.npz',p,metadata['frequency_hz'])
        # Native E/H coordinate mismatch is rejected, never interpolated.
        native=out/'native'/p['native_files']['H']
        with h5py.File(native,'a') as h5:h5['Mesh/x'][0]+=1e-5
        import shutil
        shutil.rmtree(out/'fields')
        with self.assertRaisesRegex(ConfigurationError,'incompatible'):
            finish_pcb_fields(self.g,self.mesh,metadata['planes'],metadata['frequency_hz'],result['field_port_reference'],out)


if __name__=='__main__':unittest.main()
