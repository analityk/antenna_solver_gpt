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

from .gui_commands import cmd_display, command_for, is_matching_preparation, suggest_excitation
from .gui_project_settings import (
    project_parameters_dir, read_project_settings, write_project_settings)

ROOT = Path(__file__).resolve().parents[3]
PREFS = Path.home() / '.antenna_lab_pcb_gui.json'
DEFAULTS = {
    'project': '', 'pcb_id': '', 'source_config': '', 'pth_plating_um': '',
    'dielectric_materials': '',
    'quality': 'design', 'geometry_um': '10', 'center_mhz': '1500',
    'cutoff_mhz': '1400', 'start_mhz': '1000', 'stop_mhz': '2000',
    'step_mhz': '100', 'fields_enabled': True, 'fields_mhz': '1000 2000',
    'field_mode':'far',
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
        self._active_command = None
        self._current_run = None
        self._current_stage = None
        self._stage_report = False
        self._ready = False
        values = dict(DEFAULTS)
        self._active_project = None
        self._parameters_dir = None
        self._startup_warning = None
        saved = {}
        try:
            record = json.loads(PREFS.read_text(encoding='utf-8'))
            if isinstance(record, dict):
                saved = {k: v for k, v in record.items()
                         if k in DEFAULTS and type(v) is type(DEFAULTS[k])}
                for k in ('project', 'csxcad_path'):
                    if k in saved:
                        values[k] = saved[k]
        except (OSError, ValueError, TypeError):
            pass
        initial = str(values['project']).strip()
        if initial and Path(initial).is_file():
            try:
                directory = project_parameters_dir(initial, ROOT)
                directory.mkdir(parents=True, exist_ok=True)
                per_project = read_project_settings(directory, Path(initial).parent, DEFAULTS)
                if per_project is not None:
                    values.update(per_project)
                else:
                    # One-time compatibility for settings stored by the older
                    # global GUI. Future writes use only the project sidecar.
                    values.update({k: v for k, v in saved.items()
                                   if k not in ('project', 'csxcad_path')})
                self._active_project = str(Path(initial).resolve())
                self._parameters_dir = directory
                values['project'] = self._active_project
            except (OSError, ValueError) as exc:
                self._startup_warning = str(exc)
        self.parameters_path = tk.StringVar(
            value=str(self._parameters_dir) if self._parameters_dir else 'Wybierz plik .epro')
        self.var = {key: (tk.BooleanVar(value=value) if isinstance(value, bool)
                          else tk.StringVar(value=value))
                    for key, value in values.items() if key != 'overrides'}
        self.overrides_initial = values['overrides']
        self._material_editors = {}
        self.preview_mode = tk.StringVar(value='prepare')
        self.status = tk.StringVar(value='Wskaż plik .epro i rozpocznij od inspekcji.')
        self._make_widgets()
        for v in self.var.values():
            v.trace_add('write', lambda *_: self._refresh_preview())
        self.preview_mode.trace_add('write', lambda *_: self._refresh_preview())
        self._ready = True
        if self._active_project:
            self._refresh_materials_for_project()
        self._refresh_preview()
        if self._startup_warning:
            self.status.set('Parametry projektu: '+self._startup_warning)
            self._log(self._startup_warning+'\n', 'error')
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
        self.project_entry = ttk.Entry(project_row, textvariable=self.var['project'])
        self.project_entry.pack(side='left', fill='x', expand=True)
        self.project_entry.bind('<Return>', self._commit_project_entry)
        self.project_entry.bind('<FocusOut>', self._commit_project_entry)
        self.browse_project = ttk.Button(project_row, text='Wybierz projekt…', command=self._choose_project)
        self.browse_project.pack(side='left', padx=(8, 0))

        params_row = ttk.Frame(outer)
        params_row.pack(fill='x', pady=(0, 10))
        ttk.Label(params_row, text='Katalog parametrów projektu:').pack(side='left', padx=(0, 8))
        ttk.Entry(params_row, textvariable=self.parameters_path, state='readonly').pack(
            side='left', fill='x', expand=True)
        ttk.Button(params_row, text='Otwórz parametry', command=self._open_parameter_dir).pack(side='right', padx=(8, 0))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill='x', pady=(0, 9))
        tab_exp = ttk.Frame(notebook, padding=12)
        tab_solver = ttk.Frame(notebook, padding=12)
        tab_layers = ttk.Frame(notebook, padding=12)
        tab_report = ttk.Frame(notebook, padding=12)
        notebook.add(tab_exp, text='  Eksperyment i pola  ')
        notebook.add(tab_solver, text='  Solver i źródło  ')
        notebook.add(tab_layers, text='  Warstwy EM  ')
        notebook.add(tab_report, text='  Raport  ')
        self._tab_experiment(tab_exp)
        self._tab_solver(tab_solver)
        self._tab_materials(tab_layers)
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
        self.match_button = ttk.Button(
            frame, text='Dopasuj pobudzenie do sweep', command=self._match_excitation)
        self.match_button.grid(row=2, column=3, columnspan=3, sticky='w', pady=5)

        ttk.Checkbutton(frame, text='Zapisz pola E i H', variable=self.var['fields_enabled']).grid(
            row=3, column=0, columnspan=2, sticky='w', pady=5)
        self._field(frame, 'Pola przy', 'fields_mhz', 3, 1, width=20, help_text='MHz, np. 1000 2000')
        ttk.Label(frame,text='Tryb pomiaru pól:').grid(row=4,column=0,sticky='w',pady=(6,0))
        ttk.Radiobutton(frame,text='Przekroje E/H wokół płytki (dotychczasowy)',
                        variable=self.var['field_mode'],value='far').grid(
                            row=4,column=1,columnspan=3,sticky='w',pady=(6,0))
        ttk.Radiobutton(frame,text='Powierzchnie miedzi: góra i dół każdej warstwy',
                        variable=self.var['field_mode'],value='copper_surfaces').grid(
                            row=5,column=0,columnspan=4,sticky='w')
        ttk.Label(frame,text='Powierzchnie Cu: mapy E/H/K proxy, sondy 10 µm; zmienia siatkę Z i koszt FDTD. Najpierw PREPARE.',
                  foreground='#666').grid(row=6,column=0,columnspan=6,sticky='w')
        ttk.Label(frame, text='Zakres i częstotliwości dobierasz do projektu. Użyteczny zakres pobudzenia to środek ± 0,8 × odcięcie.',
                  foreground='#666').grid(row=7, column=0, columnspan=6, sticky='w', pady=(4, 0))

    def _match_excitation(self):
        if self._busy:
            return
        try:
            center, cutoff = suggest_excitation(
                self.var['start_mhz'].get(), self.var['stop_mhz'].get())
        except ValueError as exc:
            messagebox.showerror('Niepoprawny zakres sweep', str(exc), parent=self)
            return
        self.var['center_mhz'].set(f'{center:g}')
        self.var['cutoff_mhz'].set(f'{cutoff:g}')
        self.status.set(f'Dopasowano pobudzenie: środek {center:g} MHz, '
                        f'odcięcie {cutoff:g} MHz. Sprawdź ustawienia przed FDTD.')

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
        ttk.Label(frame, text='Konfiguracja źródła (opcjonalnie)').grid(row=5, column=0, sticky='w', pady=5)
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

    def _tab_materials(self, frame):
        ttk.Label(frame,text='Warstwy fizyczne z pliku EasyEDA (bez maski, silk, pasty i dokumentacji):').pack(
            anchor='w')
        list_container=ttk.Frame(frame)
        list_container.pack(fill='x', pady=(7,5))
        self.material_canvas=tk.Canvas(list_container,height=188,highlightthickness=0)
        layer_scroll=ttk.Scrollbar(list_container,orient='vertical',
                                   command=self.material_canvas.yview)
        self.material_canvas.configure(yscrollcommand=layer_scroll.set)
        self.material_canvas.pack(side='left',fill='x',expand=True)
        layer_scroll.pack(side='right',fill='y')
        self.material_list=ttk.Frame(self.material_canvas)
        self.material_canvas.create_window((0,0),window=self.material_list,anchor='nw')
        self.material_list.bind('<Configure>',lambda _:
            self.material_canvas.configure(scrollregion=self.material_canvas.bbox('all')))
        self.material_status=tk.StringVar(value='Wybierz projekt .epro, aby zobaczyć warstwy.')
        ttk.Label(frame,textvariable=self.material_status,foreground='#666',
                  wraplength=1050).pack(anchor='w')
        ttk.Label(frame,text='Wartości εr=0 w CAD oznaczają brak modelu materiału. '
                  'Wpisz wybraną przenikalność; 0 nie będzie automatycznie zamieniane na FR-4. '
                  'Soldermaska: pominięta (jej przybliżony model będzie osobnym etapem).',
                  wraplength=1050,foreground='#666').pack(anchor='w',pady=(6,0))
        ttk.Button(frame,text='Odczytaj warstwy ponownie',
                   command=self._refresh_materials_for_project).pack(anchor='w',pady=(7,0))

    def _sync_material_inputs(self):
        """Only explicitly entered valid material rows become CLI overrides."""
        specs=[]
        for lid, (er, tangent) in self._material_editors.items():
            if er.get().strip():
                specs.append(f'{lid}:{er.get().strip()}:{tangent.get().strip()}')
        self.var['dielectric_materials'].set(';'.join(specs))
        self._refresh_preview()

    def _refresh_materials_for_project(self):
        if not self._active_project:
            return
        from .easyeda_project import load_easyeda_project,materialize_project_source
        from .easyeda_stackup import describe_source_stackup,parse_source_dielectric_materials
        try:
            source=materialize_project_source(load_easyeda_project(self._active_project))
            stack=describe_source_stackup(source.semantics,source.source_sha256)
            present=self.var['dielectric_materials'].get()
            already=parse_source_dielectric_materials(
                [s.strip() for s in present.split(';') if s.strip()])
        except (OSError,ValueError,RuntimeError) as exc:
            self.material_status.set('Nie udało się odczytać warstw: '+str(exc))
            self._log('Warstwy: '+str(exc)+'\n','error')
            return
        for widget in self.material_list.winfo_children():
            widget.destroy()
        self._material_editors={}
        heads=('Kolejność / warstwa CAD','Rola EM','Położenie Z [mm]','Grubość [mm]',
               'εr (edytuj)','tanδ (edytuj)')
        for j,header in enumerate(heads):
            ttk.Label(self.material_list,text=header,font=('Segoe UI',9,'bold')).grid(
                row=0,column=j,sticky='w',padx=(0,15),pady=(0,4))
        layers={v['id']:v for v in source.semantics['layers']}
        elements=[('copper',s,s['z_m']) for s in stack['copper_layers']]
        elements += [('dielectric',d,d['z_max_m']) for d in stack['dielectric_layers']]
        elements.sort(key=lambda x:(-x[2],x[0]!='copper'))
        for row,(kind,item,level) in enumerate(elements,1):
            lid=item['layer_id'];thickness=(item['thickness_m'] if kind=='copper' else
                                           item['z_max_m']-item['z_min_m'])
            role=(item['role'] if kind=='copper' else 'dielektryk')
            info=f'{lid} · {item["name"]}'
            for col,value in enumerate((info,role,f'{level*1e3:.3f}',f'{thickness*1e3:.3f}')):
                ttk.Label(self.material_list,text=value).grid(row=row,column=col,
                    sticky='w',padx=(0,20),pady=2)
            if kind=='dielectric':
                values=already.get(str(lid),{})
                eps=item['epsilon_r']
                eps_val=str(values['epsilon_r']) if 'epsilon_r' in values else (
                    f'{eps:g}' if eps>=1 else '')
                loss=values.get('loss_tangent',item['loss_tangent'])
                er_var=tk.StringVar(value=eps_val)
                loss_var=tk.StringVar(value=f'{loss:g}')
                self._material_editors[str(lid)]=(er_var,loss_var)
                ttk.Entry(self.material_list,textvariable=er_var,width=12).grid(
                    row=row,column=4,sticky='w')
                ttk.Entry(self.material_list,textvariable=loss_var,width=12).grid(
                    row=row,column=5,sticky='w')
        for er,tangent in self._material_editors.values():
            er.trace_add('write',lambda *_:self._sync_material_inputs())
            tangent.trace_add('write',lambda *_:self._sync_material_inputs())
        self.material_status.set(
            f'Odczytano {len(stack["copper_layers"])} warstwy miedzi, '
            f'{len(stack["dielectric_layers"])} dielektryki. '
            f'Pominięto {len(stack["ignored_layers"])} warstw nie-EM. '
            'Zapis wartości materiałowych następuje razem z ustawieniami projektu.')

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

    def _save_current_project(self):
        if self._parameters_dir is None or self._active_project is None:
            return
        write_project_settings(self._parameters_dir, Path(self._active_project).parent,
                               self._values(), DEFAULTS)

    def _save_preferences(self):
        try:
            self._save_current_project()
            # The install directory is machine-wide; only project-specific
            # simulation values live in parameters/<project folder>.
            data = {'project': self._active_project or '',
                    'csxcad_path': self.var['csxcad_path'].get()}
            PREFS.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n',
                             encoding='utf-8')
        except (OSError, ValueError) as exc:
            self._log(f'Nie zapisano ustawień GUI: {exc}\n', 'error')

    def _activate_project(self, selected, *, show_error=True):
        if self._busy:
            return False
        path = Path(str(selected).strip()).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        path = path.resolve()
        if not path.is_file() or path.suffix.lower() != '.epro':
            if show_error:
                messagebox.showerror('Plik EasyEDA', 'Wskaż istniejący plik .epro.', parent=self)
            else:
                self.status.set('Wybierz istniejący projekt .epro.')
            return False
        if str(path) == self._active_project:
            return True
        try:
            directory = project_parameters_dir(path, ROOT)
            directory.mkdir(parents=True, exist_ok=True)
            if directory == self._parameters_dir:
                # Sibling EPRO: carry unsaved GUI edits as well. Reading the
                # sidecar first would accidentally revert those edits.
                current = self._values()
                stored = {key: value for key, value in current.items()
                          if key not in ('project', 'csxcad_path', 'source_config',
                                         'pcb_id', 'run_dir')}
            else:
                stored = read_project_settings(directory, path.parent, DEFAULTS)
            # Save old values only after validating the destination.
            self._save_current_project()
        except (OSError, ValueError) as exc:
            # Leave the active CAD/settings pair consistent on failure.
            self.var['project'].set(self._active_project or '')
            if show_error:
                messagebox.showerror('Katalog parametrów', str(exc), parent=self)
            self.status.set('Nie udało się przełączyć parametrów: '+str(exc))
            return False
        values = dict(DEFAULTS)
        values.update(stored or {})
        global_install = self.var['csxcad_path'].get()
        self._active_project = str(path)
        self._parameters_dir = directory
        self.parameters_path.set(str(directory))
        self.var['project'].set(str(path))
        for name, value in values.items():
            if name in ('project', 'csxcad_path', 'overrides'):
                continue
            self.var[name].set(value)
        self.var['csxcad_path'].set(global_install)
        self.overrides_text.delete('1.0', 'end')
        self.overrides_text.insert('1.0', values['overrides'])
        self._command_prepared = None
        self.status.set('Projekt: '+path.name+' | parametry: '+str(directory))
        self._log('Parametry projektu: '+str(directory)+'\n', 'info')
        self._refresh_materials_for_project()
        # A newly created parameters directory is immediately useful: it
        # contains a real settings file even before inspection/FDTD.
        try:
            self._save_current_project()
        except (OSError, ValueError) as exc:
            self._log('Nie zapisano ustawień projektu: '+str(exc)+'\n', 'error')
            self.status.set('Projekt otwarty, ale zapis parametrów nie powiódł się: '+str(exc))
        self._refresh_preview()
        return True

    def _commit_project_entry(self, _event=None):
        if self._busy:
            return
        selected = self.var['project'].get().strip()
        if selected and selected != self._active_project:
            self._activate_project(selected, show_error=False)

    def _choose_project(self):
        initial = self.var['project'].get()
        file = filedialog.askopenfilename(
            title='Wybierz projekt EasyEDA Pro',
            initialdir=str(Path(initial).parent) if initial else str(ROOT),
            filetypes=[('Projekt EasyEDA Pro', '*.epro'), ('Wszystkie pliki', '*.*')])
        if file:
            self._activate_project(file)

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
        self.project_entry.configure(state='disabled' if busy else 'normal')
        self.match_button.configure(state='disabled' if busy else 'normal')

    def _start(self, stage):
        if self._busy:
            return
        if stage != 'report' and not self._activate_project(
                self.var['project'].get(), show_error=True):
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
        self._active_command = list(command)
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
            # Stop may be requested before Popen returns; honor that request.
            if self._cancelled and process.poll() is None:
                process.terminate()
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
            # Use the command actually executed, even if GUI inputs changed during Run.
            self._command_prepared = self._active_command
        if stage in ('prepare', 'run') and self._current_run:
            self._describe_result(self._current_run)
        self.status.set(f'Etap {stage}: proces zakończony (kod 0). Nie oznacza fizycznej walidacji.')
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

    def _open_parameter_dir(self):
        if self._parameters_dir is None or not self._parameters_dir.is_dir():
            messagebox.showerror('Parametry', 'Najpierw wybierz projekt .epro.', parent=self)
            return
        self._open_directory(self._parameters_dir)

    @staticmethod
    def _open_directory(path):
        if sys.platform == 'win32':
            os.startfile(str(path))
        else:
            import webbrowser
            webbrowser.open(Path(path).resolve().as_uri())

    def _open_folder(self):
        folder = str(self.var['run_dir'].get()).strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror('Katalog', 'Wskaż istniejący katalog wyników.', parent=self)
            return
        self._open_directory(folder)

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
