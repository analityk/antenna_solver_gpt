"""Read-only visualisation of unverified PCB sheet-current estimates.

Native rot(H) data and full-resolution complex NPZ remain immutable.
The plot is quantitative in nominal units, but validation is NOT implied.
"""
from html import escape

import numpy as np


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


def current_contrast_scale(data, index, percentile=99.5):
    """Presentation-only robust local scale on physical copper samples."""
    magnitude = _magnitude(data['k'][index])[data['on_copper']]
    if magnitude.size == 0 or not np.isfinite(magnitude).all():
        raise ValueError('Brak skończonych próbek prądu na miedzi.')
    positive = magnitude[magnitude > 0]
    peak = float(magnitude.max())
    if not positive.size:
        return dict(has_signal=False, scale=1.0, floor=0.0,
                    actual_peak=0.0, clipped=0, count=int(magnitude.size))
    local = float(np.percentile(positive, percentile))
    if local <= 0 or not np.isfinite(local):
        raise ValueError('Błędny percentyl prądu.')
    return dict(has_signal=True, scale=local, floor=local * 0.001,
                actual_peak=peak, clipped=int((magnitude > local).sum()),
                count=int(magnitude.size))


def pcb_current_section(data, figure_image, plots_path):
    """One collapsible GIF per modeled copper layer and frequency.

    The figure_image argument is kept for the existing report hook;
    GIF encoding is handled by the current-frame module instead.
    """
    from antenna_lab.pcb.postprocess import read_json
    from .pcb_current_frames import gif_phase_image, PHASES_DEG

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

    body = ('<section class="panel"><h2>Gęstość prądu na miedzi — animacja GIF</h2>'
            '<p><strong>Wynik niezweryfikowany ilościowo.</strong> '
            'Estymata K pochodzi z rot(H) na modelowanej miedzi '
            'pomnożonego przez szerokość komórki dualnej Yee. '
            'Nie przedstawia osobno obu stron folii, strat AC ani '
            'rozkładu objętościowego J.</p>'
            '<p><strong>Tylko kontrast lokalny.</strong> '
            'Każdy GIF przedstawia 24 fazy (0°–345° co 15°). '
            'Kolor to moduł chwilowego wektora '
            '|K(t)| = |Re(K · exp(jφ))|, a strzałki wskazują kierunek. '
            'Skala logarytmiczna jest stała przez cały cykl dla danej '
            'warstwy i częstotliwości, wyznaczona z percentyla p99,5 '
            'dodatnich wartości obwiedni zespolonej. '
            'Wartości powyżej limitu są nasycone kolorem. '
            'Jasności NIE są porównywalne między warstwami '
            'ani częstotliwościami. '
            'Normalizacja: 1∠0 V na porcie; nie 1 W. '
            'Każda animacja jest osadzona w zwijanej sekcji HTML. '
            'Zachowano surowe NPZ/HDF5, bez powtórnego FDTD.</p>')
    if not records:
        body += '<p>Brak danych dla obsadzonych warstw miedzi.</p>'
    for layer_idx, (plane, record) in enumerate(records):
        for index, frequency in enumerate(frequencies):
            label = f"{plane['layer_role']} · {frequency/1e6:g} MHz"
            stats = current_contrast_scale(record, index)
            body += ('<details' +
                     (' open' if layer_idx == 0 and index == 0 else '') +
                     '><summary>Kontrast lokalny · ' + escape(label) +
                     ' (GIF, 24 klatki po 15°)</summary>'
                     '<p>Maksimum modułu fazora: ' +
                     f"{stats['actual_peak']:.6g}" +
                     ' A/m / 1 V; stały próg kontrastu p99,5: ' +
                     f"{stats['scale']:.6g}" +
                     ' A/m / 1 V. Statystyka dotyczy obwiedni zespolonej, '
                     'nie chwilowej klatki.</p>')
            body += gif_phase_image(
                record, data['geometry'], plane, index, stats, plots_path)
            body += '</details>'
    for missing in metadata.get('empty_layers', ()):
        body += ('<p>Brak modelowanej miedzi na warstwie ' +
                 escape(str(missing['layer_role'])) + '.</p>')
    for name, reason in metadata.get('failed_planes', {}).items():
        body += '<p>Brak danych ' + escape(name) + ': ' + escape(reason) + '</p>'
    return body + '</section>'
