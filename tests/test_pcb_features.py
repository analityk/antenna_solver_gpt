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


def routed_fixture(dense=1, rounded=False, segments=8):
    from shapely.geometry import LineString
    g,_=normalize_port_orientation(fixture())
    points=[(-.007,.004),(.007,.004),(.007,.006),(-.007,.006),(-.007,.008),(.007,.008)]
    shape=LineString(points).buffer(.00019,cap_style='flat',
        join_style='round' if rounded else 'mitre',quad_segs=segments)
    ring=tuple(shape.exterior.coords)[:-1]
    if dense>1:
        ring=tuple((a[0]+(b[0]-a[0])*i/dense,a[1]+(b[1]-a[1])*i/dense)
                   for a,b in zip(ring,(*ring[1:],ring[0])) for i in range(dense))
    g.copper.append(CopperPolygon('route',ring,0.))
    return g


class CopperFeatureTests(unittest.TestCase):
    def test_strip_and_hole_widths_after_projection_in_every_quality(self):
        for hole in (False,True):
            for quality in ('preview','design','verify'):
                results=[];z_axes=[]
                s,_=gerber_quality_settings(quality)
                for width in WIDTHS:
                    with self.subTest(hole=hole,quality=quality,width=width):
                        raw,_,_=feature_fixture(width,hole);before=raw.as_dict()
                        g,_,_=apply_geometry_resolution(raw,PcbGrid())
                        expected=.00025 if width==.250 else .00038
                        mesh=make_pcb_domain_mesh(g,s,gerber_quality=quality)
                        audit=audit_copper_mesh(g,mesh,source_geometry=raw)
                        dims=[f for f in audit['features'] if f['copper_id']=='feature' and f['axis']=='y'
                              and f['kind']==('clearance' if hole else 'copper')
                              and abs(f['modeled_width_m']-expected)<1e-17]
                        self.assertTrue(dims)
                        for f in dims:
                            self.assertAlmostEqual(f['solver_facing_width_m'],expected,delta=1e-17)
                            self.assertAlmostEqual(f['source_width_m'],width*.001,delta=1e-17)
                            self.assertGreaterEqual(len(f['interior_lines_m']),2)
                            self.assertTrue(f['preserved'])
                            self.assertTrue(all(e['method'] in ('thirds','aligned','resolved_subcell') for e in f['mesh_edges']))
                        self.assertEqual(before,raw.as_dict())
                        self.assertEqual(audit['status'],'PASS');json.dumps(audit,allow_nan=False)
                        self.assertLess(len(mesh.x_lines_m),1000)
                        self.assertTrue(any(abs(v/1e-5-round(v/1e-5))>1e-6 for v in mesh.y_lines_m))
                        results.append((g.copper[-1],dims,mesh.y_lines_m));z_axes.append(mesh.z_lines_m)
                self.assertEqual(results[0][0],results[1][0]);self.assertEqual(results[0][2],results[1][2])
                self.assertEqual(results[0][0],results[3][0])
                self.assertNotEqual(results[2][0],results[3][0]);self.assertNotEqual(results[2][2],results[3][2])
                self.assertTrue(all(z==z_axes[0] for z in z_axes))

    def test_thirds_final_cell_has_one_third_inside_metal(self):
        raw,_,_=feature_fixture(.38);g,_,_=apply_geometry_resolution(raw,PcbGrid())
        s,_=gerber_quality_settings('preview');m=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        audit=audit_copper_mesh(g,m)
        rows=[r for r in audit['boundaries'] if r['method']=='thirds']
        self.assertTrue(rows)
        for r in rows:
            lo,hi=r['nearby_lines_m'];edge=r['coordinate_m']
            inside=hi-edge if r['metal_side']>0 else edge-lo
            self.assertAlmostEqual(inside/(hi-lo),1/3,places=10)
            self.assertNotIn(edge,getattr(m,r['axis']+'_lines_m'))
        self.assertTrue(any(r['method']=='resolved_subcell' for r in audit['boundaries']))

    def test_parallel_different_conductors_keep_gap(self):
        outcomes=[];s,_=gerber_quality_settings('preview')
        for gap in (.25,.38):
            g,_=normalize_port_orientation(fixture());mid=.006001
            lo=mid-gap*.001/2;hi=mid+gap*.001/2
            for name,a,b in (('lower',lo-.0005,lo),('upper',hi,hi+.0005)):
                g.copper.append(CopperPolygon(name,((-.008,a),(.008,a),(.008,b),(-.008,b)),0.))
            g,_,_=apply_geometry_resolution(g,PcbGrid())
            m=make_pcb_domain_mesh(g,s,gerber_quality='preview');audit=audit_copper_mesh(g,m)
            f=next(f for f in audit['features'] if f['kind']=='clearance' and f['owners']==['lower','upper'])
            self.assertAlmostEqual(f['solver_facing_width_m'],gap*.001,delta=1e-17)
            outcomes.append(m.y_lines_m)
        self.assertNotEqual(*outcomes)

    def test_coarsened_feature_mesh_is_rejected(self):
        for hole in (False,True):
            raw,_,_=feature_fixture(.25,hole);g,_,_=apply_geometry_resolution(raw,PcbGrid())
            s,_=gerber_quality_settings('preview');m=make_pcb_domain_mesh(g,s,gerber_quality='preview')
            broken=replace(m,y_lines_m=tuple(y for y in m.y_lines_m if not .004<y<.009))
            with self.assertRaisesRegex(ConfigurationError,'PCB feature|cell envelopes'):
                audit_copper_mesh(g,broken)

    def test_serpentine_collinear_density_does_not_change_mesh(self):
        from antenna_lab.solvers.pcb_features import compact_features
        s,_=gerber_quality_settings('preview');results=[]
        for dense in (1,12):
            g=routed_fixture(dense=dense);before=g.as_dict()
            m=make_pcb_domain_mesh(g,s,gerber_quality='preview');a=audit_copper_mesh(g,m)
            results.append((compact_features(g)[0],m))
            self.assertEqual(a['status'],'PASS');self.assertEqual(before,g.as_dict())
        self.assertEqual(results[0],results[1])
        self.assertEqual(len(routed_fixture(12).copper[-1].vertices_xy_m),12*len(routed_fixture().copper[-1].vertices_xy_m))

    def test_rounded_trace_tessellation_is_not_mesh_anchors(self):
        s,_=gerber_quality_settings('preview');counts=[]
        for segments in (8,32):
            g=routed_fixture(rounded=True,segments=segments);before=g.as_dict()
            plan,meta=make_gerber_mesh_anchor_plan(g,s,'preview')
            m=make_pcb_domain_mesh(g,s,gerber_quality='preview');a=audit_copper_mesh(g,m)
            self.assertEqual(a['status'],'PASS');self.assertEqual(before,g.as_dict())
            self.assertEqual(meta['direct_vertex_anchor_count'],0)
            counts.append((m.cell_count,len(meta['features']),len(plan.x_required_m)+len(plan.y_required_m)))
        self.assertLess(max(c[0] for c in counts)/min(c[0] for c in counts),2)
        self.assertEqual(counts[0][1:],counts[1][1:])

    def test_long_straight_collinear_points_are_redundant(self):
        from antenna_lab.pcb.model import BoardOutline
        g,_=normalize_port_orientation(fixture())
        board=BoardOutline(((-.03,-.015),(.03,-.015),(.03,.015),(-.03,.015)))
        g=replace(g,outline=board,substrate=replace(g.substrate,outline=board))
        ring=((-0.025,.005),(.025,.005),(.025,.00538),(-.025,.00538))
        s,_=gerber_quality_settings('preview');results=[]
        for count in (1,40):
            dense=tuple((a[0]+(b[0]-a[0])*i/count,a[1]+(b[1]-a[1])*i/count)
                        for a,b in zip(ring,(*ring[1:],ring[0])) for i in range(count))
            model=replace(g,copper=g.copper+[CopperPolygon('trace',dense,0.)])
            m=make_pcb_domain_mesh(model,s,gerber_quality='preview');results.append(m)
        self.assertEqual(*results)

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

    def test_curved_antipad_and_explicit_audit_budget(self):
        g,_=normalize_port_orientation(fixture());s,_=gerber_quality_settings('preview')
        hole=tuple(Point(0,.006).buffer(.001,quad_segs=32).exterior.coords)[:-1]
        plane=CopperPolygon('plane',((-.008,.004),(.008,.004),(.008,.009),(-.008,.009)),0.,holes_xy_m=(hole,))
        g=replace(g,copper=g.copper+[plane]);before=g.as_dict()
        mesh=make_pcb_domain_mesh(g,s,gerber_quality='preview');a=audit_copper_mesh(g,mesh)
        item=next(r for r in a['curved_regions'] if r['copper_id']=='plane')
        self.assertEqual(item['inner_topology'],[1,1]);self.assertEqual(item['outer_topology'],[1,1])
        with patch('antenna_lab.solvers.pcb_features.MAX_FIDELITY_CELLS',1):
            with self.assertRaisesRegex(ConfigurationError,'audit cells'):audit_copper_mesh(g,mesh)
        self.assertEqual(before,g.as_dict())


if __name__=='__main__':unittest.main()
