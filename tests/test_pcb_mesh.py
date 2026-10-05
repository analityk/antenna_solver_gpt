from dataclasses import replace, FrozenInstanceError
import json
from math import cos, sin, pi, hypot, ceil, prod
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import BoardOutline
from antenna_lab.pcb.workflow import prepare_pcb_placeholder
from antenna_lab.pcb.validation import validate_pcb_geometry
from antenna_lab.solvers.pcb_mesh import make_pcb_mesh_anchor_plan, ANCHOR_MERGE_TOLERANCE_M as TOL
from antenna_lab.solvers.pcb_mesh import (
    PcbPlaceholderMeshSettings, PcbPlaceholderMesh, make_pcb_placeholder_mesh,
)
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
        meshes = []
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
            meshes.append(make_pcb_placeholder_mesh(geometry, PcbPlaceholderMeshSettings(.0005, .0002, 1000000)))
        self.assertEqual(plans[0], plans[1])
        self.assertEqual(plans[1], plans[2])
        self.assertEqual(meshes[0], meshes[1])
        self.assertEqual(meshes[1], meshes[2])

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


    def test_copper_z_residue_preserves_substrate_interfaces(self):
        for residue in (-5e-11, 5e-11):
            with self.subTest(residue=residue):
                geometry = self.geometry().normalized_geometry
                geometry.copper[0] = replace(geometry.copper[0], z_m=residue)
                validate_pcb_geometry(geometry)
                before = geometry.as_dict()
                plan = make_pcb_mesh_anchor_plan(geometry)
                self.assertEqual(plan.z_required_m, (geometry.substrate.z_min_m, 0.0))
                self.assertNotIn(residue, plan.z_required_m)
                self.assertEqual(before, geometry.as_dict())

    def test_authoritative_nonzero_top_and_inconsistent_copper(self):
        geometry = self.geometry().normalized_geometry
        geometry.substrate = replace(geometry.substrate, z_max_m=5e-11)
        before = geometry.as_dict()
        plan = make_pcb_mesh_anchor_plan(geometry)
        self.assertEqual(plan.z_required_m, (geometry.substrate.z_min_m, 5e-11))
        self.assertEqual(before, geometry.as_dict())
        geometry.copper[0] = replace(geometry.copper[0], z_m=-8e-11)
        validate_pcb_geometry(geometry)
        with self.assertRaisesRegex(ConfigurationError, 'PCB Z.*miedzi'):
            make_pcb_mesh_anchor_plan(geometry)

    def test_collapsed_substrate_interfaces_rejected(self):
        for thickness in (5e-11, TOL):
            with self.subTest(thickness=thickness):
                geometry = self.geometry().normalized_geometry
                geometry.substrate = replace(geometry.substrate, z_min_m=-thickness)
                validate_pcb_geometry(geometry)
                with self.assertRaisesRegex(ConfigurationError, 'PCB Z.*nierozdzielalne'):
                    make_pcb_mesh_anchor_plan(geometry)
                with self.assertRaisesRegex(ConfigurationError, 'PCB Z'):
                    make_pcb_placeholder_mesh(geometry, PcbPlaceholderMeshSettings(.001, .001, 1000000))

    def test_resolvable_small_and_normal_substrate(self):
        for thickness in (4*TOL, .0016):
            with self.subTest(thickness=thickness):
                geometry = self.geometry().normalized_geometry
                geometry.substrate = replace(geometry.substrate, z_min_m=-thickness)
                self.assertEqual(make_pcb_mesh_anchor_plan(geometry).z_required_m, (-thickness, 0.))
                self.assert_mesh(geometry, PcbPlaceholderMeshSettings(.001, .001, 1000000))

    def test_mesh_defensively_rejects_empty_axis(self):
        geometry = self.geometry().normalized_geometry
        plan = make_pcb_mesh_anchor_plan(geometry)
        for axis in ('x_required_m', 'y_required_m', 'z_required_m'):
            with self.subTest(axis=axis), patch(
                    'antenna_lab.solvers.pcb_mesh.make_pcb_mesh_anchor_plan',
                    return_value=replace(plan, **{axis: (0.,)})):
                with self.assertRaisesRegex(ConfigurationError, 'każda oś'):
                    make_pcb_placeholder_mesh(geometry, PcbPlaceholderMeshSettings(.001, .001, 1000000))

    def assert_mesh(self, geometry, settings):
        before = geometry.as_dict()
        plan = make_pcb_mesh_anchor_plan(geometry)
        mesh = make_pcb_placeholder_mesh(geometry, settings)
        self.assertIsInstance(mesh, PcbPlaceholderMesh)
        all_steps = []
        for anchors, lines, target in zip(
                (plan.x_required_m, plan.y_required_m, plan.z_required_m),
                (mesh.x_lines_m, mesh.y_lines_m, mesh.z_lines_m),
                (settings.max_step_xy_m, settings.max_step_xy_m, settings.max_step_z_m)):
            for anchor in anchors:
                self.assertIn(anchor, lines)
            self.assertEqual((lines[0], lines[-1]), (anchors[0], anchors[-1]))
            differences = [b-a for a,b in zip(lines, lines[1:])]
            self.assertTrue(all(d > 0 for d in differences))
            self.assertLessEqual(max(differences), target + 1e-15)
            all_steps.extend(differences)
            for left, right in zip(anchors, anchors[1:]):
                interval = [x for x in lines if left <= x <= right]
                expected_count = ceil((right-left)/target)
                self.assertEqual(len(interval)-1, expected_count)
                for a,b in zip(interval, interval[1:]):
                    self.assertAlmostEqual(b-a, (right-left)/expected_count, delta=1e-15)
        n,p = geometry.port.negative_xy_m, geometry.port.positive_xy_m
        for x in (n[0], (n[0]+p[0])/2, p[0]):
            self.assertIn(x, mesh.x_lines_m)
        mid = (n[1]+p[1])/2
        for y in (mid-geometry.port.width_m/2, mid, mid+geometry.port.width_m/2):
            self.assertIn(y, mesh.y_lines_m)
        self.assertEqual(mesh.shape_cells, tuple(len(a)-1 for a in
                         (mesh.x_lines_m, mesh.y_lines_m, mesh.z_lines_m)))
        self.assertEqual(mesh.cell_count, prod(mesh.shape_cells))
        self.assertTrue(all(count > 0 for count in mesh.shape_cells))
        self.assertGreater(mesh.cell_count, 0)
        self.assertEqual(mesh.min_step_m, min(all_steps))
        self.assertEqual(mesh.max_step_m, max(all_steps))
        self.assertEqual(mesh, make_pcb_placeholder_mesh(geometry, settings))
        self.assertEqual(before, geometry.as_dict())
        return mesh

    def test_placeholder_exact_anchors_steps_and_substrate(self):
        geometry = self.geometry(angled=True).normalized_geometry
        mesh = self.assert_mesh(geometry, PcbPlaceholderMeshSettings(.0005, .0002, 1000000))
        self.assertGreater(len(mesh.z_lines_m), 2)
        self.assertEqual(mesh.z_lines_m[0], geometry.substrate.z_min_m)
        self.assertEqual(mesh.z_lines_m[-1], geometry.substrate.z_max_m)
        self.assertEqual(len(mesh.z_lines_m)-1, ceil(.0016/.0002))
        with self.assertRaises(FrozenInstanceError):
            mesh.cell_count = 0

    def test_placeholder_resolution_and_local_intervals(self):
        geometry = self.geometry().normalized_geometry
        coarse = self.assert_mesh(geometry, PcbPlaceholderMeshSettings(.0007, .0006, 1000000))
        fine = self.assert_mesh(geometry, PcbPlaceholderMeshSettings(.0002, .0001, 1000000))
        self.assertGreater(fine.cell_count, coarse.cell_count)
        plan = make_pcb_mesh_anchor_plan(geometry)
        lengths = [b-a for a,b in zip(plan.y_required_m, plan.y_required_m[1:])]
        self.assertGreater(max(lengths), 2*min(lengths))

    def test_placeholder_max_cells(self):
        geometry = self.geometry().normalized_geometry
        with self.assertRaisesRegex(ConfigurationError, 'max_cells'):
            make_pcb_placeholder_mesh(geometry, PcbPlaceholderMeshSettings(2*TOL, 2*TOL, 10))
        mesh = make_pcb_placeholder_mesh(geometry, PcbPlaceholderMeshSettings(.001, .001, 1000000))
        self.assertEqual(mesh, make_pcb_placeholder_mesh(geometry,
                         PcbPlaceholderMeshSettings(.001, .001, mesh.cell_count)))

    def test_placeholder_invalid_settings(self):
        geometry = self.geometry().normalized_geometry
        valid = PcbPlaceholderMeshSettings(.0005, .0002, 1000000)
        for field in ('max_step_xy_m', 'max_step_z_m'):
            for value in (0, -1, TOL, float('nan'), float('inf'), -float('inf'), True, 'bad'):
                with self.subTest(field=field, value=value), self.assertRaises(ConfigurationError):
                    make_pcb_placeholder_mesh(geometry, replace(valid, **{field:value}))
        for value in (0, -1, 1.5, True, float('nan'), float('inf')):
            with self.subTest(max_cells=value), self.assertRaises(ConfigurationError):
                make_pcb_placeholder_mesh(geometry, replace(valid, max_cells=value))

    def test_placeholder_wide_and_small(self):
        for gap,width in ((.5,4.), (.1,.3)):
            with self.subTest(gap=gap, width=width):
                geometry = self.geometry(gap, width, angled=True).normalized_geometry
                self.assert_mesh(geometry, PcbPlaceholderMeshSettings(.0001, .0002, 1000000))


if __name__ == '__main__':
    unittest.main()
