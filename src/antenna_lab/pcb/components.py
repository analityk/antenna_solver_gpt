"""Strict EasyEDA ideal netlist/placement import, using final top copper.

ENET Value alone defines R/C/L. FlyingProbe supplies positions and a transverse
contact window, never the longitudinal electrical gap. No package model.
"""
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import re

from shapely.geometry import Point, LineString
from shapely import union_all

from antenna_lab.core.config import ConfigurationError
from .model import PcbLumpedComponent, PcbPort, PcbSourceProvenance
from .regions import copper_shape
from .sources import member
from .validation import TOLERANCE_M

IDEAL_NOTE = ('Components are ideal lumped elements. Package parasitics, tolerance, '
              'ESR/ESL/DCR and manufacturer frequency dependence are not modeled.')
_NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
_UNITS = {'R': {'Ω':1., 'ohm':1., 'R':1., 'mΩ':1e-3, 'kΩ':1e3, 'MΩ':1e6},
          'C': {'F':1., 'pF':1e-12, 'nF':1e-9, 'uF':1e-6, 'µF':1e-6},
          'L': {'H':1., 'pH':1e-12, 'nH':1e-9, 'uH':1e-6, 'µH':1e-6, 'mH':1e-3}}


def ideal_value(kind, value):
    match = re.fullmatch(r'\s*('+_NUMBER+r')\s*(\S+)\s*', str(value))
    if not match or match[2] not in _UNITS[kind]:
        raise ConfigurationError(f'{kind}: invalid ideal Value {value!r}; explicit supported unit required.')
    number = float(match[1])*_UNITS[kind][match[2]]
    if not isfinite(number) or number <= 0:
        raise ConfigurationError(f'{kind}: Value must be finite and positive.')
    return number


def _json(path):
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result: raise ValueError(f'duplicate JSON key {key!r}')
            result[key] = value
        return result
    try:
        return json.loads(member(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique)
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f'{member(path).name}: invalid component JSON: {exc}') from exc


def discover_component_sources(directory):
    files = sorted((p for p in Path(directory).iterdir() if p.is_file()), key=lambda p:p.name)
    enet = [p for p in files if p.suffix.lower()=='.enet']
    if not enet: return None  # No-netlist legacy path, including ignored FlyingProbe.
    probes = [p for p in files if p.name.lower()=='flyingprobetesting.json']
    if len(enet)!=1 or len(probes)!=1:
        raise ConfigurationError('ENET mode requires exactly one .enet and one FlyingProbeTesting.json; '
            'candidates: '+', '.join(p.name for p in enet+probes))
    return enet[0],probes[0]


def read_netlist(path):
    value = _json(path)
    if not isinstance(value,dict): raise ConfigurationError('ENET must be an object of entries.')
    result = {}
    for entry in value.values():
        try:
            props,pins = entry['props'],entry['pins']
            ref,text = props['Designator'],props['Value']
        except (KeyError,TypeError) as exc: raise ConfigurationError('ENET entry requires props.Designator, props.Value and pins.') from exc
        if not isinstance(ref,str) or not ref or ref in result:
            raise ConfigurationError(f'ENET unique Designator required: {ref!r}.')
        if not isinstance(pins,dict) or len(pins)!=2 or any(not isinstance(v,str) or not v for v in pins.values()):
            raise ConfigurationError(f'{ref}: exactly two named pin nets required.')
        if ref=='CSRC':
            if isinstance(text,bool) or not re.fullmatch(r'\s*'+_NUMBER+r'\s*',str(text)) or float(text)!=0:
                raise ConfigurationError('CSRC Value must be numeric zero, not capacitance.')
            kind,number='SOURCE',0.
        elif ref[0] in _UNITS:
            kind=ref[0];number=ideal_value(kind,text)
        else: raise ConfigurationError(f'{ref}: unsupported component type; only R/C/L and CSRC.')
        result[ref]=(kind,number,str(text),tuple(sorted(pins.items())))
    if 'CSRC' not in result: raise ConfigurationError('ENET requires exactly one CSRC Value=0 source.')
    return result


def _finite(value, name, positive=False):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not isfinite(value) or (positive and value<=0):
        raise ConfigurationError(f'FlyingProbe {name}: finite numeric'+(' positive' if positive else '')+' value required.')
    return float(value)


