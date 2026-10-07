"""Exact axis permutations apply to the entire PCB, including PTH and holes."""
from dataclasses import replace
from math import cos,sin,radians
import unittest
from unittest.mock import patch
from antenna_lab.pcb.model import BoardOutline,Substrate,PcbGeometry,PcbPort,CopperPolygon,CopperLayer,DielectricLayer,PcbDrill
from antenna_lab.pcb.transform import normalize_port_orientation,inverse_transform_geometry,_map_xy
from antenna_lab.solvers.pcb_mesh import make_pcb_mesh_anchor_plan

TOL_M=1e-14


def geometry():
    # Binary-exact coordinates isolate trig residue from midpoint rounding.
    outline=BoardOutline(((-.03125,-.03125),(.03125,-.03125),(.03125,.03125),(-.03125,.03125)))
    left=((-0.025,-.02),(-.00390625,-.02),(-.00390625,.02),(-.025,.02))
    right=tuple((-x,y) for x,y in left)
    hole=((-0.022,-.018),(-.020,-.018),(-.020,-.016),(-.022,-.016))
    copper=[CopperPolygon('left',left,0,holes_xy_m=(hole,)),CopperPolygon('right',right,0),
            CopperPolygon('bottom',outline.vertices_xy_m,-.0016,'bottom')]
    layers=tuple(CopperLayer(role,z,'pec',35e-6,58e6,'test') for role,z in [('top',0),('bottom',-.0016)])
    d=DielectricLayer(outline,-.0016,0,4.3,.018)
    return PcbGeometry('pcb',outline,copper,Substrate(outline,-.0016,0,4.3,.018),
        PcbPort('port',(-.00390625,0),(.00390625,0),.002),dielectric_layers=(d,),copper_layers=layers,
        drills=(PcbDrill('via',-.015625,0,.0003,True,'PTH','T01','test',25e-6,.000175,('top','bottom')),))


def all_xy(g):
    return [*g.outline.vertices_xy_m,*g.substrate.outline.vertices_xy_m,
        *(v for d in g.dielectrics for v in d.outline.vertices_xy_m),
        *(v for c in g.copper for v in c.vertices_xy_m),
        *(v for c in g.copper for h in c.holes_xy_m for v in h),
        g.port.negative_xy_m,g.port.positive_xy_m,*((d.x_m,d.y_m) for d in g.drills)]


class OrthogonalTests(unittest.TestCase):
    def test_four_directions_exact_coefficients_and_inverse(self):
        for c,s in ((1,0),(-1,0),(0,1),(0,-1)):
            with self.subTest(c=c,s=s):
                source=_map_xy(geometry(),lambda p:(c*p[0]-s*p[1]+.125,s*p[0]+c*p[1]+.25))
                before=source.as_dict()
                # Neither forward nor inverse may obtain coefficients from trig.
                with patch('antenna_lab.pcb.transform.cos',side_effect=AssertionError('trig')),patch('antenna_lab.pcb.transform.sin',side_effect=AssertionError('trig')):
                    normalized,t=normalize_port_orientation(source)
                    restored=inverse_transform_geometry(normalized,t)
                self.assertTrue(t.exact_orthogonal)
                self.assertEqual(normalized.drills[0].y_m,0.)
                n,p=normalized.port.negative_xy_m,normalized.port.positive_xy_m
                self.assertEqual(((n[0]+p[0])/2,(n[1]+p[1])/2),(0.,0.))
                self.assertEqual((n,p),((-.00390625,0.),(.00390625,0.)))
                plan=make_pcb_mesh_anchor_plan(normalized)
                self.assertEqual(plan.y_required_m.count(0.),1)
                for a,b in zip(all_xy(source),all_xy(restored)):
                    for x,y in zip(a,b):self.assertAlmostEqual(x,y,delta=TOL_M)
                # Same rigid map applies to outline, every hole, dielectric and drill.
                for a,b in zip(all_xy(geometry()),all_xy(normalized)):
                    for x,y in zip(a,b):self.assertAlmostEqual(x,y,delta=TOL_M)
                self.assertEqual(source.as_dict(),before)

    def test_oblique_remains_generic_including_near_quarter_turn(self):
        for degrees in (37,89.999999999):
            c,s=cos(radians(degrees)),sin(radians(degrees))
            source=_map_xy(geometry(),lambda p:(c*p[0]-s*p[1],s*p[0]+c*p[1]))
            with patch('antenna_lab.pcb.transform.cos',wraps=cos) as cosine,patch('antenna_lab.pcb.transform.sin',wraps=sin) as sine:
                normalized,t=normalize_port_orientation(source)
                restored=inverse_transform_geometry(normalized,t)
            self.assertFalse(t.exact_orthogonal)
            self.assertEqual(cosine.call_count,2);self.assertEqual(sine.call_count,2)
            c,s=cos(t.rotation_rad),sin(t.rotation_rad)
            for old,new in zip(all_xy(source),all_xy(normalized)):
                x,y=old[0]+t.translation_xy_m[0],old[1]+t.translation_xy_m[1]
                self.assertEqual(new,(c*x-s*y,s*x+c*y))
            for a,b in zip(all_xy(source),all_xy(restored)):
                for x,y in zip(a,b):self.assertAlmostEqual(x,y,delta=TOL_M)


if __name__=='__main__':unittest.main()
