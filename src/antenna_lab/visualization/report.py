"""Self-contained, interactive HTML made exclusively from saved results."""

import base64
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from antenna_lab.core.config import ROOT
from .report_assets import CSS, JS
from .report_data import edge_work_counts, load_report_data, matching_index, read_json


def number(value, digits=3):
    if value is None:
        return "brak danych"
    value = float(value)
    if np.isnan(value):
        return "—"
    if np.isinf(value):
        return "∞" if value > 0 else "−∞"
    return f"{value:.{digits}f}".replace(".", ",")


def table(headers, rows):
    head = "".join(f"<th>{escape(str(x))}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(x))}</td>" for x in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def figure_image(fig, description, save_path=None):
    FigureCanvasAgg(fig)
    stream = BytesIO()
    fig.savefig(stream, format="png", dpi=140, facecolor="white", bbox_inches="tight")
    raw = stream.getvalue()
    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(raw)
    return f'<img alt="{escape(description, quote=True)}" src="data:image/png;base64,{base64.b64encode(raw).decode()}"/>'


def impedance_figure(data, save_path=None):
    spectrum = data["spectrum"]
    f, r, x = (np.asarray(spectrum[name]) for name in ("frequency_mhz", "r", "x"))
    z, reference = r + 1j * x, data["reference"]
    with np.errstate(divide="ignore", invalid="ignore"):
        rho = np.abs((z - reference) / (z + reference))
        swr = np.where((r > 0) & (rho < 1), (1 + rho) / (1 - rho), np.nan)
    fig = Figure(figsize=(11, 4))
    axes = fig.subplots(1, 2)
    style = "o" if len(f) == 1 else "-"
    axes[0].plot(f, r, style, color="#126eaa", label="R")
    axes[0].plot(f, x, style, color="#bd5910", label="X")
    axes[0].set(ylabel="R, X [Ω]", title="Impedancja wejściowa")
    axes[0].legend()
    axes[1].plot(f, swr, style, color="#6d43a6")
    valid = swr[np.isfinite(swr)]
    limit = min(20, max(3, float(valid.max()) * 1.05)) if len(valid) else 3
    axes[1].set(ylabel="SWR", ylim=(1, limit), title=f"SWR dla Zref = {reference:g} Ω" + (" (skala do 20)" if len(valid) and valid.max() > 20 else ""))
    axes[1].axhspan(1, 2, color="#e9f6ed", zorder=0)
    for ax in axes:
        ax.set_xlabel("Częstotliwość [MHz]")
        ax.grid(alpha=.2)
        ax.ticklabel_format(useOffset=False, axis="x")
        if f.min() <= data["target_mhz"] <= f.max():
            ax.axvline(data["target_mhz"], color="#8b9aab", linestyle=":", lw=1)
    fig.tight_layout()
    return figure_image(fig, "Impedancja i SWR dla zapisanego odniesienia portu", save_path)


def power_comparisons(data):
    """Keep both denominators explicit; never renormalize stored results."""
    power = data["power"]
    port = power.get("accepted_power_w", data["summary"].get("accepted_power_w"))
    work = power.get("source_edge_work", {}).get("frequencies", [])
    results = []
    for item in work:
        frequency = float(item["frequency_hz"])
        net = float(item["net_active_work_w"])
        if not np.isfinite(net) or not np.isfinite(frequency):
            raise ValueError("Nieskończona praca źródła lub częstotliwość w power_balance.json.")
        boxes = {b["name"]: float(b["active_flux_w"]) for b in power.get("boxes", [])
                 if matching_index([b["frequency_hz"]], frequency) is not None}
        counts = edge_work_counts(data["root"], frequency)
        if counts and not np.isclose(counts["net_w"], net, rtol=1e-7, atol=1e-12):
            raise ValueError("Praca w power_balance.json nie zgadza się z source_work_spectra.npz.")
        results.append({"frequency_hz": frequency, "work_w": net, "port_w": port,
                        "port_work_difference_percent": 100 * (port - net) / port if port and port > 0 else None,
                        "outer_work_difference_percent": 100 * (net - boxes["nf2ff"]) / net if net > 0 and "nf2ff" in boxes else None,
                        "counts": counts, "boxes": boxes})
    return results


def _power_section(data):
    power, summary = data["power"], data["summary"]
    port = power.get("accepted_power_w", summary.get("accepted_power_w"))
    rows = []
    comparisons = power_comparisons(data)
    for comparison in comparisons:
        f = comparison["frequency_hz"] / 1e6
        rows.append([number(f), "Odniesienie pojedynczego pomiaru portu", number(port, 9)])
        rows.append([number(f), "Lokalna praca netto w obszarze źródła", number(comparison["work_w"], 9)])
    names = {"nf2ff": "Strumień zewnętrzny (cała antena)", "power_inner": "Strumień wewnętrzny (cała antena)",
             "power_feed": "Strumień małej powierzchni przy porcie"}
    for box in power.get("boxes", []):
        rows.append([number(box["frequency_hz"] / 1e6), names.get(box["name"], box["name"]), number(box["active_flux_w"], 9)])
    notes = []
    for item in comparisons:
        f = item["frequency_hz"] / 1e6
        prefix = f"Przy {number(f)} MHz: "
        if item["port_work_difference_percent"] is not None:
            notes.append(prefix + f"(moc portu − praca lokalna) / moc portu = {number(item['port_work_difference_percent'], 4)}%. "
                         "To rozbieżność metod pomiaru mocy; sam raport nie przypisuje jej stratom anteny.")
        if item["outer_work_difference_percent"] is not None:
            notes.append(prefix + f"(praca lokalna − strumień zewnętrzny) / praca lokalna = {number(item['outer_work_difference_percent'], 5)}%. "
                         "Mała różnica tych dwóch wielkości nie zatwierdza pomiaru impedancji ani zbieżności siatki.")
        counts = item["counts"]
        if counts:
            notes.append(prefix + f"wkłady pracy krawędzi: {counts['positive']} dodatnich, {counts['negative']} ujemnych, {counts['zero']} bliskich zeru. "
                         "Jest to pomiar podpisanej pracy netto, a nie licznik geometrycznego pokrycia wymuszeniem.")
    if not rows:
        notes.append("Brak niezależnego bilansu powierzchni i lokalnej pracy źródła. Tego raportu nie można użyć do potwierdzenia zamknięcia bilansu mocy.")
        ratios = summary.get("radiation_to_accepted_power_ratio", [])
        for f, ratio in zip(summary.get("frequency_hz", []), ratios):
            rows.append([number(f / 1e6), "Moc promieniowania według NF2FF (odniesienie portu)", number(ratio * port, 9) if port else "brak danych"])
    elif not comparisons:
        notes.append("Zapisano strumienie przez powierzchnie, ale brak lokalnej pracy źródła. Nie można porównać tych dwóch metod.")
    notes.append("Strumień power_feed przecina przewody przy porcie; nie jest mocą promieniowania całej anteny i nie służy do obliczania jej zysku.")
    notes.append("Bilans odczytano z zapisanej diagnostyki. Raport nie powtarza całkowania surowych HDF5 ani nie koryguje normalizacji.")
    body = table(["MHz", "Wielkość", "W"], rows) if rows else ""
    body += "<ul>" + "".join(f"<li>{escape(note)}</li>" for note in notes) + "</ul>"
    return '<section class="panel"><h2>Bilans mocy</h2><p class="fixed">Częstotliwości w tej tabeli są niezależne od suwaka widma.</p>' + body + "</section>"


def _far_field(data, plot_path=None):
    summary, comparisons = data["summary"], power_comparisons(data)
    rows = []
    for index, frequency in enumerate(summary.get("frequency_hz", [])):
        gains = summary.get("forward_gain_dbi", [])
        if index >= len(gains):
            continue
        gain = gains[index]
        ratio = summary.get("radiation_to_accepted_power_ratio", [])
        directivity = gain - 10 * np.log10(ratio[index]) if index < len(ratio) and ratio[index] > 0 else None
        local_gain = None
        for item in comparisons:
            if matching_index([frequency], item["frequency_hz"]) is not None and item["work_w"] > 0 and item["port_w"]:
                local_gain = gain + 10 * np.log10(item["port_w"] / item["work_w"])
        rows.append([number(frequency / 1e6), number(gain, 4), number(directivity, 4), number(local_gain, 4)])
    body = table(["MHz", "Zysk +z, odniesienie portu [dBi]", "Kierunkowość +z [dBi]", "Porównanie: odniesienie pracy lokalnej [dBi]"], rows) if rows else "<p>Brak zapisanego zysku na osi +z.</p>"
    body += "<p>Kierunkowość odnosi natężenie promieniowania do całej mocy wypromieniowanej; zysk do mocy przyjętej. "
    body += "Kolumna pracy lokalnej jest porównaniem diagnostycznym, nie poprawionym wynikiem zysku. Zysk nie uwzględnia niedopasowania; SWR z suwaka nie zmienia tej tabeli.</p>"
    path = data["root"] / "far_field.npz"
    if not path.exists():
        body += "<p class='muted'>Brak far_field.npz: nie ma danych do narysowania charakterystyki. Mała paczka diagnostyczna może nie zawierać tego pliku.</p>"
    else:
        with np.load(path, allow_pickle=False) as raw:
            frequency = raw["frequency_hz"]
            selected = int(np.argmin(abs(frequency - data["target_mhz"] * 1e6)))
            theta, phi = raw["theta_deg"], raw["phi_deg"]
            fig = Figure(figsize=(11, 4.3))
            ax = fig.subplots()
            curves = 0
            for front, back, label, color in ((0, 180, "xz", "#126eaa"), (90, 270, "yz", "#bd5910")):
                a, b = matching_index(phi, front), matching_index(phi, back)
                if a is None or b is None:
                    continue
                gain = raw["gain_linear"][selected]
                cut = np.r_[gain[:0:-1, b], gain[:, a]]
                with np.errstate(divide="ignore", invalid="ignore"):
                    db = np.where(cut > 0, 10 * np.log10(cut), np.nan)
                ax.plot(np.r_[-theta[:0:-1], theta], db, label=label, color=color)
                curves += 1
            if curves:
                ax.set(xlabel="Kąt od +z [°]", ylabel="Zysk [dBi], odniesienie portu",
                       title=f"Przekroje pola dalekiego przy {frequency[selected] / 1e6:g} MHz")
                ax.legend(); ax.grid(alpha=.25)
                fig.tight_layout()
                body += "<figure>" + figure_image(fig, "Przekroje charakterystyki xz i yz", plot_path) + "<figcaption>0° = +z, kierunek przed reflektorem. "
                body += f"Pokazano jedną z {len(frequency)} zapisanych częstotliwości pola dalekiego. Suwak impedancji nie przesuwa tego wykresu.</figcaption></figure>"
            else:
                body += "<p>Brak kątów phi = 0/90/180/270° w zapisanej siatce; raport nie interpoluje przekrojów.</p>"
    return '<section class="panel"><h2>Kierunkowość i zysk</h2>' + body + '</section>'


def _zeros(spectrum):
    f, r, x = (np.asarray(spectrum[key]) for key in ("frequency_mhz", "r", "x"))
    roots = [(f[i], r[i]) for i in np.flatnonzero(x == 0)]
    for i in range(len(f) - 1):
        if x[i] * x[i + 1] < 0:
            weight = -x[i] / (x[i + 1] - x[i])
            roots.append((f[i] + weight * (f[i + 1] - f[i]), r[i] + weight * (r[i + 1] - r[i])))
    if not roots:
        return "<p>Brak przejścia X przez zero w zapisanym zakresie. To nie dowodzi braku rezonansu poza zakresem.</p>"
    return table(["Przybliżone X = 0 [MHz]", "R [Ω]"], [[number(f, 4), number(r)] for f, r in sorted(roots)[:30]]) + "<p class='muted'>Interpolacja liniowa między próbkami (najwyżej 30 przejść). X = 0 nie musi oznaczać najmniejszego SWR ani zweryfikowanego rezonansu konstrukcji.</p>"


def _metadata(data):
    manifest, config = data["manifest"], data["config"]
    simulation = config.get("simulation", {})
    rows = [("Stan wykonania", data["execution_status"]), ("Walidacja fizyczna", data["summary"].get("validation_status", "brak danych")),
            ("Wariant", data["variant_name"]), ("Model", config.get("antenna", {}).get("model", "brak danych")),
            ("Data przebiegu", manifest.get("created_at", "brak manifestu")), ("Commit obliczeń", manifest.get("code", {}).get("commit_sha", "brak danych")),
            ("Przewodnik / ośrodek", f"{simulation.get('conductor_model', '?')} / {simulation.get('medium', '?')}"),
            ("Reflektor / zasilanie", f"{simulation.get('reflector_model', '?')} / {simulation.get('feed_model', '?')}"),
            ("Liczba komórek siatki", data["mesh"].get("cell_count", "brak danych")),
            ("Końcowy zapis energii [dB]", number(data["end_energy_db"], 2))]
    body = '<div class="meta">' + ''.join(f'<div><small>{escape(label)}</small><br><strong>{escape(str(value))}</strong></div>' for label, value in rows) + '</div>'
    body += "<p>Poziom energii z logu opisuje wygaśnięcie przebiegu czasowego. Nie jest kontrolą zbieżności względem siatki ani dowodem poprawności portu. Idealny port nie obejmuje baluna, kabla i LNA.</p>"
    warnings = list(data["warnings"])
    if data["execution_status"] != "completed":
        warnings.insert(0, "Brak potwierdzenia ukończenia w manifeście. Raport pokazuje dostępne dane; kompletność przebiegu nie jest potwierdzona.")
    for text, count in Counter(data["native_warnings"]).items():
        warnings.append(text + (f" (liczba wystąpień: {count})" if count > 1 else ""))
    if warnings:
        body += '<h3>Ostrzeżenia z danych i logu</h3><ul>' + ''.join(f'<li>{escape(str(w))}</li>' for w in warnings) + '</ul>'
    else:
        body += '<p>Brak zapisanych ostrzeżeń. To nie oznacza zaliczonej walidacji fizycznej.</p>'
    hashes = []
    files = ["summary.json", "parameters.resolved.json", "manifest.json", "mesh.json", "solver.log", "impedance.csv", "impedance_dense.csv", "power_balance.json", "source_work_spectra.npz", "far_field.npz", "openems/port_ut_1", "openems/port_it_1"]
    files += ["geometry.json", "field_layout.json", "fields/metadata.json"]
    files += [f"fields/{plane}.npz" for plane in ("xy_front", "xz", "yz")]
    for name in files:
        # The parent finalizes this manifest after automatic reporting. Its
        # provisional digest would misidentify the file subsequently on disk.
        if name == "manifest.json" and manifest.get("status") == "running":
            continue
        path = data["root"] / name
        if path.exists():
            hashes.append((name, sha256(path.read_bytes()).hexdigest()))
    body += '<details><summary>Pliki źródłowe i ich SHA-256</summary><p>Identyfikacja dostępnych plików, nie porównanie z sumami kontrolnymi manifestu.</p>' + table(["Plik", "SHA-256"], hashes) + '</details>'
    return '<section class="panel"><h2>Przebieg i wiarygodność danych</h2>' + body + '</section>'


def _pcb_geometry(data, plots_path):
    """Draw only saved SI polygons; never reopen Gerbers or native modules."""
    from matplotlib.patches import Polygon as PatchPolygon
    from .pcb_regions import copper_patch
    geometry = data['geometry']
    fig = Figure(figsize=(8, 6)); ax = fig.subplots()
    board = np.asarray(geometry['outline']['vertices_xy_m'])*1e3
    ax.add_patch(PatchPolygon(board, facecolor='#f1f4e7', edgecolor='#53604c', label='PCB'))
    for copper in geometry['copper']:
        if copper.get('layer_role', 'top') != 'top': continue
        ax.add_patch(copper_patch(copper, facecolor='#c77c36', edgecolor='#825323', alpha=.85))
    from .pcb_drills import drill_markers
    drill_markers(ax,geometry)
    port = geometry['port']; n,p = np.asarray(port['negative_xy_m']),np.asarray(port['positive_xy_m'])
    delta = p-n; normal = np.array([-delta[1],delta[0]])/np.linalg.norm(delta)*port['width_m']/2
    face = np.asarray([n-normal,p-normal,p+normal,n+normal])*1e3
    ax.add_patch(PatchPolygon(face, fill=False, edgecolor='#175bc0', linewidth=2, label='Port'))
    ax.scatter(*np.asarray([n,p]).T*1e3, color=['#143c7a','#e43232'], s=22, zorder=5)
    ax.autoscale_view(); ax.set_aspect('equal');ax.margins(.08)
    ax.set(xlabel='x [mm]',ylabel='y [mm]',title='PCB: miedź i port, widok z góry')
    ax.grid(alpha=.15);ax.legend();fig.tight_layout()
    return '<section class="panel"><h2>Geometria PCB</h2>'+figure_image(fig,'Geometria PCB z geometry.json',plots_path/'geometry.png' if plots_path else None)+'</section>'


def _pcb_spectrum(data, plots_path):
    spectrum = data['spectrum']; f = np.asarray(spectrum['frequency_mhz'])
    z = np.asarray(spectrum['r'])+1j*np.asarray(spectrum['x']); reference=data['reference']
    rho = np.abs((z-reference)/(z+reference))
    with np.errstate(divide='ignore'):
        db = 20*np.log10(rho)
    swr = (1+rho)/(1-rho)
    html = ''
    for name,curves,ylabel in (
        ('impedance',[(z.real,'R'),(z.imag,'X')],'R, X [Ω]'),
        ('s11',[(db,'S11')],'S11 [dB]'),('swr',[(swr,'SWR')],'SWR')):
        fig=Figure(figsize=(9,3.3));ax=fig.subplots()
        for values,label in curves:ax.plot(f,values,'o-' if len(f)<3 else '-',label=label)
        ax.set(xlabel='Częstotliwość [MHz]',ylabel=ylabel);ax.grid(alpha=.2);ax.legend();fig.tight_layout()
        html += figure_image(fig,ylabel,plots_path/(name+'.png') if plots_path else None)
    return html


def _pcb_diagnostics(data):
    diag=data['pcb_diagnostics']; rows=[]; boundary=[]
    lo,hi=data['spectrum']['frequency_mhz'][0],data['spectrum']['frequency_mhz'][-1]
    for key,label,value in (('minimum_s11','Minimum próbkowane S11','s11_db'),
                            ('minimum_swr','Minimum próbkowane SWR','swr'),
                            ('minimum_abs_reactance','Minimum |X| (pokazano X)','reactance_ohm')):
        item=diag[key];freq=item['frequency_hz']/1e6
        rows.append((label,number(freq,6),'−∞' if item[value] is None else number(item[value],6)))
        if freq in (lo,hi):boundary.append(label)
    body=table(['Wielkość','MHz','Wartość'],rows)
    if boundary:body+='<p class="status">Optimum na granicy sweepu: '+escape(', '.join(boundary))+'. Rozszerz zakres, zanim uznasz minimum za wewnętrzne.</p>'
    crossings=diag['reactance_crossings']
    body+=table(['Dolne MHz','Górne MHz','X dolne [Ω]','X górne [Ω]'],[
        [number(c['frequency_low_hz']/1e6,6),number(c['frequency_high_hz']/1e6,6),number(c['x_low_ohm'],6),number(c['x_high_ohm'],6)] for c in crossings]) if crossings else '<p>Brak przejścia X przez zero w zapisanym zakresie.</p>'
    return body+'<p>Przedziały sąsiednich próbek, bez interpolacji rezonansu. Minima dotyczą zapisanego Zref.</p>'


def _pcb_metadata(data):
    s=data['summary']; imported=s.get('import',read_json(data['root']/'import.json'))
    rows=[('Katalog Gerberów',imported.get('source_directory','not recorded')),
          ('Stan wykonania',s.get('status','not recorded')),('Walidacja',s.get('validation_status','unverified')),
          ('Profil jakości',s.get('quality_profile','not recorded')),('Sweep',s.get('sweep','not recorded')),
          ('Liczba komórek',s.get('mesh',{}).get('cell_count','not recorded')),
          ('Minimalne kroki [m]',s.get('min_axis_steps_m','not recorded')),
          ('Iteracje',s.get('actual_iterations','not recorded')),('Zakończenie',s.get('termination_status','not recorded')),
          ('Źródło założeń',imported.get('physical_config_source','legacy PCB config')),
          ('Parametry fizyczne',imported.get('physical_config',imported.get('resolved_config','not recorded')))]
    body=table(['Przebieg PCB','Wartość'],rows)
    material = {**imported.get('resolved_config', {}),
                **s.get('preparation', {}).get('geometry', {}), **s}
    model = material.get('copper_model', 'pec')
    if model == 'stackup':
        body += '<p>Model miedzi: osobno dla każdej warstwy; patrz Stackup.</p>'
    else:
        physical = [('Copper model', 'conducting sheet' if model == 'conducting_sheet' else 'PEC')]
        for key, label, scale, unit in (
            ('copper_thickness_m', 'Thickness', 1e6, 'µm'),
            ('copper_conductivity_s_m', 'Conductivity', 1e-6, 'MS/m'),
            ('copper_sheet_conductance_s', 'Sheet conductance', 1, 'S')):
            value = material.get(key)
            if value is not None:
                physical.append((label, f'{value*scale:g} {unit}'))
        body += '<h3>Model fizyczny miedzi</h3>'+table(['Parametr', 'Wartość'], physical)
        body += ('<p>Skończona przewodność i grubość fizyczna: model powierzchniowy conducting sheet. '
                 'Geometria płaska, bez dodatkowych komórek Z.</p>' if model == 'conducting_sheet' else
                 '<p>PEC: parametry grubości i przewodności, jeśli podane, nie są używane przez solver.</p>')
    files=imported.get('discovered_files',[])
    if not files:
        files=[dict(name=v['path'],role=k,sha256=v['sha256'],disposition='modeled') for k,v in imported.get('files',{}).items()]
    body+=table(['Plik','Rola','Obsługa','SHA256'],[(f['name'],f['role'],f['disposition'],f['sha256']) for f in files])
    assumptions=imported.get('assumptions',data['geometry'].get('assumptions',[]))
    body+='<h3>Założenia i pominięta fizyka</h3><ul>'+''.join('<li>'+escape(str(a))+'</li>' for a in assumptions)+'</ul>'
    body+='<p>Chropowatość miedzi: pominięta. Soldermask, paste i silkscreen pominięto. PTH/NPTH są modelowane tylko gdy zapisane w sekcji Drills / vias; brak wierceń nie dowodzi kompletności modelu. E/H, NF2FF i bilans mocy: not recorded.</p>'
    if (data['root']/'fields/metadata.json').exists():
        body = body.replace('E/H, NF2FF i bilans mocy: not recorded.', 'E/H: zapisane przekroje poniżej. NF2FF i bilans mocy: not recorded.')
    body+=''.join('<p class="status">'+escape(str(w))+'</p>' for w in data['warnings'])
    return '<section class="panel"><h2>Przebieg PCB i założenia</h2>'+body+'</section>'


def render_html(data, *, plots_path=None, phase_step=None, field_components=None):
    from .fields import field_section
    spectrum, reference = data["spectrum"], data["reference"]
    pcb = data.get("is_pcb", False)
    title = ("Raport PCB · " if pcb else "Raport anteny · ") + data["run_id"]
    choices = sorted({50, 75, 100, 200, reference})
    options = ''.join(f'<option value="{value:g}"' + (' selected' if value == reference else '') + f'>{value:g} Ω</option>' for value in choices)
    payload = dict(spectrum, reference=reference, target_mhz=data["target_mhz"])
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    plot_path = plots_path / "impedance.png" if plots_path else None
    fallback = _pcb_spectrum(data, plots_path) if pcb else impedance_figure(data, plot_path)
    image_path = data["root"] / "plots" / "geometry.png"
    geometry = ""
    if image_path.exists():
        geometry = '<section class="panel"><details><summary>Geometria zapisana w przebiegu</summary><img alt="Zapisany rysunek geometrii anteny" src="data:image/png;base64,' + base64.b64encode(image_path.read_bytes()).decode() + '"></details></section>'
    if pcb:
        geometry = _pcb_geometry(data, plots_path)
        from .pcb_stackup import stackup_section
        from .pcb_drills import drill_section
        extra_sections = geometry + stackup_section(data, plots_path, figure_image, table) + drill_section(data["geometry"],table) + _pcb_metadata(data)
        if (data["root"] / "fields" / "metadata.json").exists():
            extra_sections += field_section(data, figure_image, plots_path, phase_step, field_components)
        zeros = _pcb_diagnostics(data)
    else:
        extra_sections = (_power_section(data) + _far_field(data, plots_path / 'pattern_cuts.png' if plots_path else None)
                          + field_section(data, figure_image, plots_path, phase_step, field_components) + geometry + _metadata(data))
        zeros = _zeros(spectrum)
    note = escape(data["summary"].get("note", "Wynik roboczy; wymagana kontrola modelu i zbieżności."))
    points = len(spectrum["r"])
    return f'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style></head><body><main>
<header><div class="eyebrow">Antenna Solver GPT · raport lokalny</div><h1>{"PCB pod lupą" if pcb else "Antena pod lupą"}</h1>
<p class="run">Wariant: <strong>{escape(data['variant_name'])}</strong></p>
<p class="run">Przebieg: <strong>{escape(data['run_id'])}</strong></p>
<p class="muted">{"Geometria PCB i widmo impedancji z zapisanych danych." if pcb else "Widmo, charakterystyka i bilans mocy z zapisanych danych."} Ten plik działa samodzielnie, bez internetu.</p></header>
<div class="status"><strong>Wynik roboczy — raport nie zatwierdza modelu.</strong><br>{note}</div>
<section class="panel"><h2>Impedancja i dopasowanie</h2>
<p>{points} próbek od {number(spectrum['frequency_mhz'][0])} do {number(spectrum['frequency_mhz'][-1])} MHz.
Źródło: <code>{escape(spectrum['source'])}</code>.</p>
<div class="interactive"><div class="controls">
<label for="frequency">Częstotliwość [MHz]<input id="frequency" type="number" step="any"></label>
<label for="reference">Impedancja odniesienia<select id="reference">{options}</select></label>
<button id="target" type="button">Cel: {number(data['target_mhz'])} MHz</button>
<button id="best" type="button">Najmniejszy SWR</button><button id="csv" type="button">Pobierz CSV</button></div>
<label class="slider-label" for="slider">Wybierz zapisaną próbkę: <strong id="selected"></strong></label>
<input id="slider" type="range" min="0" value="0" step="1">
<div class="metrics"><div class="metric"><span>Rezystancja R</span><strong id="resistance"></strong></div>
<div class="metric"><span>Reaktancja X</span><strong id="reactance"></strong></div>
<div class="metric"><span>SWR</span><strong id="swr"></strong></div><div class="metric"><span>S11</span><strong id="s11"></strong></div></div>
<p id="mismatch"></p><div class="plots"><div class="plot"><p class="legend"><span class="blue">● R</span> · <span class="orange">● X</span></p><div id="impedance-plot"></div></div>
<div class="plot"><p class="legend">SWR · zielone tło: 1–2</p><div id="swr-plot"></div></div></div>
<p id="best-info"></p><p class="muted">Kliknięcie wykresu wybiera najbliższą zapisaną próbkę. Linia przerywana pokazuje wybór; kropkowana — cel z konfiguracji.</p></div>
<div class="{'pcb-spectrum-static' if pcb else 'fallback'}">{fallback}<p>Wykres statyczny: Zref = {number(reference, 0)} Ω. Interaktywne sterowanie wymaga JavaScript; wydruk używa tej wersji.</p></div>
<p class="muted">Gęsty krok częstotliwości jest odczytem widma tego samego przebiegu czasowego. Nie zwiększa fizycznej rozdzielczości ani dokładności symulacji. Niski SWR sam nie oznacza dużego zysku.</p>
<details{' open' if pcb else ''}><summary>{'Minima próbkowane i przejścia reaktancji przez zero' if pcb else 'Przejścia reaktancji przez zero'}</summary>{zeros}</details></section>
{extra_sections}
<p class="footer">Generator raportu v1 · {datetime.now(timezone.utc).isoformat()} · źródło: {escape(str(data['root']))}<br>
Odczyt i interpretacja według jawnych reguł; bez AI, usług sieciowych i ponownej symulacji FDTD. Dane źródłowe pozostają niezmienione.</p>
</main><script id="report-data" type="application/json">{encoded}</script><script>{JS}</script></body></html>'''


def generate_report(run_path, output=None, *, automatic=False, start_mhz=None, stop_mhz=None, step_mhz=None,
                    variant_name=None, phase_step=None, field_components=None):
    if phase_step not in (None, 15, 30):
        raise ValueError("Krok fazy musi wynosić 15 lub 30 stopni.")
    if field_components is not None and (len(field_components) != 2 or any(c not in (0, 1, 2) for c in field_components)):
        raise ValueError("Składowe pola muszą wskazywać osie x/y/z.")
    root = Path(run_path).resolve()
    if output is None:
        label = f"{variant_name}__{root.name}" if variant_name else root.name
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", label)[:100]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        output = root / "report.html" if automatic else ROOT / "outcomes" / "reports" / f"{safe_id}_{stamp}.html"
    output = Path(output).resolve()
    if output.suffix.lower() != ".html":
        raise ValueError("Plik raportu musi mieć rozszerzenie .html.")
    if not automatic and output.is_relative_to(root):
        raise ValueError("Zakończony przebieg jest niezmienny. Zapisz nowy raport poza jego katalogiem (domyślnie outcomes/reports).")
    if output.exists():
        raise ValueError(f"Raport już istnieje: {output}. Podaj nową nazwę; istniejące pliki nie są nadpisywane.")
    data = load_report_data(root, start_mhz=start_mhz, stop_mhz=stop_mhz, step_mhz=step_mhz,
                            simulation_completed=automatic)
    if variant_name:
        data["variant_name"] = variant_name
    if automatic and data.get("is_pcb") and data["execution_status"] != "completed":
        raise ValueError("Automatyczny raport PCB wymaga ukończonego przebiegu.")
    if automatic and not data.get("is_pcb") and data["manifest"].get("status") != "running":
        raise ValueError("Raport automatyczny wolno zapisać tylko przed zamknięciem nowego przebiegu.")
    html = render_html(data, plots_path=root / "plots" if automatic else None,
                       phase_step=phase_step, field_components=field_components)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(html)
    return output
