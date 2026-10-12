"""Physical ground-PTH classification in FAST only; no native FDTD."""
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from shapely.geometry import box
from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import CopperPolygon, PcbDrill, PcbLumpedComponent, CopperLayer
from antenna_lab.pcb.validation import validate_pcb_geometry
from antenna_lab.solvers.reduced_pcb import build_reduced_model, solve_reduced_model
from test_pcb_reduced import case


def via(id='v1', x=-.005, y=0):
    diameter=.0003; plating=.00003
    return PcbDrill(id,x,y,diameter,True,'PTH','T01','a'*64,
                    plating,diameter/2+plating,('top','bottom'))


def rectangle(id,x0,y0,x1,y1):
    return CopperPolygon(id,tuple(box(x0,y0,x1,y1).exterior.coords)[:-1],0,'top')


def grounded(kind='straight'):
    g=case(kind);g.drills=(via(),)
    return g


def loaded(kind='R', value=50):
    g=grounded()
    g.copper.append(rectangle('load_ground',.0115,-.0005,.0145,.0005))
    g.drills+=(via('v2',.013,0),)
    g.components=(PcbLumpedComponent('part',kind,value,str(value),'a','b',(.01,0),(.012,0),
        'top','x',(.0105,0),(.0115,0),
        ((.0105,-.0005),(.0115,-.0005),(.0115,.0005),(.0105,.0005)),'e','f'),)
    return g


def meander():
    g=grounded('U')
    g.copper.append(rectangle('load_ground',-.0105,.0095,-.0005,.0105))
    g.drills+=(via('v2',-.005,.01),)
    return g


