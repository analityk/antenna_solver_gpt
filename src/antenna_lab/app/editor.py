"""Native text controls with a Matplotlib preview updated only on explicit apply."""

from copy import deepcopy
from pathlib import Path

from antenna_lab.antennas import build_model
from antenna_lab.core.config import ConfigurationError, ROOT, load_config, modified_config, write_json
from antenna_lab.core.geometry import check_geometry
from antenna_lab.visualization.plots import draw_geometry
from .actions import export_geometry

LABELS = {"wire_diameter": "Średnica drutu", "reflector_length": "Długość reflektora",
          "reflector_width": "Szerokość reflektora", "reflector_thickness": "Grubość reflektora"}


class EditorState:
    """Keep incomplete text separate from the last valid, full-precision model."""

    def __init__(self, config):
        if len(config["simulation"]["frequency_hz"]) != 1:
            raise ConfigurationError("Edytor geometrii obsługuje jedną częstotliwość; serie można podać w pliku JSON dla CLI.")
        self.original = deepcopy(config)
        self.config = deepcopy(config)
        self.geometry = build_model(self.config)

    @property
    def fields(self):
        return {k: f"{v * 1000:.9g}" for k, v in self.config["antenna"]["parameters"]["dimensions_m"].items()}

    @property
    def frequency(self):
        return f"{self.config['simulation']['frequency_hz'][0] / 1e6:.9g}"

    @property
    def reflector(self):
        return self.config["simulation"]["reflector_model"] != "none"

    def _commit(self, candidate):
        if candidate == self.config:
            return False
        geometry_changed = (candidate["antenna"] != self.config["antenna"]
                            or candidate["simulation"]["reflector_model"] != self.config["simulation"]["reflector_model"])
        geometry = build_model(candidate) if geometry_changed else self.geometry
        # Only commit after validation; bad input must not damage the current model.
        self.config, self.geometry = candidate, geometry
        return geometry_changed

    def apply(self, texts, frequency_text, reflector):
        def number(text, name):
            try:
                return float(text.strip().replace(",", "."))
            except ValueError as exc:
                raise ConfigurationError(f"{name}: wpisz liczbę. Zatwierdzenie: Enter lub Zastosuj.") from exc

        shown = self.fields
        changed = {key: number(text, LABELS.get(key, key)) for key, text in texts.items()
                   if text.strip() != shown[key]}
        # Do not round untouched dimensions or frequency to their displayed precision.
        frequency = (None if frequency_text.strip() == self.frequency
                     else number(frequency_text, "Częstotliwość"))
        return self._commit(modified_config(self.config, changed, frequency_mhz=frequency, reflector=reflector))

    def scale(self, target_mhz):
        return self._commit(modified_config(self.config, scale_to_mhz=target_mhz))

    def reset(self):
        return self._commit(deepcopy(self.original))


