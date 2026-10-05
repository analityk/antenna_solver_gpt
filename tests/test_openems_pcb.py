from dataclasses import asdict, replace
from math import pi
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import BoardOutline
from antenna_lab.solvers.openems_pcb import install_pcb_geometry, prepare_pcb_csx
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh, make_pcb_mesh_anchor_plan
import test_pcb_mesh as fixtures
from test_pcb_simulation import settings


class Grid:
    def __init__(self, alter=None, unit=1.0):
        self.lines = {}
        self.calls = []
        self.alter = alter
        self.unit = unit

    def SetDeltaUnit(self, unit):
        self.calls.append(('unit', unit))

    def GetDeltaUnit(self):
        return self.unit

    def SetLines(self, axis, lines):
        self.calls.append((axis, lines))
        self.lines[axis] = tuple(lines)

    def GetLines(self, axis):
        return self.alter(axis, self.lines[axis]) if self.alter else self.lines[axis]


class Material:
    def __init__(self):
        self.polygons = []

    def AddLinPoly(self, **kwargs):
        self.polygons.append(kwargs)


class Metal:
    def __init__(self):
        self.polygons = []

    def AddPolygon(self, **kwargs):
        self.polygons.append(kwargs)


class CSX:
    # Unsupported calls (box, sheet, port, smoothing, solver, XML) fail naturally.
    def __init__(self, grid=None):
        self.grid = grid if grid is not None else Grid()
        self.materials = []
        self.metals = []
        self.grid_accesses = 0

    def GetGrid(self):
        self.grid_accesses += 1
        return self.grid

    def AddMaterial(self, name, **kwargs):
        material = Material()
        self.materials.append((name, kwargs, material))
        return material

    def AddMetal(self, name):
        metal = Metal()
        self.metals.append((name, metal))
        return metal


