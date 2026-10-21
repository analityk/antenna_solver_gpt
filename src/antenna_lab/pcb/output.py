"""Atomic PCB run numbering shared by full-wave and lightweight FAST."""
from pathlib import Path
from antenna_lab.core.catalog import variant_slug


def allocate_output_dir(config_path, root):
    """Create <input-name>_<series> without timestamps or random suffixes."""
    source=Path(config_path)
    name=source.name if source.is_dir() else source.stem
    prefix=variant_slug(name) or 'pcb'
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    used=[]
    marker=prefix+'_'
    for path in root.iterdir():
        if not path.is_dir() or not path.name.startswith(marker):continue
        suffix=path.name[len(marker):]
        if suffix.isdigit():used.append(int(suffix))
    number=max(used,default=0)+1
    while True:
        candidate=root/f'{prefix}_{number:03d}'
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            number+=1

