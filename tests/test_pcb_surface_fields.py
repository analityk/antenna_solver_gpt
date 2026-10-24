"""Copper-face measurement contract, no expensive FDTD or hidden mesh changes."""
import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import CopperPolygon
from antenna_lab.solvers.pcb_mesh import copper_surface_z_anchors
from antenna_lab.solvers.pcb_fields import (pcb_field_layout, copper_surface_mask,
    COPPER_PROBE_OFFSET_M)
from antenna_lab.visualization.copper_surface_report import render_copper_surface_report


class CopperSurfaceTests(unittest.TestCase):
    def setUp(self):
        roles=('top','inner1','inner2','bottom')
        z=(0.,-0.0002,-0.0004,-0.0006)
        layers=[SimpleNamespace(role=r,z_m=v) for r,v in zip(roles,z)]
        outline=SimpleNamespace(vertices_xy_m=((-0.001,-0.001),(0.001,-0.001),
                                               (0.001,0.001),(-0.001,0.001)))
        footprint=((-0.0009,-0.0008),(0.0009,-0.0008),
                   (0.0009,0.0008),(-0.0009,0.0008))
        copper=[CopperPolygon(r,footprint,v,r) for r,v in zip(roles,z)]
        self.geometry=SimpleNamespace(copper_layers=layers,copper=copper,outline=outline,
            dielectrics=[SimpleNamespace(z_min_m=z[i+1],z_max_m=z[i])
                         for i in range(len(z)-1)])
        z_nodes=copper_surface_z_anchors(
            self.geometry,(-0.0006,-0.0004,-0.0002,0.),COPPER_PROBE_OFFSET_M)
        self.assertEqual(len(z_nodes),12)
        axes=(np.linspace(-0.003,0.003,101),np.linspace(-0.003,0.003,91),
              np.array([-0.005,*z_nodes,0.005]))
        self.mesh=SimpleNamespace(
            x_lines_m=axes[0],y_lines_m=axes[1],z_lines_m=axes[2],
            pml_start_min_m=(-0.0028,-0.0028,-0.004),
            pml_start_max_m=(0.0028,0.0028,0.004))
        self.settings=SimpleNamespace(excitation_center_hz=1.5e9,excitation_cutoff_hz=.5e9)

    def test_all_copper_faces_have_separate_exact_samples(self):
        planes=pcb_field_layout(self.geometry,self.mesh,self.settings,(1.5e9,),
            mode='copper_surfaces',surface_probe_offset_m=COPPER_PROBE_OFFSET_M)
        self.assertEqual(len(planes),8)
        self.assertEqual(len({p['name'] for p in planes}),8)
        for p in planes:
            sign=1 if p['copper_face']=='top' else -1
            self.assertAlmostEqual(p['actual_position_m']-p['copper_z_m'],
                                   sign*10e-6,delta=1e-12)
            self.assertEqual(p['normal_axis'],'z')
            self.assertEqual(p['shape_xyz'][2],1)
            self.assertEqual(p['measurement'],'copper_surface')

    def test_missing_near_face_nodes_fail_closed(self):
        mesh=SimpleNamespace(**vars(self.mesh))
        mesh.z_lines_m=tuple(float(v) for v in [-.005,-.0006,-.0004,-.0002,0.,.005])
        with self.assertRaisesRegex(ConfigurationError,'required Z sampling line'):
            pcb_field_layout(self.geometry,mesh,self.settings,(1.5e9,),
                mode='copper_surfaces',surface_probe_offset_m=COPPER_PROBE_OFFSET_M)

    def test_mask_applies_only_to_real_copper_footprint(self):
        x=np.array([-.001,0.,.001])
        y=np.array([-.001,0.,.001])
        m=copper_surface_mask((x,y,np.array([10e-6])),self.geometry,'top')
        self.assertEqual(m.shape,(3,3,1))
        self.assertEqual(m[1,1,0],0)
        self.assertEqual(int(m.sum()),8)

    def test_separate_field_only_html_without_port_impedance_sections(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'fields';folder.mkdir()
            plane=dict(name='copper_top_top',measurement='copper_surface',
                       copper_layer_role='top',copper_face='top',
                       copper_z_m=0.,actual_position_m=10e-6,offset_m=10e-6)
            (folder/'metadata.json').write_text(json.dumps(dict(mode='copper_surfaces',
                planes=[plane],frequency_hz=[1.5e9])),encoding='utf-8')
            x=np.array([-.5e-3,0.,.5e-3])
            a=np.ones((1,3,3,3,1),dtype=complex)
            np.savez_compressed(folder/(plane['name']+'.npz'),
                x_m=x,y_m=x,z_m=np.array([10e-6]),frequency_hz=np.array([1.5e9]),
                E_v_per_m=a,H_a_per_m=a,K_proxy_a_per_m=a,mask=np.zeros((3,3,1),dtype=np.uint8))
            html=render_copper_surface_report(dict(root=root,run_id='surface_001',
                summary={'field_mode':'copper_surfaces','note':'unverified'}))
            self.assertIn('TOP',html.upper())
            self.assertIn('K_face',html)
            self.assertIn('data:image/png;base64,',html)
            self.assertNotIn('Impedancja i dopasowanie',html)
            self.assertNotIn('S11',html)
            self.assertIn('Zoom:',html)


if __name__=='__main__':
    unittest.main()
