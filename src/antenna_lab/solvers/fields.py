"""Passive frequency-domain E/H planes on existing mesh nodes; no new mesh lines."""

import json
import math

import numpy as np

from antenna_lab.core.config import ConfigurationError, write_json
from .feed import resolve_feed
from .power import _read_surface

MAX_FIELD_POINTS = 4_000_000

PLANES = {"xy_front": 2, "xz": 1, "yz": 0}
CONVENTION = "real(F * exp(+j * phase)); phase zero = positive port voltage"


def field_layout(geometry, axes, mesh, config):
    request = config["requested_outputs"]
    names = request["field_planes"]
    if not names:
        return []
    margin = .15 * 299792458.0 / min(config["simulation"]["frequency_hz"])
    low, high = geometry.bounds
    indices = []
    for n, axis in enumerate("xyz"):
        lines = axes[axis]
        valid = np.flatnonzero((lines > mesh["nf2ff_start_m"][n]) & (lines < mesh["nf2ff_stop_m"][n]))
        lo, hi = (int(valid[np.argmin(abs(lines[valid] - value))])
                  for value in (low[n] - margin, high[n] + margin))
        indices.append([lo, hi])
    center = (np.asarray(geometry.port.positive) + geometry.port.negative) / 2
    offset = request.get("field_front_offset_m", .02)
    result = []
    total = 0
    for name in names:
        normal = PLANES[name]
        location = float(max(p[2] for p in geometry.nodes) + offset) if name == "xy_front" else float(center[normal])
        lines = axes["xyz"[normal]]
        index = int(np.argmin(abs(lines - location)))
        if not mesh["nf2ff_start_m"][normal] < location < mesh["nf2ff_stop_m"][normal]:
            raise ConfigurationError(f"Płaszczyzna {name} poza obszarem pomiarowym. Zmniejsz field_front_offset_m.")
        if not mesh["nf2ff_start_m"][normal] < lines[index] < mesh["nf2ff_stop_m"][normal]:
            raise ConfigurationError(f"Płaszczyzna {name} jest zbyt blisko granicy obszaru pomiarowego.")
        bounds = [pair.copy() for pair in indices]
        bounds[normal] = [index, index]
        shape = [hi - lo + 1 for lo, hi in bounds]
        if any(shape[n] < 2 for n in range(3) if n != normal):
            raise ConfigurationError(f"Za mało próbek w płaszczyźnie {name}.")
        total += math.prod(shape) * len(config["simulation"]["frequency_hz"])
        result.append({"name": name, "normal_axis": "xyz"[normal], "requested_position_m": location,
                       "actual_position_m": float(lines[index]), "shape_xyz": shape,
                       "start_m": [float(axes[a][pair[0]]) for a, pair in zip("xyz", bounds)],
                       "stop_m": [float(axes[a][pair[1]]) for a, pair in zip("xyz", bounds)],
                       "native_files": {kind: f"fields_{name}_{kind}.h5" for kind in "EH"}})
    if total > MAX_FIELD_POINTS:
        raise ConfigurationError("Zapis E/H przekracza 4 mln punktów × częstotliwości. Ogranicz field_planes lub frequency_hz.")
    return result


def install_frequency_planes(csx, layout, frequencies):
    """Shared passive complex FD node dumps; never requests grid modification."""
    for plane in layout:
        for kind, dump_type in (("E", 10), ("H", 11)):
            dump = csx.AddDump(f"fields_{plane['name']}_{kind}", dump_type=dump_type,
                               dump_mode=1, file_type=1, frequency=list(frequencies))
            dump.AddBox(start=plane["start_m"], stop=plane["stop_m"])


def install_fields(csx, layout, config, run):
    install_frequency_planes(csx, layout, config["simulation"]["frequency_hz"])
    if layout:
        write_json(run.path / "field_layout.json", {"planes": layout, "dump_mode": 1,
                   "interpolation": "node", "units": "m", "mesh_changed": False})


