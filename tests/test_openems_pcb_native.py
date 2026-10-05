"""Real supported native binaries through XML only; never execute FDTD."""

import importlib.metadata
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.etree import ElementTree

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.control import make_synthetic_control_case
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

        geometry, settings = make_synthetic_control_case()
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
