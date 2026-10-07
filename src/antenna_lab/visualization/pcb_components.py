"""Ideal-component tables and overlays from detached saved geometry only."""
from html import escape
from antenna_lab.pcb.components import IDEAL_NOTE


def component_section(data, table):
    geometry=data['geometry'];source=geometry.get('source_port');components=geometry.get('components',[])
    if not source and not components:return ''
    rows=[]
    if source:
        rows.append((source['source_refdes'],'SOURCE',f"{data['reference']:g}-ohm reference port",
                     *source['source_pin_nets'],'top','planar lumped port','ENET + FlyingProbe'))
    for c in components:
        rows.append((c['id'],c['kind'],c['value_text'],c['pin1_net'],c['pin2_net'],c['layer'],
                     'ideal lumped '+c['kind'],'ENET props.Value + FlyingProbe'))
    return ('<section class="panel"><h2>Ideal components</h2>'+table(
        ['Refdes','Type','Ideal value','Net 1','Net 2','Layer','Model','Source'],rows)+\
        '<p>'+escape(IDEAL_NOTE)+'</p><p>Region solvera: istniejąca komórka w powietrzu nad z=0; '
        'PEC end caps zapewniają kontakt z płaskimi padami. Bez geometrii obudowy i dodatkowych kotwic Z.</p></section>')


def component_markers(ax,geometry):
    for c in geometry.get('components',[]):
        a,b=c['gap_start_xy_m'],c['gap_stop_xy_m']
        ax.plot([a[0]*1e3,b[0]*1e3],[a[1]*1e3,b[1]*1e3],'-s',color='#be2366',lw=2,markersize=3,zorder=8)
        ax.annotate(c['id'],((a[0]+b[0])*500,(a[1]+b[1])*500),xytext=(4,4),
                    textcoords='offset points',fontsize=8,color='#8e174c',zorder=9)


def component_paths(geometry,plane,regions=()):
    normal={'xy_air':2,'xz_feed':1,'yz_feed':0}[plane['name']]
    horizontal=0 if normal!=0 else 1;paths=[]
    if normal==2:
        for c in geometry.get('components',[]):
            paths.append(dict(points=[[v*1e3 for v in p] for p in
                (c['gap_start_xy_m'],c['gap_stop_xy_m'])],color='#be2366'))
    else:
        position=plane['actual_position_m']
        for r in regions:
            a,b=r['start_m'],r['stop_m']
            if not a[normal]<=position<=b[normal]:continue
            x0,x1=a[horizontal]*1e3,b[horizontal]*1e3;z0,z1=a[2]*1e3,b[2]*1e3
            paths.append(dict(points=[[x0,z0],[x1,z0],[x1,z1],[x0,z1],[x0,z0]],color='#be2366'))
    return paths
