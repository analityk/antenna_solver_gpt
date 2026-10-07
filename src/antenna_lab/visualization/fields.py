"""Phase sheets from saved complex near fields, without invoking a solver."""

from html import escape
import json

from matplotlib.colors import SymLogNorm
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import numpy as np

PCB_VIEWS = {"xy_air": (2, 0, 1, 0, 2), "xz_feed": (1, 0, 2, 0, 1), "yz_feed": (0, 1, 2, 1, 0)}

VIEWS = {"xy_front": (2, 1, 0, 0, 2), "xz": (1, 0, 2, 0, 1), "yz": (0, 1, 2, 0, 1)}


def phase_values(phasor, degrees):
    return np.real(phasor * np.exp(1j * np.deg2rad(degrees)))


def load_plane(path, plane, expected_frequency):
    pcb = plane["name"] in PCB_VIEWS
    normalization_keys = (("port_voltage_phasor", "reference_voltage_v", "array_order") if pcb else ("reference_power_w",))
    with np.load(path, allow_pickle=False) as data:
        result = {key: data[key] for key in ("frequency_hz", "x_m", "y_m", "z_m", "E_v_per_m", "H_a_per_m",
                                            "mask", "normalization_factor", "phasor_convention", *normalization_keys)}
    lines = [result[a + "_m"] for a in "xyz"]
    shape = tuple(len(a) for a in lines)
    if any(not np.isfinite(a).all() or np.any(np.diff(a) <= 0) for a in lines):
        raise ValueError("Niepoprawne współrzędne przekroju pola.")
    normal = (PCB_VIEWS if pcb else VIEWS)[plane["name"]][0]
    if (shape[normal] != 1 or shape != tuple(plane["shape_xyz"])
            or not np.isclose(lines[normal][0], plane["actual_position_m"], rtol=1e-6, atol=1e-10)):
        raise ValueError("Położenie lub kształt przekroju pola różni się od metadanych.")
    frequency = result["frequency_hz"]
    if (not np.isfinite(frequency).all() or np.any(frequency <= 0)
            or str(result["phasor_convention"]) != "real(F * exp(+j * phase)); phase zero = positive port voltage"
            or result["normalization_factor"].shape != frequency.shape
            or not np.isfinite(result["normalization_factor"]).all()
            or (not pcb and (not np.isfinite(result["reference_power_w"]).all() or float(result["reference_power_w"]) <= 0))):
        raise ValueError("Nieprawidłowa normalizacja lub konwencja pól.")
    if frequency.shape != np.shape(expected_frequency) or not np.allclose(frequency, expected_frequency, rtol=1e-12, atol=0):
        raise ValueError("Częstotliwości E/H nie zgadzają się z metadanymi.")
    if pcb:
        voltage = result['port_voltage_phasor']
        if (float(result['reference_voltage_v']) != 1. or voltage.shape != frequency.shape
                or not np.isfinite(voltage).all() or np.any(voltage == 0)
                or not np.allclose(voltage*result['normalization_factor'], 1., rtol=1e-12, atol=0)
                or str(result['array_order']) != 'frequency,component_xyz,x,y,z'
                or frequency.ndim != 1 or not 1 <= len(frequency) <= 3 or np.any(np.diff(frequency)<=0)):
            raise ValueError('Nieprawidłowe odniesienie PCB 1 V lub układ tablic.')
    mask = result["mask"]
    if mask.shape != shape or not np.issubdtype(mask.dtype, np.integer) or np.any(mask > (15 if pcb else 7)) or np.any(mask < 0):
        raise ValueError("Niepoprawna maska próbek E/H.")
    for key in ("E_v_per_m", "H_a_per_m"):
        values = result[key]
        if (values.shape != (len(frequency), 3, *shape) or not np.iscomplexobj(values)
                or not np.isfinite(values[:, :, mask == 0]).all()):
            raise ValueError("Niepoprawne zespolone próbki E/H.")
        values[:, :, mask != 0] = np.nan
    return result


