from dataclasses import asdict, replace
from math import pi
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import BoardOutline
from antenna_lab.solvers.openems_pcb import (install_pcb_geometry, prepare_pcb_csx,
    install_pcb_lumped_port, prepare_pcb_native_model, configure_pcb_fdtd,
    write_pcb_xml, prepare_pcb_xml_model)
from antenna_lab.pcb.port import resolve_pcb_lumped_port
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


class Engine:
    def __init__(self, mutation=None, null=False, **kwargs):
        self.kwargs=kwargs
        self.calls=[]
        self.mutation=mutation
        self.port=None if null else object()

    def SetCSX(self, csx):
        self.csx=csx
        self.calls.append(('SetCSX',csx))

    def AddLumpedPort(self,*args,**kwargs):
        # Geometry must be installed before the port; no other native methods exist.
        assert self.csx.materials and len(self.csx.metals[0][1].polygons)>0
        self.calls.append(('AddLumpedPort',args,kwargs))
        if self.mutation: self.mutation(self.csx.grid)
        return self.port


class NativePcbPortTests(unittest.TestCase):
    def setup_model(self, gap=2., width=1., angled=False, mutation=None, null=False):
        geometry=fixtures.PcbMeshTests().geometry(gap=gap,width=width,angled=angled).normalized_geometry
        experiment=replace(settings(),reference_impedance_ohm=75)
        mesh=make_pcb_domain_mesh(geometry,experiment)
        csx=CSX()
        install_pcb_geometry(csx,geometry,mesh,experiment)
        engine=Engine(mutation=mutation,null=null)
        engine.SetCSX(csx)
        return engine,csx,geometry,mesh,experiment

    def test_exact_call_residue_wide_small_metadata_no_mutation(self):
        for gap,width,angled in ((2.,1.,False),(.5,4.,False),(.1,.3,False),(.5,4.,True)):
            with self.subTest(gap=gap,width=width,angled=angled):
                engine,csx,g,m,s=self.setup_model(gap,width,angled)
                before=(g.as_dict(),asdict(m),asdict(s),dict(csx.grid.lines))
                native,spec,meta=install_pcb_lumped_port(engine,csx,g,m,s)
                self.assertIs(native,engine.port)
                self.assertEqual(spec,resolve_pcb_lumped_port(g,m,s))
                self.assertEqual(engine.calls,[('SetCSX',csx),('AddLumpedPort',
                    (spec.port_nr,75,list(spec.start_m),list(spec.stop_m),'x',1.),{'priority':5})])
                self.assertEqual(meta,{**asdict(spec),'surface_plane_z_m':0.,'model':'planar_lumped_port'})
                second=Engine();second.SetCSX(csx)
                self.assertEqual(meta,install_pcb_lumped_port(second,csx,g,m,s)[2])
                meta['start_m']=(123.,456.,789.)
                self.assertEqual(before,(g.as_dict(),asdict(m),asdict(s),dict(csx.grid.lines)))
                if angled:
                    self.assertNotEqual((g.port.negative_xy_m[1]+g.port.positive_xy_m[1])/2,0.)

    def test_native_mutations_and_null(self):
        def remove(grid): grid.lines['z']=tuple(z for z in grid.lines['z'] if z!=0.)
        def add(grid): grid.lines['x']=tuple(sorted((*grid.lines['x'],123.)))
        def change(grid): grid.lines['y']=(grid.lines['y'][0]-.001,*grid.lines['y'][1:])
        def unit(grid): grid.unit=.001
        for mutation in (remove,add,change,unit):
            with self.subTest(mutation=mutation.__name__):
                e,c,g,m,s=self.setup_model(mutation=mutation)
                with self.assertRaisesRegex(ConfigurationError,'instalacja portu zmodyfikowała zamrożoną siatkę'):
                    install_pcb_lumped_port(e,c,g,m,s)
                self.assertEqual(len(e.calls),2)
        e,c,g,m,s=self.setup_model(null=True)
        with self.assertRaisesRegex(ConfigurationError,'AddLumpedPort.*None'):
            install_pcb_lumped_port(e,c,g,m,s)

    def test_preflight_does_not_touch_engine(self):
        for failure in ('anchor','contact','grid','unit'):
            e,c,g,m,s=self.setup_model()
            before=list(e.calls)
            if failure=='anchor': m=replace(m,z_lines_m=tuple(z for z in m.z_lines_m if z!=0.))
            elif failure=='contact':
                copper=g.copper[0]
                g.copper[0]=replace(copper,vertices_xy_m=tuple((x,y/4) for x,y in copper.vertices_xy_m))
                m=make_pcb_domain_mesh(g,s)
            elif failure=='grid': c.grid.lines['x']=c.grid.lines['x'][1:]
            else: c.grid.unit=.001
            with self.subTest(failure=failure), self.assertRaises(ConfigurationError):
                install_pcb_lumped_port(e,c,g,m,s)
            self.assertEqual(e.calls,before)

    def test_preparation_order_and_engine_settings(self):
        g=fixtures.PcbMeshTests().geometry().normalized_geometry
        s=replace(settings(),max_timesteps=12345,end_criteria=2e-5)
        csx=CSX();created=[]
        def factory(**kwargs):
            engine=Engine(**kwargs);created.append(engine);return engine
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=factory),SimpleNamespace(ContinuousStructure=lambda:csx))):
            engine,actual,port,mesh,spec,meta=prepare_pcb_native_model(g,s)
        self.assertEqual(created,[engine])
        self.assertIs(actual,csx)
        self.assertIs(port,engine.port)
        self.assertEqual(engine.kwargs,{'NrTS':12345,'EndCriteria':2e-5})
        self.assertEqual([call[0] for call in engine.calls],['SetCSX','AddLumpedPort'])
        self.assertEqual(mesh,make_pcb_domain_mesh(g,s))
        self.assertEqual(meta['engine'],{'max_timesteps':12345,'end_criteria':2e-5})
        self.assertEqual(meta['port'],{**asdict(spec),'surface_plane_z_m':0.,'model':'planar_lumped_port'})
        import json
        json.dumps(meta,allow_nan=False)  # no native objects leaked into metadata


