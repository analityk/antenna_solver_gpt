"""Small direct ZIP/member transport. Never extracts files or changes provenance."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import stat
from zipfile import ZipFile, BadZipFile

from antenna_lab.core.config import ConfigurationError

MAX_ARCHIVE_MEMBERS = 4096
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024


def file_sha256(path):
    digest = sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ZipMember:
    archive_path: Path
    member_name: str
    stored_name: str

    @property
    def name(self): return PurePosixPath(self.member_name).name
    @property
    def suffix(self): return PurePosixPath(self.member_name).suffix
    @property
    def stem(self): return PurePosixPath(self.member_name).stem
    def __str__(self): return f'{self.archive_path}::{self.member_name}'
    def read_bytes(self):
        try:
            with ZipFile(self.archive_path) as archive, archive.open(self.stored_name) as stream:
                data = stream.read(MAX_MEMBER_BYTES + 1)
                if len(data) > MAX_MEMBER_BYTES:
                    raise ConfigurationError(f'ZIP member exceeds size limit: {self}')
                return data
        except (OSError, BadZipFile, RuntimeError, NotImplementedError, KeyError) as exc:
            raise ConfigurationError(f'Cannot read ZIP member {self}: {exc}') from exc
    def read_text(self, encoding='utf-8', errors='strict'):
        return self.read_bytes().decode(encoding, errors)


def member(value):
    return value if isinstance(value, ZipMember) else Path(value)


def read_gerber(value):
    from gerbonara import GerberFile
    value = member(value)
    if isinstance(value, ZipMember):
        return GerberFile.from_string(value.read_text('utf-8-sig'), filename=str(value))
    return GerberFile.open(value, enable_includes=False)


def zip_members(path):
    """Validate the entire directory before reading bounded, individual members."""
    path = Path(path).resolve()
    try:
        if path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ConfigurationError('PCB ZIP exceeds archive size limit.')
        with ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_MEMBERS:
                raise ConfigurationError('PCB ZIP exceeds member count limit.')
            seen, total, result = set(), 0, []
            for info in entries:
                name = info.orig_filename.replace('\\', '/')
                parts = name.rstrip('/').split('/')
                if (not name or '\x00' in name or name.startswith('/') or
                    any(p in ('', '.', '..') or ':' in p for p in parts) or
                    re.match(r'^[A-Za-z]:', name)):
                    raise ConfigurationError(f'Unsafe ZIP member name: {name!r}')
                key = name.rstrip('/').casefold()
                if key in seen:
                    raise ConfigurationError(f'Duplicate normalized ZIP member: {name}')
                seen.add(key)
                mode = stat.S_IFMT(info.external_attr >> 16)
                is_dir = name.endswith('/')
                if mode not in (0, stat.S_IFDIR if is_dir else stat.S_IFREG):
                    raise ConfigurationError(f'ZIP symlink/special entry unsupported: {name}')
                if info.flag_bits & (1 | 64):
                    raise ConfigurationError(f'Encrypted ZIP member unsupported: {name}')
                total += info.file_size
                if info.file_size > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:
                    raise ConfigurationError(f'PCB ZIP exceeds uncompressed size limit: {name}')
                if not is_dir:
                    result.append(ZipMember(path, name, info.filename))
            return tuple(sorted(result, key=lambda m:m.member_name))
    except (OSError, BadZipFile) as exc:
        raise ConfigurationError(f'Invalid PCB ZIP {path}: {exc}') from exc


def resolve_bundle_root(members):
    from .bundle import _role
    if any(m.suffix.lower() == '.enet' for m in members):
        raise ConfigurationError('PCB ZIP internal .enet unsupported; external hierarchical ENET is authoritative.')
    roots = {str(PurePosixPath(m.member_name).parent) for m in members
             if _role(m) not in ('unclassified',)}
    if len(roots) != 1:
        raise ConfigurationError('PCB ZIP requires one Gerber bundle root; candidates: '+(', '.join(sorted(roots)) or '(none)'))
    root = roots.pop()
    if root != '.' and len(PurePosixPath(root).parts) != 1:
        raise ConfigurationError(f'PCB ZIP supports only root or one wrapper directory: {root}')
    selected = tuple(m for m in members if str(PurePosixPath(m.member_name).parent) == root)
    return root, selected