def phase_figure(data, plane, geometry, phases, index=0, components=None):
    normal, horizontal, vertical, e_component, h_component = VIEWS[plane["name"]]
    if components:
        e_component, h_component = components
    lines = [data[a + "_m"] for a in "xyz"]
    f = float(data["frequency_hz"][index])
    def project(array):
        remaining = [n for n in range(3) if n != normal]
        return np.transpose(np.squeeze(array, axis=normal), (remaining.index(vertical), remaining.index(horizontal)))
    fields = [project(data["E_v_per_m"][index, e_component]),
              project(data["H_a_per_m"][index, h_component]) * 1000]
    limits = []
    for values in fields:
        valid = np.abs(values[np.isfinite(values)])
        limits.append(float(np.max(valid)) if valid.size else 0.)
    # Each column uses the phasor envelope, common to every phase; no clipping.
    norms = [SymLogNorm(linthresh=max(limit * .025, 1e-30), vmin=-max(limit, 1e-30),
                        vmax=max(limit, 1e-30), base=10) for limit in limits]
    ratio = np.ptp(lines[vertical]) / np.ptp(lines[horizontal])
    plot_width = min(4.4, 3.3 / ratio)
    plot_height = plot_width * ratio
    pitch = max(plot_height, .8) + .55
    width, height = 1.55 + 2 * plot_width + .9 + .35, 1.35 + len(phases) * pitch + 1.2
    fig = Figure(figsize=(width, height))
    axes = np.empty((len(phases), 2), dtype=object)
    for row in range(len(phases)):
        bottom = height - 1.35 - (row + 1) * pitch + .35
        for col in range(2):
            axes[row, col] = fig.add_axes([(1.55 + col * (plot_width + .9)) / width,
                                          bottom / height, plot_width / width, plot_height / height])
    name = geometry.get("model", "antena")
    fig.suptitle(f"{name} · pola bliskie E/H · {f / 1e6:g} MHz", y=1 - .15 / height, fontsize=13, weight="bold")
    pos = plane["actual_position_m"] * 1000
    requested = plane["requested_position_m"] * 1000
    fig.text(.2 / width, 1 - .60 / height, f"{plane['name']}: {'xyz'[normal]} = {pos:.3f} mm (żądane {requested:.3f} mm) · "
             f"odniesienie portu {float(data['reference_power_w']):g} W · wynik niezweryfikowany", fontsize=9)
    fig.text(.2 / width, 1 - .84 / height, "Faza 0°: maksimum napięcia portu. Linie: rzut geometrii; szary: maska metalu/źródła i ich otoczenia.", fontsize=9)
    cmap = __import__("matplotlib").colormaps["RdBu_r"].copy()
    cmap.set_bad("#b4bac2")
    titles = [f"E_{'xyz'[e_component]} [V/m]", f"H_{'xyz'[h_component]} [mA/m]"]
    for row, phase in enumerate(phases):
        for col, field in enumerate(fields):
            ax = axes[row, col]
            ax.pcolormesh(lines[horizontal] * 1000, lines[vertical] * 1000,
                          np.ma.masked_invalid(phase_values(field, phase)), cmap=cmap, norm=norms[col],
                          shading="nearest", rasterized=True)
            for wire in geometry.get("wires", []):
                p = np.array([wire["start"], wire["stop"]]) * 1000
                ax.plot(p[:, horizontal], p[:, vertical], color="#202c36", lw=1.5)
                ax.plot(p[:, horizontal], p[:, vertical], color="#f7df9c", lw=.65)
            for plate in geometry.get("plates", []):
                a, b = np.array(plate["start"]) * 1000, np.array(plate["stop"]) * 1000
                ax.add_patch(Rectangle((a[horizontal], a[vertical]), b[horizontal] - a[horizontal],
                                       b[vertical] - a[vertical], fill=False, linestyle="--", lw=.7, edgecolor="#333"))
            ax.set(xlim=(lines[horizontal][0] * 1000, lines[horizontal][-1] * 1000),
                   ylim=(lines[vertical][0] * 1000, lines[vertical][-1] * 1000),
                   ylabel=f"{'xyz'[vertical]} [mm]")
            ax.set_aspect("equal", adjustable="box")
            ax.tick_params(labelsize=8)
            if row == 0:
                ax.set_title(titles[col], fontsize=11, weight="bold")
            if row == len(phases) - 1:
                ax.set_xlabel(f"{'xyz'[horizontal]} [mm]")
        bottom = axes[row, 0].get_position().y0
        fig.text(.15 / width, bottom + .65 * plot_height / height, f"{phase:g}°", fontsize=13, weight="bold")
        fig.text(.15 / width, bottom + .35 * plot_height / height, f"{phase / 360 / f * 1e9:.3f} ns", fontsize=8)
    from matplotlib.cm import ScalarMappable
    from matplotlib.ticker import FuncFormatter
    for col in range(2):
        cax = fig.add_axes([(1.55 + col * (plot_width + .9)) / width, .76 / height, plot_width / width, .10 / height])
        bar = fig.colorbar(ScalarMappable(norm=norms[col], cmap=cmap), cax=cax, orientation="horizontal")
        limit = limits[col]
        bar.set_ticks([-limit, -limit / 10, 0, limit / 10, limit] if limit else [0])
        bar.ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.3g}"))
        bar.set_label(titles[col], fontsize=9)
        bar.ax.tick_params(labelsize=8)
    fig.text(.2 / width, .08 / height, "Czerwony: + · niebieski: − · biały: 0. Skala sym-log, osobna dla E i H, stała dla wszystkich faz.\n"
             "To podpisane składowe wektorów w powietrzu; nie moduły pól ani mapa prądu na powierzchni metalu.", fontsize=9)
    return fig


