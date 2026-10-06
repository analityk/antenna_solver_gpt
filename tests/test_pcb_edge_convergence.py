"""Feed-edge experiment: real Python mesh/audits, fake native API, no FDTD."""
import contextlib
from dataclasses import asdict, replace
import csv
import io
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import edge_convergence as e
from antenna_lab.pcb.control import make_synthetic_control_case
from antenna_lab.pcb.model import BoardOutline
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from antenna_lab.solvers.pcb_mesh import (make_pcb_domain_mesh, pcb_port_edge_policy,
    make_pcb_solver_anchor_plan, audit_pcb_port_edge_mesh, derive_pcb_physical_mesh_policy)
from antenna_lab.solvers.openems_pcb import (prepare_pcb_xml_model, run_pcb_fdtd,
    read_pcb_native_statistics)
from test_openems_pcb import CSX, XmlEngine
from test_pcb_control import Port


def statistics_text(iterations=12345):
    return ('373230\t% number of cells\n2e-12\t% timestep (s)\n'
            f'{iterations}\t% number of iterations\n{iterations*2e-12:.16g}\t% total numerical time (s)\n'
            '1.25\t% simulation time (s)\n3e6\t% speed (cells/s)\n')


class RunEngine(XmlEngine):
    def __init__(self,n=3,reactance=-500,iterations=12345,**kw):
        super().__init__(**kw)
        self.port=Port([5+reactance*1j]*n,[1]*n)
        self.iterations=iterations

    def Run(self,path,**kw):
        self.calls.append(('Run',path,kw))
        os.chdir(path)
        if kw.get('dump_statistics'):
            (Path(path)/'openEMS_stats.txt').write_text(statistics_text(self.iterations))
        return 0


