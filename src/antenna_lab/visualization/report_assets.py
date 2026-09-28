"""Inline assets: a report is a single offline HTML, with no CDN or server."""

CSS = """
:root{color-scheme:light;--ink:#192b3e;--muted:#53677c;--line:#dce4ed;--blue:#126eaa;--orange:#bd5910}
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:var(--ink);font:16px/1.55 'Segoe UI',system-ui,sans-serif}
main{max-width:1180px;margin:34px auto;padding:0 24px 40px}h1{font-size:32px;line-height:1.2;margin:10px 0}
h2{font-size:23px;margin:0 0 13px}h3{font-size:18px;margin:18px 0 8px}p{margin:10px 0}
.eyebrow{color:var(--blue);font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.muted,small,figcaption{color:var(--muted)}.run{overflow-wrap:anywhere}.panel{background:white;border:1px solid var(--line);border-radius:14px;padding:23px;margin:20px 0}
.status{background:#fff5e5;border:1px solid #edcd91;border-radius:10px;padding:15px 18px;margin:18px 0}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}
.metric{border:1px solid var(--line);background:#f7faff;padding:15px;border-radius:10px}
.metric span{display:block;color:var(--muted);font-size:13px}.metric strong{display:block;font-size:25px;line-height:1.3;margin:5px 0;font-variant-numeric:tabular-nums}
.controls{display:flex;align-items:end;gap:14px;flex-wrap:wrap;margin:18px 0}.controls label{display:flex;flex-direction:column;gap:4px;font-size:13px}
input,select,button{font:inherit;border:1px solid #acbed0;border-radius:7px;padding:8px 10px;background:white;color:var(--ink)}
button{cursor:pointer;background:#edf5fc;font-size:14px}button:hover{border-color:var(--blue)}button:disabled{opacity:.5;cursor:default}
input[type=number]{width:155px}input[type=range]{padding:0;width:100%;accent-color:var(--blue)}
:focus-visible{outline:3px solid #76b9e8;outline-offset:2px}.slider-label{display:block;margin:12px 0}
.plots{display:grid;grid-template-columns:1fr 1fr;gap:18px}.plot svg{width:100%;height:auto;display:block;cursor:crosshair}
.plot{min-width:0}.legend{font-size:13px;color:var(--muted)}.blue{color:var(--blue)}.orange{color:var(--orange)}
img{max-width:100%;height:auto}figure{margin:18px 0}figcaption{font-size:13px;margin-top:6px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0}th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}
th{background:#f3f7fb}th:first-child,td:first-child{text-align:left}.table-wrap{overflow-x:auto}code{font-size:13px;overflow-wrap:anywhere}
ul{padding-left:23px}li{margin:7px 0}details{margin:14px 0}summary{cursor:pointer;font-weight:600}
.interactive{display:none}body.ready .interactive{display:block}body.ready .fallback{display:none}
.fixed{border-left:4px solid var(--blue);padding-left:14px}.meta{display:grid;grid-template-columns:1fr 1fr;gap:5px 25px}
.meta div{overflow-wrap:anywhere}.footer{font-size:12px;overflow-wrap:anywhere;color:var(--muted)}
@media(max-width:760px){main{padding:0 13px}.panel{padding:16px}.metrics{grid-template-columns:1fr 1fr}.plots,.meta{grid-template-columns:1fr}h1{font-size:26px}.metric strong{font-size:22px}}
@media print{body{background:white;font-size:11px}main{max-width:none;padding:0;margin:0}.panel{break-inside:avoid;padding:12px}.interactive,body.ready .interactive{display:none!important}body.ready .fallback{display:block}details{display:block}.status{border-color:#999}.metric strong{font-size:20px}}
"""