def sample_mask(lines, full_axes, geometry, feed):
    """Conservative geometric mask, not the native PEC occupancy map.

    Bits: 1 metal, 2 one-local-cell-diagonal halo (interpolation uncertain),
    4 ideal source and its halo. Raw native data are retained separately.
    """
    shape = tuple(len(a) for a in lines)
    points = np.stack(np.meshgrid(*lines, indexing="ij"), axis=-1).reshape(-1, 3)
    widths = []
    for n, axis in enumerate("xyz"):
        a = np.asarray(full_axes[axis])
        idx = np.searchsorted(a, lines[n])
        idx = np.clip(idx, 1, len(a) - 2)
        idx = np.where(abs(a[idx - 1] - lines[n]) < abs(a[idx] - lines[n]), idx - 1, idx)
        delta = np.maximum(a[idx] - a[idx - 1], a[idx + 1] - a[idx])
        widths.append(delta)
    halo = np.sqrt(sum(a * a for a in np.meshgrid(*widths, indexing="ij"))).ravel()
    mask = np.zeros(len(points), dtype=np.uint8)
    for wire in geometry.wires:
        start, stop = np.asarray(wire.start), np.asarray(wire.stop)
        direction = stop - start
        t = np.clip((points - start) @ direction / np.dot(direction, direction), 0, 1)
        distance = np.linalg.norm(points - start - t[:, None] * direction, axis=1)
        mask[distance <= wire.radius_m + 1e-12] |= 1
        mask[distance <= wire.radius_m + halo] |= 2
    for plate in geometry.plates:
        distance = np.linalg.norm(np.maximum(np.maximum(plate.start - points, points - plate.stop), 0), axis=1)
        mask[distance <= 1e-12] |= 1
        mask[distance <= halo] |= 2
    start, stop = np.asarray(feed["start_m"]), np.asarray(feed["stop_m"])
    distance = np.linalg.norm(np.maximum(np.maximum(start - points, points - stop), 0), axis=1)
    mask[distance <= halo] |= 4
    return mask.reshape(shape)


def finish_fields(geometry, config, run, frequency, scale):
    if not config["requested_outputs"]["field_planes"]:
        return []
    layout = json.loads((run.path / "field_layout.json").read_text(encoding="utf-8"))["planes"]
    with np.load(run.path / "mesh.npz", allow_pickle=False) as archive:
        axes = {a: archive[a] for a in "xyz"}
    feed = resolve_feed(geometry.port, axes, config["solver"].get("port_mesh_alignment", "legacy"))
    folder = run.path / "fields"
    folder.mkdir()
    for plane in layout:
        fields = {kind: [] for kind in "EH"}
        reference_lines = None
        for i, f in enumerate(frequency):
            for kind in "EH":
                lines, raw = _read_surface(run.path / "openems" / plane["native_files"][kind], f)
                if reference_lines is None:
                    reference_lines = lines
                    for n, a in enumerate("xyz"):
                        expected = axes[a][(axes[a] >= plane["start_m"][n]) & (axes[a] <= plane["stop_m"][n])]
                        if len(expected) != len(lines[n]) or not np.allclose(expected, lines[n], rtol=1e-6, atol=1e-10):
                            raise RuntimeError(f"Nieoczekiwana siatka pola {plane['name']}.")
                if not all(np.array_equal(a, b) for a, b in zip(reference_lines, lines)):
                    raise RuntimeError("Siatki E/H lub częstotliwości różnią się; nie interpolowano ich po cichu.")
                fields[kind].append(raw * scale[i])
        mask = sample_mask(reference_lines, axes, geometry, feed)
        electric, magnetic = (np.asarray(fields[kind]) for kind in "EH")
        if not np.isfinite(electric).all() or not np.isfinite(magnetic).all():
            raise RuntimeError("Normalizacja E/H dała nieskończone wartości.")
        electric[:, :, mask != 0] = np.nan
        magnetic[:, :, mask != 0] = np.nan
        np.savez_compressed(folder / f"{plane['name']}.npz", frequency_hz=frequency,
                            x_m=reference_lines[0], y_m=reference_lines[1], z_m=reference_lines[2],
                            E_v_per_m=electric, H_a_per_m=magnetic, mask=mask,
                            normalization_factor=scale, reference_power_w=config["simulation"]["accepted_power_w"],
                            phasor_convention=CONVENTION, array_order="frequency,component_xyz,x,y,z")
        plane["masked_samples"] = int(np.count_nonzero(mask))
    write_json(folder / "metadata.json", {"schema_version": 1, "planes": layout,
               "frequency_hz": list(map(float, frequency)), "units": {"E": "V/m", "H": "A/m", "coordinates": "m"},
               "phasor_convention": CONVENTION, "array_order": "frequency,component_xyz,x,y,z",
               "mask_bits": {"1": "PEC geometry", "2": "one local cell diagonal around PEC", "4": "ideal port and halo"},
               "mask_note": "Conservative geometry/interpolation mask; not native voxel occupancy. Raw spectra remain in openems/*.h5.",
               "normalization": "Same complex factor as port_spectra.npz; single U/I port power is unverified; no power-balance correction.",
               "validation_status": "unverified"})
    return [plane["name"] for plane in layout]
