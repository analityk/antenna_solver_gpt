"""Gerber-only quality, exact geometry and termination; no native FDTD."""
import contextlib
from dataclasses import asdict, replace
import io
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.gerber import load_pcb_geometry
from antenna_lab.pcb import gerber_control as control
from antenna_lab.pcb.gerber_quality import gerber_quality_settings, gerber_cost_preflight, require_excitation_fits
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.model import CopperPolygon
from antenna_lab.solvers.pcb_mesh import C0, make_pcb_domain_mesh, make_gerber_mesh_anchor_plan
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from test_pcb_edge_convergence import RunEngine
from test_openems_pcb import CSX
import test_pcb_gerber as fixtures


class GerberQualityTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.GerberTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.g,_=normalize_port_orientation(load_pcb_geometry(self.fixture.config))

    def test_exact_profiles_and_frequency_identity(self):
        expected=((10,2,2,2,.1,6,1e-3,50000,False),
                  (15,3,2,2,.15,6,1e-4,75000,False),
                  (20,4,4,4,.25,8,1e-5,120000,True))
        for q,values in zip(('preview','design','verify'),expected):
            s,exact=gerber_quality_settings(q,excitation_center_hz=2.45e9,excitation_cutoff_hz=.4e9,
                result_frequency_hz=(2.2e9,2.45e9,2.7e9),loss_reference_frequency_hz=2.4e9)
            self.assertEqual(tuple(getattr(s,k) for k in ('cells_per_wavelength','min_substrate_cells_z',
                'min_port_gap_cells','min_port_width_cells','air_padding_wavelengths','pml_cells',
                'end_criteria','max_timesteps'))+(exact,),values)
            self.assertEqual(s.result_frequency_hz,(2.2e9,2.45e9,2.7e9))
            self.assertEqual(s.loss_reference_frequency_hz,2.4e9)
        self.assertEqual(gerber_quality_settings(),gerber_quality_settings('design'))
        with self.assertRaises(ConfigurationError):gerber_quality_settings('bad')

    def test_critical_and_physical_close_edges_preserved_deterministic_no_mutation(self):
        # Two harmless off-feed islands staggered by 25 um, well inside the board.
        for i,dy in enumerate((0.,25e-6)):
            self.g.copper.append(CopperPolygon(f'island_{i}',
                ((-.009+i*.002,.008+dy),(-.008+i*.002,.008+dy),
                 (-.008+i*.002,.009+dy),(-.009+i*.002,.009+dy)),0.))
        from antenna_lab.pcb.geometry_resolution import apply_geometry_resolution
        from antenna_lab.pcb.grid import PcbGrid
        self.g,_,_=apply_geometry_resolution(self.g,PcbGrid())
        before=self.g.as_dict()
        n,p=self.g.port.negative_xy_m,self.g.port.positive_xy_m
        my=(n[1]+p[1])/2;half=self.g.port.width_m/2
        for q in ('preview','design','verify'):
            s,_=gerber_quality_settings(q)
            plan,meta=make_gerber_mesh_anchor_plan(self.g,s,q)
            self.assertEqual((plan,meta),make_gerber_mesh_anchor_plan(self.g,s,q))
            mesh=make_pcb_domain_mesh(self.g,s,gerber_quality=q)
            for v in (n[0],(n[0]+p[0])/2,p[0]):self.assertIn(v,mesh.x_lines_m)
            for v in (my-half,my,my+half):self.assertIn(v,mesh.y_lines_m)
            for axis,lines in enumerate((mesh.x_lines_m,mesh.y_lines_m)):
                vals=[v[axis] for v in self.g.outline.vertices_xy_m]
                self.assertIn(min(vals),lines);self.assertIn(max(vals),lines)
            self.assertIn(0.,mesh.z_lines_m);self.assertIn(self.g.substrate.z_min_m,mesh.z_lines_m)
            for copper in self.g.copper:
                for axis,lines in enumerate((mesh.x_lines_m,mesh.y_lines_m)):
                    for vertex in copper.vertices_xy_m:self.assertIn(vertex[axis],lines)
            self.assertEqual(meta['suppressed_physical_feature_coordinates'],0)
            self.assertTrue(all(row['kind']=='bbox_midpoint' for row in meta['suppressed_noncritical_anchors']))
            if q!='verify':
                self.assertFalse(meta['copper_midpoints'])
            resolve_pcb_lumped_port(self.g,mesh,s,gerber_quality=q)
        self.assertEqual(before,self.g.as_dict())

    def test_cfl_pulse_and_update_math(self):
        s,_=gerber_quality_settings('design')
        mesh=SimpleNamespace(x_lines_m=(0.,.001,.003),y_lines_m=(0.,.002,.005),
                             z_lines_m=(0.,.003,.006),cell_count=8)
        c=gerber_cost_preflight(mesh,s)
        expected=1/(C0*math.sqrt(1/.001**2+1/.002**2+1/.003**2))
        self.assertEqual(c['min_axis_steps_m'],dict(x=.001,y=.002,z=.003))
        self.assertAlmostEqual(c['estimated_cfl_dt_s']/expected,1.)
        self.assertEqual(c['gaussian_pulse_duration_s'],9/(math.pi*s.excitation_cutoff_hz))
        count=math.ceil(c['gaussian_pulse_duration_s']/expected)
        self.assertEqual(c['estimated_excitation_steps'],count)
        self.assertEqual(c['estimated_cell_updates'],8*count)
        with self.assertRaises(ConfigurationError):require_excitation_fits(c,replace(s,max_timesteps=count))
        require_excitation_fits(c,replace(s,max_timesteps=count+1))

    def test_cost_order_and_native_geometry_identical_successful_termination(self):
        costs=[];polygons=[];ports=[];materials=[]
        for q in ('preview','design','verify'):
            engine=RunEngine();csx=CSX();out=self.fixture.root/q
            with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=lambda:csx))),\
                    contextlib.redirect_stdout(io.StringIO()) as console:
                result=control.run_gerber_control(self.fixture.config_path,out,quality=q)
            self.assertEqual(result['quality_profile'],q)
            self.assertEqual(result['actual_iterations'],12345)
            self.assertEqual(result['termination_status'],'completed_before_limit')
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['validation_status'],'unverified')
            self.assertEqual(result,json.loads((out/'summary.json').read_text()))
            self.assertIn('Estimated excitation:',console.getvalue())
            self.assertTrue(result['suppressed_noncritical_anchors'])
            run=next(c for c in engine.calls if c[0]=='Run')
            expected=dict(cleanup=False,numThreads=0,dump_statistics=True)
            if q=='verify':expected['exact_endcriteria']=True
            self.assertEqual(run[2],expected)
            costs.append(result['estimated_cell_updates'])
            polygons.append(csx.metals[0][1].polygons)
            ports.append(next(c for c in engine.calls if c[0]=='AddLumpedPort')[1][2:4])
            materials.append(csx.materials[0][1])
            self.assertEqual(engine.port.calls[0][1].tolist(),[1.3e9,1.42e9,1.5e9])
        self.assertLess(costs[0],costs[1]);self.assertLess(costs[1],costs[2])
        self.assertTrue(all(p==polygons[0] for p in polygons))
        self.assertTrue(all(p==ports[0] for p in ports))
        self.assertTrue(all(m==materials[0] for m in materials))

    def test_unfittable_excitation_stops_before_loading_native(self):
        s,exact=gerber_quality_settings('design')
        with patch.object(control,'gerber_quality_settings',return_value=(replace(s,max_timesteps=1),exact)),\
                patch('antenna_lab.solvers.openems.native_modules') as native,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ConfigurationError,'excitation needs at least'):
                control.run_gerber_control(self.fixture.config_path,self.fixture.root/'cost_fail')
            native.assert_not_called()
        summary=json.loads((self.fixture.root/'cost_fail/summary.json').read_text())
        self.assertEqual(summary['status'],'failed')
        self.assertEqual(summary['termination_status'],'not_started')
        self.assertIsNone(summary['actual_iterations'])
        self.assertGreater(summary['estimated_excitation_steps'],1)

    def test_timestep_limit_is_failed_without_calcport_or_impedance(self):
        for q in ('preview','design','verify'):
            s,_=gerber_quality_settings(q);engine=RunEngine(iterations=s.max_timesteps)
            out=self.fixture.root/('failed_'+q)
            with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=CSX))),\
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ConfigurationError,'temporal termination'):
                    control.run_gerber_control(self.fixture.config_path,out,quality=q)
            self.assertEqual(engine.port.calls,[])
            self.assertFalse((out/'impedance.csv').exists())
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['status'],'failed')
            self.assertEqual(summary['termination_status'],'max_timesteps_reached')
            self.assertEqual(summary['actual_iterations'],s.max_timesteps)
            self.assertNotIn('resistance_ohm',summary)

    def test_cli_profile_default_and_explicit(self):
        for args,q in (([],'design'),(['--quality','preview'],'preview'),(['--quality','verify'],'verify')):
            with patch.object(control,'run_gerber_control',return_value={'status':'prepared'}) as run,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(control.main([str(self.fixture.config_path),'--output',str(self.fixture.root/'cli'),
                                               '--prepare-only',*args]),0)
                self.assertEqual(run.call_args.kwargs['quality'],q)


if __name__=='__main__':unittest.main()
