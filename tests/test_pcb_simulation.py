from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.simulation import (
    PcbSimulationSettings, load_pcb_simulation_settings, validate_pcb_simulation_config,
    validate_pcb_simulation_settings,
)


def simulation_config():
    return {
        'schema_version': 1,
        'domain': {'air_padding_wavelengths': .25, 'pml_cells': 8},
        'result_frequency_hz': [1300000000, 1420000000, 1500000000],
        'excitation': {'center_hz': 1420000000, 'cutoff_hz': 200000000},
        'port': {'reference_impedance_ohm': 50},
        'mesh': {'cells_per_wavelength': 20, 'min_substrate_cells_z': 4,
                 'min_port_gap_cells': 2, 'min_port_width_cells': 2,
                 'growth_ratio_target': 1.4, 'growth_ratio_limit': 1.5, 'max_cells': 20000000},
        'material': {'loss_reference_frequency_hz': 1420000000},
        'fdtd': {'max_timesteps': 100000, 'end_criteria': 1e-5, 'threads': 0},
    }


def settings(value=None):
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'pcb-simulation.json'
        path.write_text(json.dumps(simulation_config() if value is None else value), encoding='utf-8')
        return load_pcb_simulation_settings(path)


class PcbSimulationTests(unittest.TestCase):
    def test_all_fields_bom_determinism_frozen(self):
        expected = dict(
            air_padding_wavelengths=.25, pml_cells=8, runtime=None,
            schema_version=1, result_frequency_hz=(1.3e9, 1.42e9, 1.5e9),
            excitation_center_hz=1.42e9, excitation_cutoff_hz=.2e9,
            reference_impedance_ohm=50, cells_per_wavelength=20,
            min_substrate_cells_z=4, min_port_gap_cells=2, min_port_width_cells=2,
            growth_ratio_target=1.4, growth_ratio_limit=1.5, max_cells=20000000,
            loss_reference_frequency_hz=1.42e9, max_timesteps=100000, end_criteria=1e-5, threads=0)
        for encoding in ('utf-8', 'utf-8-sig'):
            with self.subTest(encoding=encoding), TemporaryDirectory() as directory:
                path = Path(directory) / 'pcb-simulation.json'
                path.write_text(json.dumps(simulation_config()), encoding=encoding)
                result = load_pcb_simulation_settings(path)
                self.assertIsInstance(result, PcbSimulationSettings)
                self.assertEqual(asdict(result), expected)
                self.assertEqual(result, load_pcb_simulation_settings(path))
                self.assertIsInstance(result.result_frequency_hz, tuple)
                with self.assertRaises(FrozenInstanceError):
                    result.threads = 2

    def test_runtime_validation_shares_json_policy(self):
        base=settings()
        before=asdict(base)
        self.assertIs(validate_pcb_simulation_settings(base),base)
        self.assertEqual(asdict(base),before)
        for changes in ({'result_frequency_hz': ()}, {'result_frequency_hz': (1.42e9,1.42e9)},
                        {'excitation_center_hz': float('nan')}, {'excitation_cutoff_hz': 1.42e9},
                        {'loss_reference_frequency_hz': 0}, {'result_frequency_hz': (1.6e9,)},
                        {'threads': -1}, {'pml_cells': 5}):
            with self.subTest(changes=changes), self.assertRaises(ConfigurationError):
                validate_pcb_simulation_settings(replace(base,**changes))

    def test_validation_no_mutation(self):
        value = simulation_config()
        before = deepcopy(value)
        self.assertIs(validate_pcb_simulation_config(value), value)
        self.assertEqual(value, before)

    def assert_invalid_field(self, section, key, values):
        for value in values:
            data = simulation_config()
            (data if section is None else data[section])[key] = value
            with self.subTest(section=section, key=key, value=value), self.assertRaises(ConfigurationError):
                validate_pcb_simulation_config(data)

    def test_results_order_unique_positive_window(self):
        self.assert_invalid_field(None, 'result_frequency_hz', (
            [], [1.4e9, 1.3e9], [1.4e9, 1.4e9], [0], [-1], [True],
            [1.26e9-1], [1.58e9+1]))
        value = simulation_config()
        value['result_frequency_hz'] = [1.26e9, 1.58e9]
        validate_pcb_simulation_config(value)
        value['result_frequency_hz'] = [1.42e9]
        validate_pcb_simulation_config(value)

    def test_excitation(self):
        for key in ('center_hz', 'cutoff_hz'):
            self.assert_invalid_field('excitation', key, (0, -1, True))
        self.assert_invalid_field('excitation', 'cutoff_hz', (1.42e9, 2e9))
        value = simulation_config()
        value['excitation'] = dict(center_hz=1.7e308, cutoff_hz=1e308)
        with self.assertRaises(ConfigurationError):
            validate_pcb_simulation_config(value)

    def test_impedance_and_material(self):
        self.assert_invalid_field('port', 'reference_impedance_ohm', (0, -1, True))
        self.assert_invalid_field('material', 'loss_reference_frequency_hz', (0, -1, True))
        value = simulation_config()
        value['port']['reference_impedance_ohm'] = 75
        value['material']['loss_reference_frequency_hz'] = 1.3e9
        result = settings(value)
        self.assertEqual(result.reference_impedance_ohm, 75)
        self.assertEqual(result.loss_reference_frequency_hz, 1.3e9)

    def test_mesh_integers_and_wavelength(self):
        for key in ('min_substrate_cells_z', 'min_port_gap_cells', 'min_port_width_cells', 'max_cells'):
            self.assert_invalid_field('mesh', key, (0, -1, .5, True, '2'))
        self.assert_invalid_field('mesh', 'cells_per_wavelength', (3.9, 0, -1, True))
        value = simulation_config()
        value['mesh']['cells_per_wavelength'] = 4
        validate_pcb_simulation_config(value)

    def test_growth(self):
        for key in ('growth_ratio_target', 'growth_ratio_limit'):
            self.assert_invalid_field('mesh', key, (1, 0, -1, True))
        self.assert_invalid_field('mesh', 'growth_ratio_target', (1.6,))
        value = simulation_config()
        value['mesh']['growth_ratio_target'] = 1.5
        validate_pcb_simulation_config(value)

    def test_domain_values(self):
        self.assert_invalid_field('domain', 'air_padding_wavelengths',
                                  (0, -1, float('nan'), float('inf'), -float('inf'), True, '0.25'))
        self.assert_invalid_field('domain', 'pml_cells', (0, 1, 5, 21, -1, 1.5, True, '8'))
        value = simulation_config()
        for count in (6, 8, 12, 20):
            value['domain']['pml_cells'] = count
            self.assertEqual(settings(value).pml_cells, count)
        value['domain'] = dict(air_padding_wavelengths=.5, pml_cells=12)
        result = settings(value)
        self.assertEqual(result.air_padding_wavelengths, .5)
        self.assertEqual(result.pml_cells, 12)

    def test_fdtd(self):
        self.assert_invalid_field('fdtd', 'max_timesteps', (0, -1, 1.5, True))
        self.assert_invalid_field('fdtd', 'end_criteria', (0, -1, 1, 2, True))
        self.assert_invalid_field('fdtd', 'threads', (-1, .5, True))
        value = simulation_config()
        value['fdtd']['threads'] = 8
        self.assertEqual(settings(value).threads, 8)

    def test_nonfinite_every_numeric_field(self):
        for section, fields in simulation_config().items():
            if not isinstance(fields, dict):
                continue
            for key in fields:
                self.assert_invalid_field(section, key, (float('nan'), float('inf'), -float('inf')))
        self.assert_invalid_field(None, 'result_frequency_hz', ([float('nan')], [float('inf')], [-float('inf')]))

    def test_missing_unknown_and_version(self):
        self.assert_invalid_field(None, 'schema_version', (0, 2, True, '1'))
        for section in (None, 'excitation', 'port', 'mesh', 'material', 'fdtd', 'domain'):
            data = simulation_config()
            target = data if section is None else data[section]
            for key in tuple(target):
                missing = deepcopy(data)
                del (missing if section is None else missing[section])[key]
                with self.subTest(section=section, missing=key), self.assertRaises(ConfigurationError):
                    validate_pcb_simulation_config(missing)
            target['unexpected'] = 1
            with self.subTest(section=section), self.assertRaises(ConfigurationError):
                validate_pcb_simulation_config(data)


if __name__ == '__main__':
    unittest.main()
