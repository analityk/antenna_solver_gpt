"""One explicit Gerber PCB run using the existing economical PCB pipeline."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys
from tempfile import mkdtemp

from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from .config import load_pcb_config
from .control import (make_control_settings, run_control_model, add_frequency_arguments,
                      frequency_arguments_hz)
from .gerber import load_pcb_geometry
from .port import resolve_pcb_lumped_port
from .transform import normalize_port_orientation


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def run_gerber_control(config_path, output_dir, *, prepare_only=False, **frequency_settings):
    """Import, normalize once, preflight, then XML or one normal solve. No sweep."""
    config = load_pcb_config(config_path)
    source = load_pcb_geometry(config)
    geometry, transform = normalize_port_orientation(source)
    settings = make_control_settings(**frequency_settings)
    # Fail unsafe contacts before native modules are loaded or any engine is created.
    mesh = make_pcb_domain_mesh(geometry, settings)
    resolve_pcb_lumped_port(geometry, mesh, settings)
    output = Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ConfigurationError(f'PCB Gerber: wymagany pusty/nowy katalog {output}.')
    metadata = {
        'config_path': str(Path(config_path).resolve()),
        'resolved_config': {key: str(value) if isinstance(value, Path) else value
                            for key,value in asdict(config).items()},
        'files': {role: {'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()}
                  for role,path in (('top_copper',config.copper_top_path),('outline',config.board_outline_path))},
        'dependencies': {name: version(name) for name in ('gerbonara','shapely')},
        'normalization': asdict(transform), 'assumptions': list(geometry.assumptions),
        'port_edge_mode': 'aligned', 'validation_status': 'unverified',
    }
    print('PCB Gerber: '+str(output), flush=True)
    for assumption in geometry.assumptions:
        print('  '+assumption, flush=True)
    try:
        if prepare_only:
            output.mkdir(parents=True, exist_ok=True)
            native = output/'native'
            native.mkdir()
            _, _, _, _, _, preparation = prepare_pcb_xml_model(geometry, settings, native/'model.xml')
            result = dict(status='prepared', validation_status='unverified', preparation=preparation,
                simulation_settings=asdict(settings), mesh={'shape_cells': mesh.shape_cells, 'cell_count': mesh.cell_count})
        else:
            # Default aligned mesh, ordinary termination policy: no diagnostic Run flags.
            result = run_control_model(geometry, settings, output)
            result['status'] = 'completed'
        result['import'] = metadata
        _write_json(output/'summary.json', result)
    except (Exception, KeyboardInterrupt) as exc:
        if output.is_dir():
            _write_json(output/'import_failure.json', dict(status='failed', error=str(exc), import_metadata=metadata))
        raise
    finally:
        if output.is_dir():
            _write_json(output/'geometry.source.json', source.as_dict())
            _write_json(output/'geometry.json', geometry.as_dict())
            _write_json(output/'import.json', metadata)
    return json.loads(json.dumps(result, allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Import top-copper/outline Gerbers and run one unverified PCB model')
    parser.add_argument('config', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--prepare-only', action='store_true', help='Write native XML without running FDTD')
    add_frequency_arguments(parser)
    args = parser.parse_args(argv)
    try:
        output = args.output
        if output is None:
            root = Path('outcomes/pcb_gerber')
            root.mkdir(parents=True, exist_ok=True)
            output = Path(mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_'), dir=root))
        result = run_gerber_control(args.config, output, prepare_only=args.prepare_only, **frequency_arguments_hz(args))
        print(f"Status: {result['status']}; validation_status: unverified\n{output.resolve()/'summary.json'}")
        if not args.prepare_only:
            print(output.resolve()/'impedance.csv')
        return 0
    except (ConfigurationError, OSError, RuntimeError, ValueError, KeyboardInterrupt) as exc:
        print(f'PCB Gerber: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
