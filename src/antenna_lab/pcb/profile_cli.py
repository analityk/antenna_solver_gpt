"""Current-run approval only at the CLI boundary; never edits the TOML file."""
from math import pi
import sys
from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.profiles import resolve_profile, parse_override, MESH_KEYS


def print_profile(profile):
    s = profile.metadata['resolved_settings']
    print(f"\nopenEMS profile: {profile.name}\nsource: {profile.metadata['config_path']}")
    groups = {
        'MESH': MESH_KEYS,
        'DOMAIN / BC (x-/x+/y-/y+/z-/z+)': ('air_padding_wavelengths', 'pml_cells', 'native_boundary_conditions'),
        'TIME / CONVERGENCE': ('end_criteria', 'max_timesteps', 'max_time_s', 'time_step_s',
                               'time_step_factor', 'time_step_method', 'oversampling', 'exact_endcriteria'),
        'EXPERIMENT (Hz / ohm)': ('excitation_center_hz', 'excitation_cutoff_hz', 'result_frequency_hz',
                                'loss_reference_frequency_hz', 'reference_impedance_ohm'),
        'OUTPUT': ('fields_default', 'field_frequency_policy', 'field_frequency_hz', 'report_phase_step_deg'),
        'RUNTIME': ('num_threads', 'engine', 'verbose', 'dump_statistics', 'disable_dumps'),
    }
    for group, keys in groups.items():
        print(group)
        for key in keys:
            value = s[key]
            if key == 'max_timesteps': value = f'{value} (NrTS safety ceiling)'
            if key == 'max_time_s': value = f'{value:g} s (physical simulated time, NOT wall-clock)' if value else 'OFF'
            if key == 'time_step_s': value = f'{value:g} s' if value else 'AUTO'
            if key == 'time_step_method': value = f'{value} ({"CFL" if value == 1 else "Rennings"})'
            print(f'  {key:32} {value}')
    if s['max_time_s']:
        print(f"  approximate df = 1/MaxTime: {1/s['max_time_s']:g} Hz")
    print('Fields: '+('ON' if profile.field_frequency_hz else 'OFF'), flush=True)


def approve_profile(resolve_kwargs, *, yes=False, prepare_only=False):
    """Return accepted resolved profile or None on cancellation. No native calls."""
    edits = {}
    while True:
        profile = resolve_profile(**resolve_kwargs, interactive_overrides=edits)
        print_profile(profile)
        if prepare_only:
            mode = 'prepare_only'
        elif yes:
            mode = 'yes_flag'
        elif not sys.stdin.isatty():
            if profile.interaction['noninteractive_requires_yes'] or profile.interaction['confirm_before_fdtd']:
                raise ConfigurationError('Noninteractive FDTD requires --yes; no native solver was started.')
            mode = 'noninteractive_config'
        elif not profile.interaction['confirm_before_fdtd']:
            mode = 'confirmation_disabled'
        else:
            try:
                answer = input('Continue? [Y]es / [N]o / [E]dit: ').strip().lower()
            except EOFError:
                return None
            if answer == 'n':
                return None
            if answer == 'y':
                mode = 'interactive_yes'
            elif answer == 'e':
                pending = dict(edits)
                while True:
                    try:
                        key = input('parameter (blank = finish; names above, SI units): ').strip()
                        if not key: break
                        old = pending.get(key, profile.metadata['resolved_settings'].get(key, '?'))
                        value = input(f'value [{old}]: ').strip()
                        name, parsed = parse_override(key+'='+value)
                        pending[name] = parsed
                    except EOFError:
                        return None
                    except ConfigurationError as exc:
                        print(f'Invalid edit: {exc}')
                try:
                    resolve_profile(**resolve_kwargs, interactive_overrides=pending)
                    edits = pending
                except ConfigurationError as exc:
                    print(f'Invalid edits (not applied): {exc}')
                continue
            else:
                print('Choose Y, N or E.'); continue
        profile.metadata['confirmation_mode'] = mode
        return profile