class GeometryEditor:
    def __init__(self, root, config, output_root):
        # Lazy imports: CLI geometry/export and headless checks do not require Tk.
        import tkinter as tk
        from tkinter import ttk
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure

        self.root, self.output_root = root, output_root
        self.state = EditorState(config)
        self.syncing = True
        self.dirty = False
        self.fields = {}
        self.entries = {}
        root.title("antenna_solver_gpt — Quados 8")
        width = min(1420, max(1050, root.winfo_screenwidth() - 80))
        height = min(880, max(740, root.winfo_screenheight() - 100))
        root.geometry(f"{width}x{height}")
        root.minsize(1050, 740)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        form = ttk.Frame(root, padding=(18, 14))
        form.grid(row=0, column=0, sticky="ns")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="QUADOS 8", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        ttk.Label(form, text="Wymiary [mm]", foreground="#45566b").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row = 2
        for key, value in self.state.fields.items():
            ttk.Label(form, text=LABELS.get(key, key)).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            var = tk.StringVar(master=root, value=value)
            entry = ttk.Entry(form, textvariable=var, width=17)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            entry.bind("<Return>", self.apply)
            entry.bind("<KP_Enter>", self.apply)
            var.trace_add("write", self._on_edit)
            self.fields[key], self.entries[key] = var, entry
            row += 1
        ttk.Separator(form).grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1
        ttk.Label(form, text="Częstotliwość [MHz]").grid(row=row, column=0, sticky="w", padx=(0, 12))
        self.frequency = tk.StringVar(master=root, value=self.state.frequency)
        self.frequency_entry = ttk.Entry(form, textvariable=self.frequency, width=17)
        self.frequency_entry.grid(row=row, column=1, sticky="ew")
        self.frequency_entry.bind("<Return>", self.apply)
        self.frequency_entry.bind("<KP_Enter>", self.apply)
        self.frequency.trace_add("write", self._on_edit)
        row += 1
        self.reflector = tk.BooleanVar(master=root, value=self.state.reflector)
        self.reflector.trace_add("write", self._on_edit)
        ttk.Checkbutton(form, text="Reflektor", variable=self.reflector).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(10, 8))
        row += 1
        self.apply_button = ttk.Button(form, text="Zastosuj", command=self.apply)
        self.apply_button.grid(row=row, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(form, text="Skaluj…", command=self.scale_dialog).grid(row=row, column=1, sticky="ew")
        row += 1
        ttk.Button(form, text="Przywróć początkowe", command=self.reset).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(7, 10))
        row += 1
        ttk.Label(form, text="Wpisywanie i Tab nie zmieniają podglądu.\nZatwierdź pola: Enter lub Zastosuj.",
                  foreground="#45566b", wraplength=310).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        ttk.Separator(form).grid(row=row, column=0, columnspan=2, sticky="ew", pady=12)
        row += 1
        self.load_button = ttk.Button(form, text="Wczytaj parametry…", command=self.load)
        self.load_button.grid(row=row, column=0, sticky="ew", padx=(0, 5))
        self.save_button = ttk.Button(form, text="Zapisz parametry (.json)…", command=self.save)
        self.save_button.grid(row=row, column=1, sticky="ew")
        row += 1
        ttk.Label(form, text="Plik ustawień do ponownej edycji\nlub uruchomienia obliczeń.",
                  foreground="#45566b").grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 0))

        view = ttk.Frame(root, padding=(8, 14, 18, 12))
        view.grid(row=0, column=1, sticky="nsew")
        view.columnconfigure(0, weight=1)
        view.rowconfigure(2, weight=1)
        ttk.Label(view, text="Geometria anteny", font=("Segoe UI", 18)).grid(row=0, column=0, sticky="w")
        ttk.Label(view, text="Zmiana częstotliwości zachowuje wymiary. Skaluj… przelicza całą antenę.",
                  foreground="#45566b").grid(row=1, column=0, sticky="w", pady=(5, 8))
        self.figure = Figure(figsize=(9, 5), facecolor="#eef3f8")
        self.front = self.figure.add_axes([0.09, 0.59, 0.88, 0.29])
        self.side = self.figure.add_axes([0.09, 0.17, 0.88, 0.15])
        self.canvas = FigureCanvasTkAgg(self.figure, master=view)
        self.canvas.get_tk_widget().grid(row=2, column=0, sticky="nsew")
        self.toolbar = NavigationToolbar2Tk(self.canvas, view, pack_toolbar=False)
        self.toolbar.grid(row=3, column=0, sticky="ew")
        self.status = tk.StringVar(master=root)
        # Reserve space so editing a message cannot resize/redraw the plot canvas.
        status_area = ttk.Frame(view, height=82)
        status_area.grid(row=4, column=0, sticky="ew", pady=(8, 8))
        status_area.pack_propagate(False)
        self.status_label = ttk.Label(status_area, textvariable=self.status, foreground="#1f4e43",
                                      wraplength=760, justify="left")
        self.status_label.pack(fill="both", expand=True)
        view.bind("<Configure>", lambda event: self.status_label.configure(wraplength=max(300, event.width - 30)))
        self.artifact = tk.StringVar(master=root)
        self.artifact_entry = ttk.Entry(view, textvariable=self.artifact, state="readonly")
        self.artifact_entry.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        export_panel = ttk.Frame(view)
        export_panel.grid(row=6, column=0, sticky="ew")
        export_panel.columnconfigure(0, weight=1)
        ttk.Label(export_panel, text="Eksport: nowy folder z modelem, rysunkiem PNG\ni dokumentacją. Bez obliczeń openEMS.",
                  foreground="#45566b").grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.export_button = ttk.Button(export_panel, text="Eksportuj geometrię", command=self.export)
        self.export_button.grid(row=0, column=1, sticky="e")
        self.syncing = False
        self._draw()
        self._show_metrics()

    def _message(self, text, error=False):
        self.status.set(text)
        self.status_label.configure(foreground="#b42318" if error else "#1f4e43")

    def _on_edit(self, *_):
        if not self.syncing and not self.dirty:
            self.dirty = True
            self._message("Niezastosowane zmiany. Podgląd pokazuje poprzedni model.\nNaciśnij Enter lub Zastosuj.")
        # No model building, validation or Matplotlib drawing during typing/focus changes.

    def _sync_fields(self):
        self.syncing = True
        try:
            for key, text in self.state.fields.items():
                if self.fields[key].get() != text:
                    self.fields[key].set(text)
            if self.frequency.get() != self.state.frequency:
                self.frequency.set(self.state.frequency)
            self.reflector.set(self.state.reflector)
        finally:
            self.syncing = False
            self.dirty = False

    def _draw(self):
        draw_geometry(self.front, self.side, self.state.geometry)
        self.toolbar.update()
        self.canvas.draw_idle()

    def _show_metrics(self):
        metrics = check_geometry(self.state.geometry)
        length = next(iter(metrics["branch_lengths_m"].values())) * 1000
        text = (f"Geometria poprawna: {metrics['wire_count']} odcinków; gałąź {length:.6f} mm.\n"
                "Kolory oznaczają odcinki A–F. To podgląd konstrukcji, bez rozkładu prądów i pól.")
        if metrics["warnings"]:
            text += "\n" + " ".join(metrics["warnings"])
        self._message(text)

    def apply(self, event=None):
        try:
            previous = self.state.config
            changed = self.state.apply({k: v.get() for k, v in self.fields.items()},
                                       self.frequency.get(), bool(self.reflector.get()))
            self._sync_fields()
            if self.state.config != previous:
                self.artifact.set("")
            if changed:
                self._draw()
            self._show_metrics()
            return True
        except (ValueError, OverflowError) as exc:
            self._message(str(exc), error=True)
            return False

    def reset(self):
        changed = self.state.reset()
        self._sync_fields()
        self.artifact.set("")
        if changed:
            self._draw()
        self._show_metrics()

    def scale_dialog(self):
        from tkinter import simpledialog
        if not self.apply():
            return
        current = self.state.config["simulation"]["frequency_hz"][0] / 1e6
        target = simpledialog.askfloat("Skalowanie geometrii",
                                       f"Skaluj wszystkie wymiary z {current:g} MHz do [MHz]:",
                                       initialvalue=current, minvalue=1e-9, parent=self.root)
        if target is not None:
            try:
                changed = self.state.scale(target)
                self._sync_fields()
                self.artifact.set("")
                if changed:
                    self._draw()
                self._show_metrics()
            except (ValueError, OverflowError) as exc:
                self._message(str(exc), error=True)

    def load(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Wczytaj parametry anteny — plik JSON",
                                         initialdir=str(ROOT / "parameters"),
                                         filetypes=[("Parametry JSON", "*.json")], parent=self.root)
        if not path:
            return
        try:
            # Validate the whole file and geometry before replacing any edits.
            candidate = EditorState(load_config(path))
        except (OSError, ValueError, OverflowError) as exc:
            self._message(f"Nie wczytano parametrów: {exc}", error=True)
            return
        self.state = candidate
        self._sync_fields()
        self._draw()
        self.artifact.set(str(Path(path).resolve()))
        self.root.title(f"antenna_solver_gpt — Quados 8 — {Path(path).name}")
        self._show_metrics()
        self._message("Wczytano parametry z pliku. " + self.status.get())

    def save(self):
        from tkinter import filedialog
        if not self.apply():
            return
        path = filedialog.asksaveasfilename(title="Zapisz parametry anteny — plik JSON",
                                           initialdir=str(ROOT / "parameters"), initialfile="quados8_variant.json",
                                           defaultextension=".json", filetypes=[("Parametry JSON", "*.json")],
                                           parent=self.root)
        if path:
            try:
                write_json(path, self.state.config)
                self.artifact.set(str(Path(path).resolve()))
                self._message("Zapisano parametry anteny w pliku JSON. Ścieżka poniżej.")
            except (OSError, ValueError) as exc:
                self._message(str(exc), error=True)

    def export(self):
        if not self.apply():
            return
        self.export_button.state(["disabled"])
        self._message("Zapisywanie geometrii, rysunku i dokumentacji…")
        self.root.update_idletasks()
        try:
            path = export_geometry(self.state.config, self.output_root)
            self.artifact.set(str(path))
            self._message("Zapisano model, rysunek PNG i dokumentację w nowym folderze.\nTo eksport geometrii; obliczenia openEMS nie zostały uruchomione.")
        except Exception as exc:
            self._message(str(exc), error=True)
        finally:
            self.export_button.state(["!disabled"])


def show_editor(config, output_root):
    try:
        import tkinter as tk
    except ImportError as exc:
        raise ConfigurationError("Edytor wymaga tkinter, dołączonego do standardowej instalacji Python dla Windows.") from exc
    root = tk.Tk()
    try:
        editor = GeometryEditor(root, config, output_root)
        root.mainloop()
        return editor
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
