"""Passive power diagnostics. Never rescale fields to force energy closure."""

import csv
from pathlib import Path
import zipfile

import numpy as np

from antenna_lab.core.config import ConfigurationError, write_json


def require_box_files(folder, name):
    paths = [Path(folder) / f"{name}_{kind}_{face}.h5"
             for face in range(6) for kind in "EH"]
    missing = [p.name for p in paths if not p.is_file() or p.stat().st_size == 0]
    if missing:
        raise RuntimeError("Niekompletna powierzchnia pomiarowa: " + ", ".join(missing))
    return paths


def _weights(lines):
    lines = np.asarray(lines, float)
    if len(lines) == 1:
        return np.ones(1)
    delta = np.diff(lines)
    if np.any(delta <= 0):
        raise RuntimeError("Linie powierzchni muszą rosnąć ściśle.")
    return np.r_[delta[0] / 2, (delta[:-1] + delta[1:]) / 2, delta[-1] / 2]


def _read_surface(path, frequency):
    import h5py
    with h5py.File(path, "r") as data:
        if int(data["Mesh"].attrs["mesh_type"]) != 0:
            raise RuntimeError("Diagnostyka mocy wymaga siatki kartezjańskiej.")
        lines = [np.asarray(data["Mesh"][axis], float) for axis in "xyz"]
        frequencies = np.asarray(data["FieldData/FD"].attrs["frequency"], float)
        match = np.flatnonzero(np.isclose(frequencies, frequency, rtol=1e-12, atol=0))
        if len(match) != 1:
            raise RuntimeError(f"Brak jednoznacznych pól dla {frequency:g} Hz: {path}")
        key = f"FieldData/FD/f{match[0]}"
        if key not in data:
            raise RuntimeError("Diagnostyka wymaga zespolonego formatu NXYZ z openEMS 0.37.0rc3.")
        dataset = data[key]
        if not np.isclose(float(dataset.attrs["frequency"]), frequency, rtol=1e-12, atol=0):
            raise RuntimeError(f"Częstotliwość próbek nie zgadza się z nagłówkiem w {path}.")
        order = dataset.attrs.get("d_order", "")
        if isinstance(order, bytes):
            order = order.decode("ascii")
        if order != "NXYZ" or not np.issubdtype(dataset.dtype, np.complexfloating):
            raise RuntimeError(f"Nieobsługiwany układ danych pola w {path}.")
        field = np.asarray(dataset, complex)
        if field.shape != (3, *(len(axis) for axis in lines)) or not np.isfinite(field).all():
            raise RuntimeError(f"Nieprawidłowe próbki pola w {path}.")
        if any(not np.isfinite(axis).all() or not len(axis) for axis in lines):
            raise RuntimeError(f"Nieprawidłowa siatka w {path}.")
        return lines, field