class OpenemsPcbTests(unittest.TestCase):
    def geometry(self, **kwargs):
        return fixtures.PcbMeshTests().geometry(**kwargs).normalized_geometry

    def test_install_grid_material_copper_metadata_no_mutation(self):
        geometry, experiment = self.geometry(), settings()
        mesh = make_pcb_domain_mesh(geometry, experiment)
        before = (geometry.as_dict(), asdict(experiment), asdict(mesh))
        csx = CSX()
        meta = install_pcb_geometry(csx, geometry, mesh, experiment)
        axes = (mesh.x_lines_m, mesh.y_lines_m, mesh.z_lines_m)
        self.assertEqual(csx.grid.calls, [('unit',1.0), *zip('xyz',axes)])
        self.assertEqual(meta['delta_unit_m'],1.0)
        self.assertEqual(meta['grid_line_counts'],dict(zip('xyz',map(len,axes))))
        for i,axis in enumerate('xyz'):
            self.assertIn(mesh.pml_start_min_m[i],csx.grid.GetLines(axis))
            self.assertIn(mesh.pml_start_max_m[i],csx.grid.GetLines(axis))
        self.assertEqual(len(csx.materials),1)
        name, props, material = csx.materials[0]
        expected_kappa = 2*pi*1.42e9*8.8541878128e-12*4.3*.018
        self.assertEqual(name,'pcb_substrate')
        self.assertEqual(props['epsilon'],4.3)
        self.assertAlmostEqual(props['kappa'],expected_kappa,delta=1e-16)
        self.assertEqual(meta['substrate'],dict(epsilon_r=4.3,loss_tangent_input=.018,
            loss_reference_frequency_hz=1.42e9,kappa_s_per_m=props['kappa'],loss_model='constant_kappa',
            z_min_m=-.0016,z_max_m=0.0))
        self.assertEqual(material.polygons,[dict(points=[list(v) for v in zip(*geometry.substrate.outline.vertices_xy_m)],
            norm_dir='z',elevation=-.0016,length=.0016,priority=0)])
        self.assertEqual(len(csx.metals),1)
        self.assertEqual(csx.metals[0][0],'pcb_top_copper_PEC')
        polygons=csx.metals[0][1].polygons
        self.assertEqual(len(polygons),len(geometry.copper))
        for polygon,copper in zip(polygons,geometry.copper):
            self.assertEqual(polygon,dict(points=[list(v) for v in zip(*copper.vertices_xy_m)],
                norm_dir='z',elevation=0.0,priority=10))
        self.assertEqual(meta['copper'],dict(model='PEC',polygon_count=2,ids=[p.id for p in geometry.copper]))
        self.assertEqual(meta,install_pcb_geometry(CSX(),geometry,mesh,experiment))
        meta['copper']['ids'].clear()
        self.assertEqual(before,(geometry.as_dict(),asdict(experiment),asdict(mesh)))

    def test_lossless_and_configured_reference(self):
        geometry,experiment=self.geometry(),settings()
        mesh=make_pcb_domain_mesh(geometry,experiment)
        csx=CSX()
        doubled=replace(experiment,loss_reference_frequency_hz=2*experiment.loss_reference_frequency_hz)
        meta=install_pcb_geometry(csx,geometry,mesh,doubled)
        expected=2*pi*doubled.loss_reference_frequency_hz*8.8541878128e-12*4.3*.018
        self.assertAlmostEqual(meta['substrate']['kappa_s_per_m'],expected,delta=1e-16)
        geometry.substrate=replace(geometry.substrate,loss_tangent=0.)
        csx=CSX()
        meta=install_pcb_geometry(csx,geometry,mesh,experiment)
        self.assertEqual(meta['substrate']['kappa_s_per_m'],0.)
        self.assertEqual(csx.materials[0][1]['kappa'],0.)

    def test_nonrectangular_outline_and_closing_vertices(self):
        geometry,experiment=self.geometry(),settings()
        vertices=((-0.02,-0.02),(0.025,-0.018),(0.021,0.024),(-0.015,0.019),(-0.02,-0.02))
        outline=BoardOutline(vertices)
        geometry.outline=outline
        geometry.substrate=replace(geometry.substrate,outline=outline)
        for i,copper in enumerate(geometry.copper):
            geometry.copper[i]=replace(copper,vertices_xy_m=copper.vertices_xy_m+(copper.vertices_xy_m[0],))
        mesh=make_pcb_domain_mesh(geometry,experiment)
        csx=CSX()
        install_pcb_geometry(csx,geometry,mesh,experiment)
        self.assertEqual(csx.materials[0][2].polygons[0]['points'],
                         [[-.02,.025,.021,-.015],[-.02,-.018,.024,.019]])
        for polygon,copper in zip(csx.metals[0][1].polygons,geometry.copper):
            self.assertEqual(polygon['points'],[list(v) for v in zip(*copper.vertices_xy_m[:-1])])

    def test_readback_missing_zero_pml_and_other_line(self):
        geometry,experiment=self.geometry(),settings()
        mesh=make_pcb_domain_mesh(geometry,experiment)
        plan=make_pcb_mesh_anchor_plan(geometry)
        ordinary=next(x for x in mesh.x_lines_m if x not in plan.x_required_m and x not in
                      (mesh.pml_start_min_m[0],mesh.pml_start_max_m[0]))
        for axis,coordinate,regex in (('z',0.,'grid z.*0.0'),
                                     ('x',mesh.pml_start_min_m[0],'grid x.*brak'),
                                     ('x',ordinary,'grid x.*różni')):
            with self.subTest(axis=axis,coordinate=coordinate):
                grid=Grid(alter=lambda a,lines: tuple(x for x in lines if x!=coordinate) if a==axis else lines)
                csx=CSX(grid)
                with self.assertRaisesRegex(ConfigurationError,regex):
                    install_pcb_geometry(csx,geometry,mesh,experiment)
                self.assertEqual(csx.materials,[])
                self.assertEqual(csx.metals,[])
        csx=CSX(Grid(unit=.001))
        with self.assertRaisesRegex(ConfigurationError,'delta unit'):
            install_pcb_geometry(csx,geometry,mesh,experiment)
        self.assertEqual(csx.materials,[])

    def test_mismatch_rejected_before_touching_csx(self):
        geometry,experiment=self.geometry(),settings()
        mesh=make_pcb_domain_mesh(geometry,experiment)
        bad_meshes=[replace(mesh,x_lines_m=tuple(x for x in mesh.x_lines_m if x!=geometry.port.negative_xy_m[0])),
                    replace(mesh,z_lines_m=tuple(z for z in mesh.z_lines_m if z!=0.)),
                    replace(mesh,pml_cells=12),
                    replace(mesh,pml_start_min_m=(123.,*mesh.pml_start_min_m[1:]))]
        for bad in bad_meshes:
            with self.subTest(mesh=bad.pml_cells):
                csx=CSX()
                with self.assertRaises(ConfigurationError):
                    install_pcb_geometry(csx,geometry,bad,experiment)
                self.assertEqual(csx.grid_accesses,0)
                self.assertEqual(csx.materials,[])
                self.assertEqual(csx.metals,[])
        for plane in ('copper','substrate'):
            geometry=self.geometry()
            if plane=='copper': geometry.copper[0]=replace(geometry.copper[0],z_m=5e-11)
            else: geometry.substrate=replace(geometry.substrate,z_max_m=-5e-11)
            csx=CSX()
            with self.assertRaisesRegex(ConfigurationError,'dokładnie z=0'):
                install_pcb_geometry(csx,geometry,mesh,experiment)
            self.assertEqual(csx.grid_accesses,0)

    def test_prepare_native_loader_without_engine(self):
        geometry,experiment=self.geometry(),settings()
        csx=CSX()
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(object(),SimpleNamespace(
                ContinuousStructure=lambda:csx))) as loader:
            actual,mesh,meta=prepare_pcb_csx(geometry,experiment)
        loader.assert_called_once_with()
        self.assertIs(actual,csx)
        self.assertEqual(mesh,make_pcb_domain_mesh(geometry,experiment))
        self.assertEqual(meta['copper']['polygon_count'],2)
        geometry.copper=[]
        with patch('antenna_lab.solvers.openems.native_modules') as loader:
            with self.assertRaises(ConfigurationError):
                prepare_pcb_csx(geometry,experiment)
            loader.assert_not_called()

    def test_wide_small_installation(self):
        for gap,width in ((.5,4.),(.1,.3)):
            with self.subTest(gap=gap,width=width):
                geometry,experiment=self.geometry(gap=gap,width=width),settings()
                mesh=make_pcb_domain_mesh(geometry,experiment)
                csx=CSX()
                install_pcb_geometry(csx,geometry,mesh,experiment)
                for axis,lines in zip('xyz',(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)):
                    self.assertEqual(csx.grid.GetLines(axis),lines)


if __name__=='__main__':
    unittest.main()
