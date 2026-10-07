"""Integer mesh mechanics only: no native FDTD and no production policy switch."""
from dataclasses import asdict, FrozenInstanceError, replace
from decimal import Decimal
from fractions import Fraction
import json
from math import nextafter, prod
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.quantization import quantize_pcb_geometry
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.solvers.pcb_mesh import derive_pcb_physical_mesh_policy, make_pcb_domain_mesh
from antenna_lab.solvers.pcb_lattice_mesh import (
    PcbLatticeAnchorPlan, make_pcb_lattice_domain_mesh, _subdivide_ticks,
    _grade_ticks, _maximum_ticks, _audit_axis,
)
from test_pcb_model import fixture
from test_pcb_simulation import settings


def example(quantum_nm=10000):
    """Same 20 mm board, 2 mm gap, 1 mm width, 1.6 mm depth at all quanta.

    Explicit reviewed integer anchors: no projection of legacy float mesh lines.
    This ticket deliberately does not install a production anchor selector.
    """
    grid = PcbGrid(quantum_nm)
    factor = 100000 // quantum_nm
    axis = lambda values: tuple(v*factor for v in values)
    plan = PcbLatticeAnchorPlan(
        axis((-100,-60,-35,-10,0,10,35,60,100)),
        axis((-100,-20,-5,0,5,20,100)), axis((-16,0)),
        axis((-10,10)), axis((-5,5)),
    )
    geometry = normalize_port_orientation(fixture())[0]
    policy = derive_pcb_physical_mesh_policy(geometry,settings())
    return grid,plan,policy


def steps(axis):
    return tuple(b-a for a,b in zip(axis,axis[1:]))