def field_section(data, figure_image, plots_path=None, phase_step=None, components=None):
    root = data["root"]
    metadata_path = root / "fields" / "metadata.json"
    title = '<section class="panel"><h2>Pola E/H w kolejnych fazach</h2>'
    if not metadata_path.exists():
        return title + '<p>Brak zapisanych przekrojów E/H. Uruchom nową symulację z <code>--fields</code>; stare wyniki nie zawierają tych próbek.</p></section>'
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != 1:
        raise ValueError("Nieobsługiwana wersja metadanych E/H.")
    if metadata.get('model') == 'pcb':
        from .pcb_fields import pcb_field_section
        return pcb_field_section(data, metadata, figure_image, plots_path, phase_step)
    geometry = json.loads((root / "geometry.json").read_text(encoding="utf-8"))
    phases = (list(range(0, 181, phase_step)) if phase_step else
              data["config"].get("requested_outputs", {}).get("phase_degrees", list(range(0, 181, 30))))
    body = '<p>Stan harmoniczny odtworzony z zespolonych pól FDTD. Przełączanie faz nie wymaga ponownej symulacji. '
    body += 'Widok z przodu ma długą oś y poziomo i x pionowo: domyślnie pokazuje E_x i H_z. '
    body += 'Przekroje xz/yz domyślnie pokazują E_x i H_y; wybrane składowe są w nagłówkach diagramów. H_z przy pętlach nie jest główną składową fali dalekiej. '
    body += 'Normalizacja korzysta z tego samego niezweryfikowanego pomiaru U/I portu co pozostałe wyniki.</p>'
    for plane in metadata["planes"]:
        name = plane["name"]
        if name not in VIEWS:
            raise ValueError("Nieznana płaszczyzna E/H.")
        fields = load_plane(root / "fields" / f"{name}.npz", plane, metadata["frequency_hz"])
        for i, f in enumerate(fields["frequency_hz"]):
            fig = phase_figure(fields, plane, geometry, phases, i, components)
            label = f"{name} · {f / 1e6:g} MHz · {len(phases)} faz"
            target = plots_path / f"fields_{name}_{i}.png" if plots_path else None
            img = figure_image(fig, label, target)
            uri = img.split('src="', 1)[1].split('"', 1)[0]
            body += f'<details{" open" if name == "xy_front" else ""}><summary>{escape(label)}</summary>{img}'
            body += f'<p><a download="fields_{name}_{i}.png" href="{uri}">Pobierz diagram PNG</a></p></details>'
            fig.clear()
    return title + body + '</section>'
