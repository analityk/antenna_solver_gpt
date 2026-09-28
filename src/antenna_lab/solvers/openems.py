"""openEMS 0.37 adapter. Native Windows integration requires local verification."""

import csv
import importlib
import importlib.metadata
import os
from pathlib import Path

import numpy as np

from antenna_lab.core.config import ConfigurationError, write_json
from .mesh import make_mesh

ETA0 = 376.730313668


def native_modules():
    try:
        ems = importlib.import_module("openEMS")
        csx = importlib.import_module("CSXCAD")
        return ems, csx
    except (ImportError, OSError) as exc:
        raise ConfigurationError("Nie można załadować openEMS/CSXCAD. Użyj projektowego .venv i sprawdź "
                                 "CSXCAD_INSTALL_PATH; instrukcja: docs/windows-setup.md. " + str(exc)) from exc


def check_capabilities(config):
    request = config["requested_outputs"]
    if request["currents"] or request["field_planes"] or request["full_period_animation"]:
        raise ConfigurationError("Ten adapter obsługuje obecnie impedancję i pole dalekie. "
                                 "Odczyt prądów (M2), przekroje E/H i animacje (M3) pozostają do implementacji; żądanie nie zostało pominięte.")
    if config["solver"].get("power_diagnostics") and not request["far_field"]:
        raise ConfigurationError("Diagnostyka mocy wymaga aktywnego zapisu NF2FF (far_field=true).")


def prepare(geometry, config, run):
    check_capabilities(config)
    axes, meta = make_mesh(geometry, config)
    ems_module, csx_module = native_modules()
    settings = config["solver"]
    engine = ems_module.openEMS(NrTS=settings["max_timesteps"], EndCriteria=settings["end_criteria"])
    csx = csx_module.ContinuousStructure()
    engine.SetCSX(csx)
    engine.SetGaussExcite(meta["excitation_center_hz"], meta["excitation_bandwidth_hz"])
    engine.SetBoundaryCond(meta["boundary_conditions"])
    grid = csx.GetGrid()
    grid.SetDeltaUnit(1.0)
    for axis, lines in axes.items():
        grid.SetLines(axis, lines)
    metal = csx.AddMetal("radiator_PEC")
    for wire in geometry.wires:
        metal.AddCylinder(start=list(wire.start), stop=list(wire.stop), radius=wire.radius_m, priority=10)
    # Junction spheres join the finite-radius cylinders without microscopic gaps.
    radius = geometry.wires[0].radius_m
    if any(w.radius_m != radius for w in geometry.wires):
        raise ConfigurationError("Adapter wymaga obecnie jednego promienia przewodów.")
    for node in geometry.nodes:
        metal.AddSphere(center=list(node), radius=radius, priority=10)
    for plate in geometry.plates:
        reflector = csx.AddMetal(plate.id + "_PEC")
        reflector.AddBox(start=list(plate.start), stop=list(plate.stop), priority=10)
    p = geometry.port
    if p.negative[1:] != p.positive[1:] or p.negative[0] >= p.positive[0]:
        raise ConfigurationError("Adapter wymaga obecnie portu skierowanego w +x.")
    half = p.transverse_size_m / 2
    start = [p.negative[0], p.negative[1] - half, p.negative[2] - half]
    stop = [p.positive[0], p.positive[1] + half, p.positive[2] + half]
    port = engine.AddLumpedPort(1, config["simulation"]["reference_impedance_ohm"], start, stop, "x", 1.0, priority=5)
    nf = None
    if config["requested_outputs"]["far_field"]:
        nf = engine.CreateNF2FFBox(start=meta["nf2ff_start_m"], stop=meta["nf2ff_stop_m"],
                                  frequency=config["simulation"]["frequency_hz"])
    if settings.get("power_diagnostics"):
        from .power import install_monitors
        install_monitors(engine, csx, geometry, axes, meta, config, run)
    native_path = run.path / "openems"
    native_path.mkdir()
    xml = native_path / "model.xml"
    engine.Write2XML(str(xml))
    if not xml.is_file() or xml.stat().st_size == 0:
        raise RuntimeError("openEMS nie zapisał model.xml.")
    np.savez_compressed(run.path / "mesh.npz", **axes)
    write_json(run.path / "mesh.json", meta)
    try:
        csx_version = importlib.metadata.version("CSXCAD")
    except importlib.metadata.PackageNotFoundError:
        csx_version = getattr(csx_module, "__version__", "unknown")
    run.manifest["solver"] = {"name": "openEMS", "version": ems_module.__version__, "csxcad_version": csx_version,
                              "settings": settings, "mesh": meta,
                              "feed": {"start_m": start, "stop_m": stop, "direction": "+x", "square_caps": True}}
    run.save()
    return engine, csx, port, nf, native_path


def port_quantities(voltage, current, reference, accepted_power):
    voltage, current = np.asarray(voltage, complex), np.asarray(current, complex)
    if np.any(~np.isfinite(voltage)) or np.any(~np.isfinite(current)) or np.any(np.abs(current) == 0):
        raise RuntimeError("Nieprawidłowe napięcie lub prąd portu; wynik nie został znormalizowany.")
    z = voltage / current
    power = 0.5 * np.real(voltage * current.conj())
    if np.any(power <= 0) or np.any(~np.isfinite(power)):
        raise RuntimeError("Moc przyjęta przez port musi być dodatnia i skończona.")
    s11 = (z - reference) / (z + reference)
    if np.any(np.abs(s11) >= 1):
        raise RuntimeError("Port pasywnej anteny ma |S11| >= 1; sprawdź orientację i dyskretyzację portu.")
    scale = np.sqrt(accepted_power / power) * np.exp(-1j * np.angle(voltage))
    return z, s11, (1 + np.abs(s11)) / (1 - np.abs(s11)), power, scale