JS = r"""
(() => {
  'use strict';
  const D = JSON.parse(document.getElementById('report-data').textContent);
  const $ = id => document.getElementById(id);
  const f = D.frequency_mhz, r = D.r, x = D.x;
  let reference = D.reference, index = nearest(D.target_mhz);
  const fmt = (v, digits=3) => Number.isFinite(v) ? v.toLocaleString('pl-PL', {maximumFractionDigits:digits,minimumFractionDigits:digits}) : v === Infinity ? '∞' : v === -Infinity ? '−∞' : '—';
  function nearest(value) {
    let best = 0;
    for (let i=1; i<f.length; i++) if (Math.abs(f[i]-value)<Math.abs(f[best]-value)) best=i;
    return best;
  }
  function sample(i) {
    const denominator = (r[i]+reference)**2 + x[i]**2;
    const rho2 = denominator > 0 ? ((r[i]-reference)**2 + x[i]**2)/denominator : NaN;
    const passive = r[i] > 0 && Number.isFinite(rho2) && rho2 < 1;
    const rho = Math.sqrt(rho2);
    return {rho2, swr:passive ? (1+rho)/(1-rho) : NaN,
            s11:rho2===0 ? -Infinity : 10*Math.log10(rho2),
            loss:passive ? -10*Math.log10(1-rho2) : NaN};
  }
  const W=550,H=280,L=66,R=18,T=20,B=46;
  const lo=f.length>1 ? f[0] : f[0]-.5, hi=f.length>1 ? f[f.length-1] : f[0]+.5;
  const px=v=>L+(v-lo)/(hi-lo)*(W-L-R);
  function plot(id, series, ymin, ymax, unit, clip=false) {
    const py=v=>H-B-(v-ymin)/(ymax-ymin)*(H-B-T);
    let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${unit}; kliknij, aby wybrać częstotliwość">`;
    s+=`<defs><clipPath id="clip-${id}"><rect x="${L}" y="${T}" width="${W-L-R}" height="${H-B-T}"/></clipPath></defs>`;
    if (id==='swr-plot') s+=`<rect x="${L}" y="${py(2)}" width="${W-L-R}" height="${py(1)-py(2)}" fill="#e9f6ed"/>`;
    for(let k=0;k<=4;k++) {
      const y=ymin+(ymax-ymin)*k/4, yy=py(y), fx=lo+(hi-lo)*k/4, xx=px(fx);
      s+=`<path d="M${L} ${yy}H${W-R}" stroke="#e1e8ef"/><text x="${L-8}" y="${yy+4}" text-anchor="end" font-size="11" fill="#53677c">${fmt(y,1)}</text>`;
      s+=`<text x="${xx}" y="${H-B+21}" text-anchor="middle" font-size="11" fill="#53677c">${fmt(fx,1)}</text>`;
    }
    s+=`<g clip-path="url(#clip-${id})">`;
    for(const [values,color] of series) {
      let path='',pen=false;
      for(let i=0;i<values.length;i++) {
        const value=values[i];
        if(!Number.isFinite(value)){pen=false;continue;}
        path+=(pen?' L':' M')+px(f[i]).toFixed(2)+' '+py(value).toFixed(2);pen=true;
      }
      s+=`<path d="${path}" stroke="${color}" fill="none" stroke-width="2"/>`;
      if(Number.isFinite(values[index])) s+=`<circle cx="${px(f[index])}" cy="${py(values[index])}" r="4" fill="${color}"/>`;
    }
    if(D.target_mhz>=lo&&D.target_mhz<=hi) s+=`<path d="M${px(D.target_mhz)} ${T}V${H-B}" stroke="#8093a5" stroke-dasharray="3 4"/>`;
    s+=`<path d="M${px(f[index])} ${T}V${H-B}" stroke="#28394b" stroke-dasharray="5 4"/></g>`;
    s+=`<text x="${L}" y="13" font-size="11" fill="#53677c">${unit}${clip?' · skala ograniczona':''}</text><text x="${W/2}" y="${H-3}" text-anchor="middle" font-size="12" fill="#53677c">Częstotliwość [MHz]</text></svg>`;
    $(id).innerHTML=s;
    $(id).firstElementChild.addEventListener('click',event=>{
      const rect=event.currentTarget.getBoundingClientRect();
      const xsvg=(event.clientX-rect.left)/rect.width*W;
      index=nearest(lo+Math.max(0,Math.min(1,(xsvg-L)/(W-L-R)))*(hi-lo));update();
    });
  }
  function update() {
    const v=sample(index), all=f.map((_,i)=>sample(i).swr);
    let best=null;
    for(let i=0;i<all.length;i++) if(Number.isFinite(all[i])&&(best===null||all[i]<all[best])) best=i;
    $('frequency').value=Number(f[index].toFixed(6)); $('slider').value=index;
    $('selected').textContent=`${fmt(f[index],3)} MHz · Zref = ${fmt(reference,0)} Ω`;
    $('resistance').textContent=fmt(r[index])+' Ω';$('reactance').textContent=(x[index]>=0?'+':'')+fmt(x[index])+' Ω';
    $('swr').textContent=fmt(v.swr);$('s11').textContent=fmt(v.s11,2)+' dB';
    $('mismatch').textContent=`Moc odbita: ${fmt(v.rho2*100,2)}%. Strata niedopasowania: ${fmt(v.loss,3)} dB. Zmiana Zref przelicza dopasowanie; nie dodaje baluna ani transformatora.`;
    $('best').disabled=best===null;
    $('best-info').textContent=best===null?'Brak pasywnego punktu z poprawnym SWR.':`Najmniejszy SWR w zapisanych próbkach: ${fmt(all[best])} przy ${fmt(f[best],3)} MHz.`+(f.length===1?' Dostępna tylko jedna częstotliwość.':best===0||best===f.length-1?' Minimum leży na brzegu zakresu; rezonans może być poza nim.':'');
    let low=0,high=0; for(const value of [...r,...x]){low=Math.min(low,value);high=Math.max(high,value);}
    const pad=Math.max((high-low)*.1,1);plot('impedance-plot',[[r,'#126eaa'],[x,'#bd5910']],low-pad,high+pad,'R, X [Ω]');
    let top=3;for(const value of all) if(Number.isFinite(value)) top=Math.max(top,value*1.05);
    plot('swr-plot',[[all,'#6d43a6']],1,Math.min(top,20),'SWR',top>20);
  }
  $('slider').max=f.length-1;$('slider').disabled=f.length===1;
  $('slider').addEventListener('input',()=>{index=Number($('slider').value);update();});
  $('frequency').min=f[0];$('frequency').max=f[f.length-1];
  $('frequency').addEventListener('change',()=>{const value=Number($('frequency').value);if(Number.isFinite(value)) index=nearest(value);update();});
  $('reference').addEventListener('change',()=>{reference=Number($('reference').value);update();});
  $('target').addEventListener('click',()=>{index=nearest(D.target_mhz);update();});
  $('target').disabled=D.target_mhz<f[0]||D.target_mhz>f[f.length-1];
  $('best').addEventListener('click',()=>{let best=Infinity;for(let i=0;i<f.length;i++){const v=sample(i).swr;if(Number.isFinite(v)&&v<best){best=v;index=i;}}update();});
  $('csv').addEventListener('click',()=>{
    const rows=['frequency_hz,resistance_ohm,reactance_ohm,reference_ohm,swr,s11_db,mismatch_loss_db'];
    for(let i=0;i<f.length;i++){const v=sample(i);rows.push([f[i]*1e6,r[i],x[i],reference,...[v.swr,v.s11,v.loss].map(n=>Number.isNaN(n)?'':n)].join(','));}
    const url=URL.createObjectURL(new Blob([rows.join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='impedance-report.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  update();document.body.classList.add('ready');
})();
"""
