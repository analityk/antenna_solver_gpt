"""Separate PCB experiment settings in SI; no geometry or solver construction."""

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path

from antenna_lab.core.config import ConfigurationError, validate_schema


@dataclass(frozen=True)
class PcbSimulationSettings:
    schema_version: int
    result_frequency_hz: tuple[float, ...]
    excitation_center_hz: float
    excitation_cutoff_hz: float
    reference_impedance_ohm: float
    cells_per_wavelength: float
    min_substrate_cells_z: int
    min_port_gap_cells: int
    min_port_width_cells: int
    growth_ratio_target: float
    growth_ratio_limit: float
    max_cells: int
    loss_reference_frequency_hz: float
    max_timesteps: int
    end_criteria: float
    threads: int
    air_padding_wavelengths: float
    pml_cells: int


def validate_pcb_simulation_config(value: dict) -> dict:
    """Validate without mutation; 0.8 is the project's excitation quality margin."""
    validate_schema(value, "pcb-simulation.schema.json")
    frequencies = value["result_frequency_hz"]
    if any(a >= b for a, b in zip(frequencies, frequencies[1:])):
        raise ConfigurationError("result_frequency_hz: wymagany porządek ściśle rosnący.")
    center, cutoff = value["excitation"]["center_hz"], value["excitation"]["cutoff_hz"]
    if cutoff >= center:
        raise ConfigurationError("excitation.cutoff_hz musi być mniejsze od center_hz.")
    if not isfinite(center + cutoff):
        raise ConfigurationError("excitation: center_hz + cutoff_hz musi być skończone.")
    low, high = center - .8 * cutoff, center + .8 * cutoff
    if any(not low <= f <= high for f in frequencies):
        raise ConfigurationError("result_frequency_hz: wymagany zakres center_hz ± 0.8 * cutoff_hz.")
    mesh = value["mesh"]
    if mesh["growth_ratio_target"] > mesh["growth_ratio_limit"]:
        raise ConfigurationError("mesh: growth_ratio_target nie może przekraczać growth_ratio_limit.")
    return value


def load_pcb_simulation_settings(path) -> PcbSimulationSettings:
    """Read one UTF-8/BOM JSON experiment; all input units already are SI."""
    with Path(path).open(encoding="utf-8-sig") as stream:
        value = validate_pcb_simulation_config(json.load(stream))
    mesh, fdtd = value["mesh"], value["fdtd"]
    return PcbSimulationSettings(
        schema_version=value["schema_version"],
        result_frequency_hz=tuple(float(f) for f in value["result_frequency_hz"]),
        excitation_center_hz=value["excitation"]["center_hz"],
        excitation_cutoff_hz=value["excitation"]["cutoff_hz"],
        reference_impedance_ohm=value["port"]["reference_impedance_ohm"],
        cells_per_wavelength=mesh["cells_per_wavelength"],
        min_substrate_cells_z=int(mesh["min_substrate_cells_z"]),
        min_port_gap_cells=int(mesh["min_port_gap_cells"]),
        min_port_width_cells=int(mesh["min_port_width_cells"]),
        growth_ratio_target=mesh["growth_ratio_target"],
        growth_ratio_limit=mesh["growth_ratio_limit"], max_cells=int(mesh["max_cells"]),
        loss_reference_frequency_hz=value["material"]["loss_reference_frequency_hz"],
        max_timesteps=int(fdtd["max_timesteps"]), end_criteria=fdtd["end_criteria"],
        threads=int(fdtd["threads"]),
        air_padding_wavelengths=value["domain"]["air_padding_wavelengths"],
        pml_cells=int(value["domain"]["pml_cells"]),
    )
