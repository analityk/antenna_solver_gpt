"""Copper-current layout, raw rot(H) conversion and HTML viewer: offline tests.

These tests check implementation contracts, not physical openEMS validation.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import h5py
import numpy as np

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import CopperLayer, CopperPolygon
from antenna_lab.solvers.pcb_currents import (
    pcb_current_layout, install_pcb_currents, finish_pcb_currents)
from antenna_lab.visualization.pcb_currents import (
    load_copper_current, pcb_current_section, current_contrast_scale,
    current_figure)


F = 1e9


def fixture():
    positions = [0., -.0005, -.001, -.0015, -.002]
    names = ['top', 'inner1', 'inner2', 'inner3', 'bottom']
    outer = ((-.005, -.005), (.005, -.005),
             (.005, .005), (-.005, .005))
    layers = tuple(CopperLayer(
        role=name, z_m=z, model='pec', thickness_m=.000035,
        conductivity_s_m=5.8e7, source_sha256='fixture')
        for name, z in zip(names, positions))
    metal = [CopperPolygon(f'cu-{i}', outer, z, name)
             for i, (name, z) in enumerate(zip(names, positions))]
    geom = SimpleNamespace(copper_layers=layers, copper=metal, drills=())
    mesh = SimpleNamespace(
        x_lines_m=(-.02, -.01, 0., .01, .02),
        y_lines_m=(-.02, -.01, 0., .01, .02),
        z_lines_m=(-.003, -.0025, -.002, -.0015, -.001,
                   -.0005, 0., .0005, .001),
        pml_start_min_m=(-.021, -.021, -.004),
        pml_start_max_m=(.021, .021, .002))
    settings = SimpleNamespace(
        excitation_center_hz=F, excitation_cutoff_hz=.4e9)
    return geom, mesh, settings


def fake_hdf5(path, plane):
    axes = [np.linspace(a, b, count)
            if count > 1 else np.array([a])
            for a, b, count in zip(
                plane['start_m'], plane['stop_m'], plane['shape_xyz'])]
    with h5py.File(path, 'w') as h5:
        grid = h5.create_group('Mesh')
        grid.attrs['mesh_type'] = 0
        for name, arr in zip('xyz', axes):
            grid[name] = arr
        group = h5.create_group('FieldData/FD')
        group.attrs['frequency'] = [F]
        sample = np.ones((3, *plane['shape_xyz']), dtype=complex)
        sample[0] *= 2 + 3j
        sample[1] *= -4j
        sample[2] *= 111
        field = group.create_dataset('f0', data=sample)
        field.attrs['frequency'] = F
        field.attrs['d_order'] = 'NXYZ'


class CopperCurrentTests(unittest.TestCase):
    def test_five_layers_no_four_plane_cap_and_yee_width(self):
        g, mesh, settings = fixture()
        original = (mesh.z_lines_m, tuple(x.z_m for x in g.copper))
        layout = pcb_current_layout(g, mesh, settings, (F,))
        self.assertEqual(len(layout['planes']), 5)
        self.assertEqual([p['layer_role'] for p in layout['planes']],
                         ['top', 'inner1', 'inner2', 'inner3', 'bottom'])
        self.assertTrue(all(p['dual_width_m'] > 0 for p in layout['planes']))
        self.assertEqual(original,
                         (mesh.z_lines_m, tuple(x.z_m for x in g.copper)))

    def test_native_dump_uses_total_curl_h_with_real_layer_coordinate(self):
        g, mesh, settings = fixture()
        recorded = []
        class FakeCSX:
            def AddDump(self, name, **params):
                row = dict(name=name, **params)
                recorded.append(row)
                return SimpleNamespace(AddBox=lambda **box: row.update(box))
        with patch('antenna_lab.solvers.openems_pcb._audit_port_grid'):
            metadata = install_pcb_currents(FakeCSX(), g, mesh, settings, (F,))
        self.assertEqual(len(recorded), 5)
        self.assertTrue(all(v['dump_type'] == 13 and
                            v['dump_mode'] == 1 and
                            v['start'][2] == v['stop'][2]
                            for v in recorded))
        self.assertEqual(metadata['validation_status'], 'unverified')

    def test_sheet_current_conversion_mask_and_report(self):
        g, mesh, settings = fixture()
        layer = pcb_current_layout(g, mesh, settings, (F,))['planes'][0]
        ref = dict(frequency_hz=[F], voltage_real=[2.], voltage_imag=[3.])
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            native = path / 'native'
            native.mkdir()
            fake_hdf5(native / layer['native_file'], layer)
            before = (native / layer['native_file']).read_bytes()
            result = finish_pcb_currents(
                g, mesh, [layer], (F,), ref, path, native_dir=native)
            self.assertEqual(result['validation_status'], 'unverified')
            self.assertEqual(before, (native / layer['native_file']).read_bytes())
            record = load_copper_current(
                path/'currents'/(layer['name']+'.npz'), layer, [F])
            self.assertEqual(record['on_copper'].sum(), 1)
            i, j = np.argwhere(record['on_copper'])[0]
            scale = 1 / (2+3j)
            self.assertAlmostEqual(
                record['k'][0, 0, i, j].real,
                ((2+3j) * scale * layer['dual_width_m']).real)
            self.assertTrue(
                np.isnan(record['k'][0, 0, 0, 0].real))
            body = pcb_current_section(
                dict(root=path, geometry=dict(copper=[
                    dict(vertices_xy_m=list(p.vertices_xy_m),
                         holes_xy_m=(), z_m=p.z_m,
                         layer_role=p.layer_role)
                    for p in g.copper])),
                lambda fig, description, path=None: '<img alt="mapa prądu">',
                None)
            self.assertIn('top', body)
            self.assertIn('Gęstość prądu', body)
            self.assertIn('niezweryfikowany', body)
            self.assertIn('Kontrast lokalny', body)
            stats = current_contrast_scale(record, 0)
            self.assertTrue(stats['has_signal'])
            self.assertGreater(stats['actual_peak'], 0)
            self.assertLessEqual(stats['scale'], stats['actual_peak'])
            geometry = dict(copper=[dict(
                vertices_xy_m=list(p.vertices_xy_m), holes_xy_m=(),
                z_m=p.z_m, layer_role=p.layer_role) for p in g.copper])
            fig_linear = current_figure(
                record, geometry, layer, 0, 1.0, contrast=False)
            self.assertIn('wspólna skala', fig_linear._suptitle.get_text())
            fig_linear.clear()
            fig_local = current_figure(
                record, geometry, layer, 0, 1.0, contrast=True)
            self.assertIn('lokalny kontrast', fig_local._suptitle.get_text())
            fig_local.clear()

    def test_no_silent_off_grid_sheet(self):
        g, mesh, settings = fixture()
        g.copper_layers = (CopperLayer(
            role='top', z_m=.000123, model='pec', thickness_m=.000035,
            conductivity_s_m=5.8e7, source_sha256='fixture'),)
        g.copper = [CopperPolygon(
            'cu-top', ((-.005,-.005),(.005,-.005),(.005,.005),(-.005,.005)),
            .000123,'top')]
        with self.assertRaisesRegex(ConfigurationError, 'not an interior'):
            pcb_current_layout(g, mesh, settings, (F,))


if __name__ == '__main__':
    unittest.main()
