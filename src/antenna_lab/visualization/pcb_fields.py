"""PCB-specific projection/overlays and playback within the shared HTML report.

Uses shared complex loader, phase convention and PNG encoder. Display sampling
never changes saved arrays. No native modules, Gerber parsing or solver calls.
"""
from html import escape
import json

import numpy as np
from matplotlib.figure import Figure
from matplotlib.colors import SymLogNorm
from matplotlib.cm import ScalarMappable
from shapely.geometry import Polygon, LineString

from .fields import PCB_VIEWS, load_plane, phase_values


def view_fields(data, plane, index):
    normal,horizontal,vertical,e,h = PCB_VIEWS[plane['name']]
    remaining=[i for i in range(3) if i!=normal]
    def project(a):
        return np.transpose(np.squeeze(a,axis=normal),(remaining.index(vertical),remaining.index(horizontal)))
    eu,ev=(project(data['E_v_per_m'][index,c]) for c in (horizontal,vertical))
    magnetic=project(data['H_a_per_m'][index,h])
    def maximum(values):
        finite=values[np.isfinite(values)]
        return max(float(np.max(finite)) if finite.size else 0.,1e-30)
    return dict(u=data['xyz'[horizontal]+'_m']*1000,v=data['xyz'[vertical]+'_m']*1000,
        eu=eu,ev=ev,magnetic=magnetic,e_limit=maximum(abs(eu)),h_limit=maximum(abs(magnetic)),
        vector_limit=maximum(np.sqrt(abs(eu)**2+abs(ev)**2)),
        horizontal='xyz'[horizontal],vertical='xyz'[vertical],h_component='xyz'[h],
        frequency_hz=float(data['frequency_hz'][index]))


def overlays(geometry, plane):
    """XY projections; true plane intersections with planar copper in XZ/YZ."""
    normal,horizontal,vertical,*_=PCB_VIEWS[plane['name']]
    port=geometry['port'];n,p=np.asarray(port['negative_xy_m']),np.asarray(port['positive_xy_m'])
    half=port['width_m']/2;ym=(n[1]+p[1])/2
    port_polygon=[(n[0],ym-half),(p[0],ym-half),(p[0],ym+half),(n[0],ym+half)]
    shapes=[(geometry['outline']['vertices_xy_m'],'#394635')]
    shapes += [(c['vertices_xy_m'],'#725018') for c in geometry['copper']]
    shapes += [(port_polygon,'#126eaa')]
    paths=[]
    if normal==2:
        for vertices,color in shapes:
            points=[list(v) for v in vertices];points.append(points[0])
            paths.append(dict(points=(np.asarray(points)*1000).tolist(),color=color))
    else:
        position=plane['actual_position_m']
        all_vertices=np.asarray([v for vertices,_ in shapes for v in vertices])
        low,high=float(all_vertices[:,horizontal].min()),float(all_vertices[:,horizontal].max())
        line=LineString(((low,position),(high,position)) if normal==1 else ((position,low),(position,high)))
        for i,(vertices,color) in enumerate(shapes):
            cross=Polygon(vertices).intersection(line)
            parts=[cross] if cross.geom_type=='LineString' else list(getattr(cross,'geoms',()))
            for part in parts:
                if part.geom_type!='LineString' or part.is_empty:continue
                coords=np.asarray(part.coords);a,b=float(coords[:,horizontal].min()),float(coords[:,horizontal].max())
                paths.append(dict(points=[[a*1000,0.],[b*1000,0.]],color=color))
                if i==0:
                    bottom=geometry['substrate']['z_min_m']*1000
                    paths.append(dict(points=[[a*1000,0],[a*1000,bottom],[b*1000,bottom],[b*1000,0]],color='#568255'))
    return paths


def _indices(count, maximum):
    return np.unique(np.linspace(0,count-1,min(count,maximum),dtype=int))


def _spaced_indices(values, maximum):
    targets=np.linspace(values[0],values[-1],min(len(values),maximum))
    return np.unique(np.argmin(abs(np.asarray(values)[None,:]-targets[:,None]),axis=1))


