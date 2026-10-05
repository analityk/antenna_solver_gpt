"""Real supported native binaries through XML only; never execute FDTD."""

import importlib.metadata
from math import cos, sin, radians
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.etree import ElementTree

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import BoardOutline, CopperPolygon, PcbGeometry, PcbPort, Substrate
from antenna_lab.pcb.simulation import PcbSimulationSettings
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.solvers.openems import native_modules
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model


class NativePcbXmlSmokeTest(unittest.TestCase):
    def test_native_pcb_xml(self):
        try:
            ems, csx_module = native_modules()
        except ConfigurationError as exc:
            raise unittest.SkipTest(f'Native openEMS/CSXCAD unavailable: {exc}') from exc
        ems_version = getattr(ems, '__version__', None)
        self.assertEqual(ems_version, '0.37.0rc3', 'Unsupported native openEMS version')
        try:
            csx_version = importlib.metadata.version('CSXCAD')
        except importlib.metadata.PackageNotFoundError:
            csx_version = 'unknown (module loaded; CSXCAD package metadata unavailable)'
        else:
            self.assertEqual(csx_version, '0.7.0rc3', 'Unsupported native CSXCAD version')
        self.assertIsNotNone(csx_module)

        # Rotate the complete source by 37 degrees, then normalize exactly once.
        angle = radians(37)
        c, s = cos(angle), sin(angle)
        def point(x, y):
            return (c*x-s*y+.012, s*x+c*y-.007)
        def polygon(vertices):
            return tuple(point(x,y) for x,y in vertices)
        outline = BoardOutline(polygon(((-.01,-.01),(.01,-.01),(.01,.01),(-.01,.01))))
        negative = CopperPolygon('negative_pad', polygon(((-.004,-.001),(-.0005,-.001),
                                   (-.0005,.001),(-.004,.001))), 0.0)
        positive = CopperPolygon('positive_pad', polygon(((.0005,-.001),(.004,-.001),
                                   (.004,.001),(.0005,.001))), 0.0)
        source = PcbGeometry('pcb', outline, [negative,positive],
                            Substrate(outline,-.0016,0.,4.3,.018),
                            PcbPort('native_smoke',point(-.0005,0.),point(.0005,0.),.002))
        geometry, _ = normalize_port_orientation(source)
        settings = PcbSimulationSettings(
            schema_version=1, result_frequency_hz=(1.30e9,1.42e9,1.50e9),
            excitation_center_hz=1.42e9, excitation_cutoff_hz=.20e9,
            reference_impedance_ohm=50., cells_per_wavelength=20,
            min_substrate_cells_z=4, min_port_gap_cells=2, min_port_width_cells=2,
            growth_ratio_target=1.4, growth_ratio_limit=1.5, max_cells=20_000_000,
            loss_reference_frequency_hz=1.42e9, max_timesteps=100000,
            end_criteria=1e-5, threads=0, air_padding_wavelengths=.25, pml_cells=8)
        with TemporaryDirectory() as directory:
            path = Path(directory)/'model.xml'
            engine, csx, port, mesh, spec, metadata = prepare_pcb_xml_model(geometry, settings, path)
            self.assertIsNotNone(engine)
            self.assertIsNotNone(csx)
            self.assertIsNotNone(port)
            self.assertGreater(mesh.cell_count,0)
            self.assertEqual(mesh.pml_cells,8)
            self.assertEqual((spec.port_nr,spec.exc_dir,spec.reference_impedance_ohm,spec.priority),
                             (1,'x',50.,5))
            self.assertGreater(spec.active_ex_edge_count,0)
            self.assertGreaterEqual(spec.x_cell_count,2)
            self.assertGreaterEqual(spec.y_cell_count,2)
            self.assertEqual(spec.start_m[2],0.)
            self.assertEqual(spec.stop_m[2],0.)
            self.assertIn(0.,mesh.z_lines_m)
            grid = csx.GetGrid()
            self.assertEqual(grid.GetDeltaUnit(),1.)
            for axis,lines in zip('xyz',(mesh.x_lines_m,mesh.y_lines_m,mesh.z_lines_m)):
                self.assertEqual(tuple(grid.GetLines(axis)),lines)
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size,0)
            self.assertEqual(metadata['xml']['parse_status'],'passed')
            ElementTree.parse(path)
            xml = path.read_text(encoding='utf-8')
            self.assertIn('pcb_substrate',xml)
            self.assertIn('pcb_top_copper_PEC',xml)
            self.assertEqual(metadata['excitation'],dict(type='gaussian',center_hz=1.42e9,
                cutoff_hz=.20e9,mesh_design_frequency_hz=1.62e9))
            self.assertEqual(metadata['boundary_conditions']['values'],['PML_8']*6)
            self.assertEqual(metadata['boundary_conditions']['order'],
                             ['x_min','x_max','y_min','y_max','z_min','z_max'])
            self.assertEqual(metadata['geometry']['substrate']['loss_model'],'constant_kappa')
            self.assertEqual(metadata['geometry']['copper']['model'],'PEC')
            self.assertEqual(metadata['geometry']['copper']['polygon_count'],2)
            print(f'PCB native smoke:\nopenEMS: {ems_version}\nCSXCAD: {csx_version}\n'
                  f'cells: {mesh.shape_cells}\ncell_count: {mesh.cell_count}\n'
                  f'port cells: X={spec.x_cell_count}, Y={spec.y_cell_count}\n'
                  f'active Ex edges: {spec.active_ex_edge_count}\nXML bytes: {path.stat().st_size}\nPASS')


if __name__ == '__main__':
    unittest.main()
