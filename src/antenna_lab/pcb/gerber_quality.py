"""Explicit Gerber-only quality profiles and optimistic Cartesian cost bounds."""
from dataclasses import replace
from math import ceil, isfinite, pi, sqrt

from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.pcb_mesh import C0
from .control import make_control_settings
from .simulation import validate_pcb_simulation_settings


def gerber_quality_settings(quality='design', **frequency_settings):
    from antenna_lab.solvers.profiles import resolve_profile
    profile = resolve_profile(quality, experiment=frequency_settings)
    return profile.settings, profile.settings.runtime.exact_endcriteria


def gerber_cost_preflight(mesh, settings):
    """Vacuum CFL upper bound: actual native dt may be smaller. No runtime prediction."""
    minima = tuple(min(b-a for a,b in zip(axis,axis[1:])) for axis in
                   (mesh.x_lines_m, mesh.y_lines_m, mesh.z_lines_m))
    if any(not isfinite(d) or d <= 0 for d in minima):
        raise ConfigurationError('Gerber preflight requires positive finite axis steps.')
    dt = 1 / (C0 * sqrt(sum(1/d**2 for d in minima)))
    from antenna_lab.solvers.runtime import runtime_preflight
    effective_dt = runtime_preflight(settings, mesh)
    duration = 9 / (pi * settings.excitation_cutoff_hz)
    steps = ceil(duration / effective_dt)
    return dict(min_axis_steps_m=dict(zip('xyz',minima)), cell_count=mesh.cell_count,
        estimated_cfl_dt_s=dt, estimated_effective_dt_s=effective_dt, gaussian_pulse_duration_s=duration,
        estimated_excitation_steps=steps, estimated_cell_updates=mesh.cell_count*steps,
        cost_estimate_note='Optimistic excitation-only lower bound; native dt may be smaller and decay takes additional steps.')


def require_excitation_fits(cost, settings):
    if cost['estimated_excitation_steps'] >= settings.max_timesteps:
        raise ConfigurationError(
            f"Gerber excitation needs at least {cost['estimated_excitation_steps']} steps, "
            f"but max_timesteps={settings.max_timesteps}. No native FDTD started. "
            'Coarsen numerical resolution, review critical anchor spacing, or explicitly increase the timestep budget; '
            'allow additional time for field decay.')