def read_placements(path, entries):
    value=_json(path)
    units={'mm':1e-3, 'mil':25.4e-6, 'inch':.0254, 'in':.0254, 'm':1.}
    if not isinstance(value,dict) or value.get('lengthUnit') not in units:
        raise ConfigurationError('FlyingProbe: unsupported/missing lengthUnit.')
    scale=units[value['lengthUnit']];pins=value.get('pins')
    if isinstance(pins,dict):
        fields,rows=pins.get('fields'),pins.get('rows')
        if not isinstance(fields,list) or not all(isinstance(f,str) for f in fields) or len(set(fields))!=len(fields) or not isinstance(rows,list):
            raise ConfigurationError('FlyingProbe: invalid pins fields/rows.')
        if any(not isinstance(row,list) or len(row)!=len(fields) for row in rows):
            raise ConfigurationError('FlyingProbe: pin row size does not match fields.')
        pins=[dict(zip(fields,row)) for row in rows]
    if not isinstance(pins,list) or any(not isinstance(p,dict) for p in pins):
        raise ConfigurationError('FlyingProbe: pins table required.')
    result={}
    for ref,(_,_,_,nets) in entries.items():
        resolved=[]
        for pin,net in nets:
            name=f'{ref}_{pin}';matches=[p for p in pins if p.get('PIN_NAME')==name]
            if len(matches)!=1: raise ConfigurationError(f'{name}: missing/ambiguous FlyingProbe pin record.')
            p=matches[0]
            if p.get('NET_NAME')!=net: raise ConfigurationError(f'{name}: ENET/FlyingProbe net mismatch.')
            if p.get('LAYER')!='T' or p.get('PIN_TYPE')!='SMD':
                raise ConfigurationError(f'{name}: only top-layer SMD components supported.')
            try:
                xy=tuple(_finite(p[k],name+' '+k)*scale for k in ('PIN_X','PIN_Y'))
                sizes=tuple(_finite(p[k],name+' '+k,True)*scale for k in ('PAD_SIZEX','PAD_SIZEY'))
                angle=_finite(p['PAD_ANGLE'],name+' PAD_ANGLE')
            except KeyError as exc: raise ConfigurationError(f'{name}: missing placement field {exc}.') from exc
            if angle%90!=0: raise ConfigurationError(f'{name}: axis-aligned pad required.')
            if int(angle/90)%2: sizes=sizes[::-1]
            resolved.append((xy,sizes))
        result[ref]=tuple(resolved)
    return result


def terminal_gap(ref, pins, copper):
    """One actual clear interval on the centre line, not an aperture-edge guess."""
    (a,sa),(b,sb)=pins
    shapes=[copper_shape(c) for c in copper if c.layer_role=='top']
    for xy in (a,b):
        if sum(s.buffer(TOLERANCE_M).covers(Point(xy)) for s in shapes)!=1:
            raise ConfigurationError(f'{ref}: pin {xy} must belong to exactly one final top copper region.')
    delta=(b[0]-a[0],b[1]-a[1]);axis=0 if abs(delta[1])<=TOLERANCE_M else 1
    if abs(delta[axis])<=TOLERANCE_M or abs(delta[1-axis])>TOLERANCE_M:
        raise ConfigurationError(f'{ref}: non-axis-aligned or zero-length pin pair.')
    line=LineString((a,b));clear=line.difference(union_all(shapes))
    pieces=[clear] if clear.geom_type=='LineString' else list(getattr(clear,'geoms',()))
    if len(pieces)!=1 or pieces[0].geom_type!='LineString' or pieces[0].length<=TOLERANCE_M:
        raise ConfigurationError(f'{ref}: require exactly one nonzero clear interval between copper terminals.')
    ends=(tuple(pieces[0].coords[0]),tuple(pieces[0].coords[-1]))
    start,stop=sorted(ends,key=lambda p:line.project(Point(p)))
    t=1-axis;lo=max(a[t]-sa[t]/2,b[t]-sb[t]/2);hi=min(a[t]+sa[t]/2,b[t]+sb[t]/2)
    if hi-lo<=TOLERANCE_M: raise ConfigurationError(f'{ref}: terminal pad widths do not overlap.')
    limits=(min(start[axis],stop[axis]),max(start[axis],stop[axis]))
    def point(long,trans): return (long,trans) if axis==0 else (trans,long)
    window=tuple(point(u,v) for u,v in ((limits[0],lo),(limits[1],lo),(limits[1],hi),(limits[0],hi)))
    return 'xy'[axis],start,stop,window,hi-lo


def load_components(enet, probe, copper):
    entries=read_netlist(enet);placements=read_placements(probe,entries)
    eh,fh=(sha256(member(p).read_bytes()).hexdigest() for p in (enet,probe))
    components=[];source=None;port=None
    for ref,(kind,number,text,nets) in sorted(entries.items()):
        axis,start,stop,window,width=terminal_gap(ref,placements[ref],copper)
        a,b=(p[0] for p in placements[ref]);net1,net2=(n[1] for n in nets)
        if kind=='SOURCE':
            port=PcbPort('CSRC',start,stop,width)
            source=PcbSourceProvenance(ref,(net1,net2),a,b,eh,fh)
        else:
            components.append(PcbLumpedComponent(ref,kind,number,text,net1,net2,a,b,'top',axis,
                start,stop,window,eh,fh))
    return port,tuple(components),source
