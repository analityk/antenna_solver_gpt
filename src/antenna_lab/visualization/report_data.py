"""Read-only postprocessing for reports; no native openEMS imports or solves."""

import json
from pathlib import Path
import re

import numpy as np


def read_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def latest_run(runs_path):
    """Ignore prepared, partial and geometry-only jobs, even if newer."""
    from antenna_lab.core.catalog import completed_simulations
    candidates = completed_simulations(runs_path)
    if not candidates:
        raise ValueError(f"Brak ukończonej symulacji w {runs_path}. Możesz podać katalog wyników bezpośrednio.")
    return candidates[0][2]


def matching_index(frequencies, target):
    frequencies = np.asarray(frequencies, dtype=float)
    indices = np.flatnonzero(np.isclose(frequencies, target, rtol=1e-9, atol=0.01))
    return int(indices[0]) if len(indices) else None


def _spectrum(root, summary, mesh, start_mhz, stop_mhz, step_mhz):
    explicit = any(x is not None for x in (start_mhz, stop_mhz, step_mhz))
    if explicit and not all(x is not None for x in (start_mhz, stop_mhz, step_mhz)):
        raise ValueError("Podaj razem --start-mhz, --stop-mhz i --step-mhz.")
    dense = root / "impedance_dense.csv"
    csv_path = dense if dense.exists() else root / "impedance.csv"
    raw_available = all((root / "openems" / name).is_file() for name in ("port_ut_1", "port_it_1"))
    f = np.asarray(summary.get("frequency_hz", []), dtype=float)
    r = np.asarray(summary.get("resistance_ohm", []), dtype=float)
    x = np.asarray(summary.get("reactance_ohm", []), dtype=float)
    source = "summary.json"
    if csv_path.exists() and not explicit:
        data = np.atleast_1d(np.genfromtxt(csv_path, delimiter=",", names=True, encoding="utf-8-sig"))
        required = {"frequency_hz", "resistance_ohm", "reactance_ohm"}
        if not required.issubset(data.dtype.names or ()):
            raise ValueError(f"Brak kolumn impedancji w {csv_path.name}.")
        f, r, x = (np.asarray(data[k], dtype=float) for k in ("frequency_hz", "resistance_ohm", "reactance_ohm"))
        source = csv_path.name
    if explicit or (len(f) < 2 and raw_available and mesh):
        if not raw_available:
            raise ValueError("Gęste widmo wymaga openems/port_ut_1 i openems/port_it_1. Nie uruchomiono FDTD.")
        center, bandwidth = mesh.get("excitation_center_hz"), mesh.get("excitation_bandwidth_hz")
        if center is None or bandwidth is None or center <= 0 or bandwidth <= 0:
            raise ValueError("Brak poprawnego pasma wymuszenia w mesh.json; nie można określić zakresu widma.")
        if explicit:
            start, stop, step = np.array([start_mhz, stop_mhz, step_mhz], dtype=float) * 1e6
            if not np.all(np.isfinite([start, stop, step])) or start <= 0 or stop < start or step <= 0:
                raise ValueError("Zakres widma musi być skończony, dodatni i uporządkowany.")
            count = int(np.floor((stop - start) / step + 1e-8)) + 1
            if count > 10001:
                raise ValueError("Raport obsługuje najwyżej 10001 punktów widma; zwiększ krok.")
            if start < center - bandwidth - 0.01 or stop > center + bandwidth + 0.01:
                raise ValueError("Żądany zakres wychodzi poza pasmo wymuszenia zapisane w mesh.json.")
            f = start + np.arange(count) * step
        else:
            half = min(bandwidth, center * 0.1)
            f = np.linspace(center - half, center + half, 1001)
        # This pure NumPy reader uses each probe's own timestamps, including
        # the half-timestep offset of H. It does not import the native solver.
        from antenna_lab.solvers.power import probe_spectrum
        u = probe_spectrum(root / "openems" / "port_ut_1", f)
        i = probe_spectrum(root / "openems" / "port_it_1", f)
        if np.any(np.abs(i) <= np.finfo(float).tiny):
            raise ValueError("Zerowe widmo prądu: nie można wyznaczyć impedancji w tym zakresie.")
        z = u / i
        r, x = z.real, z.imag
        source = "DFT zapisanych openems/port_ut_1 i port_it_1"
    if not (f.ndim == r.ndim == x.ndim == 1 and 0 < len(f) == len(r) == len(x) <= 10001):
        raise ValueError("Brak zgodnych tablic częstotliwości i impedancji (1–10001 punktów).")
    if not np.all(np.isfinite([f, r, x])) or np.any(f <= 0):
        raise ValueError("Częstotliwości i impedancja muszą być skończone; częstotliwości dodatnie.")
    order = np.argsort(f)
    f, r, x = f[order], r[order], x[order]
    if np.any(np.diff(f) <= 0):
        raise ValueError("Powtórzone częstotliwości w widmie impedancji.")
    return {"frequency_mhz": (f / 1e6).tolist(), "r": r.tolist(), "x": x.tolist(), "source": source}


