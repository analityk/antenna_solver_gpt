"""Explicit Gerber-only quality profiles and optimistic Cartesian cost bounds."""
from dataclasses import replace
from math import ceil, isfinite, pi, sqrt

from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.pcb_mesh import C0
from .control import make_control_settings
from .simulation import validate_pcb_simulation_settings


def gerber_quality_settings(quality='design', **frequency_settings):
    profiles = {
        'preview': (10, 2, 2, .10, 6, 1e-3, 50000),
        'design': (15, 3, 2, .15, 6, 1e-4, 75000),
        'verify': (20, 4, 4, .25, 8, 1e-5, 120000),
    }
    if quality not in profiles:
        raise ConfigurationError('Gerber quality must be preview, design or verify.')
    wave, z, port, padding, pml, end, steps = profiles[quality]
    settings = replace(make_control_settings(**frequency_settings),
        cells_per_wavelength=wave, min_substrate_cells_z=z,
        min_port_gap_cells=port, min_port_width_cells=port,
        air_padding_wavelengths=padding, pml_cells=pml,
        end_criteria=end, max_timesteps=steps)
    return validate_pcb_simulation_settings(settings), quality == 'verify'


def gerber_cost_preflight(mesh, settings):
    """Vacuum CFL upper bound: actual native dt may be smaller. No runtime prediction."""
    minima = tuple(min(b-a for a,b in zip(axis,axis[1:])) for axis in
                   (mesh.x_lines_m, mesh.y_lines_m, mesh.z_lines_m))
    if any(not isfinite(d) or d <= 0 for d in minima):
        raise ConfigurationError('Gerber preflight requires positive finite axis steps.')
    dt = 1 / (C0 * sqrt(sum(1/d**2 for d in minima)))
    duration = 9 / (pi * settings.excitation_cutoff_hz)
    steps = ceil(duration / dt)
    return dict(min_axis_steps_m=dict(zip('xyz',minima)), cell_count=mesh.cell_count,
        estimated_cfl_dt_s=dt, gaussian_pulse_duration_s=duration,
        estimated_excitation_steps=steps, estimated_cell_updates=mesh.cell_count*steps,
        cost_estimate_note='Optimistic excitation-only lower bound; native dt may be smaller and decay takes additional steps.')


def require_excitation_fits(cost, settings):
    if cost['estimated_excitation_steps'] >= settings.max_timesteps:
        raise ConfigurationError(
            f"Gerber excitation needs at least {cost['estimated_excitation_steps']} steps, "
            f"but max_timesteps={settings.max_timesteps}. No native FDTD started. "
            'Coarsen numerical resolution, review critical anchor spacing, or explicitly increase the timestep budget; '
            'allow additional time for field decay.')
