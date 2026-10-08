"""Validated openEMS runtime controls, independent of geometry and native imports."""
from dataclasses import dataclass
from math import isfinite, pi, sqrt

from antenna_lab.core.config import ConfigurationError


@dataclass(frozen=True)
class OpenEMSRuntime:
    boundary_conditions: tuple[str, ...]
    max_time_s: float
    oversampling: int
    time_step_s: float
    time_step_factor: float
    time_step_method: int
    engine: str
    verbose: int
    dump_statistics: bool
    disable_dumps: bool
    fields_default: bool
    field_frequency_policy: str
    report_phase_step_deg: int
    exact_endcriteria: bool


def validate_runtime(runtime):
    if not isinstance(runtime, OpenEMSRuntime):
        raise ConfigurationError("runtime: expected OpenEMSRuntime settings.")
    for key in ('max_time_s', 'time_step_s', 'time_step_factor'):
        value = getattr(runtime, key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ConfigurationError(f'{key}: required finite nonnegative number.')
    if not 0 < runtime.time_step_factor <= 1:
        raise ConfigurationError('time_step_factor: required 0 < factor <= 1.')
    for key, allowed in (('time_step_method', (1, 3)), ('verbose', (0, 1, 2, 3)),
                         ('report_phase_step_deg', (15, 30))):
        value = getattr(runtime, key)
        if type(value) is not int or value not in allowed:
            raise ConfigurationError(f'{key}: expected one of {allowed}.')
    if type(runtime.oversampling) is not int or runtime.oversampling < 1:
        raise ConfigurationError('oversampling: required positive integer.')
    for key in ('dump_statistics', 'disable_dumps', 'fields_default', 'exact_endcriteria'):
        if type(getattr(runtime, key)) is not bool:
            raise ConfigurationError(f'{key}: required boolean.')
    if runtime.engine not in ('fastest', 'basic', 'sse', 'sse-compressed', 'multithreaded'):
        raise ConfigurationError('engine: unsupported openEMS engine.')
    if runtime.field_frequency_policy != 'center':
        raise ConfigurationError('field_frequency_policy: only center is supported.')
    if not isinstance(runtime.boundary_conditions, tuple) or len(runtime.boundary_conditions) != 6 or any(
            v not in ('PML', 'MUR', 'PEC', 'PMC') for v in runtime.boundary_conditions):
        raise ConfigurationError('boundary_conditions: six PML/MUR/PEC/PMC faces required, x-/x+/y-/y+/z-/z+.')
    # A forced step bypasses native stability calculation. Only the conservative
    # Cartesian CFL mode is accepted, and it is checked against the actual mesh.
    if runtime.time_step_s and runtime.time_step_method != 1:
        raise ConfigurationError('Explicit time_step_s requires time_step_method=1 (CFL); use AUTO for Rennings.')
    return runtime


def cfl_bound(mesh):
    minima = tuple(min(b-a for a, b in zip(axis, axis[1:])) for axis in
                   (mesh.x_lines_m, mesh.y_lines_m, mesh.z_lines_m))
    if any(not isfinite(d) or d <= 0 for d in minima):
        raise ConfigurationError('Preflight requires positive finite axis steps.')
    return minima, 1 / (299792458.0 * sqrt(sum(1/d**2 for d in minima)))


def runtime_preflight(settings, mesh):
    """Conservative vacuum CFL guard for Cartesian PCB (epsilon>=1, mu=1)."""
    _, cfl = cfl_bound(mesh)
    runtime = settings.runtime
    if runtime is None:
        return cfl
    validate_runtime(runtime)
    if runtime.time_step_s > cfl * runtime.time_step_factor:
        raise ConfigurationError('time_step_s exceeds conservative mesh CFL stability bound * time_step_factor; use AUTO.')
    duration = 9 / (pi * settings.excitation_cutoff_hz)
    if runtime.max_time_s and runtime.max_time_s <= duration:
        raise ConfigurationError(f'max_time_s={runtime.max_time_s:g}: physical time limit cannot contain excitation ({duration:g} s).')
    return runtime.time_step_s * runtime.time_step_factor if runtime.time_step_s else cfl * runtime.time_step_factor


def native_engine_settings(settings, mesh):
    runtime_preflight(settings, mesh)
    values = dict(NrTS=settings.max_timesteps, EndCriteria=settings.end_criteria)
    runtime = settings.runtime
    if runtime:
        values.update(OverSampling=runtime.oversampling, TimeStepFactor=runtime.time_step_factor,
                      TimeStepMethod=runtime.time_step_method)
        if runtime.max_time_s:
            values['MaxTime'] = runtime.max_time_s
        if runtime.time_step_s:
            values['TimeStep'] = runtime.time_step_s
    return values


def native_boundaries(settings):
    names = settings.runtime.boundary_conditions if settings.runtime else ('PML',) * 6
    return tuple(f'PML_{settings.pml_cells}' if name == 'PML' else name for name in names)


def native_run_options(settings):
    if settings.runtime is None:
        return {}
    r = settings.runtime
    return dict(engine=r.engine, verbose=r.verbose, disable_dumps=r.disable_dumps,
                dump_statistics=r.dump_statistics, exact_endcriteria=r.exact_endcriteria)