def load_report_data(run_path, *, start_mhz=None, stop_mhz=None, step_mhz=None,
                     simulation_completed=False):
    root = Path(run_path).resolve()
    summary = read_json(root / "summary.json")
    if not summary:
        raise ValueError(f"Brak summary.json w {root}. Wskaż katalog wyników symulacji.")
    config = read_json(root / "parameters.resolved.json")
    manifest = read_json(root / "manifest.json")
    mesh = read_json(root / "mesh.json")
    spectrum = _spectrum(root, summary, mesh, start_mhz, stop_mhz, step_mhz)
    reference = float(summary.get("reference_impedance_ohm", config.get("simulation", {}).get("reference_impedance_ohm", 50)))
    if not np.isfinite(reference) or reference <= 0:
        raise ValueError("Impedancja odniesienia musi być dodatnia i skończona.")
    targets = config.get("simulation", {}).get("frequency_hz", summary.get("frequency_hz", []))
    target = float(targets[0]) / 1e6 if targets else spectrum["frequency_mhz"][0]
    warnings = list(manifest.get("warnings", []))
    if np.any(np.array(spectrum["r"]) <= 0):
        warnings.append("W widmie jest R ≤ 0: SWR i straty niedopasowania nie są tam interpretowane jako pasywna antena.")
    log_path = root / "solver.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    native_warnings = []
    for line in log.splitlines():
        if "warning:" in line.lower() or "can't open file:" in line.lower():
            native_warnings.append(line.strip())
    # Show evidence, not a guessed convergence verdict from a generic log line.
    energy_lines = [line.strip() for line in log.splitlines() if "Energy:" in line or "energy:" in line]
    end_energy = None
    if energy_lines:
        match = re.search(r"\(\s*([-+\d.eE]+)\s*dB\s*\)", energy_lines[-1])
        if match:
            end_energy = float(match.group(1))
    data = {"root": root, "summary": summary, "config": config, "mesh": mesh,
            "manifest": manifest, "spectrum": spectrum, "reference": reference,
            "target_mhz": target, "run_id": manifest.get("run_id", root.name),
            "variant_name": manifest.get("variant_name", config.get("id", root.name)),
            "execution_status": "completed" if simulation_completed else manifest.get("status", "brak manifestu"),
            "warnings": warnings, "native_warnings": native_warnings, "end_energy_db": end_energy,
            "last_energy_line": energy_lines[-1] if energy_lines else None,
            "power": read_json(root / "power_balance.json"),
            "coverage": read_json(root / "feed_grid_coverage.json")}
    return data


def edge_work_counts(root, frequency):
    path = root / "source_work_spectra.npz"
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as raw:
        index = matching_index(raw["frequency_hz"], frequency)
        if index is None:
            return None
        edge = np.asarray(raw["edge_active_work_w"][index], dtype=float)
        total = float(raw["net_active_work_w"][index])
        if not np.all(np.isfinite(edge)) or not np.isclose(edge.sum(), total, rtol=1e-7, atol=1e-12):
            raise ValueError("Niespójna suma pracy krawędzi w source_work_spectra.npz.")
        tolerance = max(float(np.max(np.abs(edge))) * 1e-10, 1e-15)
        return {"positive": int(np.sum(edge > tolerance)), "negative": int(np.sum(edge < -tolerance)),
                "zero": int(np.sum(np.abs(edge) <= tolerance)), "net_w": total}