class EdgeTests(unittest.TestCase):
    def case(self,level=2,**band):
        g,s=make_synthetic_control_case(**band)
        return g,e.make_edge_variants(s)[level-2][3]

    def test_aligned_default_matches_explicit_mode(self):
        for level in (2,3):
            g,s=self.case(level)
            self.assertEqual(make_pcb_domain_mesh(g,s),make_pcb_domain_mesh(g,s,port_edge_mode='aligned'))
            # Shape/coordinates have unchanged formulas; no thirds fields in result.
            self.assertNotIn('port_edge_mode',asdict(make_pcb_domain_mesh(g,s)))

    def test_formulas_hints_absent_edges_z_and_same_physical_port(self):
        for level in (2,3):
            g,s=self.case(level);before=g.as_dict()
            p=derive_pcb_physical_mesh_policy(g,s);edge=pcb_port_edge_policy(g,s,'thirds')
            n,pos=g.port.negative_xy_m,g.port.positive_xy_m
            my=(n[1]+pos[1])/2;yl=my-g.port.width_m/2;yu=my+g.port.width_m/2
            hx=min(p.max_port_gap_step_m,p.max_substrate_xy_step_m)
            hy=min(p.max_port_width_step_m,p.max_substrate_xy_step_m)
            self.assertEqual(edge['x_hints'],(n[0]-hx/3,n[0]+2*hx/3,pos[0]-2*hx/3,pos[0]+hx/3))
            self.assertEqual(edge['y_hints'],(yl-2*hy/3,yl+hy/3,yu-hy/3,yu+2*hy/3))
            m=make_pcb_domain_mesh(g,s,port_edge_mode='thirds')
            for axis,lines in (('x',m.x_lines_m),('y',m.y_lines_m)):
                for v in edge[axis+'_hints']: self.assertIn(v,lines)
                for v in edge['physical_'+axis+'_edges']: self.assertNotIn(v,lines)
                for left,right in (edge[axis+'_hints'][:2],edge[axis+'_hints'][2:]):
                    self.assertEqual(lines.index(right)-lines.index(left),1)
            self.assertIn(0.,m.z_lines_m)
            self.assertLessEqual(m.worst_growth_ratio,s.growth_ratio_limit*(1+1e-10))
            a=resolve_pcb_lumped_port(g,make_pcb_domain_mesh(g,s),s)
            b=resolve_pcb_lumped_port(g,m,s,port_edge_mode='thirds')
            self.assertEqual((a.start_m,a.stop_m),(b.start_m,b.stop_m))
            self.assertGreaterEqual(b.x_cell_count,s.min_port_gap_cells)
            self.assertGreaterEqual(b.y_cell_count,s.min_port_width_cells)
            self.assertGreater(b.active_ex_edge_count,0)
            self.assertEqual(g.as_dict(),before)
            with self.assertRaises(ConfigurationError): resolve_pcb_lumped_port(g,m,s)

    def test_orientation_narrow_contact_intrusion_and_critical_conflict(self):
        for fault in ('orientation','narrow','intrusion','board'):
            g,s=self.case();n=g.port.negative_xy_m[0]
            if fault=='board':
                verts=tuple((x,max(y,-g.port.width_m/2)) for x,y in g.outline.vertices_xy_m)
                g.outline=BoardOutline(verts);g.substrate=replace(g.substrate,outline=g.outline)
            else:
                copper=g.copper[0]
                if fault=='orientation': verts=((n,-.001),(n+.0002,-.001),(n+.0002,.001),(n,.001))
                elif fault=='narrow': verts=tuple((x,y/2) for x,y in copper.vertices_xy_m)
                else: verts=tuple((x+.0001 if abs(x-n)<1e-10 else x,y) for x,y in copper.vertices_xy_m)
                g.copper[0]=replace(copper,vertices_xy_m=verts)
            with self.subTest(fault=fault),self.assertRaises(ConfigurationError):
                make_pcb_domain_mesh(g,s,port_edge_mode='thirds')

    def test_hint_and_forbidden_line_and_cell_splitting_audits(self):
        g,s=self.case();m=make_pcb_domain_mesh(g,s,port_edge_mode='thirds');edge=pcb_port_edge_policy(g,s,'thirds')
        cases=[replace(m,x_lines_m=tuple(x for x in m.x_lines_m if x!=edge['x_hints'][0])),
               replace(m,x_lines_m=tuple(sorted((*m.x_lines_m,g.port.negative_xy_m[0])))),
               replace(m,y_lines_m=tuple(sorted((*m.y_lines_m,sum(edge['y_hints'][:2])/2)))),
               replace(m,z_lines_m=tuple(x for x in m.z_lines_m if x!=0.))]
        for bad in cases:
            with self.assertRaises(ConfigurationError): audit_pcb_port_edge_mesh(g,s,bad,'thirds')
        with self.assertRaises(ConfigurationError): make_pcb_domain_mesh(g,s,port_edge_mode='unknown')
        with self.assertRaises(ConfigurationError): make_pcb_domain_mesh(g,replace(s,max_cells=100),port_edge_mode='thirds')

    def test_native_geometry_grid_and_physical_port_identical(self):
        g,s=self.case();before=g.as_dict();geometries=[];ports=[]
        for mode in ('aligned','thirds'):
            csx=CSX();engine=RunEngine()
            with TemporaryDirectory() as d,patch('antenna_lab.solvers.openems.native_modules',return_value=(
                    SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=lambda:csx))):
                _,_,_,mesh,spec,_=prepare_pcb_xml_model(g,s,Path(d)/'model.xml',port_edge_mode=mode)
            geometries.append(csx.metals[0][1].polygons)
            ports.append((spec.start_m,spec.stop_m))
            for axis,lines in zip('xyz',(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)):
                self.assertEqual(csx.GetGrid().GetLines(axis),lines)
            call=next(v for v in engine.calls if v[0]=='AddLumpedPort')
            self.assertEqual(call[1][2:4],(list(spec.start_m),list(spec.stop_m)))
            self.assertNotIn('edges2grid',call[2])
            self.assertFalse(any(v[0]=='Run' for v in engine.calls))
        self.assertEqual(geometries[0],geometries[1]);self.assertEqual(ports[0],ports[1]);self.assertEqual(before,g.as_dict())

    def test_statistics_parser_good_and_bad(self):
        with TemporaryDirectory() as d:
            path=Path(d)/'openEMS_stats.txt'
            path.write_text(statistics_text())
            stats=read_pcb_native_statistics(path)
            self.assertEqual(stats['number_of_iterations'],12345)
            self.assertEqual(stats['fdtd_timestep_s'],2e-12)
            self.assertAlmostEqual(stats['total_numerical_time_s'],12345*2e-12)
            for text in ('',statistics_text().replace('12345\t','nan\t'),statistics_text().replace('2e-12','-2e-12'),
                         statistics_text().replace('12345\t','12345.5\t'),statistics_text()+'1\t% timestep (s)\n',
                         statistics_text().replace('2e-12','3e-12')):
                path.write_text(text)
                with self.assertRaises(ConfigurationError): read_pcb_native_statistics(path)
            path.unlink()
            with self.assertRaises(ConfigurationError): read_pcb_native_statistics(path)

    def test_run_flags_statistics_cap_and_cwd(self):
        g,s=self.case();mesh=make_pcb_domain_mesh(g,s)
        for iterations in (99999,100000,100001):
            csx=CSX();csx.grid.lines=dict(zip('xyz',(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)))
            engine=RunEngine(iterations=iterations);cwd=Path.cwd()
            with TemporaryDirectory() as d:
                (Path(d)/'model.xml').write_text('<model/>')
                if iterations>=s.max_timesteps:
                    with self.assertRaisesRegex(ConfigurationError,'temporal termination not established'):
                        run_pcb_fdtd(engine,csx,engine.port,mesh,s,d,exact_endcriteria=True,dump_statistics=True)
                    self.assertEqual(engine.port.calls,[])
                else:
                    result=run_pcb_fdtd(engine,csx,engine.port,mesh,s,d,exact_endcriteria=True,dump_statistics=True)
                    self.assertEqual(result['native_statistics']['number_of_iterations'],iterations)
                    self.assertEqual(result['run_options'],dict(exact_endcriteria=True,dump_statistics=True))
                self.assertEqual(engine.calls[-1],('Run',d,dict(cleanup=False,numThreads=0,exact_endcriteria=True,dump_statistics=True)))
                self.assertEqual(Path.cwd(),cwd)
                with self.assertRaisesRegex(ConfigurationError,'stare'):
                    run_pcb_fdtd(engine,csx,engine.port,mesh,s,d,dump_statistics=True)

    def test_variants_gate_and_historical_diagnostic(self):
        _,base=make_synthetic_control_case()
        variants=e.make_edge_variants(base)
        self.assertEqual(tuple(v[0] for v in variants),e.VARIANT_NAMES)
        for name,mode,level,settings in variants:
            self.assertEqual((settings.cells_per_wavelength,settings.min_port_gap_cells,settings.min_substrate_cells_z),
                             (40,6,12) if level=='L2' else (50,8,16))
            for key in ('air_padding_wavelengths','pml_cells','end_criteria','max_timesteps','result_frequency_hz'):
                self.assertEqual(getattr(settings,key),getattr(base,key))
        boundary=dict(relative_Z_magnitude=.01,relative_X=.01,relative_R=.05)
        self.assertTrue(e.engineering_gate([boundary]))
        for k in boundary:
            self.assertFalse(e.engineering_gate([{**boundary,k:math.nextafter(boundary[k],math.inf)}]))
        rows=[dict(frequency_hz=1.42e9,relative_Z_magnitude=.0235)]
        self.assertTrue(e.aligned_reproduction(rows,base)[0]['broadly_consistent'])
        self.assertIsNone(e.aligned_reproduction(rows,replace(base,excitation_center_hz=2.45e9))[0]['broadly_consistent'])

    def test_full_ab_fake_native_outputs_and_frequency_identity(self):
        for band in ({},dict(excitation_center_hz=2.45e9,excitation_cutoff_hz=.4e9,
                            result_frequency_hz=(2.2e9,2.45e9,2.7e9))):
            created=[];csxs=[];geometry=[]
            from antenna_lab.pcb.control import run_control_model as real_runner
            def runner(g,s,path,**kw):
                geometry.append(g.as_dict())
                return real_runner(g,s,path,**kw)
            def factory(**kw):
                engine=RunEngine(reactance=(-545,-558,-540,-542)[len(created)],**kw)
                created.append(engine);return engine
            def csx_factory():
                csx=CSX();csxs.append(csx);return csx
            with TemporaryDirectory() as d,patch('antenna_lab.solvers.openems.native_modules',return_value=(
                    SimpleNamespace(openEMS=factory),SimpleNamespace(ContinuousStructure=csx_factory))),\
                    patch.object(e,'run_control_model',side_effect=runner),contextlib.redirect_stdout(io.StringIO()):
                study=e.run_edge_study(d,**band)
                self.assertEqual(list(study['variants']),list(e.VARIANT_NAMES))
                self.assertTrue(study['candidate_thirds_converged'])
                self.assertEqual(study['status'],'diagnostic_candidate_converged')
                self.assertEqual(len(created),4)
                paths=[]
                for engine in created:
                    run=[v for v in engine.calls if v[0]=='Run'];self.assertEqual(len(run),1)
                    paths.append(run[0][1]);self.assertTrue(run[0][2]['exact_endcriteria'])
                    self.assertTrue(run[0][2]['dump_statistics'])
                    self.assertEqual(engine.port.calls[0][1].tolist(),list(make_synthetic_control_case(**band)[1].result_frequency_hz))
                self.assertEqual(len(set(paths)),4);self.assertTrue(all(g==geometry[0] for g in geometry))
                self.assertTrue(all(c.metals[0][1].polygons==csxs[0].metals[0][1].polygons for c in csxs))
                self.assertEqual(len(study['comparisons']),4)
                self.assertAlmostEqual(study['comparisons']['thirds_L3_vs_L2'][0]['delta_X_ohm'],-2.)
                self.assertTrue(all(v['smaller'] for v in study['thirds_change_smaller']))
                self.assertEqual(study,json.loads((Path(d)/'edge_convergence.json').read_text()))
                json.dumps(study,allow_nan=False)
                with (Path(d)/'edge_convergence.csv').open(newline='') as stream:
                    rows=list(csv.DictReader(stream))
                self.assertEqual(len(rows),12)
                self.assertEqual(rows[-1]['number_of_iterations'],'12345')
                with self.assertRaises(ConfigurationError): e.run_edge_study(d,**band)

    def test_failure_preserves_aligned_runs_and_rejects_nonpassivity(self):
        from antenna_lab.pcb.control import run_control_model as real_runner
        created=[]
        def factory(**kw):
            engine=RunEngine(iterations=100000 if len(created)==2 else 12345,**kw)
            created.append(engine);return engine
        with TemporaryDirectory() as d,patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=factory),SimpleNamespace(ContinuousStructure=CSX))),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ConfigurationError,'temporal termination'): e.run_edge_study(d)
            study=json.loads((Path(d)/'edge_convergence.json').read_text())
            self.assertEqual(study['status'],'failed');self.assertFalse(study['candidate_thirds_converged'])
            self.assertEqual(study['variants']['aligned_L3']['status'],'completed')
            self.assertEqual(study['variants']['thirds_L2']['status'],'failed')
            self.assertEqual(study['variants']['thirds_L3']['status'],'pending')
            self.assertTrue((Path(d)/'aligned_L2/summary.json').is_file())
            result=study['variants']['aligned_L2']['result'];result['s11_magnitude'][0]=1.
            with self.assertRaisesRegex(ConfigurationError,'non-passive'):
                e.audit_experiment_result(result,self.case()[1])

    def test_cli_conversion(self):
        with TemporaryDirectory() as d,patch.object(e,'run_edge_study',return_value=dict(status='diagnostic_not_converged',candidate_thirds_converged=False)) as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(e.main(['--output',d,'--center-mhz','900','--cutoff-mhz','150',
                                    '--frequencies-mhz','800','900','1000','--loss-reference-mhz','850']),0)
            self.assertEqual(run.call_args.kwargs,dict(excitation_center_hz=.9e9,excitation_cutoff_hz=.15e9,
                result_frequency_hz=(.8e9,.9e9,1e9),loss_reference_frequency_hz=.85e9))


if __name__=='__main__': unittest.main()
