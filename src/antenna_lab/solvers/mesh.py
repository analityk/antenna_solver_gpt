"""Nonuniform Cartesian mesh with explicit port, metal and PML locations."""

import math
import numpy as np

from antenna_lab.core.config import ConfigurationError

C0 = 299792458.0


def _axis(anchors, fine, coarse, padding, growth, pml):
    anchors = sorted(set(round(float(v), 12) for v in anchors))
    points = [anchors[0]]
    for a, b in zip(anchors, anchors[1:]):
        if b - a < fine * 1e-4:
            raise ConfigurationError("Geometria wymusza niemal pokrywające się linie siatki. Sprawdź wymiary portu i reflektora.")
        points.extend(np.linspace(a, b, max(1, math.ceil((b - a) / fine)) + 1)[1:])
    ends = []
    for edge, sign in ((points[0], -1), (points[-1], 1)):
        region, distance, step = [], 0.0, fine
        while distance < padding:
            step = min(step * growth, coarse)
            distance += step
            region.append(edge + sign * distance)
        # A uniform outer layer, with extra free-space cells before the PML.
        for _ in range(pml + 2):
            distance += coarse
            region.append(edge + sign * distance)
        ends.append(region)
    return np.array(list(reversed(ends[0])) + points + ends[1], dtype=float)


def make_mesh(geometry, config):
    settings = config["solver"]
    frequencies = config["simulation"]["frequency_hz"]
    f0 = (frequencies[0] + frequencies[-1]) / 2
    fc = max(settings["excitation_fractional_bandwidth"] * f0, (frequencies[-1] - frequencies[0]) * 0.6)
    if fc >= f0:
        raise ConfigurationError("Zakres częstotliwości jest zbyt szeroki dla wybranego impulsu Gaussa.")
    coarse = C0 / (f0 + fc) / settings["cells_per_wavelength"]
    radius = min(w.radius_m for w in geometry.wires)
    fine = min(2 * radius / settings["cells_per_wire_diameter"], coarse)
    low, high = geometry.bounds
    nodes = np.array(geometry.nodes)
    port = geometry.port
    mid = (np.array(port.negative) + np.array(port.positive)) / 2
    transverse = port.transverse_size_m / 2
    anchors = [list(nodes[:, axis]) + [low[axis], high[axis]] for axis in range(3)]
    # This first adapter supports a differential port directed along x.
    anchors[0] += [port.negative[0], port.positive[0], mid[0]]
    anchors[1] += [mid[1] - transverse, mid[1], mid[1] + transverse]
    anchors[2] += [mid[2] - transverse, mid[2], mid[2] + transverse]
    for plate in geometry.plates:
        for axis in range(3):
            anchors[axis] += [plate.start[axis], plate.stop[axis]]
    axes = {name: _axis(anchor, fine, coarse, settings["padding_wavelengths"] * C0 / frequencies[0],
                         settings["growth_ratio"], settings["pml_cells"])
            for name, anchor in zip("xyz", anchors)}
    shape = [len(axes[a]) - 1 for a in "xyz"]
    cells = math.prod(shape)
    if cells > settings["max_cells"]:
        raise ConfigurationError(f"Siatka ma {cells:,} komórek, limit konfiguracji to {settings['max_cells']:,}. "
                                 "Dostosuj wymiary lub ustawienia solvera; nic nie zostało uruchomione.")
    i = settings["pml_cells"] + 1
    nf_start, nf_stop = [float(axes[a][i]) for a in "xyz"], [float(axes[a][-i-1]) for a in "xyz"]
    if np.any(np.array(nf_start) >= low) or np.any(np.array(nf_stop) <= high):
        raise ConfigurationError("Powierzchnia NF2FF musi otaczać całą antenę w wolnej przestrzeni.")
    meta = {"units": "m", "shape_cells": shape, "cell_count": cells,
            "fine_step_target_m": fine, "max_step_target_m": coarse,
            "min_step_m": min(float(np.min(np.diff(v))) for v in axes.values()),
            "excitation_center_hz": f0, "excitation_bandwidth_hz": fc,
            "nf2ff_start_m": nf_start, "nf2ff_stop_m": nf_stop,
            "boundary_conditions": [f"PML_{settings['pml_cells']}"] * 6}
    return axes, meta
