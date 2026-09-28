"""A local Matplotlib editor; changing parameters only rebuilds geometry."""

from copy import deepcopy
from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
from matplotlib.widgets import Button, CheckButtons, TextBox

from antenna_lab.antennas import build_model
from antenna_lab.core.config import ConfigurationError, ROOT, modified_config, write_json
from antenna_lab.core.geometry import check_geometry
from antenna_lab.visualization.plots import draw_geometry
from .actions import export_geometry

LABELS = {"wire_diameter": "Średnica drutu", "reflector_length": "Długość reflektora",
          "reflector_width": "Szerokość reflektora", "reflector_thickness": "Grubość reflektora"}


def show_editor(config, output_root):
    if len(config["simulation"]["frequency_hz"]) != 1:
        raise ConfigurationError("Edytor geometrii obsługuje jedną częstotliwość; serie można podać w pliku JSON dla CLI.")
    original = deepcopy(config)
    state = {"config": deepcopy(config), "shown": {}, "changing": False}
    fig = plt.figure(figsize=(15, 8), facecolor="#eef3f8")
    fig.canvas.manager.set_window_title("antenna_solver_gpt — Quados 8")
    fig.text(0.03, 0.95, "QUADOS 8", fontsize=19, weight="bold", color="#172d47")
    fig.text(0.29, 0.95, "Geometria anteny", fontsize=18, color="#172d47")
    fig.text(0.29, 0.905, "Edytuj wymiary w mm. Enter lub Zastosuj aktualizuje podgląd.", fontsize=10)
    front = fig.add_axes([0.34, 0.55, 0.63, 0.27])
    side = fig.add_axes([0.34, 0.29, 0.63, 0.13])
    status = fig.text(0.34, 0.13, "", fontsize=10, va="top", color="#1f4e43")
    fields = {}
    for index, (key, value) in enumerate(config["antenna"]["parameters"]["dimensions_m"].items()):
        ax = fig.add_axes([0.175, 0.85 - index * 0.047, 0.085, 0.034])
        fields[key] = TextBox(ax, LABELS.get(key, key) + "  ", initial=f"{value*1000:.9g}")
        fields[key].label.set_fontsize(9)
    freq = TextBox(fig.add_axes([0.175, 0.225, 0.085, 0.035]), "MHz  ",
                   initial=f"{config['simulation']['frequency_hz'][0]/1e6:.9g}")
    reflect = CheckButtons(fig.add_axes([0.045, 0.16, 0.215, 0.042], facecolor="#eef3f8"),
                          ["Reflektor"], [config["simulation"]["reflector_model"] != "none"])
    buttons = []

    def set_fields():
        state["changing"] = True
        try:
            for key, box in fields.items():
                text = f"{state['config']['antenna']['parameters']['dimensions_m'][key]*1000:.9g}"
                box.set_val(text)
                state["shown"][key] = text
            freq.set_val(f"{state['config']['simulation']['frequency_hz'][0]/1e6:.9g}")
            enabled = state["config"]["simulation"]["reflector_model"] != "none"
            if reflect.get_status()[0] != enabled:
                reflect.set_active(0)
        finally:
            state["changing"] = False

    def display(geometry, message=None):
        draw_geometry(front, side, geometry)
        metrics = check_geometry(geometry)
        length = next(iter(metrics["branch_lengths_m"].values())) * 1000
        info = message or (f"Geometria poprawna: {metrics['wire_count']} odcinków. Długość każdej gałęzi: {length:.6f} mm.\n"
                           "Podgląd nie przedstawia rozkładu prądów ani pól. Częstotliwość nie skaluje wymiarów automatycznie.")
        if metrics["warnings"]:
            info += "\n" + " ".join(metrics["warnings"])
        status.set_text(info)
        status.set_color("#1f4e43")
        fig.canvas.draw_idle()

    def apply(scale=False):
        if state["changing"]:
            return False
        try:
            changed = {key: float(box.text.replace(",", ".")) for key, box in fields.items() if box.text != state["shown"].get(key)}
            f = float(freq.text.replace(",", "."))
            # Scaling is a separate explicit action, relative to the last applied frequency.
            candidate = modified_config(state["config"], changed, reflector=bool(reflect.get_status()[0]),
                                        scale_to_mhz=f if scale else None, frequency_mhz=None if scale else f)
            geometry = build_model(candidate)
            state["config"] = candidate
            set_fields()
            display(geometry)
            return True
        except (ValueError, OverflowError) as exc:
            status.set_text(textwrap.fill(str(exc), 90))
            status.set_color("#b42318")
            fig.canvas.draw_idle()
            return False

    def reset(_):
        state["config"] = deepcopy(original)
        set_fields()
        display(build_model(state["config"]))

    def scale_dialog(_):
        if not apply():
            return
        try:
            from tkinter import Tk, simpledialog
            dialog = Tk()
            dialog.withdraw()
            try:
                current = state["config"]["simulation"]["frequency_hz"][0] / 1e6
                target = simpledialog.askfloat("Skalowanie geometrii", f"Skaluj wszystkie wymiary z {current:g} MHz do [MHz]:",
                                               initialvalue=current, minvalue=1e-9, parent=dialog)
            finally:
                dialog.destroy()
            if target is not None:
                candidate = modified_config(state["config"], scale_to_mhz=target)
                geometry = build_model(candidate)
                state["config"] = candidate
                set_fields()
                display(geometry)
        except Exception as exc:
            status.set_text(textwrap.fill(str(exc), 90))
            status.set_color("#b42318")
            fig.canvas.draw_idle()

    def save(_):
        if not apply():
            return
        try:
            from tkinter import Tk, filedialog
            dialog = Tk()
            dialog.withdraw()
            try:
                path = filedialog.asksaveasfilename(title="Zapisz wariant anteny", initialdir=str(ROOT / "parameters"),
                                                   initialfile="quados8_variant.json", defaultextension=".json",
                                                   filetypes=[("Parametry JSON", "*.json")], parent=dialog)
            finally:
                dialog.destroy()
            if path:
                write_json(path, state["config"])
                display(build_model(state["config"]), "Zapisano wariant:\n" + str(Path(path).resolve()))
        except Exception as exc:
            status.set_text(textwrap.fill(str(exc), 90))
            status.set_color("#b42318")
            fig.canvas.draw_idle()

    def export(_):
        if not apply():
            return
        try:
            path = export_geometry(state["config"], output_root)
            display(build_model(state["config"]), "Zapisano geometrię, parametry i rysunek:\n" + str(path))
        except Exception as exc:
            status.set_text(textwrap.fill(str(exc), 90))
            status.set_color("#b42318")
            fig.canvas.draw_idle()

    for rect, title, callback in [([0.03, 0.09, 0.105, 0.045], "Zastosuj", lambda _: apply()),
                                   ([0.15, 0.09, 0.11, 0.045], "Skaluj...", scale_dialog),
                                   ([0.03, 0.025, 0.105, 0.045], "Reset", reset),
                                   ([0.15, 0.025, 0.11, 0.045], "Zapisz wariant", save),
                                   ([0.78, 0.025, 0.19, 0.045], "Eksport geometrii", export)]:
        button = Button(fig.add_axes(rect), title, color="#dce7f2", hovercolor="#c5d8eb")
        button.on_clicked(callback)
        buttons.append(button)
    for box in (*fields.values(), freq):
        box.on_submit(lambda _: apply())
    reflect.on_clicked(lambda _: apply())
    set_fields()
    display(build_model(state["config"]))
    # Keep widget callbacks alive as long as the window exists.
    fig._antenna_editor = (fields, freq, reflect, buttons, state)
    plt.show()
    return fig