class PcbLatticeMeshTests(unittest.TestCase):
    def test_all_four_quanta_audit_determinism_and_si_export(self):
        for quantum in (100000,10000,1000,100):
            with self.subTest(quantum_nm=quantum):
                grid,plan,policy = example(quantum)
                before = asdict(plan),asdict(policy)
                mesh = make_pcb_lattice_domain_mesh(plan,policy,grid)
                self.assertEqual(mesh,make_pcb_lattice_domain_mesh(plan,policy,grid))
                self.assertEqual(before,(asdict(plan),asdict(policy)))
                self.assertEqual(mesh.cell_count,prod(mesh.shape_cells))
                self.assertLessEqual(mesh.cell_count,policy.max_cells)
                widths = tuple(w for a in mesh.axes_ticks for w in steps(a))
                self.assertEqual(mesh.min_cell_ticks,min(widths))
                self.assertEqual(mesh.max_cell_ticks,max(widths))
                self.assertGreaterEqual(min(widths),1)
                for axis,required in zip(mesh.axes_ticks,(plan.x_required_ticks,plan.y_required_ticks,plan.z_required_ticks)):
                    self.assertTrue(all(type(v) is int for v in axis))
                    self.assertTrue(set(required).issubset(axis))
                    self.assertTrue(all(a < b for a,b in zip(axis,axis[1:])))
                    self.assertLessEqual(max(Fraction(max(a,b),min(a,b)) for a,b in zip(steps(axis),steps(axis)[1:])),Fraction('1.4'))
                info = mesh.metadata()
                self.assertEqual(info['off_grid_line_count'],0)
                self.assertEqual(info['grid_quantum_um'],quantum/1000)
                json.dumps(info,allow_nan=False)
                self.assertEqual(mesh.min_cell_ticks*grid.quantum_decimal_m,Decimal(str(info['min_step_m'])))
                native = mesh.to_domain_mesh()
                self.assertEqual(native.shape_cells,mesh.shape_cells)
                self.assertEqual(native.cell_count,mesh.cell_count)
                for axis,export in zip(mesh.axes_ticks,(native.x_lines_m,native.y_lines_m,native.z_lines_m)):
                    self.assertEqual(export,tuple(grid.to_metres(t) for t in axis))
                    self.assertEqual(axis,tuple(grid.nearest_tick(x) for x in export))
                self.assertIn(0,native.z_lines_m)
                self.assertEqual(native.min_step_m,grid.to_metres(min(widths)))
                self.assertEqual(native.max_step_m,grid.to_metres(max(widths)))
                with self.assertRaises(FrozenInstanceError):mesh.cell_count=0

    def test_maximum_is_strict_floor_not_nearest_or_float_tie_guard(self):
        for nm in (100000,10000,1000,100):
            grid=PcbGrid(nm);q=grid.quantum_decimal_m
            self.assertEqual(_maximum_ticks(grid,q*Decimal('2.806')),2)
            self.assertEqual(_maximum_ticks(grid,q*Decimal('5.4026666')),5)
            with self.assertRaisesRegex(ConfigurationError,'coarser than required EM resolution'):
                _maximum_ticks(grid,q*Decimal('.999999'))
            with self.assertRaisesRegex(ConfigurationError,'coarser than required EM resolution'):
                _maximum_ticks(grid,nextafter(grid.quantum_m,0.))
        self.assertEqual(_maximum_ticks(PcbGrid(),28.06e-6),2)
        with self.assertRaises(ConfigurationError):_maximum_ticks(PcbGrid(),.12e-6)

    def test_balanced_interval_division_exhaustive_small_cases(self):
        for length in range(1,51):
            for maximum in range(1,21):
                axis = _subdivide_ticks((-13,length-13),(maximum,))
                widths = steps(axis)
                self.assertEqual(sum(widths),length)
                self.assertEqual(len(widths),(length+maximum-1)//maximum)
                self.assertGreaterEqual(min(widths),1)
                self.assertLessEqual(max(widths),maximum)
                self.assertLessEqual(max(widths)-min(widths),1)
                self.assertEqual(axis[0],-13);self.assertEqual(axis[-1],length-13)
                self.assertEqual(axis,_subdivide_ticks((-13,length-13),(maximum,)))
        self.assertEqual(_subdivide_ticks((0,10),(3,)),(0,3,6,8,10))
        self.assertEqual(_subdivide_ticks((-7,3,16),(3,5)),(-7,-4,-1,1,3,8,12,16))

    def test_integer_grading_both_transitions_and_progressive_cells(self):
        cases=((40,1,40),(1,40,1),(40,10,3,1,2,8,30),(1,2),(2,3),(17,5,19,2))
        for widths in cases:
            points=[-70]
            for w in widths:points.append(points[-1]+w)
            result=_grade_ticks(tuple(points),Fraction('1.4'),sum(widths))
            self.assertEqual(result,_grade_ticks(tuple(points),Fraction('1.4'),sum(widths)))
            self.assertTrue(set(points).issubset(result))
            self.assertEqual((result[0],result[-1]),(points[0],points[-1]))
            self.assertEqual(sum(steps(result)),sum(widths))
            self.assertTrue(all(type(v) is int for v in result))
            self.assertGreaterEqual(min(steps(result)),1)
            self.assertLessEqual(max(steps(result)),max(widths))
            for a,b in zip(steps(result),steps(result)[1:]):
                self.assertLessEqual(Fraction(max(a,b),min(a,b)),Fraction('1.4'))
        # No legal 1 -> 2 transition at a 1.5 hard limit: tick quantization
        # forces all ones. Budget failure is explicit, never a fractional tick.
        self.assertEqual(_grade_ticks((0,1,3),Fraction('1.4'),3),(0,1,2,3))
        with self.assertRaisesRegex(ConfigurationError,'cannot satisfy growth.*max_cells'):
            _grade_ticks((0,1,41),Fraction('1.4'),3)

    def test_exact_duplicate_identity_no_coordinate_tolerance(self):
        grid,plan,policy=example()
        repeated=replace(plan,x_required_ticks=tuple(reversed(plan.x_required_ticks))+(0,0))
        self.assertEqual(make_pcb_lattice_domain_mesh(plan,policy,grid),
                         make_pcb_lattice_domain_mesh(repeated,policy,grid))
        # Separate consecutive ticks remain separate regardless of legacy tolerances.
        thin=replace(plan,x_required_ticks=plan.x_required_ticks+(1,))
        with self.assertRaisesRegex(ConfigurationError,'max_cells'):
            make_pcb_lattice_domain_mesh(thin,replace(policy,max_cells=100000),grid)
        for bad in (0.,True,Decimal(0)):
            with self.assertRaisesRegex(ConfigurationError,'integer ticks'):
                make_pcb_lattice_domain_mesh(replace(plan,x_required_ticks=plan.x_required_ticks+(bad,)),policy,grid)

    def test_padding_ceiling_exact_pml_and_bounds_metadata(self):
        grid,plan,policy=example()
        policy=replace(policy,air_padding_m=.00123456)
        mesh=make_pcb_lattice_domain_mesh(plan,policy,grid)
        padding=124
        required=(plan.x_required_ticks,plan.y_required_ticks,plan.z_required_ticks)
        native=mesh.to_domain_mesh()
        for i,(axis,core) in enumerate(zip(mesh.axes_ticks,required)):
            low,high=mesh.pml_start_min_ticks[i],mesh.pml_start_max_ticks[i]
            self.assertEqual(low,min(core)-padding);self.assertEqual(high,max(core)+padding)
            self.assertGreaterEqual(grid.to_metres(padding),policy.air_padding_m)
            self.assertEqual(axis.index(low),policy.pml_cells)
            self.assertEqual(len(axis)-1-axis.index(high),policy.pml_cells)
            w=steps(axis);n=policy.pml_cells
            self.assertEqual(w[:n],(w[n],)*n)
            self.assertEqual(w[-n:],(w[-n-1],)*n)
            self.assertEqual(native.pml_start_min_m[i],grid.to_metres(low))
            self.assertEqual(native.pml_start_max_m[i],grid.to_metres(high))
            self.assertEqual(native.outer_min_m[i],grid.to_metres(axis[0]))
            self.assertEqual(native.outer_max_m[i],grid.to_metres(axis[-1]))
        with self.assertRaises(ConfigurationError):
            make_pcb_lattice_domain_mesh(plan,replace(policy,air_padding_m=0),grid)

    def test_local_maxima_feature_counts_and_multilayer_z_limits(self):
        grid,plan,policy=example()
        plan=replace(plan,z_required_ticks=(-160,-80,0))
        mesh=make_pcb_lattice_domain_mesh(plan,policy,grid,substrate_z_max_steps_m=(.000117,.000237))
        for axis,bounds,maximum in (
                (mesh.x_lines_ticks,plan.port_x_ticks,policy.max_port_gap_step_m),
                (mesh.y_lines_ticks,plan.port_y_ticks,policy.max_port_width_step_m),
                (mesh.z_lines_ticks,(-160,-80),.000117),
                (mesh.z_lines_ticks,(-80,0),.000237)):
            lo,hi=map(axis.index,bounds)
            self.assertLessEqual(max(steps(axis[lo:hi+1])),grid.floor_tick(str(maximum)))
        self.assertGreaterEqual(mesh.x_lines_ticks.index(100)-mesh.x_lines_ticks.index(-100),policy.min_port_gap_cells)
        self.assertGreaterEqual(mesh.y_lines_ticks.index(50)-mesh.y_lines_ticks.index(-50),policy.min_port_width_cells)
        self.assertGreaterEqual(mesh.z_lines_ticks.index(0)-mesh.z_lines_ticks.index(-160),policy.min_substrate_cells_z)
        with self.assertRaisesRegex(ConfigurationError,'per substrate interval'):
            make_pcb_lattice_domain_mesh(plan,policy,grid,substrate_z_max_steps_m=(.0001,))

    def test_existing_quality_policies_supply_the_physical_resolution(self):
        from antenna_lab.pcb.gerber_quality import gerber_quality_settings
        grid,plan,_=example()
        raw=normalize_port_orientation(fixture())[0]
        for quality in ('preview','design','verify'):
            s,_=gerber_quality_settings(quality)
            policy=derive_pcb_physical_mesh_policy(raw,s)
            mesh=make_pcb_lattice_domain_mesh(plan,policy,grid)
            self.assertEqual(mesh.pml_cells,s.pml_cells)
            self.assertLessEqual(mesh.worst_growth_ratio,s.growth_ratio_limit)
            for axis,low,high,minimum in (
                    (mesh.x_lines_ticks,*plan.port_x_ticks,s.min_port_gap_cells),
                    (mesh.y_lines_ticks,*plan.port_y_ticks,s.min_port_width_cells),
                    (mesh.z_lines_ticks,-160,0,s.min_substrate_cells_z)):
                self.assertGreaterEqual(axis.index(high)-axis.index(low),minimum)
            self.assertEqual(mesh.metadata()['off_grid_line_count'],0)

    def test_large_offset_remains_integer_until_explicit_si_export(self):
        grid,plan,policy=example()
        shift=10**22
        shifted=replace(plan,x_required_ticks=tuple(x+shift for x in plan.x_required_ticks),
                        port_x_ticks=tuple(x+shift for x in plan.port_x_ticks))
        normal=make_pcb_lattice_domain_mesh(plan,policy,grid)
        mesh=make_pcb_lattice_domain_mesh(shifted,policy,grid)
        self.assertEqual(mesh.x_lines_ticks,tuple(x+shift for x in normal.x_lines_ticks))
        self.assertEqual(mesh.shape_cells,normal.shape_cells)
        with self.assertRaisesRegex(ConfigurationError,'SI export cannot represent'):
            mesh.to_domain_mesh()

    def test_coarse_quantum_and_invalid_limits_fail_before_axes_allocation(self):
        grid,plan,policy=example()
        cases=({'max_port_gap_step_m':.12e-6}, {'max_air_step_m':0},
               {'max_substrate_z_step_m':-1}, {'max_substrate_xy_step_m':float('nan')},
               {'max_port_width_step_m':float('inf')}, {'min_port_width_cells':1000},
               {'min_substrate_cells_z':1000}, {'max_cells':1}, {'max_cells':False},
               {'pml_cells':5}, {'growth_ratio_target':1}, {'growth_ratio_limit':1.3})
        for changes in cases:
            with self.subTest(changes=changes),patch(
                    'antenna_lab.solvers.pcb_lattice_mesh._subdivide_ticks',side_effect=AssertionError('allocated')):
                with self.assertRaises(ConfigurationError):
                    make_pcb_lattice_domain_mesh(plan,replace(policy,**changes),grid)

    def test_final_budget_exact_boundary_and_no_overspend(self):
        grid,plan,policy=example()
        mesh=make_pcb_lattice_domain_mesh(plan,policy,grid)
        self.assertEqual(mesh,make_pcb_lattice_domain_mesh(plan,replace(policy,max_cells=mesh.cell_count),grid))
        with self.assertRaisesRegex(ConfigurationError,'max_cells'):
            make_pcb_lattice_domain_mesh(plan,replace(policy,max_cells=mesh.cell_count-1),grid)

    def test_port_and_drill_required_anchors_are_not_created_or_snapped(self):
        grid,plan,policy=example()
        for changed in (replace(plan,x_required_ticks=tuple(x for x in plan.x_required_ticks if x != 0)),
                        replace(plan,port_y_ticks=(-50,51)),replace(plan,z_required_ticks=(-160,1)),
                        replace(plan,drill_centres_xy_ticks=((123,456),))):
            with self.assertRaises(ConfigurationError):make_pcb_lattice_domain_mesh(changed,policy,grid)
        via=replace(plan,drill_centres_xy_ticks=((350,200),))
        mesh=make_pcb_lattice_domain_mesh(via,policy,grid)
        self.assertEqual(mesh.drill_centres_xy_ticks,((350,200),))
        self.assertEqual(mesh.to_domain_mesh().drill_centres_xy_m,((.0035,.002),))

    def test_no_off_grid_style_width_or_subquantum_interval(self):
        grid,plan,policy=example()
        mesh=make_pcb_lattice_domain_mesh(plan,policy,grid)
        physical_widths={Decimal(w)*grid.quantum_decimal_m for axis in mesh.axes_ticks for w in steps(axis)}
        self.assertNotIn(Decimal('0.00002806'),physical_widths)
        self.assertNotIn(Decimal('0.000054026666'),physical_widths)
        self.assertNotIn(Decimal('0.00000012'),physical_widths)
        self.assertTrue(all(w % grid.quantum_decimal_m == 0 for w in physical_widths))

    def test_audit_rejects_off_grid_missing_anchor_and_oversized_cell(self):
        for axis,bounds,limits in (
                ((0,1.5,3),(0,3),(2,)), ((0,0,3),(0,3),(3,)),
                ((0,3),(0,1,3),(3,3)), ((0,3),(0,3),(2,)),
                ((0,1,3),(0,3),(3,))):
            with self.assertRaises(ConfigurationError):_audit_axis(axis,bounds,limits,Fraction('1.5'))

    def test_detached_quantized_anchors_and_legacy_path_unchanged(self):
        grid,plan,policy=example()
        raw=normalize_port_orientation(fixture())[0];before=raw.as_dict();s=settings()
        legacy=make_pcb_domain_mesh(raw,s)
        quantized,audit=quantize_pcb_geometry(raw,grid)
        self.assertEqual(audit['topology_status'],'PASS')
        self.assertEqual(plan.port_x_ticks,(quantized.port.negative[0],quantized.port.positive[0]))
        self.assertEqual(plan.port_y_ticks,(-quantized.port.width//2,quantized.port.width//2))
        self.assertEqual(plan.z_required_ticks,(quantized.dielectrics[0].bottom,0))
        with patch('antenna_lab.solvers.pcb_mesh._merge',side_effect=AssertionError('legacy merge used')),patch(
                'antenna_lab.solvers.pcb_mesh._grade_domain_axis',side_effect=AssertionError('float grading used')):
            make_pcb_lattice_domain_mesh(plan,policy,grid)
        self.assertEqual(raw.as_dict(),before)
        self.assertEqual(legacy,make_pcb_domain_mesh(raw,s))


if __name__ == '__main__':
    unittest.main()
