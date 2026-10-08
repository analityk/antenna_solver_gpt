"""External profile resolution. No interaction, native modules or global cache."""
from dataclasses import asdict, dataclass, fields, replace
from hashlib import sha256
from pathlib import Path
from math import pi
import tomllib

from antenna_lab.core.config import ConfigurationError
from .runtime import OpenEMSRuntime, native_boundaries

DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / 'parameters/openems_profiles.toml'
MESH_KEYS = ('cells_per_wavelength', 'min_substrate_cells_z', 'min_port_gap_cells',
             'min_port_width_cells', 'growth_ratio_target', 'growth_ratio_limit', 'max_cells')
BASE_KEYS = (*MESH_KEYS, 'air_padding_wavelengths', 'pml_cells', 'end_criteria', 'max_timesteps', 'num_threads')
RUNTIME_KEYS = tuple(f.name for f in fields(OpenEMSRuntime))
EXPERIMENT_KEYS = ('excitation_center_hz', 'excitation_cutoff_hz', 'result_frequency_hz',
                   'loss_reference_frequency_hz', 'reference_impedance_ohm')
OVERRIDE_KEYS = (*BASE_KEYS, *RUNTIME_KEYS, *EXPERIMENT_KEYS, 'field_frequency_hz')


def load_profiles(path=DEFAULT_CONFIG):
    path = Path(path).resolve()
    try:
        raw = path.read_bytes()
        data = tomllib.loads(raw.decode('utf-8-sig'))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f'openEMS profiles {path}: {exc}') from exc
    if set(data) != {'schema_version', 'default_profile', 'interaction', 'profiles'} or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ConfigurationError('openEMS profiles: expected schema_version=1 and known top-level keys.')
    if not isinstance(data['profiles'], dict) or set(data['profiles']) != {'preview', 'design', 'verify'} or data['default_profile'] not in data['profiles']:
        raise ConfigurationError('openEMS profiles: require preview/design/verify and a valid default_profile.')
    interaction = data['interaction']
    if not isinstance(interaction, dict) or set(interaction) != {'confirm_before_fdtd', 'noninteractive_requires_yes'} or any(type(v) is not bool for v in interaction.values()):
        raise ConfigurationError('openEMS interaction: two explicit boolean controls required.')
    for name, values in data['profiles'].items():
        if not isinstance(values, dict) or set(values) != set((*BASE_KEYS, *RUNTIME_KEYS)):
            raise ConfigurationError(f'openEMS profile {name}: missing or unknown parameter.')
        _settings(values, {})  # Validate even profiles not selected; no native load.
    return data, dict(config_path=str(path), config_sha256=sha256(raw).hexdigest(), schema_version=1)


def parse_override(text):
    key, sep, value = text.partition('=')
    key = key.strip(); value = value.strip()
    if not sep or key not in OVERRIDE_KEYS or not value:
        raise ConfigurationError('Expected known openEMS parameter=value (SI units; arrays in TOML syntax).')
    try:
        parsed = tomllib.loads('value = '+value)['value']
    except tomllib.TOMLDecodeError:
        if key in ('engine', 'field_frequency_policy'):
            parsed = value
        else:
            raise ConfigurationError(f'{key}: invalid value {value!r}; use numbers, true/false or TOML arrays.')
    return key, parsed


def _settings(profile, experiment):
    from antenna_lab.pcb.control import make_control_settings
    from antenna_lab.pcb.simulation import validate_pcb_simulation_settings
    base = make_control_settings()
    values = {k: v for k, v in profile.items() if k in BASE_KEYS and k != 'num_threads'}
    values['threads'] = profile['num_threads']
    values.update(experiment)
    if values.get('loss_reference_frequency_hz') is None:
        values['loss_reference_frequency_hz'] = values.get('excitation_center_hz', base.excitation_center_hz)
    if 'result_frequency_hz' in values:
        value = values['result_frequency_hz']
        if not isinstance(value, (list, tuple)):
            raise ConfigurationError('result_frequency_hz: expected an array of Hz values.')
        values['result_frequency_hz'] = tuple(value)
    runtime = {k: profile[k] for k in RUNTIME_KEYS}
    if not isinstance(runtime['boundary_conditions'], (list, tuple)):
        raise ConfigurationError('boundary_conditions: expected six-element array.')
    runtime['boundary_conditions'] = tuple(runtime['boundary_conditions'])
    values['runtime'] = OpenEMSRuntime(**runtime)
    return validate_pcb_simulation_settings(replace(base, **values))


@dataclass(frozen=True)
class ResolvedProfile:
    name: str
    settings: object
    field_frequency_hz: tuple[float, ...]
    metadata: dict
    interaction: dict


def resolve_profile(name=None, *, config_path=DEFAULT_CONFIG, experiment=None,
                    cli_overrides=None, interactive_overrides=None,
                    field_frequency_hz=None, no_fields=False):
    data, provenance = load_profiles(config_path)
    name = data['default_profile'] if name is None else name
    if name not in data['profiles']:
        raise ConfigurationError(f'Unknown openEMS profile: {name}.')
    values = dict(data['profiles'][name]); band = dict(experiment or {})
    fields_hz = field_frequency_hz
    for overrides in (cli_overrides or {}, interactive_overrides or {}):
        if set(overrides) - set(OVERRIDE_KEYS):
            raise ConfigurationError('Unknown openEMS override: '+str(sorted(set(overrides)-set(OVERRIDE_KEYS))))
        for key, value in overrides.items():
            if key in EXPERIMENT_KEYS:
                band[key] = value
            elif key == 'field_frequency_hz':
                fields_hz = value
            else:
                values[key] = value
    settings = _settings(values, band)
    if settings.runtime.max_time_s and settings.runtime.max_time_s <= 9/(pi*settings.excitation_cutoff_hz):
        raise ConfigurationError('max_time_s: physical simulated time limit is shorter than the excitation duration.')
    if no_fields and fields_hz:
        raise ConfigurationError('--no-fields conflicts with explicit field frequencies.')
    if no_fields:
        fields_hz = ()
    elif fields_hz is None:
        fields_hz = (settings.excitation_center_hz,) if settings.runtime.fields_default else ()
    from .pcb_fields import validate_field_frequencies
    if not isinstance(fields_hz, (list, tuple)):
        raise ConfigurationError('field_frequency_hz: expected an array.')
    fields_hz = validate_field_frequencies(tuple(fields_hz), settings)
    if fields_hz and settings.runtime.disable_dumps:
        raise ConfigurationError('disable_dumps=true conflicts with E/H fields; explicitly use --no-fields.')
    resolved = {**{k: getattr(settings, k) for k in BASE_KEYS if k != 'num_threads'},
                'num_threads': settings.threads, **asdict(settings.runtime),
                **{k: getattr(settings, k) for k in EXPERIMENT_KEYS},
                'field_frequency_hz': fields_hz, 'native_boundary_conditions': native_boundaries(settings)}
    return ResolvedProfile(name, settings, fields_hz,
        dict(provenance, name=name, resolved_settings=resolved,
             cli_overrides=dict(cli_overrides or {}), interactive_overrides=dict(interactive_overrides or {}),
             confirmation_mode='library_api', interaction=dict(data['interaction'])), dict(data['interaction']))
