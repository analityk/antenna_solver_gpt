"""Derive the PCB electrical contract from placed EasyEDA Pro instances.

Never infer values from a footprint, manufacture barrel plating, or launch FDTD.
An explicit PCB instance Value wins over a referenced Device Value; the latter
is only a fallback for ordinary passives, NEVER an excitation source.
"""
import argparse
import json
from math import isfinite
from pathlib import Path
import re

from antenna_lab.core.config import ConfigurationError
from .components import ideal_value
from .easyeda_project import load_easyeda_project, resolve_project_components


def _passive_value(ref, value):
    """The recorded unit, not the footprint, selects the ideal R/L/C model."""
    possible = []
    for kind in ('R', 'L', 'C'):
        try:
            ideal_value(kind, value)
        except ConfigurationError:
            pass
        else:
            possible.append(kind)
    if len(possible) != 1:
        raise ConfigurationError(
            f'EasyEDA {ref}: value {value!r} has no unique supported R/L/C unit; '
            'set a unit-bearing Value on the PCB instance (or its referenced Device).')
    kind = possible[0]
    # Refdes is not a footprint type. A contradictory refdes/value is evidence
    # of an unresolved electrical role, not permission to silently reinterpret.
    expected = re.fullmatch(r'([RLC])\d+[A-Za-z]?', ref)
    if expected and expected.group(1) != kind:
        raise ConfigurationError(
            f'EasyEDA {ref}: designator implies {expected.group(1)} but Value '
            f'{value!r} has {kind} units; resolve the CAD conflict.')
    return kind


def derive_source_config(project, *, bindings=None, pth_plating_um=None):
    """Return (source-config JSON object, CAD evidence) without parsing PCB shapes.

    The latter makes this usable even when a new non-electrical PCB record is not
    yet supported by the physical importer. No defaults are assigned to plating.
    """
    if bindings is None:
        bindings = resolve_project_components(project)
    sources = [c for c in bindings if c['role'] == 'source']
    if len(sources) != 1:
        raise ConfigurationError(
            f'EasyEDA automatic excitation requires exactly one explicitly marked '
            f'CAD source, found {len(sources)}; use a source role/CSRC in CAD '
            'or provide an explicit --source-config.')
    index = sources[0]['source_index']
    if type(index) is not int or index != 0:
        raise ConfigurationError('EasyEDA automatic single-source mode requires source_index=0.')
    config = {'port': {'mode': 'source', 'source_index': index}, 'component_values': {}}
    evidence = {'mode': 'derived_from_project', 'source_designator': sources[0]['designator'],
                'component_value_origins': {}}
    devices = project.data['project'].get('devices', {})
    for component in bindings:
        if component['role'] == 'source':
            continue
        ref = component['designator']
        attributes = component['attributes']
        value = attributes.get('Value')
        origin = 'pcb_instance'
        if value is None or (isinstance(value, str) and not value.strip()):
            device = devices.get(component.get('device_id'), {})
            value = device.get('attributes', {}).get('Value')
            origin = 'referenced_device'
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(
                f'EasyEDA {ref}: no unit-bearing Value on PCB instance or referenced '
                'Device; cannot generate a physical component value.')
        kind = _passive_value(ref, value)
        config['component_values'][ref] = {'kind': kind, 'value': value.strip()}
        evidence['component_value_origins'][ref] = origin
    if pth_plating_um is not None:
        if (isinstance(pth_plating_um, bool) or not isinstance(pth_plating_um, (int, float))
                or not isfinite(pth_plating_um) or pth_plating_um <= 0):
            raise ConfigurationError('EasyEDA explicit PTH plating must be finite and >0 um.')
        config['drills'] = {'pth_model': 'solid_pec_equivalent',
                            'pth_plating_um': float(pth_plating_um)}
        evidence['pth_plating_origin'] = 'explicit_user_option'
    return config, evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate an EasyEDA electrical source-config from source CAD; no FDTD.')
    parser.add_argument('--easyeda-project', type=Path, required=True)
    parser.add_argument('--source-pcb-id')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pth-plating-um', type=float, help='Explicit fabrication assumption; never inferred from CAD')
    args = parser.parse_args(argv)
    try:
        project = load_easyeda_project(args.easyeda_project, pcb_id=args.source_pcb_id)
        config, evidence = derive_source_config(project, pth_plating_um=args.pth_plating_um)
        if args.output.suffix.lower() != '.json':
            raise ConfigurationError('Source configuration output must be a .json file.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(config, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
        print('Source configuration: '+str(args.output.resolve()))
        print('CAD value origins: '+json.dumps(evidence, ensure_ascii=False, sort_keys=True))
        print('PTH plating is omitted unless supplied explicitly; native model validation will enforce it if needed.')
        return 0
    except (ConfigurationError, ValueError, OSError) as exc:
        print(f'EasyEDA automatic source-config: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
