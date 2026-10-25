"""Read-only visualisation of unverified PCB sheet-current estimates.

Native rot(H) data and full-resolution complex NPZ remain immutable.
The plot is quantitative in nominal units, but validation is NOT implied.
"""
from html import escape

import numpy as np
from matplotlib.figure import Figure
from matplotlib import colormaps
from shapely.geometry import Polygon


def load_copper_current(path, plane, frequencies):
    """Validate all model coordinates and preserved complex current components."""
    with np.load(path, allow_pickle=False) as raw:
        f = np.asarray(raw['frequency_hz'], dtype=float)
        x = np.asarray(raw['x_m'], dtype=float)
        y = np.asarray(raw['y_m'], dtype=float)
        current = np.asarray(raw['K_estimated_a_per_m'])
        on_copper = np.asarray(raw['on_copper'])
        dual_width = float(raw['dual_width_m'])
        vref = float(raw['reference_voltage_v'])
    if (not np.array_equal(f, np.asarray(frequencies, dtype=float)) or
            not np.iscomplexobj(current) or current.shape !=
            (len(f), 2, len(x), len(y)) or
            on_copper.shape != (len(x), len(y)) or
            on_copper.dtype != bool or not np.any(on_copper) or
            vref != 1.0 or dual_width <= 0 or
            not np.isclose(dual_width, plane['dual_width_m'], rtol=1e-10, atol=0) or
            np.any(np.diff(x) <= 0) or np.any(np.diff(y) <= 0) or
            not np.all(np.isfinite(current[:, :, on_copper]))):
        raise ValueError('Niekompletne lub niezgodne dane prądu powierzchniowego PCB.')
    return dict(frequency_hz=f, x_m=x, y_m=y, k=current,
                on_copper=on_copper, layer_role=plane['layer_role'])


def _magnitude(k):
    return np.sqrt(np.abs(k[0]) ** 2 + np.abs(k[1]) ** 2)


def current_figure(data, geometry, plane, index, shared_limit):
    """Fixed magnitude scale; phasor-vector snapshots at 0 and 90 degrees."""
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable

    x, y = data['x_m'] * 1e3, data['y_m'] * 1e3
    k = data['k'][index]
    amplitude = np.ma.array(_magnitude(k).T,
                            mask=~data['on_copper'].T)
    fig = Figure(figsize=(11, 4.5), layout='constrained')
    axes = fig.subplots(1, 2, sharex=True, sharey=True)
    cmap = colormaps['viridis'].with_extremes(bad='#d2d5db')
    norm = Normalize(vmin=0.0, vmax=max(shared_limit, 1e-30))
    gx, gy = np.meshgrid(x, y)
    # At most 20x20 arrows, display-only thinning; NPZ remains full resolution.
    ix = np.unique(np.linspace(0, len(x)-1, min(len(x), 20), dtype=int))
    iy = np.unique(np.linspace(0, len(y)-1, min(len(y), 20), dtype=int))
    px, py = np.meshgrid(x[ix], y[iy])
    from shapely.geometry import Point
    polys = [Polygon(c['vertices_xy_m'], c.get('holes_xy_m', ()))
             for c in geometry['copper']
             if c['layer_role'] == plane['layer_role'] and
             abs(c['z_m'] - plane['z_m']) <= 1e-12]
    for ax, phase in zip(axes, (0, 90)):
        ax.pcolormesh(gx, gy, amplitude, norm=norm, cmap=cmap, shading='nearest',
                      rasterized=True)
        for poly in polys:
            if poly.is_empty:
                continue
            for ring in (poly.exterior, *poly.interiors):
                boundary = np.asarray(ring.coords) * 1e3
                ax.plot(boundary[:, 0], boundary[:, 1],
                        linewidth=.6, color='#252525')
        samples = k[:, np.ix_(ix, iy)[0], np.ix_(ix, iy)[1]]
        # Equivalent to np.real(K*exp(j phase)): no rescaling between snapshots.
        instant = (samples.real * np.cos(np.deg2rad(phase)) -
                   samples.imag * np.sin(np.deg2rad(phase)))
        u = instant[0].T.copy()
        v = instant[1].T.copy()
        valid = data['on_copper'][np.ix_(ix, iy)].T
        u[~valid] = np.nan
        v[~valid] = np.nan
        ax.quiver(px, py, u, v, color='#151515', angles='xy', scale_units='width',
                  scale=max(shared_limit, 1e-30)*26, width=.003)
        ax.set(xlabel='X [mm]', ylabel='Y [mm]',
               title=f'Wektor K — faza {phase}°')
        ax.set_aspect('equal', adjustable='box')
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=list(axes),
                 label='|K| estymowane [A/m / 1 V port]')
    fig.suptitle(f"Warstwa {plane['layer_role']} · "
                 f"{data['frequency_hz'][index] / 1e6:g} MHz · "
                 'rot(H) · wynik niewalidowany')
    return fig