def solve(prepared, config, run):
    engine, csx, port, nf, native_path = prepared
    from .native_io import prepare_native_io
    run.manifest["solver"]["native_io"] = prepare_native_io(native_path / "model.xml")
    run.save()
    cwd = Path.cwd()
    try:
        result = engine.Run(str(native_path), cleanup=False, numThreads=config["solver"]["threads"])
    finally:
        os.chdir(cwd)  # openEMS.Run changes the process working directory.
    if result not in (None, 0):
        raise RuntimeError(f"openEMS zakończył przygotowanie z kodem {result}.")
    frequency = np.asarray(config["simulation"]["frequency_hz"], float)
    reference = config["simulation"]["reference_impedance_ohm"]
    target = config["simulation"]["accepted_power_w"]
    port.CalcPort(str(native_path), frequency, ref_impedance=reference)
    z, s11, swr, native_power, scale = port_quantities(port.uf_tot, port.if_tot, reference, target)
    np.savez_compressed(run.path / "port_spectra.npz", frequency_hz=frequency,
                        voltage_fourier=port.uf_tot, current_fourier=port.if_tot, native_power=native_power,
                        normalization_factor=scale,
                        convention=np.array("Native openEMS pulse Fourier spectra, not unnormalised sinusoidal amplitudes"))
    with (run.path / "impedance.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["frequency_hz", "resistance_ohm", "reactance_ohm", "reference_ohm", "s11_real", "s11_imag", "swr"])
        for i, f in enumerate(frequency):
            writer.writerow([f, z[i].real, z[i].imag, reference, s11[i].real, s11[i].imag, swr[i]])
    summary = {"validation_status": "unverified", "accepted_power_w": target,
               "note": "Roboczy wynik FDTD. Wymaga kontroli źródła i zbieżności; nie jest zweryfikowaną charakterystyką anteny.",
               "frequency_hz": frequency.tolist(), "resistance_ohm": z.real.tolist(), "reactance_ohm": z.imag.tolist(),
               "swr": swr.tolist(), "reference_impedance_ohm": reference}
    if nf is not None:
        from .power import require_box_files
        # Native CalcNF2FF silently skips absent E/H pairs. Require a closed box.
        require_box_files(native_path, "nf2ff")
        step = config["solver"]["far_field_step_deg"]
        theta = np.linspace(0, 180, int(np.ceil(180 / step)) + 1)
        phi = np.unique(np.r_[np.arange(0, 360, step), 0, 90, 180, 270])
        far = nf.CalcNF2FF(str(native_path), frequency, theta, phi, center=[0, 0, 0], radius=1, read_cached=False)
        if not np.allclose(far.freq, frequency, rtol=1e-10, atol=0):
            raise RuntimeError("Częstotliwości NF2FF nie zgadzają się z konfiguracją.")
        e_theta = np.asarray(far.E_theta) * scale[:, None, None]
        e_phi = np.asarray(far.E_phi) * scale[:, None, None]
        prad = np.asarray(far.Prad, float).reshape(-1) * np.abs(scale) ** 2
        if np.any(~np.isfinite(e_theta)) or np.any(~np.isfinite(e_phi)) or np.any(~np.isfinite(prad)) or np.any(prad <= 0):
            raise RuntimeError("Nieprawidłowe pole dalekie albo moc promieniowana.")
        intensity = (np.abs(e_theta) ** 2 + np.abs(e_phi) ** 2) / (2 * ETA0)  # radius = 1 m
        gain = 4 * np.pi * intensity / target
        directivity = 4 * np.pi * intensity / prad[:, None, None]
        realized = gain * (1 - np.abs(s11) ** 2)[:, None, None]
        np.savez_compressed(run.path / "far_field.npz", frequency_hz=frequency, theta_deg=theta, phi_deg=phi,
                            e_theta_v_per_m=e_theta, e_phi_v_per_m=e_phi, reference_distance_m=np.array([1.0]),
                            gain_linear=gain, directivity_linear=directivity, realized_gain_linear=realized,
                            radiated_power_w=prad, accepted_power_w=np.array([target]),
                            phasor_convention=np.array("real(F * exp(+j * phase)); phase zero = positive port voltage"))
        summary["radiation_to_accepted_power_ratio"] = (prad / target).tolist()
        if np.any(np.abs(prad / target - 1) > 0.1):
            run.manifest["warnings"].append("Bilans mocy PEC odbiega o ponad 10%; wymagana kontrola portu, siatki i czasu zaniku.")
        summary["forward_gain_dbi"] = [float(10 * np.log10(v)) if v > 0 else None for v in gain[:, 0, 0]]
    run.manifest["warnings"].append("Nie wykonano kontroli zbieżności. Osiągnięcie EndCriteria należy sprawdzić w solver.log.")
    run.manifest["normalization"]["applied"] = True
    write_json(run.path / "summary.json", summary)
    if config["solver"].get("power_diagnostics"):
        from .power import finish_diagnostics
        finish_diagnostics(config, run)
    return summary
