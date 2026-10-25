"""Offline PNG phase playback for existing complex PCB sheet-current estimates.

Viewer only: does not rescale or modify the complex NPZ/HDF5 source data.
"""
import math
from pathlib import Path

import numpy as np
from matplotlib import colormaps
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LogNorm, Normalize
from matplotlib.figure import Figure
from shapely.geometry import Polygon

PHASE_STEP_DEG = 15
PHASES_DEG = tuple(range(0, 360, PHASE_STEP_DEG))


# The viewer selects pre-rendered PNGs. No field calculations in JavaScript.
# All layer/frequency players run independently in the standalone HTML.
PLAYER_JS = """<script>
(()=>{
 document.querySelectorAll('.pcb-current-player').forEach(player=>{
  const frames=Array.from(player.querySelectorAll('.pcb-current-frame'));
  const slider=player.querySelector('.pcb-current-slider');
  const output=player.querySelector('.pcb-current-phase');
  const button=player.querySelector('.pcb-current-play');
  let interval=null;
  const update=()=>{
   const idx=Number(slider.value);
   frames.forEach((frame,i)=>{frame.hidden=i!==idx;});
   output.textContent=String(idx*15)+'°';
  };
  const stop=()=>{
   if(interval!==null)clearInterval(interval);
   interval=null;button.textContent='Play';
  };
  slider.addEventListener('input',update);
  button.addEventListener('click',()=>{
   if(interval!==null){stop();return;}
   button.textContent='Pause';
   interval=setInterval(()=>{
    slider.value=String((Number(slider.value)+1)%frames.length);
    update();
   },220);
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
  update();
 });
})();
</script>"""


def current_at_phase(k, degrees):
    """Real phasor snapshot, (2, X, Y), and instantaneous vector modulus."""
    radians = math.radians(degrees)
    instantaneous = k.real * math.cos(radians) - k.imag * math.sin(radians)
    magnitude = np.hypot(instantaneous[0], instantaneous[1])
    return instantaneous, magnitude


def layer_outlines(geometry, plane):
    """Source copper boundary polylines in millimetres, including holes."""
    lines = []
    for copper in geometry['copper']:
        if copper['layer_role'] != plane['layer_role'] or abs(copper['z_m'] - plane['z_m']) > 1e-12:
            continue
        shape = Polygon(copper['vertices_xy_m'], copper.get('holes_xy_m', ()))
        if shape.is_empty:
            continue
        for ring in (shape.exterior, *shape.interiors):
            lines.append(np.asarray(ring.coords) * 1000)
    return lines


def frame_figure(data, plane, index, degrees, contrast, outlines):
    """One true PNG frame; fixed layer/frequency log scale for all phases."""
    x, y = data['x_m'] * 1000, data['y_m'] * 1000
    k = data['k'][index]
    instant, magnitude = current_at_phase(k, degrees)
    metal = data['on_copper']
    fig = Figure(figsize=(7.8, 4.1), layout='constrained')
    ax = fig.subplots()
    cmap = colormaps['viridis'].with_extremes(bad='#d2d5db')
    if contrast['has_signal']:
        norm = LogNorm(vmin=contrast['floor'], vmax=contrast['scale'], clip=True)
        displayed = np.ma.array(
            np.maximum(np.nan_to_num(magnitude, nan=0.0), contrast['floor']).T,
            mask=~metal.T)
    else:
        norm = Normalize(vmin=0, vmax=1)
        displayed = np.ma.array(np.nan_to_num(magnitude, nan=0).T, mask=~metal.T)
    ax.pcolormesh(x, y, displayed, norm=norm, cmap=cmap,
                  shading='nearest', rasterized=True)
    for line in outlines:
        ax.plot(line[:, 0], line[:, 1], color='#242424', linewidth=0.55)
    # Sample only on copper; a sparse uniform XY grid misses narrow traces.
    positions = np.argwhere(metal)
    chosen = positions[np.linspace(0, len(positions) - 1,
                                   min(180, len(positions)), dtype=int)]
    ii, jj = chosen[:, 0], chosen[:, 1]
    ax.quiver(x[ii], y[jj], instant[0, ii, jj], instant[1, ii, jj],
              color='#111111', angles='xy', scale_units='width',
              scale=max(contrast['scale'], 1e-30) * 26, width=0.0028)
    ax.set(xlabel='X [mm]', ylabel='Y [mm]')
    ax.set_aspect('equal', adjustable='box')
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax,
                 label='|K(t)| = |Re(K exp(jφ))| [A/m / 1 V port]')
    fig.suptitle(f"{plane['layer_role']} · {data['frequency_hz'][index]/1e6:g} MHz"
                 f" · faza {degrees}° · kontrast lokalny (p99,5) · UNVERIFIED")
    return fig


def png_phase_player(data, geometry, plane, index, contrast, figure_image, plots_path=None):
    """Generate self-contained PNG frames with Play/Pause and 15° slider."""
    if not data['on_copper'].any():
        raise ValueError('Cannot animate a PCB layer with no copper samples.')
    base = f"current_phase_{plane['name']}_{index:02d}"
    outlines = layer_outlines(geometry, plane)
    label = f"{plane['layer_role']} · {data['frequency_hz'][index]/1e6:g} MHz"
    result = ['<div class="pcb-current-player">',
              '<div class="controls">'
              '<button type="button" class="pcb-current-play">Play</button>'
              '<label>Faza [°] <input type="range" class="pcb-current-slider"'
              ' min="0" max="23" step="1" value="0"></label>'
              '<output class="pcb-current-phase">0°</output></div>']
    for n, phase in enumerate(PHASES_DEG):
        fig = frame_figure(data, plane, index, phase, contrast, outlines)
        target = Path(plots_path) / f'{base}_{phase:03d}.png' if plots_path else None
        picture = figure_image(fig, f'{label}, {phase}°', target)
        fig.clear()
        result.append('<div class="pcb-current-frame"' +
                      (' hidden' if n else '') + '>' + picture + '</div>')
    result.append('</div>')
    return ''.join(result)


PLAYER_CSS = """<style>
.pcb-current-frame[hidden]{display:none!important}
.pcb-current-player{margin:12px 0}
.pcb-current-player img{display:block;width:100%;height:auto}
.pcb-current-phase{font-weight:700;min-width:4em}
</style>"""
