from dataclasses import replace, FrozenInstanceError, asdict
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
from antenna_lab.solvers import pcb_mesh
from antenna_lab.solvers.pcb_mesh import PcbDomainMesh, make_pcb_domain_mesh
from test_pcb_config import config
from test_pcb_simulation import settings, simulation_config
from antenna_lab.solvers.pcb_mesh import derive_pcb_physical_mesh_policy


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


    def test_copper_z_residue_rejected_without_mutation(self):
        for residue in (-5e-11, 5e-11):
            for index in (0, 1):
                with self.subTest(residue=residue, copper=index):
                    geometry = self.geometry().normalized_geometry
                    geometry.copper[index] = replace(geometry.copper[index], z_m=residue)
                    validate_pcb_geometry(geometry)
                    before = geometry.as_dict()
                    with self.assertRaisesRegex(ConfigurationError, 'PCB v0.*dokładnie z=0.*miedzi'):
                        make_pcb_mesh_anchor_plan(geometry)
                    self.assertEqual(before, geometry.as_dict())
                    with self.assertRaisesRegex(ConfigurationError, 'PCB v0.*dokładnie z=0'):
                        make_pcb_placeholder_mesh(geometry, PcbPlaceholderMeshSettings(.001, .001, 1000000))
                    self.assertEqual(before, geometry.as_dict())

    def test_substrate_top_residue_rejected_without_mutation(self):
        for residue in (-5e-11, 5e-11):
            with self.subTest(residue=residue):
                geometry = self.geometry().normalized_geometry
                geometry.substrate = replace(geometry.substrate, z_max_m=residue)
                validate_pcb_geometry(geometry)
                before = geometry.as_dict()
                with self.assertRaisesRegex(ConfigurationError, 'PCB v0.*dokładnie z=0.*laminatu'):
                    make_pcb_mesh_anchor_plan(geometry)
                self.assertEqual(before, geometry.as_dict())
                with self.assertRaisesRegex(ConfigurationError, 'PCB v0.*dokładnie z=0'):
                    make_pcb_placeholder_mesh(geometry, PcbPlaceholderMeshSettings(.001, .001, 1000000))
                self.assertEqual(before, geometry.as_dict())

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


