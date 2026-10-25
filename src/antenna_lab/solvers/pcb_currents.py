"""Optional planar PCB rot(H) frequency dumps, with no four-layer limit.

These are raw total-current-density samples [A/m^2], NOT directly a
validated surface current density.  A later step converts them using the
local dual Yee-cell width and preserves the native HDF5 without mutation.
"""
from math import prod
import numpy as np

from antenna_lab.core.config import ConfigurationError
from .fields import MAX_FIELD_POINTS
from .pcb_fields import validate_field_frequencies


def pcb_current_layout(geometry, mesh, settings, frequencies):
    """Return physically located native dump planes for each populated Cu layer."""
    freqs = validate_field_frequencies(frequencies, settings)
    if not freqs:
        return {'planes': [], 'empty_layers': [], 'frequency_hz': []}

    axes = [np.asarray(getattr(mesh, a + '_lines_m'), dtype=float) for a in 'xyz']
    ordinary = [
        np.flatnonzero((axis > mesh.pml_start_min_m[i]) &
                       (axis < mesh.pml_start_max_m[i]))
        for i, axis in enumerate(axes)
    ]
    if any(len(v) < 2 for v in ordinary):
        raise ConfigurationError('PCB current: mesh has no adequate ordinary domain.')

    # Preserve physically empty layers: their absence is not zero current data.
    layers = [(c.role, c.z_m) for c in geometry.copper_layers]
    if not layers:
        layers = sorted({(c.layer_role, c.z_m) for c in geometry.copper},
                        key=lambda item: -item[1])
    planes, empty = [], []
    for layer_number, (role, z) in enumerate(layers):
        pieces = [c for c in geometry.copper
                  if c.layer_role == role and abs(c.z_m - z) <= 1e-12]
        if not pieces:
            empty.append({'layer_role': role, 'z_m': float(z),
                          'reason': 'no modeled copper polygon'})
            continue
        zi = int(np.argmin(np.abs(axes[2] - z)))
        if (zi not in ordinary[2] or zi <= 0 or zi >= len(axes[2]) - 1 or
                abs(float(axes[2][zi]) - z) > 1e-12):
            raise ConfigurationError(
                f'PCB current: copper {role} z={z:g} m is not an interior '
                'native grid line with dual-cell support.')
        xy = np.asarray([v for piece in pieces for v in piece.vertices_xy_m])
        bounds = []
        for k in (0, 1):
            a = axes[k]
            left = max(0, int(np.searchsorted(a, float(xy[:, k].min()), side='left')) - 1)
            right = min(len(a) - 1,
                        int(np.searchsorted(a, float(xy[:, k].max()), side='right')))
            candidates = ordinary[k][(ordinary[k] >= left) &
                                     (ordinary[k] <= right)]
            if len(candidates) < 2:
                raise ConfigurationError(
                    f'PCB current: insufficient native samples for {role} on axis {"xy"[k]}.')
            bounds.append((int(candidates[0]), int(candidates[-1])))
        (ix0, ix1), (iy0, iy1) = bounds
        dual_width = float((axes[2][zi + 1] - axes[2][zi - 1]) / 2.0)
        if not np.isfinite(dual_width) or dual_width <= 0:
            raise ConfigurationError('PCB current: invalid local normal dual-cell width.')
        name = f'pcb_curlH_{layer_number:03d}'
        planes.append({
            'name': name, 'layer_role': role, 'layer_index': layer_number,
            'normal_axis': 'z', 'z_m': float(z), 'dual_width_m': dual_width,
            'sampling': 'node interpolation at PEC/conducting-sheet plane',
            'shape_xyz': [ix1 - ix0 + 1, iy1 - iy0 + 1, 1],
            'start_m': [float(axes[0][ix0]), float(axes[1][iy0]),
                        float(axes[2][zi])],
            'stop_m': [float(axes[0][ix1]), float(axes[1][iy1]),
                       float(axes[2][zi])],
            'native_file': name + '.h5',
        })
    count = sum(prod(p['shape_xyz']) for p in planes) * len(freqs)
    if count > MAX_FIELD_POINTS:
        raise ConfigurationError(
            f'PCB current: {count} sampled positions × frequencies exceed '
            f'{MAX_FIELD_POINTS}. Select fewer frequencies or explicit mesh settings.')
    return {'planes': planes, 'empty_layers': empty,
            'frequency_hz': list(freqs), 'sample_count': count}


def install_pcb_currents(csx, geometry, mesh, settings, frequencies):
    """Attach passive rot(H) frequency-domain HDF5 dumps without mesh edits."""
    from .openems_pcb import _audit_port_grid
    layout = pcb_current_layout(geometry, mesh, settings, frequencies)
    _audit_port_grid(csx, mesh, context='before PCB current dumps')
    for plane in layout['planes']:
        dump = csx.AddDump(plane['name'], dump_type=13, dump_mode=1,
                           file_type=1, frequency=layout['frequency_hz'])
        dump.AddBox(start=plane['start_m'], stop=plane['stop_m'])
    _audit_port_grid(csx, mesh, context='after PCB current dumps')
    return {**layout, 'dump_type': 13, 'dump_mode': 1,
            'quantity': 'total_current_density_curl_H',
            'native_units': 'A/m^2', 'surface_units_estimated': 'A/m',
            'mesh_changed': False, 'additional_fdtd_runs': 0,
            'validation_status': 'unverified',
            'interpretation': 'J_total = rot(H) sampled on the copper plane. '
                'Surface-current estimate requires local dual-cell-width '
                'integration and native solver validation; it is not the '
                'independently validated jump of H across the sheet.'}