class XmlEngine(Engine):
    def __init__(self, fault=None, xml_mode='valid', **kwargs):
        super().__init__(**kwargs)
        self.fault=fault
        self.xml_mode=xml_mode

    def SetGaussExcite(self, center, cutoff):
        self.calls.append(('SetGaussExcite',center,cutoff))
        if self.fault=='excitation': self.csx.grid.lines['x']=self.csx.grid.lines['x'][1:]

    def SetBoundaryCond(self, boundaries):
        self.calls.append(('SetBoundaryCond',list(boundaries)))
        if self.fault=='boundary': self.csx.grid.unit=.001

    def Write2XML(self, path):
        self.calls.append(('Write2XML',path))
        if self.fault=='xml': self.csx.grid.lines['z']=self.csx.grid.lines['z'][1:]
        if self.xml_mode=='missing': return
        target=Path(path)
        if self.xml_mode=='directory': target.mkdir();return
        target.write_text({'valid':'<model/>','empty':'','malformed':'<broken>'}[self.xml_mode],encoding='utf-8')

    def Run(self,*args,**kwargs):
        raise AssertionError('FDTD forbidden')


class PcbXmlTests(unittest.TestCase):
    def installed(self, **kwargs):
        _,csx,g,m,s=NativePcbPortTests().setup_model()
        engine=XmlEngine(**kwargs);engine.SetCSX(csx)
        return engine,csx,g,m,s

    def test_configure_exact_calls_metadata_determinism(self):
        for count in (8,12):
            e,c,g,m,s=self.installed()
            m=replace(m,pml_cells=count);s=replace(s,pml_cells=count)
            before=(g.as_dict(),asdict(m),asdict(s),dict(c.grid.lines))
            meta=configure_pcb_fdtd(e,c,m,s)
            self.assertEqual(e.calls,[('SetCSX',c),('SetGaussExcite',s.excitation_center_hz,s.excitation_cutoff_hz),
                                     ('SetBoundaryCond',[f'PML_{count}']*6)])
            self.assertEqual(meta['excitation'],{'type':'gaussian','center_hz':1.42e9,'cutoff_hz':.2e9,
                                                 'mesh_design_frequency_hz':1.62e9})
            self.assertEqual(meta['boundary_conditions'],{'order':['x_min','x_max','y_min','y_max','z_min','z_max'],
                                                          'values':[f'PML_{count}']*6,'pml_cells':count})
            other=XmlEngine();other.SetCSX(c)
            self.assertEqual(meta,configure_pcb_fdtd(other,c,m,s))
            meta['boundary_conditions']['values'].clear()
            self.assertEqual(before,(g.as_dict(),asdict(m),asdict(s),dict(c.grid.lines)))

    def test_configure_grid_mutation_and_pml_preflight(self):
        for fault,context in (('excitation','SetGaussExcite'),('boundary','SetBoundaryCond')):
            e,c,g,m,s=self.installed(fault=fault)
            with self.assertRaisesRegex(ConfigurationError,context): configure_pcb_fdtd(e,c,m,s)
            if fault=='excitation': self.assertNotIn('SetBoundaryCond',[v[0] for v in e.calls])
        for count in (5,21,True,1.5,12):
            e,c,g,m,s=self.installed()
            with self.assertRaisesRegex(ConfigurationError,'pml_cells'):
                configure_pcb_fdtd(e,c,m,replace(s,pml_cells=count))
            self.assertEqual(e.calls,[('SetCSX',c)])
        e,c,g,m,s=self.installed();c.grid.unit=.001
        with self.assertRaisesRegex(ConfigurationError,'before FDTD'): configure_pcb_fdtd(e,c,m,s)
        self.assertEqual(e.calls,[('SetCSX',c)])

    def test_xml_failure_modes_and_grid(self):
        for mode in ('missing','empty','malformed','directory'):
            with self.subTest(mode=mode), TemporaryDirectory() as directory:
                e,c,g,m,s=self.installed(xml_mode=mode)
                with self.assertRaisesRegex(ConfigurationError,'PCB XML'):
                    write_pcb_xml(e,c,m,Path(directory)/'model.xml')
        with TemporaryDirectory() as directory:
            e,c,g,m,s=self.installed(fault='xml')
            with self.assertRaisesRegex(ConfigurationError,'after Write2XML'):
                write_pcb_xml(e,c,m,Path(directory)/'model.xml')
        with TemporaryDirectory() as directory:
            e,c,g,m,s=self.installed();c.grid.unit=.001
            with self.assertRaisesRegex(ConfigurationError,'before Write2XML'):
                write_pcb_xml(e,c,m,Path(directory)/'model.xml')
            self.assertEqual(e.calls,[('SetCSX',c)])

    def test_full_xml_path_order_wide_small_metadata_no_mutation(self):
        for gap,width in ((2.,1.),(.5,4.),(.1,.3)):
            with self.subTest(gap=gap,width=width), TemporaryDirectory() as directory:
                g=fixtures.PcbMeshTests().geometry(gap=gap,width=width).normalized_geometry
                s=settings();before=(g.as_dict(),asdict(s))
                path=Path(directory)/'nested'/'deeper'/'model.xml'
                outputs=[]
                for supplied in (path,str(path)):
                    csx=CSX();engine=XmlEngine(NrTS=s.max_timesteps,EndCriteria=s.end_criteria)
                    with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                            SimpleNamespace(openEMS=lambda **kw:engine),SimpleNamespace(ContinuousStructure=lambda:csx))):
                        result=prepare_pcb_xml_model(g,s,supplied)
                    e,c,p,m,spec,meta=result
                    self.assertIs(e,engine);self.assertIs(c,csx);self.assertIs(p,engine.port)
                    self.assertEqual([v[0] for v in engine.calls],
                                     ['SetCSX','AddLumpedPort','SetGaussExcite','SetBoundaryCond','Write2XML'])
                    self.assertEqual(engine.calls[-1],('Write2XML',str(supplied)))
                    self.assertEqual(meta['xml'],{'path':str(supplied),'size_bytes':path.stat().st_size,'parse_status':'passed'})
                    self.assertGreater(meta['xml']['size_bytes'],0)
                    self.assertEqual(meta['port'],{**asdict(spec),'surface_plane_z_m':0.,'model':'planar_lumped_port'})
                    self.assertEqual(set(meta),{'geometry','port','engine','excitation','boundary_conditions','xml'})
                    self.assertEqual(m,make_pcb_domain_mesh(g,s))
                    import json
                    json.dumps(meta,allow_nan=False)
                    outputs.append(meta)
                self.assertEqual(outputs[0],outputs[1])
                self.assertEqual(before,(g.as_dict(),asdict(s)))
                self.assertEqual([p for p in Path(directory).rglob('*') if p.is_file()],[path])


if __name__=='__main__':
    unittest.main()