class PcbPhysicalPolicyTests(unittest.TestCase):
    def geometry(self, **kwargs):
        return PcbMeshTests().geometry(**kwargs).normalized_geometry

    def test_limits_metadata_determinism_no_mutation(self):
        geometry = self.geometry(gap=.5, width=4.)
        experiment = settings()
        before = geometry.as_dict()
        policy = derive_pcb_physical_mesh_policy(geometry, experiment)
        self.assertEqual(policy.f_mesh_hz, 1.62e9)
        self.assertAlmostEqual(policy.air_wavelength_m, 299792458.0/1.62e9, delta=1e-15)
        substrate = 299792458.0/(1.62e9 * 4.3**.5)
        self.assertAlmostEqual(policy.substrate_wavelength_m, substrate, delta=1e-15)
        self.assertAlmostEqual(policy.max_air_step_m, 299792458.0/1.62e9/20, delta=1e-16)
        self.assertAlmostEqual(policy.max_substrate_xy_step_m, substrate/20, delta=1e-16)
        self.assertLess(policy.max_substrate_xy_step_m, policy.max_air_step_m)
        self.assertEqual(policy.max_substrate_z_step_m, .0016/4)
        self.assertAlmostEqual(policy.max_port_gap_step_m, .0005/2, delta=1e-17)
        self.assertEqual(policy.max_port_width_step_m, .004/2)
        for name in ('min_substrate_cells_z', 'min_port_gap_cells', 'min_port_width_cells',
                     'growth_ratio_target', 'growth_ratio_limit', 'max_cells'):
            self.assertEqual(getattr(policy, name), getattr(experiment, name))
        self.assertEqual(geometry.as_dict(), before)
        self.assertEqual(experiment, settings())
        self.assertEqual(policy, derive_pcb_physical_mesh_policy(geometry, experiment))
        with self.assertRaises(FrozenInstanceError):
            policy.max_cells = 1

    def test_configured_counts_and_growth(self):
        value = simulation_config()
        value['mesh'].update(cells_per_wavelength=32, min_substrate_cells_z=8,
                             min_port_gap_cells=5, min_port_width_cells=3,
                             growth_ratio_target=1.2, growth_ratio_limit=1.3, max_cells=12345)
        geometry = self.geometry()
        policy = derive_pcb_physical_mesh_policy(geometry, settings(value))
        plan = make_pcb_mesh_anchor_plan(geometry)
        self.assertEqual(policy.max_air_step_m, policy.air_wavelength_m/32)
        self.assertEqual(policy.max_substrate_xy_step_m, policy.substrate_wavelength_m/32)
        self.assertEqual(policy.max_substrate_z_step_m, .0016/8)
        self.assertEqual(policy.max_port_gap_step_m, plan.port_length_m/5)
        self.assertEqual(policy.max_port_width_step_m, plan.port_width_m/3)
        self.assertEqual((policy.min_substrate_cells_z, policy.min_port_gap_cells,
                          policy.min_port_width_cells), (8,5,3))
        self.assertEqual((policy.growth_ratio_target, policy.growth_ratio_limit, policy.max_cells),
                         (1.2,1.3,12345))

    def test_wavelength_dominates_z_and_epsilon_effect(self):
        geometry = self.geometry()
        geometry.substrate = replace(geometry.substrate, z_min_m=-1.)
        first = derive_pcb_physical_mesh_policy(geometry, settings())
        self.assertEqual(first.max_substrate_z_step_m, first.max_substrate_xy_step_m)
        geometry.substrate = replace(geometry.substrate, epsilon_r=9.)
        second = derive_pcb_physical_mesh_policy(geometry, settings())
        self.assertLess(second.substrate_wavelength_m, first.substrate_wavelength_m)
        self.assertLess(second.max_substrate_xy_step_m, first.max_substrate_xy_step_m)
        self.assertLess(second.max_substrate_z_step_m, first.max_substrate_z_step_m)
        self.assertEqual(second.max_air_step_m, first.max_air_step_m)

    def test_excitation_not_result_sampling_controls_resolution(self):
        geometry = self.geometry()
        value = simulation_config()
        first = derive_pcb_physical_mesh_policy(geometry, settings(value))
        value['result_frequency_hz'] = [1.3e9, 1.5e9]
        self.assertEqual(first, derive_pcb_physical_mesh_policy(geometry, settings(value)))
        value['excitation']['center_hz'] *= 2
        value['excitation']['cutoff_hz'] *= 2
        value['result_frequency_hz'] = [2.84e9]
        second = derive_pcb_physical_mesh_policy(geometry, settings(value))
        self.assertEqual(second.f_mesh_hz, 3.24e9)
        self.assertEqual(second.max_air_step_m, first.max_air_step_m/2)
        self.assertEqual(second.max_substrate_xy_step_m, first.max_substrate_xy_step_m/2)

    def test_padding_limits_and_configured_pml_without_geometry(self):
        geometry = self.geometry()
        before = geometry.as_dict()
        value = simulation_config()
        first = derive_pcb_physical_mesh_policy(geometry, settings(value))
        self.assertEqual(first.padding_frequency_hz, 1.3e9)
        self.assertEqual(first.padding_air_wavelength_m, 299792458.0/1.3e9)
        self.assertEqual(first.air_padding_m, .25 * first.padding_air_wavelength_m)
        self.assertEqual(first.pml_cells, 8)
        value['domain']['air_padding_wavelengths'] = .5
        second = derive_pcb_physical_mesh_policy(geometry, settings(value))
        self.assertEqual(second, replace(first, air_padding_m=first.air_padding_m*2))
        value['domain']['pml_cells'] = 12
        third = derive_pcb_physical_mesh_policy(geometry, settings(value))
        self.assertEqual(third, replace(second, pml_cells=12))
        self.assertEqual(geometry.as_dict(), before)

    def test_lowest_result_controls_padding_only(self):
        geometry = self.geometry()
        value = simulation_config()
        first = derive_pcb_physical_mesh_policy(geometry, settings(value))
        value['result_frequency_hz'][0] = 1.35e9
        second = derive_pcb_physical_mesh_policy(geometry, settings(value))
        self.assertEqual(second.padding_frequency_hz, 1.35e9)
        self.assertLess(second.air_padding_m, first.air_padding_m)
        self.assertEqual(second, replace(first, padding_frequency_hz=1.35e9,
                         padding_air_wavelength_m=299792458.0/1.35e9,
                         air_padding_m=.25 * (299792458.0/1.35e9)))

    def test_excitation_changes_resolution_not_padding(self):
        geometry = self.geometry()
        value = simulation_config()
        first = derive_pcb_physical_mesh_policy(geometry, settings(value))
        value['excitation']['cutoff_hz'] = 300000000
        second = derive_pcb_physical_mesh_policy(geometry, settings(value))
        self.assertGreater(second.f_mesh_hz, first.f_mesh_hz)
        self.assertLess(second.max_air_step_m, first.max_air_step_m)
        self.assertLess(second.max_substrate_xy_step_m, first.max_substrate_xy_step_m)
        for field in ('padding_frequency_hz', 'padding_air_wavelength_m', 'air_padding_m', 'pml_cells'):
            self.assertEqual(getattr(second, field), getattr(first, field))

    def test_solver_geometry_contract_propagates(self):
        for plane in ('substrate', 'copper'):
            for residue in (-5e-11, 5e-11):
                with self.subTest(plane=plane, residue=residue):
                    geometry = self.geometry()
                    if plane == 'substrate':
                        geometry.substrate = replace(geometry.substrate, z_max_m=residue)
                    else:
                        geometry.copper[0] = replace(geometry.copper[0], z_m=residue)
                    validate_pcb_geometry(geometry)
                    before = geometry.as_dict()
                    with self.assertRaisesRegex(ConfigurationError, 'dokładnie z=0'):
                        derive_pcb_physical_mesh_policy(geometry, settings())
                    self.assertEqual(before, geometry.as_dict())
        geometry = PcbMeshTests().geometry().source_geometry
        with self.assertRaisesRegex(ConfigurationError, 'znormalizowany'):
            derive_pcb_physical_mesh_policy(geometry, settings())
        geometry = self.geometry()
        geometry.substrate = replace(geometry.substrate, z_min_m=-TOL)
        with self.assertRaisesRegex(ConfigurationError, 'nierozdzielalne'):
            derive_pcb_physical_mesh_policy(geometry, settings())