def pcb_phase_figure(view, paths, plane, phases=(0,90,180,270)):
    fig=Figure(figsize=(11,3.2*len(phases)));axes=fig.subplots(len(phases),2,squeeze=False)
    norms=[SymLogNorm(linthresh=limit*.025,vmin=-limit,vmax=limit,base=10)
           for limit in (view['e_limit'],view['h_limit'])]
    labels=[f"E{view['horizontal']} [V/m per 1 V port] + E vectors",
            f"H{view['h_component']} [A/m per 1 V port]"]
    iy,ix=_spaced_indices(view['v'],16),_spaced_indices(view['u'],20)
    from matplotlib import colormaps
    cmap=colormaps['RdBu_r'].copy();cmap.set_bad('#b4bac2')
    u,v=np.meshgrid(view['u'][ix],view['v'][iy])
    for row,phase in enumerate(phases):
        for col,(field,norm) in enumerate(zip((view['eu'],view['magnetic']),norms)):
            ax=axes[row,col]
            ax.pcolormesh(view['u'],view['v'],np.ma.masked_invalid(phase_values(field,phase)),
                          cmap=cmap,norm=norm,shading='nearest',rasterized=True)
            if col==0:
                a,b=(phase_values(view[k][np.ix_(iy,ix)],phase) for k in ('eu','ev'))
                ax.quiver(u,v,a,b,angles='xy',scale_units='width',scale=view['vector_limit']*18,
                          width=.003,color='#171717')
            for path in paths:
                points=np.asarray(path['points']);ax.plot(points[:,0],points[:,1],color=path['color'],lw=.7)
            ax.set(xlim=(view['u'][0],view['u'][-1]),ylim=(view['v'][0],view['v'][-1]),
                xlabel=view['horizontal']+' [mm]',ylabel=view['vertical']+' [mm]',
                title=f"{phase}° · {phase/360/view['frequency_hz']*1e9:.4g} ns · {labels[col]}")
            ax.set_aspect('equal',adjustable='box')
    fig.suptitle(f"PCB {plane['name']} · {view['frequency_hz']/1e6:g} MHz · 1∠0 V port\n"
                'Fixed symmetric symlog scales across phases; geometric copper/source halo mask',fontsize=11)
    fig.subplots_adjust(top=.92,bottom=.09,hspace=.5,wspace=.2)
    for col in (0,1):
        cax=fig.add_axes([.13+col*.43,.035,.32,.012])
        from matplotlib.ticker import FuncFormatter
        limit=(view['e_limit'],view['h_limit'])[col]
        bar=fig.colorbar(ScalarMappable(norm=norms[col],cmap=cmap),cax=cax,orientation='horizontal',label=labels[col])
        bar.set_ticks([-limit,-limit/10,0,limit/10,limit])
        bar.ax.xaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:.3g}'))
    return fig


def viewer_payload(view,paths,phases):
    # At most 80×80 for browser display; full complex NPZ stays untouched.
    iy,ix=_indices(len(view['v']),80),_indices(len(view['u']),80)
    def parts(values):
        values=values[np.ix_(iy,ix)]
        return [np.where(np.isfinite(a),a,None).tolist() for a in (values.real,values.imag)]
    return dict(u=view['u'][ix].tolist(),v=view['v'][iy].tolist(),
        eu=parts(view['eu']),ev=parts(view['ev']),h=parts(view['magnetic']),
        e_limit=view['e_limit'],h_limit=view['h_limit'],vector_limit=view['vector_limit'],
        frequency_hz=view['frequency_hz'],horizontal=view['horizontal'],vertical=view['vertical'],
        h_component=view['h_component'],paths=paths,phases=phases,
        display_sampling='deterministic index subset, at most 80 per axis; NPZ unchanged')


