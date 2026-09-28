"""Local grid work at a distributed source; diagnostic, not a port correction.

For each x-directed electric edge, pair -integral(E.dx) with the positively
oriented H circulation around its dual face. The real part of their product
measures net work into the field (source work less resistive absorption).
It avoids multiplying one voltage line by the current of the whole source.
"""

import re

import numpy as np

from antenna_lab.core.config import ConfigurationError


def edge_probe_layout(axes, voltage_lines):
    """Cover every edge of the snapped lumped element, without editing the grid.

    Current-probe requests lie inside the desired dual contour. openEMS's
    outward snapping expands them to that contour. A quarter-cell inset avoids
    floating-point ambiguity when requesting a coordinate exactly on it.
    Actual native indices are checked against the probe headers after Run.
    """
    points = np.array([p["start_m"] for p in voltage_lines])
    start = points.min(axis=0)
    stop = np.array([p["stop_m"] for p in voltage_lines]).max(axis=0)
    ranges = []
    for n, axis in enumerate("xyz"):
        a = np.asarray(axes[axis])
        lo, hi = (int(np.argmin(abs(a - value))) for value in (start[n], stop[n]))
        if not (0 < lo <= hi < len(a) - 1) or (n == 0 and lo == hi):
            raise ConfigurationError("Źródło musi mieć długość i mieścić się wewnątrz siatki.")
        ranges.append(range(lo, hi + (n != 0)))
    count = len(ranges[0]) * len(ranges[1]) * len(ranges[2])
    if count > 10000:
        raise ConfigurationError("Diagnostyka pracy źródła przekracza limit 10000 krawędzi.")
    x, y, z = (np.asarray(axes[a]) for a in "xyz")
    edges = []
    for i in ranges[0]:
        for j in ranges[1]:
            for k in ranges[2]:
                center = (x[i] + x[i + 1]) / 2
                edges.append({
                    "index": [i, j, k],
                    "voltage": {
                        "name": f"power_edge_u_{len(edges):04d}",
                        "start_m": [float(x[i]), float(y[j]), float(z[k])],
                        "stop_m": [float(x[i + 1]), float(y[j]), float(z[k])],
                        "start_index": [i, j, k], "stop_index": [i + 1, j, k]},
                    "current": {
                        "name": f"power_edge_i_{len(edges):04d}",
                        "start_m": [float(center), float(y[j] - (y[j] - y[j - 1]) / 4),
                                    float(z[k] - (z[k] - z[k - 1]) / 4)],
                        "stop_m": [float(center), float(y[j] + (y[j + 1] - y[j]) / 4),
                                   float(z[k] + (z[k + 1] - z[k]) / 4)],
                        "start_index": [i, j - 1, k - 1], "stop_index": [i, j, k]}})
    return {"method": "sum_local_negative_e_voltage_times_conjugate_h_circulation",
            "shape": [len(r) for r in ranges], "edges": edges}


def install_edge_probes(csx, layout):
    for edge in layout["edges"]:
        for kind, options in (("voltage", {"p_type": 0, "weight": -1}),
                              ("current", {"p_type": 1, "weight": 1, "norm_dir": 0})):
            item = edge[kind]
            csx.AddProbe(item["name"], **options).AddBox(item["start_m"], item["stop_m"])


def check_probe_indices(path, probe):
    """Headers print primary coordinates even for H; integer indices are decisive."""
    with path.open(encoding="utf-8") as stream:
        header = "".join(stream.readline() for _ in range(4))
    for side in ("start", "stop"):
        match = re.search(rf"% {side}-coordinates:.*?->\s*\[(\d+),(\d+),(\d+)\]", header)
        if match is None or list(map(int, match.groups())) != probe[f"{side}_index"]:
            raise RuntimeError(f"Sonda {path.name} została osadzona na nieoczekiwanych krawędziach ({side}).")


