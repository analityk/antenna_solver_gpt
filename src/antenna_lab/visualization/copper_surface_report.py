"""Offline copper-face diagnostic report: fields and approximate surface current only.

The face current is a near-field proxy n x H(z_face +/- offset), NOT an
exact PEC boundary-limit current, proximity loss, or skin-depth solution.
"""
import base64
from html import escape
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure

from antenna_lab.pcb.postprocess import read_json
from .report_assets import CSS


def _magnitude(phasor):
    return np.sqrt(np.sum(np.abs(phasor) ** 2, axis=0))


def _figure(record, plane, index, frequency_hz, global_scales):
    x = record['x_m'] * 1e3
    y = record['y_m'] * 1e3
    labels = (('|E|', 'V/m / 1 V port', 'E_v_per_m'),
              ('|H|', 'A/m / 1 V port', 'H_a_per_m'),
              ('|K_face, proxy|', 'A/m / 1 V port', 'K_proxy_a_per_m'))
    fig = Figure(figsize=(17, 5.1), dpi=140, constrained_layout=True)
    axes = fig.subplots(1, 3)
    for ax, (label, units, name) in zip(axes, labels):
        field = record[name][index]
        values = _magnitude(field)[:,:,0]
        # Same 0...max color range for this quantity/frequency across
        # every copper face. Do not normalize each face independently:
        # that would hide physically important differences in magnitude.
        maximum=global_scales.get((index,name),0.)
        colors = ax.pcolormesh(x, y, np.ma.masked_invalid(values).T,
                               shading='auto', cmap='inferno', vmin=0,
                               vmax=maximum if maximum>0 else 1.)
        fig.colorbar(colors, ax=ax, label=units)
        if name == 'K_proxy_a_per_m':
            kx, ky = np.real(field[0,:,:,0]), np.real(field[1,:,:,0])
            amplitude = np.hypot(kx,ky)
            valid = np.isfinite(amplitude) & (amplitude>0)
            sx = np.arange(0,len(x),max(1,len(x)//20))
            sy = np.arange(0,len(y),max(1,len(y)//12))
            gridx, gridy = np.meshgrid(x[sx], y[sy], indexing='ij')
            a = amplitude[np.ix_(sx,sy)]
            good = valid[np.ix_(sx,sy)]
            uu = np.divide(kx[np.ix_(sx,sy)],a,where=good,out=np.zeros_like(a))
            vv = np.divide(ky[np.ix_(sx,sy)],a,where=good,out=np.zeros_like(a))
            ax.quiver(gridx[good], gridy[good], uu[good], vv[good],
                      color='#22c7e9', scale=25, scale_units='inches', width=.0025)
        ax.set_title(label, fontsize=12)
        ax.set_xlabel('X [mm]')
        ax.set_ylabel('Y [mm]')
        ax.set_aspect('equal', adjustable='box')
    fig.suptitle(
        f'{plane["copper_layer_role"]} · {plane["copper_face"]} · '
        f'{frequency_hz/1e6:g} MHz · offset {plane["offset_m"]*1e6:g} µm',
        fontsize=15)
    from io import BytesIO
    buffer=BytesIO()
    fig.savefig(buffer,format='png',dpi=140)
    return buffer.getvalue()


def render_copper_surface_report(data):
    """Independent HTML: no impedance/SWR/S11 sections or interactive spectrum."""
    root = Path(data['root'])
    field_file = root / 'fields' / 'metadata.json'
    metadata = read_json(field_file) if field_file.is_file() else {}
    if metadata and metadata.get('mode') != 'copper_surfaces':
        raise ValueError('Saved fields do not match copper-surface report mode.')
    global_scales={}
    if metadata:
        for plane in metadata.get('planes',()):
            with np.load(root/'fields'/(plane['name']+'.npz'),allow_pickle=False) as record:
                for name in ('E_v_per_m','H_a_per_m','K_proxy_a_per_m'):
                    if name not in record:
                        raise ValueError(f'Missing {name} in {plane["name"]}.')
                    for i in range(len(record['frequency_hz'])):
                        values=_magnitude(record[name][i])
                        finite=values[np.isfinite(values)]
                        maximum=float(np.max(finite)) if len(finite) else 0.
                        key=(i,name)
                        global_scales[key]=max(global_scales.get(key,0.),maximum)
    panels=[]
    if not metadata:
        panels.append('<section class="panel"><p>Nie zapisano przetworzonych map '
                      'powierzchni miedzi. Brak danych to nie zero pola.</p></section>')
    else:
        for plane in metadata.get('planes',()):
            if plane.get('measurement')!='copper_surface':
                raise ValueError('Unexpected non-copper plane in surface-only report.')
            name = plane['name']
            with np.load(root / 'fields' / (name+'.npz'), allow_pickle=False) as record:
                required=('E_v_per_m','H_a_per_m','K_proxy_a_per_m','frequency_hz','mask','x_m','y_m')
                if any(k not in record for k in required):
                    raise ValueError(f'Missing copper field arrays for {name}.')
                frames=[]
                for i,f in enumerate(record['frequency_hz']):
                    png=_figure(record,plane,i,float(f),global_scales)
                    encoded=base64.b64encode(png).decode('ascii')
                    frames.append(
                        f'<details><summary>{f/1e6:g} MHz · E / H / K_face</summary>'
                        '<label>Zoom: <input class="copper-zoom" type="range" min="50" max="400" value="100" step="25"> '
                        '<output>100%</output></label>'
                        '<div class="copper-scroll" style="overflow:auto;max-height:75vh;border:1px solid #dce4ed">'
                        f'<img alt="{escape(name)} · E, H, approximate surface current" '
                        f'width="2380" style="max-width:none;height:auto" src="data:image/png;base64,{encoded}">'
                        '</div></details>')
            side='od góry' if plane['copper_face']=='top' else 'od dołu'
            panels.append(
                f'<section class="panel"><details open><summary>{escape(plane["copper_layer_role"])} — '
                f'{side}</summary><p>Z = {plane["copper_z_m"]*1e3:g} mm; '
                f'punkt pomiaru Z = {plane["actual_position_m"]*1e3:g} mm, '
                f'odległość {plane["offset_m"]*1e6:g} µm. '
                'Jedna strona warstwy, oddzielny zapis zespolony.</p>'
                + ''.join(frames) + '</details></section>')
    missing=metadata.get('failed_planes',{}) if metadata else {}
    if missing:
        panels.append('<section class="panel"><h2>Niekompletne dane</h2><p>'
                      +escape(str(missing))+'</p></section>')
    note=escape(str(data['summary'].get('note','Wynik niezweryfikowany.')))
    run=escape(str(data['run_id']))
    body=''.join(panels)
    return f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Powierzchnie miedzi · {run}</title><style>{CSS}</style>
</head><body><main>
<header><h1>Powierzchnie miedzi — E / H / prąd powierzchniowy (proxy)</h1>
<p>Przebieg: <strong>{run}</strong></p>
<p>Każda fizyczna warstwa Cu osobno: widok od góry i od dołu. Bez przekrojów pola daleko od PCB.</p></header>
<div class="status">Wynik niezweryfikowany · {note}</div>
<section class="panel"><h2>Co oznaczają mapy</h2>
<p>Kolory E/H pokazują moduł zespolonych pól (norma amplitud trzech składowych). Skale dla danej wielkości i częstotliwości są wspólne na wszystkich warstwach i stronach.
Kolor K_face oznacza |n × H| przy zapisanej odległości od powierzchni miedzi.
Strzałki to kierunek chwilowej części rzeczywistej K_face przy fazie 0°.
Pola i prądy są normalizowane do 1 V napięcia portu.</p>
<p><strong>Ograniczenie fizyczne:</strong> K_face to przybliżenie z pola H zmierzonego
10 µm od idealnej cienkiej miedzi PEC, nie graniczny prąd powierzchniowy ani
gęstość prądu w objętości metalu. Nie licz strat skin/proximity z tej mapy
bez osobnej zbieżności przestrzennej, przewodności i modelu grubości.
Zoom powiększa zapisany obraz, nie zwiększa rozdzielczości siatki FDTD.</p></section>
{body}
<footer class="footer">Zapisane pola z istniejącego FDTD. Raport offline, bez nowego rozwiązania pola.</footer>
</main><script>
document.querySelectorAll('.copper-zoom').forEach(slider => {{
  slider.addEventListener('input', () => {{
    const panel=slider.parentElement.nextElementSibling;
    panel.querySelector('img').style.width=(2380*Number(slider.value)/100)+'px';
    slider.parentElement.querySelector('output').textContent=slider.value+'%';
  }});
}});
</script></body></html>"""
