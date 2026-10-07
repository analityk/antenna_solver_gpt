"""Offline PCB stack table and symbolic sheet cross section from saved metadata."""
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle


def stackup_section(data, plots_path, figure_image, table):
    stack = data['summary'].get('resolved_stackup') or data['summary'].get('preparation', {}).get('geometry', {}).get('resolved_stackup')
    if not stack:
        return ''
    rows = []
    fig = Figure(figsize=(10, 4.8)); ax = fig.subplots()
    colors = ('#e9dca9', '#b6d5c7', '#c4d4e7')
    index = 0
    for layer in stack['layers']:
        if layer['type'] == 'dielectric':
            top, bottom = layer['z_max_m']*1e3, layer['z_min_m']*1e3
            rows.append((layer['name'], 'dielectric', f'{top:g}', f'{bottom:g}',
                f"{layer['thickness_m']*1e3:g} mm", layer['epsilon_r'], layer['loss_tangent'], '—', '—'))
            ax.add_patch(Rectangle((0, bottom), 1, top-bottom, facecolor=colors[index % len(colors)], edgecolor='none'))
            ax.text(.5, (top+bottom)/2, f"{layer['name']} · {layer['thickness_m']*1e3:g} mm", ha='center', va='center', fontsize=9)
            index += 1
        else:
            z = layer['z_m']*1e3
            rows.append((layer['role'], 'copper sheet', f'{z:g}', f'{z:g}',
                f"{layer['thickness_m']*1e6:g} µm (material)", '—', '—', layer['model'],
                f"{layer['conductivity_s_m']/1e6:g} MS/m"))
            ax.plot([0, 1], [z, z], color='#ad6627', lw=2)
            ax.text(1.04, z, f"{layer['role']} · z={z:g} mm", va='center', fontsize=9)
    total = stack['total_dielectric_thickness_m']*1e3
    ax.set(xlim=(-.05,1.8), ylim=(-total*1.12,total*.12), ylabel='z [mm]',
        title='Stackup · copper sheets drawn symbolically, thickness not to scale')
    ax.set_xticks([]); ax.grid(axis='y', alpha=.2); fig.tight_layout()
    body = table(['Role/name','Type','Z top [mm]','Z bottom [mm]','Thickness','epsilon_r','loss tangent','Copper model','Conductivity'], rows)
    body += f'<p>Łączna grubość dielektryków: {total:g} mm. Miedź przedstawiono symbolicznie; grubość conducting sheet jest parametrem materiału, bez objętości geometrycznej.</p>'
    body += figure_image(fig, 'Stackup: symboliczna miedź, wymiary dielektryków w mm', plots_path/'stackup.png' if plots_path else None)
    body += '<p>Dla PEC grubość i przewodność są zapisanymi założeniami, nie są używane przez solver.</p>'
    body += '<p>Vias/drills i soldermask oraz chropowatość: nie są modelowane. Brak plików wierceń nie oznacza kompletności fizycznej modelu. Wyniki unverified.</p>'
    fig.clear()
    return '<section class="panel"><h2>Stackup</h2>'+body+'</section>'