PLAYBACK_JS = r"""
(()=>{document.querySelectorAll('.pcb-field-player').forEach(player=>{
 const d=JSON.parse(player.querySelector('.pcb-field-data').textContent);
 const slider=player.querySelector('input'), button=player.querySelector('button'), label=player.querySelector('output');
 const canvases=player.querySelectorAll('canvas');let timer=null;
 const instant=(part,j,i,phase)=>part[0][j][i]===null||part[1][j][i]===null?null:part[0][j][i]*Math.cos(phase)-part[1][j][i]*Math.sin(phase);
 function draw(){const degrees=d.phases[Number(slider.value)],phase=degrees*Math.PI/180;
 label.textContent=degrees+'° · '+(degrees/360/d.frequency_hz*1e9).toFixed(5)+' ns';
 canvases.forEach((canvas,col)=>{const ctx=canvas.getContext('2d'),left=54,top=30,scale=Math.min(490/(d.u.at(-1)-d.u[0]),350/(d.v.at(-1)-d.v[0])),w=(d.u.at(-1)-d.u[0])*scale,h=(d.v.at(-1)-d.v[0])*scale;
 ctx.clearRect(0,0,580,440);ctx.fillStyle='#b4bac2';ctx.fillRect(left,top,w,h);
 const x=v=>left+(v-d.u[0])/(d.u.at(-1)-d.u[0])*w,y=v=>top+h-(v-d.v[0])/(d.v.at(-1)-d.v[0])*h;
 const values=col===0?d.eu:d.h,limit=col===0?d.e_limit:d.h_limit;
 for(let j=0;j<d.v.length;j++)for(let i=0;i<d.u.length;i++){
 const val=instant(values,j,i,phase);if(val===null)continue;
 const ratio=Math.abs(val)/(limit*.025),linear=1/0.9;
 const strength=Math.min(1,(ratio<=1?ratio*linear:linear+Math.log10(ratio))/(linear+Math.log10(40)));
 const tint=Math.round(255*(1-strength));ctx.fillStyle=val<0?`rgb(${tint},${tint},255)`:`rgb(255,${tint},${tint})`;
 const a=i? (d.u[i-1]+d.u[i])/2:d.u[0],b=i+1<d.u.length?(d.u[i]+d.u[i+1])/2:d.u.at(-1);
 const c=j? (d.v[j-1]+d.v[j])/2:d.v[0],e=j+1<d.v.length?(d.v[j]+d.v[j+1])/2:d.v.at(-1);
 ctx.fillRect(x(a),y(e),x(b)-x(a)+.5,y(c)-y(e)+.5);}
 if(col===0){ctx.strokeStyle='#111';ctx.lineWidth=1;
 const spaced=(a,n)=>[...new Set(Array.from({length:Math.min(n,a.length)},(_,k)=>{const target=a[0]+(a.at(-1)-a[0])*k/(Math.min(n,a.length)-1);return a.reduce((best,v,i)=>Math.abs(v-target)<Math.abs(a[best]-target)?i:best,0);}))];
 for(const j of spaced(d.v,14))for(const i of spaced(d.u,18)){const eu=instant(d.eu,j,i,phase),ev=instant(d.ev,j,i,phase);
 if(eu===null||ev===null)continue;const dx=eu/d.vector_limit*24,dy=-ev/d.vector_limit*24,px=x(d.u[i]),py=y(d.v[j]);
 if(Math.hypot(dx,dy)<.3)continue;const angle=Math.atan2(dy,dx);ctx.beginPath();ctx.moveTo(px,py);ctx.lineTo(px+dx,py+dy);
 ctx.moveTo(px+dx-4*Math.cos(angle-.5),py+dy-4*Math.sin(angle-.5));ctx.lineTo(px+dx,py+dy);ctx.lineTo(px+dx-4*Math.cos(angle+.5),py+dy-4*Math.sin(angle+.5));ctx.stroke();}}
 d.paths.forEach(path=>{ctx.strokeStyle=path.color;ctx.lineWidth=1;ctx.beginPath();path.points.forEach((p,i)=>i?ctx.lineTo(x(p[0]),y(p[1])):ctx.moveTo(x(p[0]),y(p[1])));ctx.stroke();});
 ctx.strokeStyle='#333';ctx.strokeRect(left,top,w,h);ctx.fillStyle='#111';ctx.font='13px sans-serif';
 ctx.fillText(col===0?'E'+d.horizontal+' [V/m per 1 V port] + E vectors':'H'+d.h_component+' [A/m per 1 V port]',left,19);
 ctx.fillText(d.horizontal+' [mm]: '+d.u[0].toPrecision(4)+' … '+d.u.at(-1).toPrecision(4),left,403);
 ctx.fillText(d.vertical+' [mm]: '+d.v[0].toPrecision(4)+' … '+d.v.at(-1).toPrecision(4),left,421);
 ctx.fillText('Fixed scale: ±'+limit.toExponential(3)+' · blue − / red +',left,437);
 });}
 slider.addEventListener('input',draw);button.addEventListener('click',()=>{if(timer){clearInterval(timer);timer=null;button.textContent='Play';}
 else{button.textContent='Pause';timer=setInterval(()=>{slider.value=(Number(slider.value)+1)%d.phases.length;draw();},160);}});
 draw();});})();
"""


