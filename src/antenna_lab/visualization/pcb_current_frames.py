"""Offline GIF playback for existing complex PCB sheet-current estimates.

24 phases at 15-degree intervals; one self-contained GIF per copper plane
and frequency, embedded in a native collapsible HTML details element.
Viewer only: the complex NPZ/HDF5 and the FDTD solver remain untouched.
"""
import base64
from io import BytesIO
import math
from html import escape
from pathlib import Path

import numpy as np
from matplotlib import colormaps
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LogNorm, Normalize
from matplotlib.figure import Figure
from PIL import Image
from shapely.geometry import Polygon

PHASE_STEP_DEG = 15
PHASES_DEG = tuple(range(0, 360, PHASE_STEP_DEG))


GIF_DURATION_MS = 180  # 24 frames per cycle; fixed phase step of 15 degrees


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


def _fixed_gif_palette():
    """Fixed Viridis + neutral palette: no recolouring/flicker between phases."""
    viridis = np.rint(
        colormaps['viridis'](np.linspace(0, 1, 192))[:, :3] * 255
    ).astype(np.uint8)
    neutral = np.rint(
        np.linspace(0, 255, 60)[:, None] * np.ones((1, 3))
    ).astype(np.uint8)
    extras = np.asarray([(210, 213, 219), (36, 36, 36),
                         (17, 17, 17), (255, 255, 255)], dtype=np.uint8)
    colors = np.concatenate((viridis, neutral, extras), axis=0)
    assert colors.shape == (256, 3)
    palette = Image.new('P', (1, 1))
    palette.putpalette(colors.ravel().tolist())
    return palette


def gif_current_bytes(data, geometry, plane, index, contrast):
    """Return one looping GIF made from 24 unchanged phase evaluations.

    The fixed colour scale is computed separately (once per plane/frequency)
    and held constant for all phases. This is display-only; no EM solver run.
    """
    if not data['on_copper'].any():
        raise ValueError('Cannot animate a PCB layer without copper samples.')
    outlines = layer_outlines(geometry, plane)
    palette = _fixed_gif_palette()
    frames = []
    for degrees in PHASES_DEG:
        fig = frame_figure(data, plane, index, degrees, contrast, outlines)
        png = BytesIO()
        try:
            # Constant canvas dimensions; avoid bbox_inches='tight' per frame.
            fig.savefig(png, format='png', dpi=105, facecolor='white')
        finally:
            fig.clear()
        png.seek(0)
        with Image.open(png) as source:
            rgb = source.convert('RGB')
            frame = rgb.quantize(palette=palette, dither=Image.Dither.NONE)
            frames.append(frame.copy())
    output = BytesIO()
    frames[0].save(
        output, format='GIF', save_all=True, append_images=frames[1:],
        loop=0, duration=GIF_DURATION_MS, disposal=2, optimize=False)
    return output.getvalue()


def gif_phase_image(data, geometry, plane, index, contrast, plots_path=None):
    """Inline self-contained GIF; optional output copy in automatic plot dir."""
    image = gif_current_bytes(data, geometry, plane, index, contrast)
    if not image.startswith((b'GIF87a', b'GIF89a')):
        raise ValueError('Copper current animation was not encoded as GIF.')
    if plots_path is not None:
        destination = Path(plots_path) / (
            f"current_phase_{plane['name']}_{index:02d}.gif")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(image)
    title = (f"{plane['layer_role']} · "
             f"{data['frequency_hz'][index]/1e6:g} MHz · "
             "24 fazy po 15°")
    embedded = base64.b64encode(image).decode('ascii')
    return (f'<img alt="{escape(title, quote=True)}" '
            'style="max-width:100%;height:auto;display:block" '
            f'src="data:image/gif;base64,{embedded}">')
