from pathlib import Path

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
    """Compatibility entry point for a new run, before its manifest is closed."""
    from .report import generate_report
    return generate_report(run_path, automatic=True)