def pcb_current_section(data, figure_image, plots_path):
    from pathlib import Path
    from antenna_lab.pcb.postprocess import read_json
    root = data['root']
    metadata = read_json(root / 'currents/metadata.json')
    if (metadata.get('schema_version') != 1 or
            metadata.get('quantity') != 'K_estimated_from_curl_H' or
            metadata.get('reference_voltage_v') != 1.0 or
            not isinstance(metadata.get('planes'), list)):
        raise ValueError('Nieobsługiwane metadane powierzchniowego prądu PCB.')
    frequencies = metadata['frequency_hz']
    records = [(plane, load_copper_current(
        root / 'currents' / (plane['name'] + '.npz'), plane, frequencies))
        for plane in metadata['planes']]

    # Common absolute scale across all layers and frequencies.
    peaks = []
    for _plane, record in records:
        for k in record['k']:
            amplitude = _magnitude(k)
            valid = amplitude[record['on_copper']]
            if valid.size:
                peaks.append(float(valid.max()))
    limit = max(peaks, default=0.0)
    body = ('<section class="panel"><h2>Gęstość prądu na miedzi — mapa diagnostyczna</h2>'
            '<p><strong>Wynik niezweryfikowany ilościowo.</strong> '
            'openEMS zapisuje rot(H) [A/m²] na płaszczyźnie miedzi; '
            'przeliczenie przez lokalną szerokość komórki dualnej daje '
            'estymatę wypadkowego K [A/m] na sheetcie PEC/conducting sheet. '
            'Nie jest to pomiar osobnych prądów obu fizycznych stron '
            'folii, rozkład J przez jej grubość ani obliczenie strat AC. '
            'Punkty przy portach, krawędziach i przelotkach wymagają '
            'kontroli zbieżności i warunków brzegowych.</p>'
            '<p>Kolory: moduł zespolonego wektora K, wspólna skala '
            'dla wszystkich warstw i częstotliwości; strzałki: '
            'chwilowy kierunek i wartość w fazach 0°/90°. '
            'Źródło: 1∠0 V na porcie (nie 1 W). Szare: poza rzeczywistą '
            'powierzchnią miedzi. Surowe HDF5 i pełne NPZ '
            'pozostają zachowane.</p>')
    if not records:
        body += '<p>Nie zapisano prądu dla żadnej obsadzonej warstwy.</p>'
    for layer_idx, (plane, record) in enumerate(records):
        for index, f in enumerate(frequencies):
            title = f"{plane['layer_role']} · {f/1e6:g} MHz"
            fig = current_figure(record, data['geometry'], plane, index, limit)
            path = (Path(plots_path) /
                    f"current_{plane['name']}_{index}.png") if plots_path else None
            body += ('<details'+(' open' if layer_idx == 0 and index == 0 else '')+
                     '><summary>'+escape(title)+'</summary>')
            body += figure_image(fig, title, path) + '</details>'
            fig.clear()
    for missing in metadata.get('empty_layers', ()):
        body += ('<p>Brak modelowanej miedzi na warstwie '+
                 escape(str(missing['layer_role']))+'.</p>')
    for name, reason in metadata.get('failed_planes', {}).items():
        body += '<p>Brak danych '+escape(name)+': '+escape(reason)+'</p>'
    return body+'</section>'