def check_aggregation(voltage, current, shape, line_voltage, plane_current):
    """Local edges must reconstruct independently recorded U lines / I contours."""
    nf = voltage.shape[0]
    reconstructed_u = voltage.reshape(nf, *shape).sum(axis=1).reshape(nf, -1)
    reconstructed_i = current.reshape(nf, *shape).sum(axis=(2, 3))
    errors = {}
    for name, actual, expected in (("voltage", reconstructed_u, line_voltage),
                                   ("current", reconstructed_i, plane_current)):
        if actual.shape != expected.shape or not np.isfinite(actual).all():
            raise RuntimeError(f"Niezgodne dane kontrolne sond {name}.")
        scale = np.max(abs(expected), axis=1)
        if np.any(scale <= 0) or not np.isfinite(scale).all():
            raise RuntimeError(f"Brak niezerowego odniesienia sond {name}.")
        relative = np.max(abs(actual - expected), axis=1) / scale
        errors[name + "_max_relative_error"] = relative.tolist()
        # Currents are summed in single precision by openEMS; allow cancellation
        # error, but never accept a missing, duplicated or wrongly snapped edge.
        if np.any(relative > 1e-4):
            raise RuntimeError(f"Suma lokalnych sond {name} nie odtwarza pomiaru całego źródła.")
    return errors


def edge_work(voltage, current, accepted, target):
    """Return individually signed contributions in the original port normalization."""
    voltage, current = np.asarray(voltage), np.asarray(current)
    accepted = np.asarray(accepted)
    if (voltage.ndim != 2 or voltage.shape != current.shape
            or accepted.shape != (voltage.shape[0],)
            or not np.isfinite(voltage).all() or not np.isfinite(current).all()
            or not np.isfinite(accepted).all() or np.any(accepted <= 0)
            or not np.isfinite(target) or target <= 0):
        raise RuntimeError("Nieprawidłowe widma lub normalizacja pracy źródła.")
    # I includes displacement current. Its contribution to active work vanishes
    # in harmonic steady state in lossless cells; finite-record error remains.
    return .5 * np.real(voltage * current.conj()) * (target / accepted[:, None])


def finish_edge_work(root, layout, frequencies, accepted, target, line_voltage, plane_current, boxes):
    from .power import probe_spectrum
    native = root / "openems"
    spectra = {}
    for kind in ("voltage", "current"):
        values = []
        for edge in layout["edges"]:
            probe = edge[kind]
            path = native / probe["name"]
            check_probe_indices(path, probe)
            values.append(probe_spectrum(path, frequencies))
        spectra[kind] = np.array(values).T
    checks = check_aggregation(spectra["voltage"], spectra["current"], layout["shape"],
                               line_voltage, plane_current)
    contributions = edge_work(spectra["voltage"], spectra["current"], accepted, target)
    totals = contributions.sum(axis=1)
    np.savez_compressed(root / "source_work_spectra.npz", frequency_hz=frequencies,
                        voltage_fourier=spectra["voltage"], current_fourier=spectra["current"],
                        edge_indices=[e["index"] for e in layout["edges"]],
                        edge_active_work_w=contributions, net_active_work_w=totals,
                        original_port_native_power=accepted, original_port_target_power_w=[target])
    result = {"method": layout["method"], "edge_count": len(layout["edges"]),
              "aggregation_checks": checks, "frequencies": [],
              "note": "Praca netto na krawędziach obszaru źródła, po odjęciu lokalnego pochłaniania. "
                      "Obejmuje błąd skończonego zapisu; nie zastępuje mocy portu ani jego impedancji. "
                      "Nie zastosowano korekty normalizacji ani zysku."}
    for frequency, total in zip(frequencies, totals):
        fluxes = {box["name"]: box["active_flux_w"] for box in boxes
                  if box["frequency_hz"] == float(frequency)}
        result["frequencies"].append({
            "frequency_hz": float(frequency), "net_active_work_w": float(total),
            "work_to_original_port_power_ratio": float(total / target),
            "surface_flux_minus_work_w": {name: float(flux - total) for name, flux in fluxes.items()}})
        print(f"Praca lokalna źródła @ {frequency / 1e6:g} MHz: {total / target:.8f} mocy portu", flush=True)
    return result
