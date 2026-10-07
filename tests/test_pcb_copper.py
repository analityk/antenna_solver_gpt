"""Material choice changes native property, never geometry/mesh; native fakes only."""
import contextlib
from copy import deepcopy
from dataclasses import asdict, replace
import io
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.bundle import DEFAULT_PHYSICAL, load_bundle_geometry, load_physical_config
from antenna_lab.pcb.copper import copper_metadata
from antenna_lab.pcb.gerber_control import run_gerber_control
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model, install_pcb_geometry
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from antenna_lab.visualization.report import generate_report
from test_pcb_bundle import bundle_fixture
from test_pcb_fields import FieldCSX, FieldEngine
from test_openems_pcb import Metal


class CopperCSX(FieldCSX):
    def __init__(self):
        super().__init__(); self.copper_calls = []

    def AddMetal(self, name):
        self.copper_calls.append(('AddMetal', name, {}))
        return super().AddMetal(name)

    def AddConductingSheet(self, name, **kwargs):
        self.copper_calls.append(('AddConductingSheet', name, kwargs))
        material = Metal()
        # Existing fake engine checks installed conductor polygons using this list.
        self.metals.append((name, material))
        return material


class CopperTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = bundle_fixture(self.root/'gerbers', vertical=True, loop=True)

    def physical(self, model):
        value = deepcopy(DEFAULT_PHYSICAL); value['copper']['model'] = model
        path = self.root/(model+'.json'); path.write_text(json.dumps(value))
        return path

    def natives(self, csx, engine):
        return patch('antenna_lab.solvers.openems.native_modules', return_value=(
            SimpleNamespace(openEMS=lambda **kwargs: engine),
            SimpleNamespace(ContinuousStructure=lambda: csx)))

    def test_native_material_polygons_and_exact_mesh_identity_all_profiles(self):
        for quality in ('preview', 'design', 'verify'):
            outputs = []
            for model in ('pec', 'conducting_sheet'):
                config, source, _ = load_bundle_geometry(self.bundle, self.physical(model))
                geometry, _ = normalize_port_orientation(source)
                settings, _ = gerber_quality_settings(quality)
                before = (geometry.as_dict(), asdict(settings), asdict(config))
                csx = CopperCSX(); engine = FieldEngine(csx)
                with self.natives(csx, engine):
                    _, _, _, mesh, _, metadata = prepare_pcb_xml_model(geometry, settings,
                        self.root/f'{quality}_{model}.xml', gerber_quality=quality, copper_config=config)
                self.assertEqual(before, (geometry.as_dict(), asdict(settings), asdict(config)))
                self.assertEqual(len(csx.copper_calls), 1)
                expected = ('AddMetal', 'pcb_top_copper_PEC', {}) if model == 'pec' else (
                    'AddConductingSheet', 'pcb_top_copper_sheet',
                    dict(conductivity=config.copper_conductivity_s_m, thickness=config.copper_thickness_m))
                self.assertEqual(csx.copper_calls[0], expected)
                material = metadata['geometry']
                self.assertEqual(material['copper_model'], model)
                self.assertEqual(material['copper_thickness_m'], config.copper_thickness_m)
                self.assertEqual(material['copper_conductivity_s_m'], 58e6)
                self.assertAlmostEqual(material['copper_sheet_conductance_s'], 2030)
                self.assertEqual(material['copper_inputs_used_by_solver'], model == 'conducting_sheet')
                self.assertEqual(material['geometric_copper_thickness_m'], 0)
                self.assertEqual(material['extra_copper_z_cells'], 0)
                self.assertEqual(metadata['xml']['parse_status'], 'passed')
                json.dumps(metadata, allow_nan=False)
                self.assertFalse(any(c[0] == 'Run' for c in engine.calls))
                outputs.append((mesh, csx.grid.lines, csx.metals[0][1].polygons))
            self.assertEqual(outputs[0], outputs[1])  # all axes, metadata, count, identical planar polygons
            self.assertIn(0.0, outputs[0][0].z_lines_m)
            self.assertNotIn(35e-6, outputs[0][0].z_lines_m)

    def test_invalid_physical_material_and_native_preflight(self):
        path = self.physical('conducting_sheet'); original = json.loads(path.read_text())
        for key in ('thickness_um', 'conductivity_s_m'):
            for invalid in (0, -1, float('nan'), float('inf'), True, '35'):
                value = deepcopy(original); value['copper'][key] = invalid
                path.write_text(json.dumps(value))
                with self.subTest(key=key, value=invalid), self.assertRaises(ConfigurationError):
                    load_physical_config(path)
        for model in ('copper', 'volume', ''):
            value = deepcopy(original); value['copper']['model'] = model; path.write_text(json.dumps(value))
            with self.assertRaises(ConfigurationError): load_physical_config(path)
        config, g, _ = load_bundle_geometry(self.bundle, self.physical('conducting_sheet'))
        g, _ = normalize_port_orientation(g); s, _ = gerber_quality_settings('preview')
        mesh = make_pcb_domain_mesh(g, s, gerber_quality='preview')
        for values in (dict(copper_thickness_m=0), dict(copper_conductivity_s_m=float('nan')),
                       dict(copper_model='unknown')):
            csx = CopperCSX()
            with self.assertRaises(ConfigurationError):
                install_pcb_geometry(csx, g, mesh, s, gerber_quality='preview', copper_config=replace(config, **values))
            self.assertEqual(csx.grid_accesses, 0)
        self.assertFalse(copper_metadata()['copper_inputs_used_by_solver'])

    def test_sheet_fields_summary_reports_and_offline_regeneration(self):
        results = []
        for model in ('pec', 'conducting_sheet'):
            csx = CopperCSX(); engine = FieldEngine(csx); out = self.root/model
            with self.natives(csx, engine), contextlib.redirect_stdout(io.StringIO()):
                result = run_gerber_control(self.bundle, out, quality='preview',
                    pcb_config=self.physical(model), field_frequency_hz=(1.411e9,))
            self.assertEqual(len([c for c in engine.calls if c[0] == 'Run']), 1)
            self.assertEqual(len(engine.port.calls), 1)
            saved = json.loads((out/'summary.json').read_text())
            for key in ('copper_model', 'copper_thickness_m', 'copper_conductivity_s_m', 'copper_sheet_conductance_s'):
                self.assertEqual(saved[key], saved['preparation']['geometry'][key])
            html = re.sub(r'data:image/[^"\s]+', '', (out/'report.html').read_text())
            self.assertIn('Copper model', html)
            self.assertIn('35 µm', html); self.assertIn('58 MS/m', html); self.assertIn('2030 S', html)
            self.assertIn('Pola E/H — przebieg jednego okresu', html)
            if model == 'conducting_sheet':
                self.assertIn('conducting sheet', html)
                self.assertNotIn('PEC', html)
                fields = (out/'fields/metadata.json').read_text()
                self.assertNotIn('PEC', fields)
            else:
                self.assertIn('PEC', html); self.assertIn('nie są używane przez solver', html)
            for plane in ('xy_air', 'xz_feed', 'yz_feed'):
                self.assertTrue((out/'fields'/f'{plane}.npz').is_file())
            with patch('antenna_lab.solvers.openems.native_modules', side_effect=AssertionError('offline')):
                generate_report(out, self.root/f'{model}_offline.html')
            results.append((csx.grid.lines, result['mesh'], result['frequency_hz'], result['simulation_settings']))
        self.assertEqual(results[0], results[1])

    def test_prepare_only_passes_physical_material(self):
        csx = CopperCSX(); engine = FieldEngine(csx)
        with self.natives(csx, engine), contextlib.redirect_stdout(io.StringIO()):
            result = run_gerber_control(self.bundle, self.root/'prepared', quality='preview',
                pcb_config=self.physical('conducting_sheet'), prepare_only=True)
        self.assertEqual(result['preparation']['geometry']['copper_model'], 'conducting_sheet')
        self.assertFalse(any(c[0] == 'Run' for c in engine.calls))


if __name__ == '__main__': unittest.main()
