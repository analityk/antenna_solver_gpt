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



def _copper_occupancy(geometry, plane, x, y):
    """Exact 2-D copper footprint mask; never the E/H halo exclusion mask."""
    from shapely import intersects, points, union_all
    from shapely.geometry import Point
    from antenna_lab.pcb.regions import copper_shape

    pieces = [copper_shape(c) for c in geometry.copper
              if c.layer_role == plane['layer_role'] and
              abs(c.z_m - plane['z_m']) <= 1e-12]
    if not pieces:
        raise ConfigurationError('PCB current: no copper at saved layer.')
    metal = union_all(pieces)
    for drill in geometry.drills:
        if not drill.plated:
            metal = metal.difference(
                Point(drill.x_m, drill.y_m).buffer(
                    drill.drill_diameter_m / 2.0, quad_segs=128))
    uu, vv = np.meshgrid(x, y, indexing='ij')
    occupancy = np.asarray(intersects(metal, points(uu.ravel(), vv.ravel())),
                           dtype=bool).reshape(uu.shape)
    if not np.any(occupancy):
        raise ConfigurationError(
            f"PCB current: no copper samples in layer {plane['layer_role']}; "
            'increase mesh resolution, do not manufacture interpolated current.')
    return occupancy


def finish_pcb_currents(geometry, mesh, planes, frequencies, reference,
                        output, *, native_dir=None):
    """Convert native curl(H) into a tagged sheet-current *estimate*.

    No physical surface-charge/current jump is claimed. Native rot(H) remains
    preserved in HDF5. One saved NPZ per actual copper plane.
    """
    from pathlib import Path
    from .pcb_fields import voltage_scale
    from .power import _read_surface
    from antenna_lab.core.config import write_json

    frequencies = np.asarray(frequencies, dtype=float)
    if not np.array_equal(frequencies,
                          np.asarray(reference['frequency_hz'], dtype=float)):
        raise ConfigurationError('PCB current: phase-reference frequencies differ.')
    voltage = np.asarray(reference['voltage_real'], dtype=float) + (
        1j * np.asarray(reference['voltage_imag'], dtype=float))
    scale = voltage_scale(voltage)
    output = Path(output)
    native = Path(native_dir) if native_dir is not None else output / 'native'
    folder = output / 'currents'
    folder.mkdir()  # intentionally refuse overwrite
    axes = [np.asarray(getattr(mesh, a + '_lines_m'), dtype=float) for a in 'xyz']

    for plane in planes:
        start, stop = plane['start_m'], plane['stop_m']
        expected = [axis[(axis >= lo) & (axis <= hi)]
                    for axis, lo, hi in zip(axes, start, stop)]
        occupied = None
        data = []
        xy_ref = None
        for i, frequency in enumerate(frequencies):
            lines, density = _read_surface(native / plane['native_file'], frequency)
            if any(len(found) != len(target) or
                   not np.allclose(found, target, rtol=1e-6, atol=1e-10)
                   for found, target in zip(lines, expected)):
                raise ConfigurationError(
                    f"PCB current: native rot(H) grid mismatch for {plane['layer_role']}.")
            if len(lines[2]) != 1 or not np.isclose(
                    lines[2][0], plane['z_m'], rtol=0, atol=1e-10):
                raise ConfigurationError('PCB current: dump not on actual copper plane.')
            if xy_ref is None:
                xy_ref = (lines[0], lines[1])
                occupied = _copper_occupancy(geometry, plane, *xy_ref)
            elif not all(np.array_equal(a, b) for a, b in
                         zip(xy_ref, (lines[0], lines[1]))):
                raise ConfigurationError('PCB current: inconsistent frequency grids.')
            # J_total = curl(H) is A/m².  Multiplication by the local
            # normal dual-cell width is an UNVERIFIED sheet approximation.
            k = density[:2, :, :, 0] * scale[i] * plane['dual_width_m']
            if not np.isfinite(k).all():
                raise ConfigurationError('PCB current: non-finite complex phasors.')
            data.append(k)
        estimated = np.asarray(data)
        # Only the exact conductor area is a valid surface-current estimate.
        # Original native J samples remain unchanged in native/*.h5.
        estimated[:, :, ~occupied] = np.nan + 1j * np.nan
        np.savez_compressed(
            folder / (plane['name'] + '.npz'),
            frequency_hz=frequencies, x_m=xy_ref[0], y_m=xy_ref[1],
            K_estimated_a_per_m=estimated, on_copper=occupied,
            dual_width_m=float(plane['dual_width_m']),
            normalization_factor=scale, port_voltage_phasor=voltage,
            reference_voltage_v=1.0,
            array_order='frequency,component_xy,x,y')
    metadata = {
        'schema_version': 1, 'quantity': 'K_estimated_from_curl_H',
        'planes': planes, 'frequency_hz': frequencies.tolist(),
        'normalization': 'total port voltage = 1∠0 V, not accepted power',
        'reference_voltage_v': 1.0,
        'units': {'K_estimate': 'A/m per 1 V port', 'native_curl_H': 'A/m^2',
                  'coordinates': 'm'},
        'array_order': 'frequency,component_xy,x,y',
        'phasor_convention': 'real(K * exp(+j * phase))',
        'mask_definition': 'exact modeled copper footprint; no artificial metal halo',
        'conversion': 'K_est = rot(H)_t at sheet * normal Yee dual-cell width',
        'validation_status': 'unverified',
        'limitations': [
            'Surface conversion is not yet cross-checked against one-sided H jumps.',
            'Node interpolation and finite Yee cells affect PEC/sheet edges.',
            'Near ports, plated vias and sharp corners requires separate validation.',
            'Not a finite-foil volumetric J or a validated AC-loss calculation.',
            'The 1 V terminal normalization inherits the unverified port model.'
        ],
        'native_data_preserved': True
    }
    write_json(folder / 'metadata.json', metadata)
    return metadata