def pcb_field_section(data, metadata, figure_image, plots_path, phase_step):
    if metadata.get('reference_voltage_v')!=1. or metadata.get('array_order')!='frequency,component_xyz,x,y,z':
        raise ValueError('Nieobsługiwane metadane pól PCB (wymagane odniesienie 1 V).')
    phases=list(range(0,360,phase_step or 30))
    body='<section class="panel"><h2>Pola E/H — przebieg jednego okresu</h2>'
    body+='<p>Stan harmoniczny Re(F·exp(+j·faza)); faza 0° = dodatnie maksimum napięcia portu. Odniesienie 1∠0 V portu, nie moc przyjęta. E: V/m per 1 V port; H: A/m per 1 V port. Strzałki pokazują chwilowy wektor E w przekroju; kolory podpisaną składową. Stałe symetryczne skale symlog we wszystkich fazach. Szary: konserwatywna maska geometrii copper/portu i halo jednej lokalnej komórki, nie natywna zajętość Yee. Laminat nie jest maskowany.</p>'
    body+='<p>Odtwarzanie nie uruchamia FDTD. Płaszczyzny pochodzą z istniejącej siatki, poza PML. Widok przeglądarki jest próbkowany najwyżej 80×80, strzałki dodatkowo rozrzedzone; zapis NPZ zachowuje wszystkie próbki i składowe.</p>'
    for plane in metadata['planes']:
        if plane['name'] not in PCB_VIEWS:raise ValueError('Nieznana płaszczyzna PCB E/H.')
        fields=load_plane(data['root']/'fields'/(plane['name']+'.npz'),plane,metadata['frequency_hz'])
        paths=overlays(data['geometry'],plane)
        for i,f in enumerate(fields['frequency_hz']):
            view=view_fields(fields,plane,i);payload=viewer_payload(view,paths,phases)
            encoded=json.dumps(payload,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
            title=f"{plane['name']} · {f/1e6:g} MHz"
            body+=f'<details open><summary>{escape(title)}</summary><p>{escape(plane["requested_policy"])}: żądane {plane["requested_position_m"]*1e3:g} mm; rzeczywiste {plane["actual_position_m"]*1e3:g} mm.</p>'
            body+='<div class="pcb-field-player"><button type="button">Play</button> <output></output><label>Faza <input type="range" min="0" max="'+str(len(phases)-1)+'" step="1" value="0"></label>'
            body+='<div style="display:flex;flex-wrap:wrap"><canvas width="580" height="440" style="max-width:100%;height:auto"></canvas><canvas width="580" height="440" style="max-width:100%;height:auto"></canvas></div>'
            body+='<script type="application/json" class="pcb-field-data">'+encoded+'</script></div>'
            fig=pcb_phase_figure(view,paths,plane)
            path=plots_path/f'fields_{plane["name"]}_{i}.png' if plots_path else None
            body+='<details><summary>Diagram 0°, 90°, 180°, 270° (bez JavaScript)</summary>'+figure_image(fig,title,path)+'</details></details>'
            fig.clear()
    return body+'</section><script>'+PLAYBACK_JS+'</script>'
