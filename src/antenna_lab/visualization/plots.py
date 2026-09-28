from html import escape
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import numpy as np

COLORS = {"A": "#d97706", "B": "#e11d48", "C": "#059669", "D": "#7c3aed", "E": "#1676bd", "F": "#a855f7"}


def draw_geometry(front, side, geometry):
    for ax in (front, side):
        ax.clear()
        ax.set_facecolor("#f5f8fb")
        ax.grid(alpha=0.2)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("y [mm]")
    front.set_title("Rzut xy — długa oś y poziomo", loc="left", fontsize=11, pad=32)
    front.set_ylabel("x [mm]")
    side.set_title("Rzut yz — wysokość nad reflektorem", loc="left", fontsize=11)
    side.set_ylabel("z [mm]")
    for plate in geometry.plates:
        a, b = np.array(plate.start) * 1000, np.array(plate.stop) * 1000
        for ax, vertical in ((front, 0), (side, 2)):
            ax.add_patch(Rectangle((a[1], a[vertical]), b[1] - a[1], b[vertical] - a[vertical],
                                   color="#c8d2dc", alpha=0.8, zorder=1))
    seen = set()
    for wire in geometry.wires:
        points = np.array([wire.start, wire.stop]) * 1000
        label = wire.label if wire.label not in seen else None
        seen.add(wire.label)
        front.plot(points[:, 1], points[:, 0], color=COLORS.get(wire.label, "#1676bd"), lw=1.8, label=label, zorder=3)
        side.plot(points[:, 1], points[:, 2], color="#1676bd", lw=1.2, zorder=3)
    terminals = np.array([geometry.port.negative, geometry.port.positive]) * 1000
    front.plot(terminals[:, 1], terminals[:, 0], "o--", color="#111827", ms=3, lw=1, label="port", zorder=4)
    for ax in (front, side):
        low, high = geometry.bounds
        ax.set_xlim(low[1] * 1000 - 25, high[1] * 1000 + 25)
    front.set_ylim(geometry.bounds[0][0] * 1000 - 15, geometry.bounds[1][0] * 1000 + 15)
    side.set_ylim(geometry.bounds[0][2] * 1000 - 6, geometry.bounds[1][2] * 1000 + 10)
    front.legend(ncol=7, loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=8, frameon=False)


def geometry_plot(geometry, filename):
    # File export must not create a second GUI window in an embedded Tk editor.
    fig = Figure(figsize=(13, 5))
    FigureCanvasAgg(fig)
    front, side = fig.subplots(2, 1, gridspec_kw={"height_ratios": [3, 1.5]})
    draw_geometry(front, side, geometry)
    fig.suptitle("Quados 8 — geometria konstrukcyjna, bez wyników elektromagnetycznych", fontsize=12)
    fig.subplots_adjust(top=0.76, bottom=0.12, hspace=0.8, left=0.06, right=0.98)
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, dpi=160)


def render_results(run_path):
    """Read saved CSV/NPZ only. Plotting can never trigger a new FDTD solve."""
    root = Path(run_path)
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    data = np.atleast_1d(np.genfromtxt(root / "impedance.csv", delimiter=",", names=True))
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(data["frequency_hz"] / 1e6, data["resistance_ohm"], "o-", label="R")
    ax.plot(data["frequency_hz"] / 1e6, data["reactance_ohm"], "o-", label="X")
    ax.set(xlabel="Częstotliwość [MHz]", ylabel="Impedancja [Ω]", title="Impedancja wejściowa — wynik niezweryfikowany")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(root / "plots" / "impedance.png", dpi=150)
    plt.close(fig)
    images = ["geometry.png", "impedance.png"]
    if (root / "far_field.npz").exists():
        with np.load(root / "far_field.npz", allow_pickle=False) as field:
            theta, phi = field["theta_deg"], field["phi_deg"]
            angle = np.r_[-theta[:0:-1], theta]
            fig, ax = plt.subplots(figsize=(10, 4))
            for forward, backward, label in ((0, 180, "xz"), (90, 270, "yz")):
                a, b = np.where(phi == forward)[0][0], np.where(phi == backward)[0][0]
                gain = np.r_[field["gain_linear"][0, :0:-1, b], field["gain_linear"][0, :, a]]
                ax.plot(angle, 10 * np.log10(np.maximum(gain, 1e-12)), label=label)
            f = field["frequency_hz"][0] / 1e6
            ax.set(xlabel="Kąt od +z [°]", ylabel="Zysk [dBi], moc przyjęta przez port", title=f"Przekroje przy {f:g} MHz — wynik niezweryfikowany")
            ax.grid(alpha=0.25)
            ax.legend()
            fig.tight_layout()
            fig.savefig(root / "plots" / "pattern_cuts.png", dpi=150)
            plt.close(fig)
            images.append("pattern_cuts.png")
    body = "".join(f'<figure><img src="plots/{name}" alt="{name}"></figure>' for name in images)
    rows = "".join(f"<tr><td>{float(row['frequency_hz'])/1e6:g}</td><td>{row['resistance_ohm']:.6g}</td>"
                   f"<td>{row['reactance_ohm']:.6g}</td><td>{row['swr']:.6g}</td></tr>" for row in data)
    page = ("<!doctype html><html lang='pl'><meta charset='utf-8'><title>Wynik anteny</title>"
            "<style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#172333}"
            "img{max-width:100%}td,th{padding:10px;text-align:right;border-bottom:1px solid #ddd}"
            ".status{background:#fff3d6;padding:16px;border-radius:8px}</style>"
            f"<h1>Wynik {escape(root.name)}</h1><p class='status'>{escape(summary['note'])}</p>"
            "<p>PEC, wolna przestrzeń, idealny port różnicowy. Balun i kabel poza modelem.</p>"
            f"<table><tr><th>MHz</th><th>R [Ω]</th><th>X [Ω]</th><th>SWR</th></tr>{rows}</table>{body}</html>")
    (root / "report.html").write_text(page, encoding="utf-8")
