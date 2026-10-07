"""Saved drill records only: report tables, top markers and section outlines."""
from html import escape
from math import sqrt, cos, sin, pi
from matplotlib.patches import Circle

NOTE='PTH barrel model: solid PEC equivalent cylinder; plating losses and hollow barrel geometry are not modeled.'


def drill_markers(ax, geometry):
    for d in geometry.get('drills',[]):
        radius=d.get('equivalent_outer_radius_m') or d['drill_diameter_m']/2
        ax.add_patch(Circle((d['x_m']*1e3,d['y_m']*1e3),radius*1e3,
            facecolor='#cc8940' if d['plated'] else 'white',
            edgecolor='#47266e' if d['plated'] else '#223b56',linewidth=1.2,zorder=6))
        if d['plated']:
            ax.plot(d['x_m']*1e3,d['y_m']*1e3,'+',color='#47266e',markersize=4,zorder=7)


def drill_section(geometry,table):
    drills=geometry.get('drills',[])
    if not drills:return ''
    rows=[]
    for d in drills:
        rows.append((d['id'],d['source_file_role'],d['source_tool'],
            f"{d['drill_diameter_m']*1e3:g}",
            f"{d['plating_thickness_m']*1e6:g}" if d['plated'] else '—',
            ', '.join(d['connected_layer_roles']) or 'none'))
    counts=f"PTH: {sum(d['plated'] for d in drills)}; NPTH: {sum(not d['plated'] for d in drills)}"
    return '<section class="panel"><h2>Drills / vias</h2><p>'+counts+'</p>'+table(
        ['ID','Role','Tool','Diameter [mm]','Plating assumption [µm]','Connected layers'],rows)+\
        '<p>'+escape(NOTE)+'</p><p>NPTH: air cylinder, no electrical connection. Plating is an unverified physical assumption.</p></section>'


def drill_paths(geometry,plane):
    normal={'xy_air':2,'xz_feed':1,'yz_feed':0}[plane['name']]
    horizontal=0 if normal!=0 else 1
    bottom=min(d['z_min_m'] for d in geometry.get('dielectric_layers') or [geometry['substrate']])
    paths=[]
    for d in geometry.get('drills',[]):
        x,y=d['x_m'],d['y_m'];radius=d.get('equivalent_outer_radius_m') or d['drill_diameter_m']/2
        if normal==2:
            points=[[(x+radius*cos(i*pi/24))*1e3,(y+radius*sin(i*pi/24))*1e3] for i in range(49)]
        else:
            offset=(x,y)[normal]-plane['actual_position_m']
            if abs(offset)>radius:continue
            extent=sqrt(max(0,radius*radius-offset*offset));centre=(x,y)[horizontal]
            a,b=(centre-extent)*1e3,(centre+extent)*1e3
            points=[[a,0],[a,bottom*1e3],[b,bottom*1e3],[b,0],[a,0]]
        paths.append(dict(points=points,color='#793b92' if d['plated'] else '#267294'))
    return paths