class PcbDomainMeshTests(unittest.TestCase):
    # Relative arithmetic tolerance, not a geometry/anchor merging tolerance.
    REL_TOL = 1e-9

    def geometry(self, **kwargs):
        return PcbMeshTests().geometry(**kwargs).normalized_geometry

    def assert_domain(self, geometry, experiment):
        before = geometry.as_dict()
        settings_before = asdict(experiment)
        plan = make_pcb_mesh_anchor_plan(geometry)
        policy = derive_pcb_physical_mesh_policy(geometry, experiment)
        mesh = make_pcb_domain_mesh(geometry, experiment)
        self.assertIsInstance(mesh, PcbDomainMesh)
        self.assertEqual(before, geometry.as_dict())
        self.assertEqual(settings_before, asdict(experiment))
        self.assertEqual(mesh, make_pcb_domain_mesh(geometry, experiment))
        axes = (mesh.x_lines_m, mesh.y_lines_m, mesh.z_lines_m)
        required = (plan.x_required_m, plan.y_required_m, plan.z_required_m)
        n, p = geometry.port.negative_xy_m, geometry.port.positive_xy_m
        mid_y = (n[1]+p[1])/2
        ranges = ((n[0], p[0]), (mid_y-plan.port_width_m/2, mid_y+plan.port_width_m/2))
        all_steps, all_ratios = [], []
        for axis, (lines, anchors) in enumerate(zip(axes, required)):
            self.assertIsInstance(lines, tuple)
            for anchor in anchors:
                self.assertIn(anchor, lines)
            lo, hi = anchors[0]-policy.air_padding_m, anchors[-1]+policy.air_padding_m
            self.assertIn(lo, lines)
            self.assertIn(hi, lines)
            self.assertEqual(mesh.pml_start_min_m[axis], lo)
            self.assertEqual(mesh.pml_start_max_m[axis], hi)
            # The boundary expressions are exact; subtracting them can round.
            self.assertAlmostEqual(anchors[0]-lo, policy.air_padding_m, delta=1e-15)
            self.assertAlmostEqual(hi-anchors[-1], policy.air_padding_m, delta=1e-15)
            self.assertLess(lines[0], lo)
            self.assertLess(hi, lines[-1])
            self.assertEqual(mesh.outer_min_m[axis], lines[0])
            self.assertEqual(mesh.outer_max_m[axis], lines[-1])
            ilo, ihi = lines.index(lo), lines.index(hi)
            self.assertEqual(ilo, experiment.pml_cells)
            self.assertEqual(len(lines)-1-ihi, experiment.pml_cells)
            steps = [b-a for a,b in zip(lines, lines[1:])]
            self.assertTrue(all(v > TOL for v in steps))
            for actual, expected in ((steps[:ilo], steps[ilo]), (steps[ihi:], steps[ihi-1])):
                for step in actual:
                    self.assertAlmostEqual(step, expected, delta=expected*self.REL_TOL)
            ordinary = lines[ilo:ihi+1]
            core_count = 0
            port_count = 0
            for a,b in zip(ordinary, ordinary[1:]):
                if b <= anchors[0] or a >= anchors[-1]:
                    maximum = policy.max_air_step_m
                else:
                    core_count += 1
                    maximum = policy.max_substrate_z_step_m if axis == 2 else policy.max_substrate_xy_step_m
                    if axis < 2 and ranges[axis][0] <= a and b <= ranges[axis][1]:
                        port_count += 1
                        maximum = min(maximum, (policy.max_port_gap_step_m, policy.max_port_width_step_m)[axis])
                self.assertLessEqual(b-a, maximum*(1+self.REL_TOL))
            if axis == 2:
                self.assertGreaterEqual(core_count, experiment.min_substrate_cells_z)
            else:
                self.assertGreaterEqual(port_count, (experiment.min_port_gap_cells, experiment.min_port_width_cells)[axis])
            ratios = [max(a,b)/min(a,b) for a,b in zip(steps, steps[1:])]
            self.assertLessEqual(max(ratios), experiment.growth_ratio_limit*(1+self.REL_TOL))
            ordinary_steps = steps[ilo:ihi]
            self.assertLessEqual(max(max(a,b)/min(a,b) for a,b in zip(ordinary_steps, ordinary_steps[1:])),
                                 experiment.growth_ratio_target*(1+self.REL_TOL))
            all_steps.extend(steps)
            all_ratios.extend(ratios)
        for x in (n[0], (n[0]+p[0])/2, p[0]):
            self.assertIn(x, mesh.x_lines_m)
        for y in (mid_y-plan.port_width_m/2, mid_y, mid_y+plan.port_width_m/2):
            self.assertIn(y, mesh.y_lines_m)
        self.assertIn(0., mesh.z_lines_m)
        self.assertEqual(mesh.shape_cells, tuple(len(a)-1 for a in axes))
        self.assertTrue(all(n > 0 for n in mesh.shape_cells))
        self.assertEqual(mesh.cell_count, prod(mesh.shape_cells))
        self.assertGreater(mesh.cell_count, 0)
        self.assertLessEqual(mesh.cell_count, experiment.max_cells)
        self.assertEqual(mesh.min_step_m, min(all_steps))
        self.assertEqual(mesh.max_step_m, max(all_steps))
        self.assertEqual(mesh.worst_growth_ratio, max(all_ratios))
        with self.assertRaises(FrozenInstanceError):
            mesh.cell_count = 1
        return mesh

    def test_complete_domain_and_pml_faces(self):
        for count in (8,12):
            with self.subTest(pml_cells=count):
                self.assert_domain(self.geometry(), replace(settings(), pml_cells=count))

    def test_wide_and_small_ports_and_grading(self):
        for gap,width in ((.5,4.), (.1,.3)):
            with self.subTest(gap=gap,width=width):
                geometry = self.geometry(gap=gap,width=width)
                experiment = settings()
                mesh = self.assert_domain(geometry, experiment)
                plan = make_pcb_mesh_anchor_plan(geometry)
                policy = derive_pcb_physical_mesh_policy(geometry, experiment)
                # Strong transition from the explicit small X port interval.
                initial_count = 0
                for a,b in zip(plan.x_required_m, plan.x_required_m[1:]):
                    step = policy.max_substrate_xy_step_m
                    if geometry.port.negative_xy_m[0] <= a and b <= geometry.port.positive_xy_m[0]:
                        step = min(step, policy.max_port_gap_step_m)
                    count = ceil((b-a)/step)
                    initial_count += count
                    # Grading retains ALL initial subdivision lines as well as anchors.
                    for k in range(1,count):
                        self.assertIn(a+(b-a)*(k/count), mesh.x_lines_m)
                initial_count += 2*ceil(policy.air_padding_m/policy.max_air_step_m)
                self.assertGreater(mesh.shape_cells[0]-2*experiment.pml_cells, initial_count)

    def test_logical_port_extents_beyond_board(self):
        geometry = self.geometry()
        geometry.port = replace(geometry.port, width_m=.04)
        plan = make_pcb_mesh_anchor_plan(geometry)
        self.assertLess(plan.y_required_m[0], min(y for x,y in geometry.outline.vertices_xy_m))
        self.assert_domain(geometry, settings())

    def test_custom_minimum_port_resolution(self):
        self.assert_domain(self.geometry(gap=.5,width=4), replace(
            settings(), min_port_gap_cells=5, min_port_width_cells=7, min_substrate_cells_z=9))

    def test_resource_guards_and_exact_budget(self):
        geometry = self.geometry()
        experiment = settings()
        with patch.object(pcb_mesh, '_subdivide', side_effect=AssertionError('must guard before allocation')):
            with self.assertRaisesRegex(ConfigurationError, 'max_cells'):
                make_pcb_domain_mesh(geometry, replace(experiment, max_cells=1))
            with self.assertRaisesRegex(ConfigurationError, 'max_cells'):
                make_pcb_domain_mesh(geometry, replace(experiment, cells_per_wavelength=1e12))
        mesh = make_pcb_domain_mesh(geometry, experiment)
        self.assertEqual(mesh, make_pcb_domain_mesh(geometry, replace(experiment, max_cells=mesh.cell_count)))
        with self.assertRaisesRegex(ConfigurationError, 'max_cells'):
            make_pcb_domain_mesh(geometry, replace(experiment, max_cells=mesh.cell_count-1))
        with self.assertRaisesRegex(ConfigurationError, 'shape=.*cell_count=.*max_cells='):
            pcb_mesh._domain_count_guard((2,3,4), 23)

    def test_grading_progress_and_independent_audits(self):
        with self.assertRaisesRegex(ConfigurationError, 'max_cells'):
            pcb_mesh._grade_domain_axis((0., .001, .1), 1.4, 2)
        with self.assertRaisesRegex(ConfigurationError, 'tolerancji'):
            pcb_mesh._grade_domain_axis((0., TOL, .1), 1.4, 100)
        # Every initial step is legal, but splitting the larger cell cannot be.
        with self.assertRaisesRegex(ConfigurationError, 'postępu.*|tolerancji'):
            pcb_mesh._grade_domain_axis((0., 1.01*TOL, 2.51*TOL), 1.4, 100)
        with self.assertRaisesRegex(ConfigurationError, 'growth_ratio_limit'):
            pcb_mesh._audit_domain_axis((0., .001, .01), (0., .01), (.1,), 1.5)
        with self.assertRaisesRegex(ConfigurationError, 'maksimum'):
            pcb_mesh._audit_domain_axis((0., .01, .02), (0., .02), (.001,), 1.5)
        with self.assertRaisesRegex(ConfigurationError, 'kotwicę'):
            pcb_mesh._audit_domain_axis((0., .01, .02), (0., .005, .02), (.1,.1), 1.5)
        with patch.object(pcb_mesh, '_grade_domain_axis', side_effect=lambda lines, target, budget: lines):
            with self.assertRaisesRegex(ConfigurationError, 'growth_ratio_limit'):
                make_pcb_domain_mesh(self.geometry(), settings())

    def test_padding_frequency_changes_domain_not_inner_resolution(self):
        geometry = self.geometry()
        value = simulation_config()
        first = self.assert_domain(geometry, settings(value))
        value['result_frequency_hz'][0] = 1.35e9
        second = self.assert_domain(geometry, settings(value))
        self.assertNotEqual(first.pml_start_min_m, second.pml_start_min_m)
        plan = make_pcb_mesh_anchor_plan(geometry)
        for required,a,b in zip((plan.x_required_m,plan.y_required_m,plan.z_required_m),
                               (first.x_lines_m,first.y_lines_m,first.z_lines_m),
                               (second.x_lines_m,second.y_lines_m,second.z_lines_m)):
            self.assertEqual(tuple(x for x in a if required[0]<=x<=required[-1]),
                             tuple(x for x in b if required[0]<=x<=required[-1]))

    def test_excitation_changes_resolution_not_requested_padding(self):
        geometry = self.geometry(gap=20,width=8)
        value = simulation_config()
        first = self.assert_domain(geometry, settings(value))
        value['excitation'] = dict(center_hz=1.6e9, cutoff_hz=.5e9)
        second = self.assert_domain(geometry, settings(value))
        self.assertEqual(first.pml_start_min_m, second.pml_start_min_m)
        self.assertEqual(first.pml_start_max_m, second.pml_start_max_m)
        plan = make_pcb_mesh_anchor_plan(geometry)
        def inner_x(mesh):
            return tuple(x for x in mesh.x_lines_m if plan.x_required_m[0]<=x<=plan.x_required_m[-1])
        self.assertNotEqual(inner_x(first), inner_x(second))

    def test_solver_plane_protection(self):
        for plane in ('copper','substrate'):
            for residue in (-5e-11,5e-11):
                with self.subTest(plane=plane,residue=residue):
                    geometry = self.geometry()
                    if plane == 'copper':
                        geometry.copper[0] = replace(geometry.copper[0], z_m=residue)
                    else:
                        geometry.substrate = replace(geometry.substrate, z_max_m=residue)
                    validate_pcb_geometry(geometry)
                    before = geometry.as_dict()
                    with self.assertRaisesRegex(ConfigurationError, 'dokładnie z=0'):
                        make_pcb_domain_mesh(geometry, settings())
                    self.assertEqual(before, geometry.as_dict())


if __name__ == '__main__':
    unittest.main()
