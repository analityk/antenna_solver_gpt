from dataclasses import FrozenInstanceError
import json
from math import cos, sin, radians
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.config import load_pcb_config
from antenna_lab.pcb.validation import validate_pcb_geometry
from antenna_lab.pcb.workflow import (
    PcbWorkflowResult, make_synthetic_pcb_geometry, prepare_pcb_placeholder,
)
from test_pcb_config import config

COORDINATE_TOL_M = 1e-14


class PcbWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'pcb.json'

    def write_config(self, gap_mm=2., width_mm=1., angle=37.):
        value = config()
        value['files'] = {'copper_top': 'missing_top.gbr', 'board_outline': 'missing_edge.gbr'}
        value['port'] = {'negative_mm': [19., -7.],
                         'positive_mm': [19. + gap_mm * cos(radians(angle)),
                                         -7. + gap_mm * sin(radians(angle))],
                         'width_mm': width_mm}
        self.path.write_text(json.dumps(value), encoding='utf-8')
        return value

    def assert_geometry(self, result):
        self.assertIsInstance(result, PcbWorkflowResult)
        cfg = result.config
        for geometry in (result.source_geometry, result.normalized_geometry):
            self.assertEqual(validate_pcb_geometry(geometry)['geometry_status'], 'passed')
            self.assertEqual(len(geometry.copper), 2)
            self.assertEqual([c.id for c in geometry.copper], ['synthetic_negative', 'synthetic_positive'])
            self.assertTrue(all(c.z_m == 0. for c in geometry.copper))
            self.assertEqual(geometry.substrate.z_min_m, -cfg.substrate_thickness_m)
            self.assertEqual(geometry.substrate.z_max_m, 0.)
            self.assertEqual(geometry.substrate.epsilon_r, cfg.substrate_epsilon_r)
            self.assertEqual(geometry.substrate.loss_tangent, cfg.substrate_loss_tangent)
            self.assertEqual(geometry.port.width_m, cfg.port_width_m)
        self.assertEqual(result.source_geometry.port.negative_xy_m, cfg.port_negative_xy_m)
        self.assertEqual(result.source_geometry.port.positive_xy_m, cfg.port_positive_xy_m)
        a, b = result.normalized_geometry.port.negative_xy_m, result.normalized_geometry.port.positive_xy_m
        self.assertLess(a[0], 0)
        self.assertGreater(b[0], 0)
        for residual in (a[1], b[1], a[0] + b[0]):
            self.assertAlmostEqual(residual, 0., delta=COORDINATE_TOL_M)

    def test_complete_arbitrary_angle_workflow_and_config_preservation(self):
        self.write_config()
        result = prepare_pcb_placeholder(self.path)
        self.assert_geometry(result)
        self.assertEqual(result.config, load_pcb_config(self.path))
        self.assertIn('Gerber geometry not loaded', result.source_geometry.assumptions)
        with self.assertRaises(FrozenInstanceError):
            result.transform = None

    def test_missing_gerbers_never_opened(self):
        self.write_config()
        original_open = Path.open

        def guarded_open(path, *args, **kwargs):
            self.assertNotEqual(path.suffix, '.gbr')
            return original_open(path, *args, **kwargs)

        with patch.object(Path, 'open', guarded_open):
            self.assert_geometry(prepare_pcb_placeholder(self.path))

    def test_determinism_and_source_not_mutated(self):
        self.write_config()
        cfg = load_pcb_config(self.path)
        constructed = make_synthetic_pcb_geometry(cfg)
        before = constructed.as_dict()
        with patch('antenna_lab.pcb.workflow.make_synthetic_pcb_geometry', return_value=constructed):
            first = prepare_pcb_placeholder(self.path)
        self.assertIs(first.source_geometry, constructed)
        self.assertIsNot(first.normalized_geometry, constructed)
        self.assertEqual(constructed.as_dict(), before)
        second = prepare_pcb_placeholder(self.path)
        self.assertEqual(first.config, second.config)
        self.assertEqual(first.source_geometry.as_dict(), second.source_geometry.as_dict())
        self.assertEqual(first.normalized_geometry.as_dict(), second.normalized_geometry.as_dict())
        self.assertEqual(first.transform, second.transform)

    def test_changed_materials(self):
        value = self.write_config()
        value['substrate'] = {'thickness_mm': .8, 'epsilon_r': 2.2, 'loss_tangent': .0009}
        self.path.write_text(json.dumps(value), encoding='utf-8')
        result = prepare_pcb_placeholder(self.path)
        self.assert_geometry(result)
        self.assertAlmostEqual(result.source_geometry.substrate.z_min_m, -.0008)
        self.assertEqual(result.source_geometry.substrate.epsilon_r, 2.2)
        self.assertEqual(result.source_geometry.substrate.loss_tangent, .0009)

    def test_varied_dimensions_and_orientations(self):
        for gap, width, angle in ((2., 1., 0.), (8., .5, 90.), (.5, 4., 180.),
                                  (.2, .1, 37.), (.1, .3, -73.)):
            with self.subTest(gap=gap, width=width, angle=angle):
                self.write_config(gap, width, angle)
                cfg = load_pcb_config(self.path)
                validate_pcb_geometry(make_synthetic_pcb_geometry(cfg))
                self.assert_geometry(prepare_pcb_placeholder(self.path))

    def test_invalid_config_propagates(self):
        value = self.write_config()
        value['port']['width_mm'] = 0
        self.path.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaises(ConfigurationError):
            prepare_pcb_placeholder(self.path)


if __name__ == '__main__':
    unittest.main()
