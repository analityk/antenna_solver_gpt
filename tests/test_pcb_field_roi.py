"""Report-only ROI on deterministic phasors: no native solver or new mesh."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from antenna_lab.visualization.field_roi import FieldCrop,field_roi,phase_peak,add_crop_arguments,crop_arguments
from antenna_lab.visualization.pcb_fields import viewer_payload,pcb_phase_figure,pcb_field_section


class RoiTests(unittest.TestCase):
    def fixture(self):
        axis=np.linspace(-20,20,81)
        e=np.zeros((81,81),complex);h=e.copy()
        e[38:43,38:43]=1j;h[45:48,47:50]=.00001
        view=dict(u=axis,v=axis,eu=e,ev=e*.5,magnetic=h,
                  e_limit=1.,h_limit=1e-5,vector_limit=1.2,frequency_hz=2e9,
                  horizontal='x',vertical='y',h_component='z')
        paths=[dict(points=[[-12,-12],[12,-12],[12,12],[-12,12]],color='gray',role='board'),
               dict(points=[[-3,-2],[-1,-2],[-1,1],[-3,1]],color='blue',role='geometry')]
        return view,paths

    def test_local_roi_contains_geometry_and_both_unit_independent_fields(self):
        view,paths=self.fixture();before=deepcopy(view)
        roi=field_roi(view,paths)
        self.assertLess(roi['u'][1]-roi['u'][0],40)
        self.assertLess(roi['v'][1]-roi['v'][0],40)
        self.assertLessEqual(roi['u'][0],-4)
        self.assertGreaterEqual(roi['u'][1],5.5) # weak H is significant in its own units
        for key in ('eu','ev','magnetic'):np.testing.assert_array_equal(view[key],before[key])

    def test_continuous_phase_max_including_imaginary_and_elliptical_fields(self):
        self.assertAlmostEqual(float(phase_peak([np.array(1j)])),1.)
        self.assertAlmostEqual(float(phase_peak([np.array(1.),np.array(1j)])),1.)
        view,paths=self.fixture();expected=field_roi(view,paths)
        for phase in (15,30,90,180,270):
            other=dict(view,**{k:view[k]*np.exp(1j*np.deg2rad(phase)) for k in ('eu','ev','magnetic')})
            self.assertEqual(field_roi(other,paths),expected)

    def test_same_roi_png_html_e_h_and_every_phase_all_planes(self):
        view,paths=self.fixture()
        for plane,axes in (('xy_air',('x','y')),('xz_feed',('x','z')),('yz_feed',('y','z'))):
            current=dict(view,horizontal=axes[0],vertical=axes[1])
            roi=field_roi(current,paths)
            a=viewer_payload(current,paths,[0,90,180],roi=roi)
            b=viewer_payload(current,paths,list(range(0,360,15)),roi=roi)
            self.assertEqual(a['roi'],b['roi'])
            fig=pcb_phase_figure(current,paths,{'name':plane},phases=(0,90),roi=roi)
            for axis in fig.axes[:4]:
                self.assertEqual(tuple(axis.get_xlim()),tuple(roi['u']))
                self.assertEqual(tuple(axis.get_ylim()),tuple(roi['v']))
            self.assertEqual((a['u'][0],a['u'][-1]),tuple(roi['u']))
            self.assertEqual((a['v'][0],a['v'][-1]),tuple(roi['v']))
            fig.clear();json.dumps(a,allow_nan=False)

    def test_domain_board_threshold_margin_and_boundary_clipping(self):
        view,paths=self.fixture()
        domain=field_roi(view,paths,FieldCrop('domain'))
        self.assertEqual(domain['u'],(-20.,20.));self.assertEqual(domain['v'],(-20.,20.))
        board=field_roi(view,paths,FieldCrop('board'))
        self.assertEqual(board['u'],(-13.,13.))
        view['eu'][1,1]=1e-3
        strict=field_roi(view,paths,FieldCrop('active',-40,0))
        relaxed=field_roi(view,paths,FieldCrop('active',-80,0))
        self.assertLess(relaxed['u'][0],strict['u'][0])
        huge=field_roi(view,paths,FieldCrop('active',-40,100))
        self.assertEqual(huge['u'],domain['u'])

    def test_empty_zero_nan_fallbacks_and_single_active_sample(self):
        view,paths=self.fixture()
        for value in (0.,complex(float('nan'))):
            empty=dict(view,**{k:np.full_like(view[k],value) for k in ('eu','ev','magnetic')})
            roi=field_roi(empty,paths,FieldCrop('active'))
            self.assertEqual(roi['reason'],'fallback_geometry')
            self.assertEqual(field_roi(empty,paths[:1],FieldCrop('active'))['reason'],'fallback_board')
            self.assertEqual(field_roi(empty,[],FieldCrop('active'))['reason'],'fallback_domain')
        empty['eu'][40,40]=1.
        empty['ev'][40,40]=0.
        roi=field_roi(empty,[],FieldCrop('active',-40,0))
        self.assertLess(roi['u'][0],roi['u'][1]);self.assertLess(roi['v'][0],roi['v'][1])

    def test_uniform_activity_is_not_artificially_cropped(self):
        view,paths=self.fixture();view['eu'][:]=1
        self.assertEqual(field_roi(view,paths)['u'],(-20.,20.))

    def test_options_validate_and_parse(self):
        parser=argparse.ArgumentParser();add_crop_arguments(parser)
        self.assertEqual(crop_arguments(parser.parse_args([])),dict(field_view='active+geometry',field_crop_threshold_db=-40.,field_crop_margin_mm=1.))
        for kwargs in ({'mode':'bad'},{'threshold_db':1},{'threshold_db':float('nan')},{'margin_mm':-1},{'margin_mm':float('inf')}):
            with self.assertRaises(ValueError):FieldCrop(**kwargs)

    def test_report_section_uses_per_frequency_roi_and_records_policy(self):
        view,paths=self.fixture()
        planes=[dict(name='xy_air',requested_policy='test',requested_position_m=.001,actual_position_m=.001)]
        metadata=dict(reference_voltage_v=1.,array_order='frequency,component_xyz,x,y,z',planes=planes,frequency_hz=[1e9,2e9])
        second=deepcopy(view);second['eu'][:]=1.
        with patch('antenna_lab.visualization.pcb_fields.load_plane',return_value={'frequency_hz':[1e9,2e9]}), \
             patch('antenna_lab.visualization.pcb_fields.overlays',return_value=paths), \
             patch('antenna_lab.visualization.pcb_fields.view_fields',side_effect=[view,second]):
            html=pcb_field_section({'root':Path('.'),'geometry':{}},metadata,lambda *a:'PNG',None,30)
        self.assertEqual(html.count('ROI: active+geometry'),2)
        self.assertIn('"roi":',html);self.assertIn('ctx.clip()',html)
        self.assertNotIn('<script src=',html)

    def test_both_public_clis_forward_report_only_options(self):
        from tempfile import TemporaryDirectory
        from antenna_lab.cli import main
        from antenna_lab.pcb.postprocess import main as replay
        with TemporaryDirectory() as tmp:
            options=['--field-view','domain','--field-crop-threshold-db','-25','--field-crop-margin-mm','2.5']
            with patch('antenna_lab.visualization.report.generate_report',return_value=Path(tmp)/'report.html') as generate:
                self.assertEqual(main(['report',tmp,*options]),0)
            for k,v in dict(field_view='domain',field_crop_threshold_db=-25.,field_crop_margin_mm=2.5).items():
                self.assertEqual(generate.call_args.kwargs[k],v)
            with patch('antenna_lab.pcb.postprocess.recover_run',return_value=(Path(tmp),{'status':'finished_unverified'})) as recover:
                self.assertEqual(replay(['--run-dir',tmp,*options]),0)
            self.assertEqual(recover.call_args.kwargs['report_options'],dict(field_view='domain',field_crop_threshold_db=-25.,field_crop_margin_mm=2.5))