def integrate_box(folder, name, frequency, start, stop, native_accepted_power, target_power=1.0):
    """Integrate signed 0.5 Re(E x H*) on all six faces, in double precision.

    Native pulse spectra carry time factors; only the explicitly normalized
    values below are powers in W. A feed box is a flux measurement, not Prad.
    """
    require_box_files(folder, name)
    if not np.isfinite(native_accepted_power) or native_accepted_power <= 0:
        raise RuntimeError("Diagnostyka wymaga dodatniej mocy odniesienia portu.")
    scale2 = target_power / native_accepted_power
    faces, meshes = [], []
    for face in range(6):
        lines, electric = _read_surface(Path(folder) / f"{name}_E_{face}.h5", frequency)
        h_lines, magnetic = _read_surface(Path(folder) / f"{name}_H_{face}.h5", frequency)
        if not all(np.array_equal(a, b) for a, b in zip(lines, h_lines)):
            raise RuntimeError(f"Siatki E/H różnią się na ścianie {face} powierzchni {name}.")
        normal, side = divmod(face, 2)
        bound = (start, stop)[side][normal]
        if (len(lines[normal]) != 1
                or not np.isclose(lines[normal][0], bound, rtol=1e-7, atol=1e-10)):
            raise RuntimeError(f"Ściana {face} powierzchni {name} ma nieoczekiwane położenie.")
        for axis in range(3):
            if axis != normal and (len(lines[axis]) < 2
                    or not np.isclose(lines[axis][0], start[axis], rtol=1e-7, atol=1e-10)
                    or not np.isclose(lines[axis][-1], stop[axis], rtol=1e-7, atol=1e-10)):
                raise RuntimeError(f"Powierzchnia {name} nie jest zamkniętym prostopadłościanem.")
        meshes.append(lines)
        one, two = (normal + 1) % 3, (normal + 2) % 3
        density = (side * 2 - 1) * 0.5 * (
            electric[one] * magnetic[two].conj() - electric[two] * magnetic[one].conj())
        weights = [_weights(axis) for axis in lines]
        area = weights[0][:, None, None] * weights[1][None, :, None] * weights[2][None, None, :]
        flux = np.sum(area * density) * scale2
        faces.append({"face": ("-x", "+x", "-y", "+y", "-z", "+z")[face],
                      "active_flux_w": float(flux.real), "reactive_flux_var": float(flux.imag),
                      "shape": [len(axis) for axis in lines]})
    for axis in range(3):
        tangent_meshes = [m[axis] for face, m in enumerate(meshes) if face // 2 != axis]
        if not all(np.array_equal(tangent_meshes[0], m) for m in tangent_meshes[1:]):
            raise RuntimeError(f"Niezgodne krawędzie ścian powierzchni {name}.")
    total = sum(item["active_flux_w"] for item in faces)
    return {"name": name, "frequency_hz": frequency, "active_flux_w": total,
            "flux_to_port_power_ratio": total / target_power, "faces": faces}


def probe_spectrum(path, frequencies):
    data = np.loadtxt(path, comments="%", ndmin=2)
    if data.shape[1] != 2 or len(data) < 3 or not np.isfinite(data).all():
        raise RuntimeError(f"Nieprawidłowe próbki sondy: {path}")
    time, samples = data.T
    delta = np.diff(time)
    if np.any(delta <= 0) or not np.allclose(delta, delta[0], rtol=1e-7, atol=0):
        raise RuntimeError(f"Niejednorodne znaczniki czasu: {path}")
    # Use each probe's own timestamps, including the half-step offset of H/I.
    freq = np.asarray(frequencies, float)
    result = np.empty(len(freq), complex)
    for offset in range(0, len(freq), 128):
        batch = freq[offset:offset + 128]
        result[offset:offset + len(batch)] = 2 * delta[0] * (
            np.exp(-2j * np.pi * batch[:, None] * time[None, :]) @ samples)
    return result


def monitor_layout(geometry, axes, mesh, settings):
    spectrum_frequencies(settings, mesh)  # Reject invalid ranges before an expensive solve.
    def snap(point):
        return [float(axes[axis][np.argmin(abs(axes[axis] - value))])
                for axis, value in zip("xyz", point)]
    low, high = map(np.asarray, geometry.bounds)
    outer_low, outer_high = np.asarray(mesh["nf2ff_start_m"]), np.asarray(mesh["nf2ff_stop_m"])
    fraction = settings["inner_box_fraction"]
    inner_low = snap(low + fraction * (outer_low - low))
    inner_high = snap(high + fraction * (outer_high - high))
    if not (np.all(inner_low < low) and np.all(inner_high > high)
            and np.all(inner_low > outer_low) and np.all(inner_high < outer_high)):
        raise ConfigurationError("Wewnętrzna powierzchnia mocy musi otaczać antenę i mieścić się w NF2FF.")
    port = geometry.port
    center = (np.asarray(port.negative) + np.asarray(port.positive)) / 2
    half = port.transverse_size_m / 2
    start = np.array([port.negative[0], center[1] - half, center[2] - half])
    stop = np.array([port.positive[0], center[1] + half, center[2] + half])
    margin = settings["feed_margin_diameters"] * port.transverse_size_m
    feed_low, feed_high = snap(start - margin), snap(stop + margin)
    if not (np.all(feed_low < start) and np.all(feed_high > stop)
            and np.all(np.asarray(feed_low) > inner_low) and np.all(np.asarray(feed_high) < inner_high)):
        raise ConfigurationError("Powierzchnia źródła nie mieści się wewnątrz powierzchni anteny.")
    indices = [(int(np.argmin(abs(axes[a] - start[n]))), int(np.argmin(abs(axes[a] - stop[n]))))
               for n, a in enumerate("xyz")]
    transverse = [axes[a][i:j + 1] for a, (i, j) in zip("yz", indices[1:])]
    voltage = []
    for y in transverse[0]:
        for z in transverse[1]:
            voltage.append({"name": f"power_u_{len(voltage):03d}",
                            "start_m": [float(start[0]), float(y), float(z)],
                            "stop_m": [float(stop[0]), float(y), float(z)]})
    i, j = indices[0]
    x_midpoints = (axes["x"][i:j] + axes["x"][i + 1:j + 1]) / 2
    current = []
    for x in x_midpoints:
        current.append({"name": f"power_i_{len(current):03d}",
                        "start_m": [float(x), float(start[1]), float(start[2])],
                        "stop_m": [float(x), float(stop[1]), float(stop[2])]})
    return {"method": "passive_monitors_same_geometry_mesh_excitation",
            "boxes": [{"name": "nf2ff", "start_m": outer_low.tolist(), "stop_m": outer_high.tolist(),
                       "scope": "whole_antenna_outer"},
                      {"name": "power_inner", "start_m": inner_low, "stop_m": inner_high,
                       "scope": "whole_antenna_inner"},
                      {"name": "power_feed", "start_m": feed_low, "stop_m": feed_high,
                       "scope": "source_region_flux_not_far_field"}],
            "voltage_probes": voltage, "current_probes": current}


def spectrum_frequencies(settings, mesh):
    spec = settings["port_spectrum_hz"]
    count = int(np.floor((spec["stop"] - spec["start"]) / spec["step"] + 1e-9)) + 1
    if not 1 <= count <= 10001:
        raise ConfigurationError("Diagnostyczne widmo portu musi zawierać 1–10001 punktów.")
    frequencies = spec["start"] + spec["step"] * np.arange(count)
    if np.any(abs(frequencies - mesh["excitation_center_hz"]) > mesh["excitation_bandwidth_hz"]):
        raise ConfigurationError("Diagnostyczne częstotliwości portu wychodzą poza deklarowane pasmo impulsu.")
    return frequencies


def install_monitors(engine, csx, geometry, axes, mesh, config, run):
    layout = monitor_layout(geometry, axes, mesh, config["solver"]["power_diagnostics"])
    if config["solver"]["power_diagnostics"].get("source_edge_work", False):
        from .source_work import edge_probe_layout, install_edge_probes
        layout["source_edge_work"] = edge_probe_layout(axes, layout["voltage_probes"])
        install_edge_probes(csx, layout["source_edge_work"])
    for box in layout["boxes"][1:]:
        # Reuse the native surface recorder; do NOT transform the feed box to far field.
        engine.CreateNF2FFBox(name=box["name"], start=box["start_m"], stop=box["stop_m"],
                             frequency=config["simulation"]["frequency_hz"])
    for item in layout["voltage_probes"]:
        csx.AddProbe(item["name"], p_type=0, weight=-1).AddBox(item["start_m"], item["stop_m"])
    for item in layout["current_probes"]:
        csx.AddProbe(item["name"], p_type=1, weight=1, norm_dir=0).AddBox(item["start_m"], item["stop_m"])
    write_json(run.path / "power_monitor_layout.json", layout)


def finish_diagnostics(config, run):
    import json
    import h5py
    native_path = run.path / "openems"
    layout = json.loads((run.path / "power_monitor_layout.json").read_text(encoding="utf-8"))
    with np.load(run.path / "port_spectra.npz", allow_pickle=False) as data:
        frequencies = data["frequency_hz"]
        accepted = data["native_power"]
        native_voltage, native_current = data["voltage_fourier"], data["current_fourier"]
    target = config["simulation"]["accepted_power_w"]
    boxes = [integrate_box(native_path, box["name"], float(freq), box["start_m"], box["stop_m"], float(power), target)
             for freq, power in zip(frequencies, accepted) for box in layout["boxes"]]
    with h5py.File(native_path / "nf2ff.h5", "r") as data:
        native_radiated = np.atleast_1d(data["nf2ff"].attrs["Prad"])
    if native_radiated.shape != accepted.shape:
        raise RuntimeError("Liczba częstotliwości mocy NF2FF nie zgadza się z portem.")
    comparisons = []
    for index, freq in enumerate(frequencies):
        measured = boxes[index * len(layout["boxes"])]
        expected = float(native_radiated[index] / accepted[index])
        comparisons.append({"frequency_hz": float(freq), "openems_ratio": expected,
                            "independent_ratio": measured["flux_to_port_power_ratio"]})
        if not np.isclose(expected, measured["flux_to_port_power_ratio"], rtol=1e-5, atol=1e-8):
            raise RuntimeError("Niezależne całkowanie nie odtwarza Prad openEMS. Zachowano surowe dane.")
    voltage = np.array([probe_spectrum(native_path / p["name"], frequencies) for p in layout["voltage_probes"]]).T
    current = np.array([probe_spectrum(native_path / p["name"], frequencies) for p in layout["current_probes"]]).T
    np.savez_compressed(run.path / "port_probe_spectra.npz", frequency_hz=frequencies,
                        voltage_fourier=voltage, current_fourier=current,
                        original_voltage_fourier=native_voltage, original_current_fourier=native_current,
                        voltage_positions_m=[p["start_m"][1:] for p in layout["voltage_probes"]],
                        current_positions_m=[p["start_m"][0] for p in layout["current_probes"]])
    mesh = json.loads((run.path / "mesh.json").read_text(encoding="utf-8"))
    frequency_dense = spectrum_frequencies(config["solver"]["power_diagnostics"], mesh)
    u = probe_spectrum(native_path / "port_ut_1", frequency_dense)
    i = probe_spectrum(native_path / "port_it_1", frequency_dense)
    from .openems import port_quantities
    z, s11, swr, _, _ = port_quantities(u, i, config["simulation"]["reference_impedance_ohm"], target)
    with (run.path / "impedance_dense.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["frequency_hz", "resistance_ohm", "reactance_ohm", "reference_ohm", "swr", "s11_real", "s11_imag"])
        reference = np.full(len(frequency_dense), config["simulation"]["reference_impedance_ohm"])
        writer.writerows(zip(frequency_dense, z.real, z.imag, reference, swr, s11.real, s11.imag))
    result = {"validation_status": "unverified", "accepted_power_w": target, "boxes": boxes,
              "native_comparison": comparisons,
              "note": "Pomiary lokalizują rozbieżność; nie stanowią kontroli zbieżności ani korekty zysku. "
                      "Moc powierzchni źródła jest strumieniem netto, nie charakterystyką pola dalekiego. "
                      "Gęsty krok widma nie jest deklaracją rozdzielczości ani dokładności fizycznej."}
    with np.load(run.path / "mesh.npz", allow_pickle=False) as axes:
        ratios = {}
        for axis in "xyz":
            delta = np.diff(axes[axis])
            ratios[axis] = float(np.max(np.maximum(delta[1:] / delta[:-1], delta[:-1] / delta[1:])))
    result["mesh_max_adjacent_cell_ratio"] = ratios
    if "source_edge_work" in layout:
        from .source_work import finish_edge_work
        result["source_edge_work"] = finish_edge_work(
            run.path, layout["source_edge_work"], frequencies, accepted, target, voltage, current, boxes)
    write_json(run.path / "power_balance.json", result)
    for item in boxes:
        print(f"Bilans {item['name']} @ {item['frequency_hz']/1e6:g} MHz: "
              f"{item['flux_to_port_power_ratio']:.8f} mocy portu", flush=True)
    return result


def pack_diagnostics(path):
    """A small evidence bundle; the original native field files remain in the run."""
    root = Path(path)
    names = ["power_balance.json", "power_monitor_layout.json", "port_probe_spectra.npz",
             "impedance_dense.csv", "port_spectra.npz", "parameters.resolved.json", "mesh.json", "mesh.npz",
             "summary.json", "solver.log", "source.zip", "openems/model.xml",
             "openems/port_ut_1", "openems/port_it_1", "openems/et", "openems/ht"]
    paths = [root / name for name in names]
    paths.extend(sorted((root / "openems").glob("power_[ui]_*")))
    import json
    layout = json.loads((root / "power_monitor_layout.json").read_text(encoding="utf-8"))
    if "source_edge_work" in layout:
        paths.append(root / "source_work_spectra.npz")
        paths.extend(root / "openems" / edge[kind]["name"]
                     for edge in layout["source_edge_work"]["edges"] for kind in ("voltage", "current"))
    bundle = root / "power_diagnostics.zip"
    with zipfile.ZipFile(bundle, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            if not path.is_file():
                raise RuntimeError(f"Brak pliku diagnostycznego: {path}")
            archive.write(path, path.relative_to(root).as_posix())
    return bundle
