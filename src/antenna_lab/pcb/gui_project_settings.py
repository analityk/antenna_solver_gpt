"""Per-project PCB GUI settings. Sidecar storage, never CAD or solver state.

One settings directory per project *folder*, not per EPRO file: multiple .epro
files in a single gerbs subfolder always share the same settings. Paths outside
the repository's gerbs tree use a stable suffix to prevent accidental collisions.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile


SCHEMA_VERSION = 1
SETTINGS_FILE = 'gui-settings.json'


def project_parameters_dir(project_path, repository_root):
    root = Path(repository_root).resolve()
    project = Path(project_path).expanduser()
    if not project.is_absolute():
        project = root / project
    project = project.resolve()
    if project.suffix.lower() != '.epro':
        raise ValueError('Parametry projektu: wymagany plik EasyEDA .epro.')
    folder = project.parent
    try:
        relative = folder.relative_to((root / 'gerbs').resolve())
    except ValueError:
        # Outside gerbs: make this folder stable and collision-resistant, while
        # still sharing the directory across .epro siblings in the same folder.
        name = folder.name or 'external'
        digest = sha256(str(folder).casefold().encode('utf-8')).hexdigest()[:10]
        relative = Path(f'{name}-{digest}')
    if relative == Path('.'):
        relative = Path(project.stem)  # .epro directly under gerbs/
    return root / 'parameters' / relative


def read_project_settings(directory, project_folder, defaults):
    """Load only known GUI keys, keep physics defaults explicit in caller."""
    path = Path(directory) / SETTINGS_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f'Nie można odczytać {path}: {exc}') from exc
    if (not isinstance(data, dict) or data.get('schema_version') != SCHEMA_VERSION
            or not isinstance(data.get('settings'), dict)
            or data.get('project_folder') != str(Path(project_folder).resolve())):
        raise ValueError(f'{path}: niezgodny format lub inny folder źródłowy.')
    result = {}
    for key, default in defaults.items():
        if key in ('project', 'csxcad_path'):
            continue
        value = data['settings'].get(key)
        if type(value) is type(default):
            result[key] = value
    return result


def write_project_settings(directory, project_folder, values, defaults):
    """Atomic replacement of *only* our managed sidecar; never delete CAD."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    settings = {
        key: values[key] for key, default in defaults.items()
        if key not in ('project', 'csxcad_path')
        and key in values and type(values[key]) is type(default)
    }
    record = dict(schema_version=SCHEMA_VERSION,
                  project_folder=str(Path(project_folder).resolve()),
                  settings=settings)
    payload = json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=directory,
                                         prefix='.gui-settings-', suffix='.tmp',
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        os.replace(temporary, directory / SETTINGS_FILE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return directory / SETTINGS_FILE
