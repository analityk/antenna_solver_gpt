from dataclasses import replace, FrozenInstanceError
import json
from math import cos, sin, pi, hypot
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import BoardOutline
from antenna_lab.pcb.workflow import prepare_pcb_placeholder
from antenna_lab.pcb.validation import validate_pcb_geometry
from antenna_lab.solvers.pcb_mesh import make_pcb_mesh_anchor_plan, ANCHOR_MERGE_TOLERANCE_M as TOL
from test_pcb_config import config


class PcbMeshTests(unittest.TestCase):
    def geometry(self, gap=2., width=1., angled=False):
        value = config()
        value['port']['width_mm'] = width
        value['port']['positive_mm'] = [9. + gap, 10.]
        if angled:
            value['port']['positive_mm'] = [9. + gap*cos(37*pi/180), 10. + gap*sin(37*pi/180)]
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'pcb.json'
            path.write_text(json.dumps(value), encoding='utf-8')
            return prepare_pcb_placeholder(path)

    def assert_ordered(self, plan):
        for axis in (plan.x_required_m, plan.y_required_m, plan.z_required_m):
            self.assertIsInstance(axis, tuple)
            self.assertTrue(all(b - a > TOL for a, b in zip(axis, axis[1:])))

    def assert_port(self, geometry, plan):
        n, p = geometry.port.negative_xy_m, geometry.port.positive_xy_m
        for x in (n[0], (n[0]+p[0])/2, p[0]):
            self.assertIn(x, plan.x_required_m)
        mid = (n[1]+p[1])/2
        for y in (mid-geometry.port.width_m/2, mid, mid+geometry.port.width_m/2):
            self.assertIn(y, plan.y_required_m)

    def test_required_features_metadata_determinism_no_mutation(self):
        geometry = self.geometry(angled=True).normalized_geometry
        validate_pcb_geometry(geometry)
        before = geometry.as_dict()
        plan = make_pcb_mesh_anchor_plan(geometry)
        self.assert_port(geometry, plan)
        self.assert_ordered(plan)
        for axis, anchors in ((0, plan.x_required_m), (1, plan.y_required_m)):
            board = [p[axis] for p in geometry.outline.vertices_xy_m]
            self.assertIn(min(board), anchors)
            self.assertIn(max(board), anchors)
            for copper in geometry.copper:
                vals = [p[axis] for p in copper.vertices_xy_m]
                for expected in (min(vals), (min(vals)+max(vals))/2, max(vals)):
                    self.assertTrue(any(abs(a-expected) <= TOL for a in anchors))
        self.assertEqual(plan.z_required_m, (geometry.substrate.z_min_m, geometry.substrate.z_max_m))
        n, p = geometry.port.negative_xy_m, geometry.port.positive_xy_m
        self.assertEqual(plan.port_length_m, hypot(p[0]-n[0], p[1]-n[1]))
        self.assertEqual(plan.port_width_m, geometry.port.width_m)
        self.assertEqual(plan.substrate_thickness_m, geometry.substrate.z_max_m-geometry.substrate.z_min_m)
        self.assertEqual(plan, make_pcb_mesh_anchor_plan(geometry))
        self.assertEqual(before, geometry.as_dict())
        with self.assertRaises(FrozenInstanceError):
            plan.port_width_m = 0

    def test_port_precedence(self):
        geometry = self.geometry().normalized_geometry
        for i, copper in enumerate(geometry.copper):
            delta = TOL / 4 if i == 0 else -TOL / 4
            geometry.copper[i] = replace(copper, vertices_xy_m=tuple(
                (x+delta, y+TOL/4) for x, y in copper.vertices_xy_m))
        validate_pcb_geometry(geometry)
        plan = make_pcb_mesh_anchor_plan(geometry)
        self.assert_port(geometry, plan)
        self.assert_ordered(plan)
        for endpoint in (geometry.port.negative_xy_m, geometry.port.positive_xy_m):
            self.assertEqual([x for x in plan.x_required_m if abs(x-endpoint[0]) <= TOL], [endpoint[0]])

    def test_distinct_nonport_features_survive(self):
        geometry = self.geometry().normalized_geometry
        copper = geometry.copper[0]
        low = min(x for x, y in copper.vertices_xy_m)
        boundary = low - 4*TOL
        points = geometry.outline.vertices_xy_m
        left = min(x for x, y in points)
        outline = BoardOutline(tuple((boundary if x == left else x, y) for x, y in points))
        geometry.outline = outline
        geometry.substrate = replace(geometry.substrate, outline=outline)
        plan = make_pcb_mesh_anchor_plan(geometry)
        self.assertIn(low, plan.x_required_m)
        self.assertIn(boundary, plan.x_required_m)
        self.assert_ordered(plan)

    def test_many_vertices_same_bounds_same_plan(self):
        plans = []
        for count in (4, 32, 64):
            geometry = self.geometry().normalized_geometry
            for i, copper in enumerate(geometry.copper):
                xs = [x for x,y in copper.vertices_xy_m]
                ys = [y for x,y in copper.vertices_xy_m]
                cx, rx = (min(xs)+max(xs))/2, (max(xs)-min(xs))/2
                ry = (max(ys)-min(ys))/2
                vertices = []
                for j in range(count):
                    # Exact cardinal extrema give identical bounding boxes.
                    cardinal = {0:(1.,0.), count//4:(0.,1.), count//2:(-1.,0.), 3*count//4:(0.,-1.)}
                    dx, dy = cardinal.get(j, (cos(2*pi*j/count), sin(2*pi*j/count)))
                    vertices.append((cx+rx*dx, ry*dy))
                geometry.copper[i] = replace(copper, vertices_xy_m=tuple(vertices))
            plan = make_pcb_mesh_anchor_plan(geometry)
            self.assertLessEqual(len(plan.x_required_m), 2+3*2+3)
            self.assertLessEqual(len(plan.y_required_m), 2+3*2+3)
            plans.append(plan)
        self.assertEqual(plans[0], plans[1])
        self.assertEqual(plans[1], plans[2])

    def test_reject_non_normalized_and_invalid(self):
        result = self.geometry(angled=True)
        validate_pcb_geometry(result.source_geometry)
        with self.assertRaisesRegex(ConfigurationError, 'znormalizowany'):
            make_pcb_mesh_anchor_plan(result.source_geometry)
        result.normalized_geometry.copper = []
        with self.assertRaises(ConfigurationError):
            make_pcb_mesh_anchor_plan(result.normalized_geometry)

    def test_wide_and_small_ports(self):
        for gap, width in ((.5,4.), (.1,.3)):
            with self.subTest(gap=gap, width=width):
                geometry = self.geometry(gap, width, angled=True).normalized_geometry
                plan = make_pcb_mesh_anchor_plan(geometry)
                self.assert_port(geometry, plan)
                self.assert_ordered(plan)

    def test_unresolvable_critical_anchors_rejected_not_collapsed(self):
        geometry = self.geometry().normalized_geometry
        geometry.port = replace(geometry.port, width_m=TOL)
        validate_pcb_geometry(geometry)
        with self.assertRaisesRegex(ConfigurationError, 'krytyczne'):
            make_pcb_mesh_anchor_plan(geometry)


if __name__ == '__main__':
    unittest.main()