class GroundViaTests(unittest.TestCase):
    def test_one_ground_via_excluded_source_mapping_metadata_no_mutation(self):
        g=grounded();before=g.as_dict();m=build_reduced_model(g)
        self.assertEqual(m['ground_connected_top_conductors'],['left'])
        self.assertEqual(m['active_top_signal_conductors'],['right'])
        self.assertEqual([s['owner'] for s in m['line_sections']],['right'])
        self.assertEqual(m['source_port_nodes'][0],'ground')
        self.assertNotEqual(m['source_port_nodes'][1],'ground')
        v=m['ground_vias'][0]
        self.assertEqual(v['contacted_top_conductor'],'left')
        self.assertEqual(v['contacted_bottom_conductor'],'ground')
        self.assertEqual(v['treatment'],'ideal_ground_connection')
        self.assertEqual(v['centre_xy_m'],[-.005,0])
        self.assertEqual(v['equivalent_outer_radius_m'],g.drills[0].equivalent_outer_radius_m)
        self.assertIn('via_inductance',m['omitted_effects'])
        self.assertIn('via_barrel_loss',m['omitted_effects'])
        self.assertEqual(m,build_reduced_model(g));self.assertEqual(before,g.as_dict())
        json.dumps(m,allow_nan=False)
        self.assertEqual(len(solve_reduced_model(m,[1e9])),1)

    def test_ground_square_pad_needs_no_transmission_line_centerline(self):
        g=grounded();g.copper[0]=rectangle('left',-.0025,-.001,-.0005,.001)
        g.drills=(via(x=-.0015),)
        self.assertEqual(len(build_reduced_model(g)['line_sections']),1)

    def test_contact_uses_disk_not_center_containment(self):
        g=grounded();g.drills=(via(y=.0006),) # center outside copper, disk touches
        self.assertEqual(build_reduced_model(g)['ground_connected_top_conductors'],['left'])

    def test_two_ground_regions_and_each_rlc_terminal(self):
        for kind,value in [('R',50),('L',1e-9),('C',1e-12)]:
            with self.subTest(kind=kind):
                g=loaded(kind,value);m=build_reduced_model(g)
                self.assertEqual(m['ground_connected_top_conductors'],['left','load_ground'])
                self.assertEqual(len(m['ground_vias']),2)
                self.assertEqual(m['lumped_components'][0]['node_b'],'ground')
                self.assertNotEqual(m['lumped_components'][0]['node_a'],'ground')
                self.assertEqual(len(m['line_sections']),1)
                self.assertEqual(len(solve_reduced_model(m,[1e9])),1)
                g.drills=tuple(reversed(g.drills))
                self.assertEqual(m,build_reduced_model(g))

    def test_both_source_terminals_ground_rejected(self):
        g=grounded();g.drills+=(via('v2',.005,0),)
        with self.assertRaisesRegex(ConfigurationError,'source.*shorted to ground'):
            build_reduced_model(g)

    def test_both_component_terminals_ground_rejected(self):
        g=meander()
        g.components=(PcbLumpedComponent('R1','R',50,'50','a','b',(-.005,0),(-.005,.01),
            'top','y',(-.005,.0005),(-.005,.0095),
            ((-.0055,.0005),(-.0045,.0005),(-.0045,.0095),(-.0055,.0095)),'e','f'),)
        with self.assertRaisesRegex(ConfigurationError,'both terminals map to ground'):
            build_reduced_model(g)

    def test_no_bottom_contact_is_not_inferred_from_metadata(self):
        g=grounded()
        g.copper[-1]=replace(g.copper[-1],holes_xy_m=(
            ((-.006,-.001),(-.004,-.001),(-.004,.001),(-.006,.001)),))
        with self.assertRaises(ConfigurationError):build_reduced_model(g)

    def test_ambiguous_physical_top_contact_despite_valid_layer_labels(self):
        g=grounded();g.drills=(via(x=-.006,y=.0006),)
        g.copper.append(rectangle('other',-.007,.0007,-.005,.0017))
        validate_pcb_geometry(g) # same top/bottom role list, two top owners
        with self.assertRaisesRegex(ConfigurationError,'ambiguous/unresolved top ownership'):
            build_reduced_model(g)

    def test_inner_layer_fail_closed(self):
        g=grounded()
        g.copper.append(CopperPolygon('inner',g.outline.vertices_xy_m,-.0005,'inner1'))
        upper=replace(g.dielectrics[0],z_min_m=-.0005,name='upper')
        lower=replace(g.dielectrics[0],z_max_m=-.0005,name='lower')
        g.dielectric_layers=(upper,lower)
        g.substrate=replace(g.substrate,z_min_m=-.0005)
        g.copper_layers=(g.copper_layers[0],CopperLayer('inner1',-.0005,'pec',35e-6,58e6,'i'),g.copper_layers[1])
        g.drills=(replace(g.drills[0],connected_layer_roles=('top','inner1','bottom')),)
        validate_pcb_geometry(g)
        with self.assertRaisesRegex(ConfigurationError,'one homogeneous dielectric'):
            build_reduced_model(g)

    def test_npth_rejected(self):
        g=grounded();g.drills=(PcbDrill('hole',-.005,0,.0003,False,'NPTH','T01','b'*64),)
        validate_pcb_geometry(g)
        with self.assertRaisesRegex(ConfigurationError,'NPTH unsupported'):build_reduced_model(g)

    def test_invalid_radius_rejected(self):
        for r in (0,-1,None,float('nan'),float('inf')):
            with self.subTest(radius=r):
                g=grounded();g.drills=(replace(g.drills[0],equivalent_outer_radius_m=r),)
                with self.assertRaises(ConfigurationError):build_reduced_model(g)

    def test_active_signal_still_needs_exact_centerline_contact(self):
        g=grounded();g.port=replace(g.port,positive_xy_m=(.0005,.0001))
        with self.assertRaises(ConfigurationError):build_reduced_model(g)

    def test_coupling_is_next_blocker_with_two_ground_vias(self):
        m=build_reduced_model(meander())
        self.assertEqual(len(m['line_sections']),3)
        self.assertAlmostEqual(m['total_centerline_length_m'],.03)
        self.assertEqual(len(m['ground_vias']),2)
        self.assertEqual(len(m['ground_connected_top_conductors']),2)
        self.assertEqual(len(m['coupled_sections']),1)
        self.assertEqual(m['unsupported_status'],'coupling_required')
        with self.assertRaisesRegex(ConfigurationError,'coupling is NOT silently omitted'):
            solve_reduced_model(m,[1e9])

    def test_cli_preserves_ground_diagnostics_when_coupling_stops_solve(self):
        from antenna_lab.pcb.reduced_control import run_reduced
        with TemporaryDirectory() as tmp:
            inp=Path(tmp)/'input';inp.mkdir();out=Path(tmp)/'out';console=StringIO()
            with patch('antenna_lab.pcb.bundle.load_bundle_geometry',return_value=(None,meander(),{})), \
                 patch('antenna_lab.solvers.pcb_mesh.make_pcb_domain_mesh',side_effect=AssertionError('no FDTD mesh')), \
                 redirect_stdout(console):
                with self.assertRaisesRegex(ConfigurationError,'coupling'):
                    run_reduced(inp,out)
            self.assertIn('Ground vias: 2',console.getvalue())
            self.assertIn('Ground-connected top conductors: 2',console.getvalue())
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['unsupported_status'],'coupling_required')
            self.assertEqual(summary['native_fdtd_runs'],0)
            self.assertEqual(summary['extracted_section_count'],3)
            self.assertEqual(len(summary['ground_vias']),2)
            self.assertFalse((out/'impedance.csv').exists())


if __name__=='__main__':unittest.main()
