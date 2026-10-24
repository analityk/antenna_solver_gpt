"""Pure Windows PCB GUI command composition; the solver remains the sole backend."""
from __future__ import annotations

import math
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys

VIEWS = ('active+geometry', 'active', 'board', 'domain')
QUALITIES = ('preview', 'design', 'verify')


def _positive(text, name):
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name}: oczekiwana liczba.') from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name}: wymagana skończona liczba dodatnia.')
    return value


def _nonnegative(text, name):
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name}: oczekiwana liczba.') from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f'{name}: wymagana skończona liczba nieujemna.')
    return value


def _fields(text):
    parts = re.split(r'[;,\s]+', text.strip()) if text.strip() else []
    return [_positive(x, 'Częstotliwości pól MHz') for x in parts]


def suggest_excitation(start_mhz, stop_mhz):
    """Center and Gaussian cutoff spanning the requested sweep under the 0.8 guard.

    Only a GUI suggestion: no automatic changes to the physical experiment.
    """
    start = _positive(start_mhz, 'Początek sweep')
    stop = _positive(stop_mhz, 'Koniec sweep')
    if stop <= start:
        raise ValueError('Koniec sweep musi być większy niż początek.')
    return (start + stop) / 2, (stop - start) / (2 * 0.8)


def command_for(action, values, *, interpreter=None):
    """No shell, no external process. Validate form and emit native CLI argv."""
    python = str(interpreter or sys.executable)
    # The double-click launcher uses pythonw.exe (no console); child CLI
    # MUST use python.exe so its native solver stdout/stderr reaches our log.
    if PureWindowsPath(python).name.lower() == 'pythonw.exe':
        python = python[:-len('pythonw.exe')] + 'python.exe'
    action = str(action)
    if action == 'report':
        run_dir = str(values.get('run_dir', '')).strip()
        if not run_dir:
            raise ValueError('Wskaż katalog ukończonego przebiegu do raportu.')
        view = values.get('field_view', 'active+geometry')
        if view not in VIEWS:
            raise ValueError('Nieznany tryb widoku pola.')
        threshold = float(values.get('threshold_db', '-40'))
        if not math.isfinite(threshold) or threshold > 0:
            raise ValueError('Próg pola musi być skończony i <= 0 dB.')
        margin = _nonnegative(values.get('margin_mm', '1'), 'Margines kadru')
        phase = int(values.get('phase_step', '15'))
        if phase not in (15, 30):
            raise ValueError('Krok fazy: 15 lub 30 stopni.')
        return [python, '-u', '-m', 'antenna_lab', 'report', run_dir,
                '--field-view', view, '--field-crop-threshold-db', str(threshold),
                '--field-crop-margin-mm', str(margin), '--phase-step', str(phase), '--open']
    if action not in ('inspect', 'prepare', 'run'):
        raise ValueError(f'Nieznany etap: {action}')
    project = str(values.get('project', '')).strip()
    if not project or Path(project).suffix.lower() != '.epro':
        raise ValueError('Wskaż pełny projekt EasyEDA Pro (*.epro).')
    if action == 'inspect':
        cmd = [python, '-u', '-m', 'antenna_lab.pcb.reduced_control',
               '--easyeda-project', project, '--inspect-source']
        pcb_id = str(values.get('pcb_id', '')).strip()
        if pcb_id:
            cmd.extend(['--source-pcb-id', pcb_id])
        return cmd
    quality = str(values.get('quality', 'design'))
    if quality not in QUALITIES:
        raise ValueError('Profil openEMS: preview, design lub verify.')
    resolution = str(values.get('geometry_um', '10'))
    if resolution not in ('100', '10', '1', '0.1'):
        raise ValueError('Rozdzielczość geometrii: 100, 10, 1 lub 0.1 µm.')
    center = _positive(values.get('center_mhz', ''), 'Środek pobudzenia')
    cutoff = _positive(values.get('cutoff_mhz', ''), 'Szerokość pobudzenia')
    low = _positive(values.get('start_mhz', ''), 'Początek sweep')
    high = _positive(values.get('stop_mhz', ''), 'Koniec sweep')
    step = _positive(values.get('step_mhz', ''), 'Krok sweep')
    if high <= low or step > high - low:
        raise ValueError('Zakres sweep musi mieć dodatnią długość i co najmniej dwa punkty.')
    # Match the backend guard: usable result frequencies lie inside
    # center ± 0.8 × cutoff, not the full nominal Gaussian bandwidth.
    guard = 0.8 * cutoff
    tolerance = 1e-9 * max(1., abs(center), abs(cutoff))
    if low < center - guard - tolerance or high > center + guard + tolerance:
        proposed_center, proposed_cutoff = suggest_excitation(low, high)
        raise ValueError(
            f'Sweep {low:g}–{high:g} MHz jest poza dopuszczalnym pasmem '
            f'pobudzenia {center-guard:g}–{center+guard:g} MHz '
            f'(środek ± 0.8 × odcięcie). Kliknij "Dopasuj pobudzenie do sweep" '
            f'lub ustaw środek {proposed_center:g} MHz i odcięcie '
            f'{proposed_cutoff:g} MHz.')
    n = (high - low) / step
    if abs(n - round(n)) > 1e-7:
        raise ValueError('Krok sweep musi dzielić zakres dokładnie (punkt końcowy).')
    if n > 10000:
        raise ValueError('Sweep > 10001 próbek; zmień krok lub zakres.')
    cmd = [python, '-u', '-m', 'antenna_lab.pcb.easyeda_control',
           '--easyeda-project', project,
           '--quality', quality, '--geometry-resolution-um', resolution,
           '--center-mhz', str(center), '--cutoff-mhz', str(cutoff),
           '--sweep-start-mhz', str(low), '--sweep-stop-mhz', str(high),
           '--sweep-step-mhz', str(step)]
    pcb_id = str(values.get('pcb_id', '')).strip()
    if pcb_id:
        cmd.extend(['--source-pcb-id', pcb_id])
    config = str(values.get('source_config', '')).strip()
    plating = str(values.get('pth_plating_um', '')).strip()
    dielectric_text=str(values.get('dielectric_materials','')).strip()
    dielectric_specs=[v.strip() for v in re.split(r'[;\\n]+',dielectric_text) if v.strip()]
    if dielectric_specs:
        from .easyeda_stackup import parse_source_dielectric_materials
        try:
            parsed=parse_source_dielectric_materials(dielectric_specs)
        except Exception as exc:
            from antenna_lab.core.config import ConfigurationError
            if not isinstance(exc,ConfigurationError):
                raise
            raise ValueError(str(exc)) from exc
    if config:
        if plating or dielectric_specs:
            raise ValueError('Ręczna source-config nie może łączyć się z PTH/dielectric GUI overrides.')
        cmd.extend(['--source-config', config])
    else:
        if plating:
            cmd.extend(['--pth-plating-um', str(_positive(plating, 'Metalizacja PTH µm'))])
        for spec in dielectric_specs:
            cmd.extend(['--dielectric-material',spec])
    mode=values.get('field_mode','far')
    if mode not in ('far','copper_surfaces'):
        raise ValueError('Tryb pól: wybierz przekroje E/H albo powierzchnie miedzi.')
    if mode=='copper_surfaces' and not values.get('fields_enabled',True):
        raise ValueError('Powierzchnie miedzi wymagają włączonego zapisu pól E/H.')
    if values.get('fields_enabled', True):
        fields = _fields(str(values.get('fields_mhz', '')))
        if not fields:
            raise ValueError('Włączono pola: wpisz częstotliwości w MHz albo wyłącz zapis pól.')
        if any(f < low - 1e-9 or f > high + 1e-9 for f in fields):
            raise ValueError('Częstotliwości pól muszą leżeć w zakresie sweep.')
        if len(set(fields)) != len(fields):
            raise ValueError('Powtórzone częstotliwości pól.')
        cmd += ['--fields-mhz', *(str(f) for f in fields)]
        if mode=='copper_surfaces':
            cmd += ['--field-mode','copper_surfaces']
    else:
        cmd.append('--no-fields')
    overrides = []
    for line in str(values.get('overrides', '')).splitlines():
        item = line.strip()
        if not item or item.startswith('#'):
            continue
        if '=' not in item or not item.split('=', 1)[0].strip():
            raise ValueError(f'Nadpisanie solvera musi mieć postać KEY=VALUE: {item}')
        overrides.append(item)
    for item in overrides:
        cmd.extend(['--openems-set', item])
    if action == 'prepare':
        cmd.append('--prepare-only')
    else:
        cmd.append('--yes')
    return cmd


def cmd_display(argv):
    """Windows CMD-safe display for ordinary argv (execution never uses a shell)."""
    return subprocess.list2cmdline(argv)


def is_matching_preparation(prepared_argv, run_argv):
    """The sole expected differences are the execution selector flags."""
    def normalized(argv):
        return tuple(v for v in argv if v not in ('--prepare-only', '--yes'))
    return bool(prepared_argv) and normalized(prepared_argv) == normalized(run_argv)
