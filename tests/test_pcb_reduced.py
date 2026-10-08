"""Reduced physics identities and fail-closed extraction; never native FDTD."""
from dataclasses import replace
from copy import deepcopy
import csv
import json
from math import pi, tan
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from shapely.geometry import LineString, box

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import (BoardOutline, CopperPolygon, CopperLayer,
    DielectricLayer, PcbGeometry, PcbPort, Substrate, PcbLumpedComponent)
from antenna_lab.solvers.reduced_pcb import (microstrip_parameters, extract_trace_sections,
    build_reduced_model, solve_network, solve_reduced_model, detect_coupled_sections)


def case(kind='straight'):
    outline=BoardOutline(((-.02,-.02),(.02,-.02),(.02,.02),(-.02,.02)))
    routes={'straight':[(.0005,0),(.0105,0)],
            'L':[(.0005,0),(.0105,0),(.0105,.01)],
            'U':[(.0005,0),(.0105,0),(.0105,.01),(.0005,.01)]}
    shape=LineString(routes[kind]).buffer(.0005,cap_style='flat',join_style='mitre')
    left=box(-.0105,-.0005,-.0005,.0005)
    def copper(id,s,role='top',z=0):return CopperPolygon(id,tuple(s.exterior.coords)[:-1],z,role)
    d=DielectricLayer(outline,-.001,0,4.3,0,'core')
    return PcbGeometry('pcb',outline,[copper('left',left),copper('right',shape),
        CopperPolygon('ground',outline.vertices_xy_m,-.001,'bottom')],
        Substrate(outline,-.001,0,4.3,0),PcbPort('src',(-.0005,0),(.0005,0),.001),
        dielectric_layers=(d,),copper_layers=(CopperLayer('top',0,'pec',35e-6,58e6,'a'),
                                             CopperLayer('bottom',-.001,'pec',35e-6,58e6,'b')))


def line(length=.02,width=.001,height=.001,er=4.3,a='in',b='out'):
    return dict(node_a=a,node_b=b,length_m=length,parameters=microstrip_parameters(width,height,er))


