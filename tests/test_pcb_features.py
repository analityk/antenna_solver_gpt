"""Modeled copper dimensions must survive meshing; no native FDTD."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from shapely.geometry import Point
from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import CopperPolygon
from antenna_lab.pcb.geometry_resolution import apply_geometry_resolution
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh, make_gerber_mesh_anchor_plan
from antenna_lab.solvers.pcb_features import audit_copper_mesh, copper_features, represented_coordinate
from test_pcb_model import fixture


WIDTHS = (.376, .384, .250, .380)


def feature_fixture(width_mm, hole=False):
    g,_=normalize_port_orientation(fixture())
    # Same source centerline for every width. Its 1-um offset deliberately
    # avoids half-tick ties at the 0.25-mm strip's two independent vertices.
    centre=.006001;lo=centre-width_mm*.001/2;hi=centre+width_mm*.001/2
    if hole:
        outer=((-0.008,.004),(.008,.004),(.008,.009),(-.008,.009))
        holes=(((-.005,lo),(.005,lo),(.005,hi),(-.005,hi)),)
    else:
        # Thin trace INSIDE one connected polygon with large pads at both ends:
        # whole-conductor bounding box has no information about the trace width.
        outer=((-0.008,centre-.001),(-.006,centre-.001),(-.006,lo),(.006,lo),
               (.006,centre-.001),(.008,centre-.001),(.008,centre+.001),
               (.006,centre+.001),(.006,hi),(-.006,hi),(-.006,centre+.001),(-.008,centre+.001))
        holes=()
    g.copper.append(CopperPolygon('feature',outer,0.,holes_xy_m=holes))
    return g,lo,hi


class CopperFeatureTests(unittest.TestCase):
    def test_strip_and_hole_widths_after_projection_in_every_quality(self):
        for hole in (False,True):
            for quality in ('preview','design','verify'):
                records=[];z_axes=[]
                s,_=gerber_quality_settings(quality)
                for width in WIDTHS:
                    with self.subTest(hole=hole,quality=quality,width=width):
                        raw,lo,hi=feature_fixture(width,hole);before=raw.as_dict()
                        g,_,_=apply_geometry_resolution(raw,PcbGrid())
                        c=g.copper[-1]
                        ring=c.holes_xy_m[0] if hole else c.vertices_xy_m
                        a,b=(min(y for x,y in ring),max(y for x,y in ring)) if hole else (ring[2][1],ring[8][1])
                        expected=.00025 if width==.250 else .00038
                        self.assertAlmostEqual(b-a,expected,delta=1e-17)
                        mesh=make_pcb_domain_mesh(g,s,gerber_quality=quality)
                        audit=audit_copper_mesh(g,mesh,source_geometry=raw)
                        self.assertEqual(audit['status'],'PASS')
                        self.assertTrue(audit['source_boundaries'])
                        dimensions=[r for r in audit['sections'] if r['copper_id']=='feature'
                                    and r['axis']=='y' and r['kind']==('clearance' if hole else 'copper')
                                    and abs(r['modeled_width_m']-expected)<1e-17]
                        self.assertTrue(dimensions)
                        self.assertTrue(all(r['solver_facing_width_m']==r['modeled_width_m'] for r in dimensions))
                        self.assertTrue(any(abs(r['source_width_m']-width*.001)<1e-17 for r in dimensions))
                        relevant=[r for r in audit['boundaries'] if r['copper_id']=='feature' and r['axis']=='y']
                        for boundary in (a,b):
                            rows=[r for r in relevant if r['coordinate_m']==boundary]
                            self.assertTrue(rows)
                            self.assertTrue(all(r['preserved'] and r['retained_mesh_coordinate_m']==boundary for r in rows))
                            self.assertIn(boundary,mesh.y_lines_m)
                        measured=mesh.y_lines_m[mesh.y_lines_m.index(b)]-mesh.y_lines_m[mesh.y_lines_m.index(a)]
                        self.assertEqual(measured,b-a)
                        plan,meta=make_gerber_mesh_anchor_plan(g,s,quality)
                        self.assertEqual(meta['suppressed_physical_feature_coordinates'],0)
                        self.assertEqual(meta['physical_boundary_roundoff_equivalences'],[])
                        self.assertTrue(all(r['reason']=='exact_line' for r in audit['boundaries']))
                        self.assertTrue(all(r['kind']=='bbox_midpoint' for r in meta['suppressed_noncritical_anchors']))
                        self.assertEqual(raw.as_dict(),before)
                        self.assertLess(len(mesh.x_lines_m),1000) # No global 10-um grid over air.
                        self.assertTrue(any(abs(v/1e-5-round(v/1e-5))>1e-6 for v in mesh.y_lines_m))
                        json.dumps(audit,allow_nan=False)
                        records.append((c,(a,b),measured));z_axes.append(mesh.z_lines_m)
                self.assertEqual(records[0],records[1])
                self.assertEqual(records[0],records[3])
                self.assertNotEqual(records[2][1:],records[3][1:])
                self.assertTrue(all(z==z_axes[0] for z in z_axes))

    def test_missing_internal_run_or_hole_line_is_fatal(self):
        for hole in (False,True):
            raw,_,_=feature_fixture(.25,hole)
            g,_,_=apply_geometry_resolution(raw,PcbGrid())
            s,_=gerber_quality_settings('preview');mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
            c=g.copper[-1];boundary=c.holes_xy_m[0][0][1] if hole else c.vertices_xy_m[2][1]
            broken=replace(mesh,y_lines_m=tuple(v for v in mesh.y_lines_m if v!=boundary))
            with self.assertRaisesRegex(ConfigurationError,'feature.*missing exact y physical boundary'):
                audit_copper_mesh(g,broken)

    def test_fidelity_audit_is_in_production_mesh_path_and_cost_fails_closed(self):
        raw,_,_=feature_fixture(.25);g,_,_=apply_geometry_resolution(raw,PcbGrid())
        s,_=gerber_quality_settings('preview')
        with patch('antenna_lab.solvers.pcb_features.audit_copper_mesh',side_effect=ConfigurationError('audit sentinel')):
            with self.assertRaisesRegex(ConfigurationError,'audit sentinel'):
                make_pcb_domain_mesh(g,s,gerber_quality='preview')
        with self.assertRaisesRegex(ConfigurationError,'max_cells'):
            make_pcb_domain_mesh(g,replace(s,max_cells=10),gerber_quality='preview')

    def test_roundoff_only_equivalence_never_hides_a_modeled_feature(self):
        value=-.00043200500000000093;line=-.000432005
        self.assertEqual(represented_coordinate(value,(line,),.025),line)
        for delta in (1e-5,1e-7,1e-10):
            self.assertIsNone(represented_coordinate(line+delta,(line,),.025))
        # Even at huge coordinate magnitudes the ULP allowance may not exceed
        # the existing geometry tolerance and erase a physical 100-nm feature.
        self.assertIsNone(represented_coordinate(1e8+1e-7,(1e8,),1e8))

    def test_curved_antipad_and_explicit_audit_budget(self):
        g,_=normalize_port_orientation(fixture());s,_=gerber_quality_settings('preview')
        hole=tuple(Point(0,.006).buffer(.001,quad_segs=32).exterior.coords)[:-1]
        plane=CopperPolygon('plane',((-.008,.004),(.008,.004),(.008,.009),(-.008,.009)),
                            0.,holes_xy_m=(hole,))
        g=replace(g,copper=g.copper+[plane]);before=g.as_dict()
        mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        audit=audit_copper_mesh(g,mesh)
        item=next(r for r in audit['curved_regions'] if r['copper_id']=='plane')
        self.assertEqual(item['inner_topology'],[1,1]);self.assertEqual(item['outer_topology'],[1,1])
        with patch('antenna_lab.solvers.pcb_features.MAX_FIDELITY_CELLS',1):
            with self.assertRaisesRegex(ConfigurationError,'audit cells'):
                audit_copper_mesh(g,mesh)
        self.assertEqual(before,g.as_dict())

    def test_curves_bounded_support_and_fail_closed_on_lost_hole(self):
        g,_=normalize_port_orientation(fixture());s,_=gerber_quality_settings('preview')
        # Tessellation complexity must not imply one mesh line per vertex.
        counts=[]
        for segments in (32,128):
            disk=Point(.0075,.006).buffer(.001,quad_segs=segments)
            c=CopperPolygon('disk',tuple(disk.exterior.coords)[:-1],0.)
            curved=replace(g,copper=g.copper+[c])
            plan,meta=make_gerber_mesh_anchor_plan(curved,s,'preview')
            counts.append((len(plan.x_required_m),len(plan.y_required_m)))
            mesh=make_pcb_domain_mesh(curved,s,gerber_quality='preview')
            audit=audit_copper_mesh(curved,mesh)
            self.assertTrue(audit['curved_regions'])
            self.assertTrue(all(r['preserved'] for r in audit['curved_regions']))
        self.assertEqual(counts[0],counts[1])
        # Force no interior cells in the disk while keeping the required extrema.
        records,_=copper_features(curved)
        x=sorted({r['coordinate_m'] for r in records if r['axis']=='x'})
        y=sorted({r['coordinate_m'] for r in records if r['axis']=='y'})
        # Isolate the disk interval to one bounding-box cell (no full inner cell).
        lo=min(p[0] for p in c.vertices_xy_m);hi=max(p[0] for p in c.vertices_xy_m)
        x=[v for v in x if not lo<v<hi]
        broken=replace(mesh,x_lines_m=tuple(x),y_lines_m=tuple(y))
        with self.assertRaisesRegex(ConfigurationError,'cell envelopes'):
            audit_copper_mesh(curved,broken)


if __name__=='__main__':unittest.main()
