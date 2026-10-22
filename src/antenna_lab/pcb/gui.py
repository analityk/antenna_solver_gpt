"""Native Windows Tkinter front-end for the existing EasyEDA PCB CLI.

The GUI does not model PCB physics and never invokes openEMS in its own process.
Each stage runs as a separate subprocess with argv (shell=False); GUI shutdown
does not attempt to repair or rewrite incomplete native run artifacts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .gui_commands import cmd_display, command_for, is_matching_preparation

ROOT = Path(__file__).resolve().parents[3]
PREFS = Path.home() / '.antenna_lab_pcb_gui.json'
DEFAULTS = {
    'project': '', 'pcb_id': '', 'source_config': '', 'pth_plating_um': '',
    'quality': 'design', 'geometry_um': '10', 'center_mhz': '1500',
    'cutoff_mhz': '1400', 'start_mhz': '1000', 'stop_mhz': '2000',
    'step_mhz': '100', 'fields_enabled': True, 'fields_mhz': '1000 2000',
    'csxcad_path': r'C:\dev\openems\openEMS', 'overrides': '',
    'run_dir': '', 'field_view': 'active+geometry', 'threshold_db': '-40',
    'margin_mm': '1', 'phase_step': '15', 'open_after_run': True,
}


class PcbDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Antenna Lab  |  PCB EasyEDA → openEMS')
        self.geometry('1140x810')
        self.minsize(900, 650)
        self._events = queue.Queue()
        self._process = None
        self._busy = False
        self._cancelled = False
        self._command_prepared = None
        self._current_run = None
        self._current_stage = None
        self._stage_report = False
        self._ready = False
        values = dict(DEFAULTS)
        try:
            saved = json.loads(PREFS.read_text(encoding='utf-8'))
            if isinstance(saved, dict):
                values.update({k: v for k, v in saved.items()
                               if k in DEFAULTS and isinstance(v, type(DEFAULTS[k]))})
        except (OSError, ValueError, TypeError):
            pass
        self.var = {key: (tk.BooleanVar(value=value) if isinstance(value, bool)
                          else tk.StringVar(value=value))
                    for key, value in values.items() if key != 'overrides'}
        self.overrides_initial = values['overrides']
        self.preview_mode = tk.StringVar(value='prepare')
        self.status = tk.StringVar(value='Wskaż plik .epro i rozpocznij od inspekcji.')
        self._make_widgets()
        for v in self.var.values():
            v.trace_add('write', lambda *_: self._refresh_preview())
        self.preview_mode.trace_add('write', lambda *_: self._refresh_preview())
        self._ready = True
        self._refresh_preview()
        self.after(100, self._drain_events)
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _make_widgets(self):
        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TButton', padding=(11, 6))
        style.configure('Run.TButton', padding=(12, 6), font=('Segoe UI', 10, 'bold'))
        style.configure('Header.TLabel', font=('Segoe UI', 16, 'bold'))
        style.configure('Status.TLabel', font=('Segoe UI', 10))
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='PCB EasyEDA · kreator symulacji', style='Header.TLabel').pack(anchor='w')
        ttk.Label(outer, text='Import CAD → inspekcja → siatka → FDTD → raport E/H. Bez ręcznego JSON-a i bez powtarzania FDTD przy zmianie widoku.',
                  wraplength=1070).pack(anchor='w', pady=(2, 12))

        project_row = ttk.Frame(outer)
        project_row.pack(fill='x', pady=(0, 8))
        ttk.Label(project_row, text='Plik .epro:').pack(side='left', padx=(0, 8))
        ttk.Entry(project_row, textvariable=self.var['project']).pack(side='left', fill='x', expand=True)
        self.browse_project = ttk.Button(project_row, text='Wybierz projekt…', command=self._choose_project)
        self.browse_project.pack(side='left', padx=(8, 0))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill='x', pady=(0, 9))
        tab_exp = ttk.Frame(notebook, padding=12)
        tab_solver = ttk.Frame(notebook, padding=12)
        tab_report = ttk.Frame(notebook, padding=12)
        notebook.add(tab_exp, text='  Eksperyment i pola  ')
        notebook.add(tab_solver, text='  Solver i źródło  ')
        notebook.add(tab_report, text='  Raport  ')
        self._tab_experiment(tab_exp)
        self._tab_solver(tab_solver)
        self._tab_report(tab_report)

        workflow = ttk.Frame(outer)
        workflow.pack(fill='x', pady=(2, 8))
        self.buttons = {}
        for mode, caption in (
            ('inspect', '1. Sprawdź projekt'),
            ('prepare', '2. Przygotuj siatkę'),
            ('run', '3. Uruchom FDTD'),
            ('report', '4. Raport i pola E/H'),
        ):
            self.buttons[mode] = ttk.Button(workflow, text=caption,
                style='Run.TButton' if mode == 'run' else 'TButton',
                command=lambda stage=mode: self._start(stage))
            self.buttons[mode].pack(side='left', padx=(0, 8))
        self.stop_button = ttk.Button(workflow, text='Przerwij', command=self._stop, state='disabled')
        self.stop_button.pack(side='right')

        command_row = ttk.Frame(outer)
        command_row.pack(fill='x')
        ttk.Label(command_row, text='Podgląd polecenia CMD:').pack(side='left')
        ttk.Combobox(command_row, textvariable=self.preview_mode, state='readonly', width=13,
                     values=('inspect', 'prepare', 'run', 'report')).pack(side='left', padx=(8, 0))
        ttk.Button(command_row, text='Kopiuj', command=self._copy_command).pack(side='right')
        self.command_text = tk.Text(outer, height=3, wrap='word', font=('Consolas', 9))
        self.command_text.pack(fill='x', pady=(3, 7))
        self.command_text.configure(state='disabled')

        status_row = ttk.Frame(outer)
        status_row.pack(fill='x', pady=(0, 5))
        ttk.Label(status_row, textvariable=self.status, style='Status.TLabel',
                  wraplength=950).pack(side='left', fill='x', expand=True)
        ttk.Button(status_row, text='Otwórz katalog wyników', command=self._open_folder).pack(side='right')
        ttk.Label(outer, text='Log programu (bieżący przebieg i błędy):').pack(anchor='w')
        self.console = scrolledtext.ScrolledText(outer, height=11, wrap='word',
                                                font=('Consolas', 9))
        self.console.pack(fill='both', expand=True)
        self.console.tag_config('error', foreground='#b33b32')
        self.console.tag_config('info', foreground='#376b8b')

    def _field(self, parent, label, key, row, column=0, width=16, help_text=None):
        base = column * 3
        ttk.Label(parent, text=label).grid(row=row, column=base, sticky='w', pady=6, padx=(0, 8))
        entry = ttk.Entry(parent, textvariable=self.var[key], width=width)
        entry.grid(row=row, column=base+1, sticky='we', padx=(0, 20))
        if help_text:
            ttk.Label(parent, text=help_text, foreground='#666').grid(
                row=row, column=base+2, sticky='w', padx=(0, 15))
        return entry

    def _tab_experiment(self, frame):
        self._field(frame, 'Środek pobudzenia', 'center_mhz', 0, help_text='MHz')
        self._field(frame, 'Odcięcie pobudzenia', 'cutoff_mhz', 1, help_text='MHz')
        self._field(frame, 'Sweep od', 'start_mhz', 0, 1, help_text='MHz')
        self._field(frame, 'Sweep do', 'stop_mhz', 1, 1, help_text='MHz')
        self._field(frame, 'Krok sweep', 'step_mhz', 2, help_text='MHz')
        ttk.Checkbutton(frame, text='Zapisz pola E i H', variable=self.var['fields_enabled']).grid(
            row=3, column=0, columnspan=2, sticky='w', pady=5)
        self._field(frame, 'Pola przy', 'fields_mhz', 3, 1, width=20, help_text='MHz, np. 1000 2000')
        ttk.Label(frame, text='Zakres i częstotliwości dobierasz do projektu; GUI ich nie odczytuje ani nie zgaduje z nazwy pliku.',
                  foreground='#666').grid(row=4, column=0, columnspan=6, sticky='w', pady=(4, 0))

    def _tab_solver(self, frame):
        ttk.Label(frame, text='Profil openEMS').grid(row=0, column=0, sticky='w', padx=(0, 8), pady=5)
        ttk.Combobox(frame, values=('preview', 'design', 'verify'), textvariable=self.var['quality'],
                     width=18, state='readonly').grid(row=0, column=1, sticky='w')
        ttk.Label(frame, text='Geometria [µm]').grid(row=1, column=0, sticky='w', pady=5)
        ttk.Combobox(frame, values=('100','10','1','0.1'), textvariable=self.var['geometry_um'],
                     width=18, state='readonly').grid(row=1, column=1, sticky='w')
        self._field(frame, 'PCB ID (opcjonalnie)', 'pcb_id', 2, width=35)
        self._field(frame, 'PTH metalizacja', 'pth_plating_um', 3, width=14, help_text='µm, tylko gdy wymagane')
        ttk.Label(frame, text='CSXCAD_INSTALL_PATH').grid(row=4, column=0, sticky='w', pady=5)
        ttk.Entry(frame, textvariable=self.var['csxcad_path'], width=50).grid(
            row=4, column=1, columnspan=3, sticky='we')
        ttk.Label(frame, text='Konfiguracja źródła').grid(row=5, column=0, sticky='w', pady=5)
        ttk.Entry(frame, textvariable=self.var['source_config'], width=50).grid(
            row=5, column=1, columnspan=3, sticky='we')
        ttk.Button(frame, text='Wskaż JSON…', command=self._choose_config).grid(row=5, column=4, padx=10)
        ttk.Label(frame, text='Puste pole: automatyczne odczytanie CSRC oraz wartości R/L/C z .epro.',
                  foreground='#666').grid(row=6, column=0, columnspan=5, sticky='w')
        ttk.Label(frame, text='Opcjonalne nadpisania solvera (KEY=VALUE, po jednym wierszu):'
                  ).grid(row=7, column=0, columnspan=5, sticky='w', pady=(9, 2))
        self.overrides_text = tk.Text(frame, height=4, width=90, wrap='none', font=('Consolas', 9))
        self.overrides_text.insert('1.0', self.overrides_initial)
        self.overrides_text.grid(row=8, column=0, columnspan=5, sticky='we')
        self.overrides_text.bind('<KeyRelease>', lambda _: self._refresh_preview())

    def _tab_report(self, frame):
        ttk.Label(frame, text='Katalog FDTD:').grid(row=0, column=0, sticky='w', pady=7)
        ttk.Entry(frame, textvariable=self.var['run_dir'], width=90).grid(
            row=0, column=1, columnspan=4, sticky='we', padx=(5, 8))
        ttk.Button(frame, text='Wybierz…', command=self._choose_run).grid(row=0, column=5)
        ttk.Label(frame, text='Kadrowanie pól').grid(row=1, column=0, sticky='w', pady=7)
        ttk.Combobox(frame, textvariable=self.var['field_view'],
                     values=('active+geometry','active','board','domain'), width=20,
                     state='readonly').grid(row=1, column=1, sticky='w')
        self._field(frame, 'Próg pola [dB]', 'threshold_db', 2)
        self._field(frame, 'Margines [mm]', 'margin_mm', 3)
        ttk.Label(frame, text='Krok fazy').grid(row=1, column=3, sticky='w', padx=(30, 8))
        ttk.Combobox(frame, textvariable=self.var['phase_step'],
                     values=('15','30'), width=8, state='readonly'
                     ).grid(row=1, column=4, sticky='w')
        ttk.Checkbutton(frame, text='Automatycznie otwórz raport po udanym FDTD',
                        variable=self.var['open_after_run']).grid(
                            row=4, column=0, columnspan=5, sticky='w', pady=9)
        ttk.Label(frame, text='Raport korzysta z istniejących CSV/NPZ. Zmiana fazy lub kadru nie uruchamia FDTD.',
                  foreground='#666').grid(row=5, column=0, columnspan=6, sticky='w')

    def _values(self):
        values = {name: variable.get() for name, variable in self.var.items()}
        values['overrides'] = self.overrides_text.get('1.0', 'end-1c')
        return values

    def _save_preferences(self):
        try:
            PREFS.write_text(json.dumps(self._values(), indent=2, ensure_ascii=False)+'\n',
                             encoding='utf-8')
        except OSError as exc:
            self._log(f'Nie zapisano preferencji GUI: {exc}\n', 'error')

    def _choose_project(self):
        initial = self.var['project'].get()
        file = filedialog.askopenfilename(
            title='Wybierz projekt EasyEDA Pro', initialdir=str(Path(initial).parent) if initial else str(ROOT),
            filetypes=[('Projekt EasyEDA Pro', '*.epro'), ('Wszystkie pliki', '*.*')])
        if file:
            if file != self.var['project'].get():
                self.var['source_config'].set('')
                self.var['pth_plating_um'].set('')
                self._command_prepared = None
            self.var['project'].set(file)
            self.status.set('Wybrano projekt. Inspekcja sprawdzi model źródłowy bez FDTD.')

    def _choose_config(self):
        file = filedialog.askopenfilename(
            title='Opcjonalny source-config', filetypes=[('JSON','*.json'),('Wszystkie','*.*')])
        if file:
            self.var['source_config'].set(file)

    def _choose_run(self):
        folder = filedialog.askdirectory(title='Wskaż katalog wyników FDTD', initialdir=str(ROOT / 'outcomes'))
        if folder:
            self.var['run_dir'].set(folder)

    def _refresh_preview(self):
        if not self._ready:
            return
        try:
            command = cmd_display(command_for(self.preview_mode.get(), self._values()))
        except (ValueError, TypeError, KeyError) as exc:
            command = f'Wybierz wymagane dane: {exc}'
        self.command_text.configure(state='normal')
        self.command_text.delete('1.0', 'end')
        self.command_text.insert('1.0', command)
        self.command_text.configure(state='disabled')

    def _copy_command(self):
        self.clipboard_clear()
        self.clipboard_append(self.command_text.get('1.0', 'end-1c'))
        self.status.set('Skopiowano podgląd do schowka.')

    def _log(self, message, tag=None):
        self.console.configure(state='normal')
        self.console.insert('end', message, tag)
        self.console.see('end')
        self.console.configure(state='disabled')

    def _set_busy(self, busy):
        self._busy = busy
        for button in self.buttons.values():
            button.configure(state='disabled' if busy else 'normal')
        self.stop_button.configure(state='normal' if busy else 'disabled')
        self.browse_project.configure(state='disabled' if busy else 'normal')

    def _start(self, stage):
        if self._busy:
            return
        values = self._values()
        try:
            command = command_for(stage, values)
        except (ValueError, TypeError) as exc:
            messagebox.showerror('Nieprawidłowe ustawienia', str(exc), parent=self)
            return
        if stage != 'report' and not Path(values['project']).is_file():
            messagebox.showerror('Brak pliku', 'Nie znaleziono wskazanego projektu .epro.', parent=self)
            return
        if stage == 'report' and not Path(values['run_dir']).is_dir():
            messagebox.showerror('Brak katalogu', 'Nie znaleziono wskazanego katalogu wyników.', parent=self)
            return
        if stage == 'run':
            matching = is_matching_preparation(self._command_prepared, command)
            if not matching:
                if not messagebox.askyesno(
                    'Brak potwierdzonego PREPARE-ONLY',
                    'W bieżącej sesji GUI nie przygotowano siatki dla dokładnie tych parametrów.\n'
                    'Uruchomienie może być kosztowne.\n\n'
                    'Czy mimo to uruchomić pełne FDTD?', parent=self):
                    return
            if not messagebox.askyesno(
                'Potwierdź pełne FDTD',
                f'Projekt: {Path(values["project"]).name}\n'
                f'Profil: {values["quality"]}, sweep: {values["start_mhz"]}–'
                f'{values["stop_mhz"]} MHz, krok {values["step_mhz"]} MHz.\n\n'
                'Uruchomić nowy, kosztowny przebieg openEMS?', parent=self):
                return
        self._save_preferences()
        self._current_stage = stage
        self._current_run = None if stage in ('prepare', 'run') else self._current_run
        self._cancelled = False
        self._set_busy(True)
        self.status.set('Wykonywanie: '+stage)
        self._log('\n'+('='*70)+'\n'+cmd_display(command)+'\n', 'info')
        env = os.environ.copy()
        if values.get('csxcad_path', '').strip():
            env['CSXCAD_INSTALL_PATH'] = str(values['csxcad_path']).strip()
        env['PYTHONIOENCODING'] = 'utf-8'
        threading.Thread(target=self._worker, args=(stage, command, env), daemon=True).start()

    def _worker(self, stage, command, env):
        try:
            process = subprocess.Popen(
                command, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                bufsize=1, shell=False)
            self._process = process
            assert process.stdout is not None
            for line in process.stdout:
                self._events.put(('line', stage, line))
            code = process.wait()
            self._events.put(('done', stage, code))
        except (OSError, RuntimeError) as exc:
            self._events.put(('error', stage, str(exc)))
        finally:
            self._process = None

    def _capture_path(self, stage, line):
        text = line.strip()
        if stage in ('prepare', 'run') and text.startswith('PCB EasyEDA: '):
            candidate = Path(text[len('PCB EasyEDA: '):].strip())
            if candidate.is_dir():
                self._current_run = candidate
                self.var['run_dir'].set(str(candidate))
        if stage == 'inspect' and text.endswith('source_model.json'):
            candidate = Path(text)
            if candidate.is_file():
                self._log('Zapisano inspekcję: '+str(candidate)+'\n', 'info')

    def _finish(self, stage, code):
        self._set_busy(False)
        interrupted = self._cancelled
        self._cancelled = False
        if interrupted:
            self.status.set(f'Przerwano {stage}. Sprawdź artefakty i statusy przed ponownym uruchomieniem.')
            self._log(f'Etap {stage} przerwany. Dane przebiegu pozostają na dysku.\n', 'error')
            return
        if code != 0:
            self.status.set(f'Etap {stage} zakończony błędem (kod {code}). Zobacz log poniżej.')
            self._log(f'Kod zakończenia {code}. Żadne ponowne FDTD nie jest uruchamiane automatycznie.\n', 'error')
            return
        if stage == 'prepare':
            self._command_prepared = command_for('prepare', self._values())
        if stage in ('prepare', 'run') and self._current_run:
            self._describe_result(self._current_run)
        self.status.set(f'Etap {stage} zakończony bez błędu.')
        if stage == 'run' and self.var['open_after_run'].get() and self._current_run:
            self._log('Raport: generowanie z istniejących wyników, bez nowego FDTD.\n', 'info')
            self._start('report')
        if stage == 'report':
            self.status.set('Raport wygenerowany i przekazany do przeglądarki.')

    def _describe_result(self, root):
        try:
            summary = json.loads((root / 'summary.json').read_text(encoding='utf-8-sig'))
            status = summary.get('status', '?')
            mesh = summary.get('mesh') or {}
            cells = mesh.get('cell_count', '?')
            stages = summary.get('stages') or {}
            fields = stages.get('fields', {}).get('status', 'n/d')
            self._log(f'Podsumowanie {root.name}: status={status}, cells={cells}, fields={fields}\n', 'info')
            if status in ('failed', 'postprocess_failed', 'postprocess_partial'):
                self.status.set(f'{root.name}: {status}; zachowano istniejące artefakty.')
        except (OSError, ValueError, TypeError) as exc:
            self._log(f'Nie odczytano summary.json: {exc}\n', 'error')

    def _drain_events(self):
        try:
            while True:
                kind, stage, payload = self._events.get_nowait()
                if kind == 'line':
                    self._log(payload)
                    self._capture_path(stage, payload)
                elif kind == 'done':
                    self._finish(stage, payload)
                elif kind == 'error':
                    self._set_busy(False)
                    self.status.set(f'Błąd uruchomienia {stage}: {payload}')
                    self._log(f'Błąd uruchomienia: {payload}\n', 'error')
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _stop(self):
        if not self._busy:
            return
        if not messagebox.askyesno(
            'Przerwać aktualny etap?',
            'Przerwanie FDTD może pozostawić niekompletne wyniki natywne.\n'
            'Program nie usunie ich ani nie oznaczy jako ukończonych.\n\nPrzerwać?',
            parent=self):
            return
        self._cancelled = True
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError as exc:
                self._log(f'Nie można przerwać procesu: {exc}\n', 'error')
        self.status.set('Wysłano prośbę o przerwanie procesu.')

    def _open_folder(self):
        folder = str(self.var['run_dir'].get()).strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror('Katalog', 'Wskaż istniejący katalog wyników.', parent=self)
            return
        if sys.platform == 'win32':
            os.startfile(folder)
        else:
            import webbrowser
            webbrowser.open(Path(folder).resolve().as_uri())

    def _on_close(self):
        if self._busy:
            messagebox.showwarning('Trwa zadanie', 'Najpierw zakończ lub przerwij bieżący etap.', parent=self)
            return
        self._save_preferences()
        self.destroy()


def main():
    app = PcbDesktop()
    app.mainloop()


if __name__ == '__main__':
    main()