class ReducedTests(unittest.TestCase):
    def test_straight_L_U_extraction_lengths_and_determinism(self):
        for kind,length,count in [('straight',.02,2),('L',.03,3),('U',.04,4)]:
            with self.subTest(kind=kind):
                g=case(kind);before=g.as_dict();sections,_=extract_trace_sections(g)
                self.assertEqual(len(sections),count)
                self.assertAlmostEqual(sum(s.length_m for s in sections),length,places=14)
                self.assertEqual(sections,extract_trace_sections(g)[0])
                g.copper.reverse()
                self.assertEqual(sections,extract_trace_sections(g)[0])
                g.copper.reverse();self.assertEqual(before,g.as_dict())

    def test_branch_and_unresolved_pad_fail(self):
        for shape in (LineString(((.0005,0),(.01,0))).buffer(.0005,cap_style='flat').union(
                      box(.006,-.005,.007,.005)), box(.0005,-.0005,.0015,.0005)):
            g=case();g.copper[1]=replace(g.copper[1],vertices_xy_m=tuple(shape.exterior.coords)[:-1])
            with self.assertRaisesRegex(ConfigurationError,'branched|unresolved|ambiguous'):
                extract_trace_sections(g)

    def test_width_height_epsilon_physical_direction(self):
        base=microstrip_parameters(.001,.001,4.3)
        self.assertLess(microstrip_parameters(.002,.001,4.3)['z0_ohm'],base['z0_ohm'])
        self.assertGreater(microstrip_parameters(.001,.002,4.3)['z0_ohm'],base['z0_ohm'])
        self.assertLess(microstrip_parameters(.001,.001,8)['velocity_m_s'],base['velocity_m_s'])
        self.assertAlmostEqual(base['z0_ohm']**2,base['inductance_h_m']/base['capacitance_f_m'])
        vacuum=microstrip_parameters(.001,.001,1.)
        self.assertEqual(vacuum['effective_epsilon_r'],1.)
        self.assertEqual(vacuum['velocity_m_s'],299792458.)
        self.assertGreater(vacuum['z0_ohm'],base['z0_ohm'])

    def test_invalid_dimensions(self):
        for w,h,e in [(0,.001,4),(.001,0,4),(.001,.001,.5),(float('nan'),.001,4),(.001,.001,129)]:
            with self.assertRaises(ConfigurationError):microstrip_parameters(w,h,e)
        with self.assertRaises(ConfigurationError):
            solve_network(['in','out'],[line(length=0)],[],['ground','in'],1e9)

    def test_line_open_short_load_identities_and_phase(self):
        f=1e9;length=.02;s=line(length);z0=s['parameters']['z0_ohm'];v=s['parameters']['velocity_m_s']
        t=tan(2*pi*f*length/v)
        actual=solve_network(['in','out'],[s],[],['ground','in'],f)
        self.assertAlmostEqual(abs(actual-(-1j*z0/t)),0,places=10)
        short=solve_network(['in'],[line(length,b='ground')],[],['ground','in'],f)
        self.assertAlmostEqual(abs(short-1j*z0*t),0,places=10)
        for r in (z0,100):
            load=dict(kind='R',value_si=r,node_a='out',node_b='ground')
            z=solve_network(['in','out'],[s],[load],['ground','in'],f)
            expected=z0*(r+1j*z0*t)/(z0+1j*r*t)
            self.assertAlmostEqual(abs(z-expected),0,places=10)
            if r==z0:self.assertLess(abs((z-z0)/(z+z0)),1e-12)
        longer=solve_network(['in','out'],[line(.03)],[],['ground','in'],f)
        self.assertGreater(abs(longer-actual),1)

    def test_halfwave_stamp_is_not_artificially_singular(self):
        s=line();s['length_m']=s['parameters']['velocity_m_s']/(2e9)
        z=solve_network(['in','out'],[s],[dict(kind='R',value_si=75,node_a='out',node_b='ground')],['ground','in'],1e9)
        self.assertAlmostEqual(abs(z-75),0,places=10)

    def test_rlc_and_differential_source(self):
        f=1e9;w=2*pi*f
        for kind,value,expected in [('R',25,25),('L',1e-9,1j*w*1e-9),('C',1e-12,1/(1j*w*1e-12))]:
            z=solve_network(['p'],[],[dict(kind=kind,value_si=value,node_a='p',node_b='ground')],['ground','p'],f)
            self.assertAlmostEqual(abs(z-expected),0,places=9)
        parts=[dict(kind='R',value_si=20,node_a='a',node_b='ground'),
               dict(kind='R',value_si=30,node_a='b',node_b='ground')]
        self.assertAlmostEqual(solve_network(['a','b'],[],parts,['a','b'],f),50)
        self.assertAlmostEqual(solve_network(['a','b'],[],parts,['b','a'],f),50)
        with self.assertRaisesRegex(ConfigurationError,'singular'):
            solve_network(['a','b'],[],[],['a','b'],f)

    def test_ground_and_curves_fail(self):
        g=case();g.copper.pop()
        with self.assertRaises(ConfigurationError):build_reduced_model(g)
        g=case();g.copper[-1]=replace(g.copper[-1],holes_xy_m=(((.015,.015),(.016,.015),(.016,.016),(.015,.016)),))
        with self.assertRaisesRegex(ConfigurationError,'ground'):build_reduced_model(g)
        g=case();g.copper[1]=replace(g.copper[1],vertices_xy_m=((.0005,-.0005),(.01,-.0005),(.012,.001),(.0005,.0005)))
        with self.assertRaisesRegex(ConfigurationError,'curved/oblique'):build_reduced_model(g)

    def test_parallel_runs_detected_not_silently_ignored(self):
        model=build_reduced_model(case('U'))
        self.assertEqual(len(model['coupled_sections']),1)
        self.assertAlmostEqual(model['coupled_sections'][0]['physical_gap_m'],.009)
        self.assertEqual(model['unsupported_status'],'coupling_required')
        with self.assertRaisesRegex(ConfigurationError,'coupling is NOT silently omitted'):
            solve_reduced_model(model,[1e9])

    def test_model_solve_and_strict_json(self):
        g=case();before=g.as_dict();model=build_reduced_model(g)
        result=solve_reduced_model(model,[1e9,1.1e9])
        self.assertEqual(g.as_dict(),before)
        self.assertEqual(model['validation_status'],'approximate')
        self.assertIn('dielectric_loss',model['omitted_effects'])
        self.assertEqual(result[0]['swr'],None) # infinite for an open lossless network
        json.dumps(dict(model=model,results=result),allow_nan=False)

    def test_component_mapping_and_gap_audit(self):
        g=case();g.copper[1]=replace(g.copper[1],vertices_xy_m=tuple(box(.0005,-.0005,.0045,.0005).exterior.coords)[:-1])
        g.copper.append(CopperPolygon('tail',tuple(box(.0055,-.0005,.0105,.0005).exterior.coords)[:-1],0))
        g.components=(PcbLumpedComponent('R1','R',50,'50 ohm','a','b',(.004,0),(.006,0),'top','x',
            (.0045,0),(.0055,0),((.0045,-.0005),(.0055,-.0005),(.0055,.0005),(.0045,.0005)),'e','f'),)
        m=build_reduced_model(g)
        self.assertEqual(m['lumped_components'][0]['value_si'],50)
        self.assertEqual(len(solve_reduced_model(m,[1e9])),1)
        # An otherwise valid port endpoint is insufficient: wide face must contact.
        g.port=replace(g.port,width_m=.002)
        with self.assertRaisesRegex(ConfigurationError,'contact'):build_reduced_model(g)

    def test_cli_artifacts_without_native_or_mesh_or_prompt(self):
        from antenna_lab.pcb.reduced_control import main
        g=case()
        with TemporaryDirectory() as tmp:
            root=Path(tmp);inp=root/'gerbers';inp.mkdir();out=root/'result'
            with patch('antenna_lab.pcb.bundle.load_bundle_geometry',return_value=(None,g,{'files':[]})), \
                 patch('antenna_lab.solvers.pcb_mesh.make_pcb_domain_mesh',side_effect=AssertionError('FDTD mesh forbidden')), \
                 patch('builtins.input',side_effect=AssertionError('prompt forbidden')):
                status=main([str(inp),'--output',str(out),'--center-mhz','2000','--cutoff-mhz','1900',
                             '--sweep-start-mhz','1500','--sweep-stop-mhz','2500','--sweep-step-mhz','10'])
            self.assertEqual(status,0)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['solver_model'],'reduced_quasi_tem')
            self.assertEqual(summary['native_fdtd_runs'],0)
            with (out/'impedance.csv').open() as table:
                self.assertEqual(len(list(csv.DictReader(table))),101)
            self.assertTrue((out/'reduced_model.json').is_file())
            self.assertFalse((out/'native').exists())

    def test_cli_frequency_conflicts_and_band(self):
        from antenna_lab.pcb.reduced_control import main
        for args in [('--sweep-start-mhz','1500'),
                     ('--sweep-start-mhz','1500','--sweep-stop-mhz','2500','--sweep-step-mhz','10','--frequencies-mhz','1500'),
                     ('--frequencies-mhz','2500')]:
            with patch('antenna_lab.pcb.bundle.load_bundle_geometry',side_effect=AssertionError('invalid band must fail first')):
                self.assertEqual(main(['missing',*args]),1)

    def test_import_does_not_load_native_or_fullwave_adapter(self):
        import os, subprocess, sys
        check = "import antenna_lab.pcb.reduced_control; import sys; assert not any(n in sys.modules for n in ('openEMS','CSXCAD','antenna_lab.solvers.openems_pcb','antenna_lab.solvers.openems'))"
        subprocess.run([sys.executable,'-c',check],check=True,env=os.environ.copy())

    def test_cli_unsupported_saves_failure_not_impedance(self):
        from antenna_lab.pcb.reduced_control import run_reduced
        with TemporaryDirectory() as tmp:
            inp=Path(tmp)/'input';inp.mkdir();out=Path(tmp)/'out'
            with patch('antenna_lab.pcb.bundle.load_bundle_geometry',return_value=(None,case('U'),{})):
                with self.assertRaisesRegex(ConfigurationError,'coupling'):
                    run_reduced(inp,out)
            self.assertFalse((out/'impedance.csv').exists())
            self.assertEqual(json.loads((out/'summary.json').read_text())['status'],'failed')
            self.assertTrue((out/'reduced_model.json').exists())


if __name__=='__main__':unittest.main()
