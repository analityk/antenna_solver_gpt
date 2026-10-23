"""EasyEDA Pro PCB 1.8 JSON-lines -> semantic IR, without manufacturing files.

Units are dialect/record-specific, NEVER inferred from dimensions or CANVAS.
See docs/pcb-easyeda.md for primary format and KiCad implementation references.
PCB coordinates/widths/thickness: mil. Materialized POURED paths: 10 mil.
Source coordinates are retained in a Cartesian +Y-up frame, positive CCW arcs.
No KiCad IU rounding or screen-coordinate Y inversion is applied here.
"""
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
from math import cos, sin, radians, tan, isfinite
from pathlib import Path

from antenna_lab.core.config import ConfigurationError
from .source_ir import EasyEdaSource, SourceRoutePrimitive, SourceVia

FORMAT_REFERENCE='https://github.com/easyeda/easyeda-file-format-v2/tree/63f38c2758cbe2456e8b5c7e76469369430d94af/docs/en/pcb'
IMPLEMENTATION_REFERENCE='https://gitlab.com/kicad/code/kicad/-/tree/master/pcbnew/pcb_io/easyedapro'
UNITS=dict(profile='easyeda_pro_pcb_1.8',coordinate_unit='mil',metres_per_unit=0.0000254,
           poured_path_unit='10mil',poured_path_metres_per_unit=0.000254,
           canvas='display only',axes='Cartesian XY; +Y up; positive sweep CCW',
           format_reference=FORMAT_REFERENCE,implementation_reference=IMPLEMENTATION_REFERENCE)


def number(value, label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value):
        raise ConfigurationError(f'EasyEDA {label}: expected finite number.')
    return value


def metres(value, label, *, poured=False):
    number(value,label)
    return float(Decimal(str(value))*Decimal('0.000254' if poured else '0.0000254'))


def positive(value,label,*,poured=False):
    result=metres(value,label,poured=poured)
    if result<=0:raise ConfigurationError(f'EasyEDA {label}: positive dimension required.')
    return result


def arc_center(start,stop,sweep,label):
    number(sweep,label)
    if sweep==0 or abs(sweep)>=360 or start==stop:
        raise ConfigurationError(f'EasyEDA {label}: degenerate/unsupported ARC sweep or endpoints.')
    dx,dy=stop[0]-start[0],stop[1]-start[1]
    factor=0. if abs(sweep)==180 else 1/(2*tan(radians(sweep)/2))
    return ((start[0]+stop[0])/2-dy*factor,(start[1]+stop[1])/2+dx*factor)


def polygon_ring(path,label,*,poured=False):
    """Explicit subset: unrounded rectangle or straight L contour, no repair."""
    if not isinstance(path,list) or not path:raise ConfigurationError(f'EasyEDA {label}: missing polygon path.')
    m=lambda v:metres(v,label,poured=poured)
    if path[0]=='R':
        if (not 6<=len(path)<=8 or
                (len(path)>6 and path[6] not in (0,1,False,True)) or
                (len(path)>7 and path[7]!=0)):
            raise ConfigurationError(f'EasyEDA {label}: unsupported R winding/rounded corner variant.')
        x,y,w,h=map(m,path[1:5]);a=radians(number(path[5],label))
        if w<=0 or h<=0:raise ConfigurationError(f'EasyEDA {label}: collapsed rectangle.')
        # Top-left anchor in source +Y-up coordinates: height extends downward.
        points=[(x+u*cos(a)-v*sin(a),y+u*sin(a)+v*cos(a)) for u,v in ((0,0),(w,0),(w,-h),(0,-h))]
        # EasyEDA R isCCW flag: preserve winding for nonzero fill-rule holes.
        if len(path)>6 and bool(path[6]):
            points.reverse()
    else:
        if len(path)<7 or path[2]!='L' or len(path[3:])%2:
            raise ConfigurationError(f'EasyEDA {label}: unsupported polygon subtype (only R or straight L contour).')
        values=path[:2]+path[3:]
        points=[(m(values[i]),m(values[i+1])) for i in range(0,len(values),2)]
    if points[-1]==points[0]:points.pop()
    from shapely.geometry import Polygon
    shape=Polygon(points)
    if len(set(points))<3 or not shape.is_valid or shape.area<=0:
        raise ConfigurationError(f'EasyEDA {label}: invalid polygon; no topology repair.')
    return tuple(points)



def curved_polygon_ring(path, label, *, poured=False):
    """EasyEDA V2 single polygon with straight L and signed ARC/CARC segments.

    Convert every sampled point to source SI coordinates (POURED=10 mil). Use
    the same geometric curve-error budget as the existing Gerber/route import,
    not the FDTD mesh resolution. No automatic shape/topology repair.
    """
    if not isinstance(path, list) or not path:
        raise ConfigurationError(f'EasyEDA {label}: missing polygon path.')
    if path[0]=='R':
        return polygon_ring(path,label,poured=poured)
    if len(path)<6:
        raise ConfigurationError(f'EasyEDA {label}: incomplete mixed polygon path.')
    from math import acos, atan2, ceil, hypot, pi
    from .gerber import CURVE_ERROR_M
    m=lambda value:metres(value,label,poured=poured)
    points=[(m(path[0]),m(path[1]))]
    i=2
    while i<len(path):
        op=path[i]
        if op=='L':
            i+=1
            beginning=i
            while i<len(path) and not isinstance(path[i],str):
                if i+1>=len(path) or isinstance(path[i+1],str):
                    raise ConfigurationError(f'EasyEDA {label}: incomplete L coordinates.')
                points.append((m(path[i]),m(path[i+1])))
                i+=2
            if i==beginning:
                raise ConfigurationError(f'EasyEDA {label}: empty L segment.')
        elif op in ('ARC','CARC'):
            if i+3>=len(path) or isinstance(path[i+1],str):
                raise ConfigurationError(f'EasyEDA {label}: incomplete ARC parameters.')
            angle=number(path[i+1],label)
            finish=(m(path[i+2]),m(path[i+3]))
            begin=points[-1]
            center=arc_center(begin,finish,angle,label)
            radius=hypot(begin[0]-center[0],begin[1]-center[1])
            if radius<=0:
                raise ConfigurationError(f'EasyEDA {label}: collapsed ARC radius.')
            # Chord sagitta is bounded by CURVE_ERROR_M; the end vertex is
            # always the exact source endpoint rather than a derived float.
            limit=2*acos(max(-1.,min(1.,1-CURVE_ERROR_M/radius)))
            steps=max(2,ceil(abs(radians(angle))/limit)) if limit>0 else 100001
            if steps>100000:
                raise ConfigurationError(f'EasyEDA {label}: ARC exceeds curve vertex budget.')
            first=atan2(begin[1]-center[1],begin[0]-center[0])
            sweep=radians(angle)
            for j in range(1,steps):
                theta=first+sweep*j/steps
                points.append((center[0]+radius*cos(theta),center[1]+radius*sin(theta)))
            points.append(finish)
            i+=4
        else:
            raise ConfigurationError(
                f'EasyEDA {label}: unsupported polygon segment {op!r} '
                '(supported L, ARC, CARC, unrounded R).')
        if len(points)>100000:
            raise ConfigurationError(f'EasyEDA {label}: polygon exceeds vertex budget.')
    if points[-1]==points[0]:
        points.pop()
    from shapely.geometry import Polygon
    shape=Polygon(points)
    if len(set(points))<3 or not shape.is_valid or shape.area<=0:
        raise ConfigurationError(f'EasyEDA {label}: invalid curved polygon; no topology repair.')
    return tuple(points)


def complex_polygon_rings(paths, label, *, poured=False):
    """Parse all contour types supported by exact source geometry.

    The nonzero fill rule is resolved by the model; we must not flatten arc
    apertures, lose rings or fabricate solid fill from the parent boundary.
    """
    if not isinstance(paths, list) or not paths:
        raise ConfigurationError(f'EasyEDA {label}: missing complex polygon paths.')
    return tuple(curved_polygon_ring(path, label, poured=poured) for path in paths)


def load_easyeda_source(path):
    path=Path(path);raw=path.read_bytes()
    return parse_easyeda_source(raw,source_file=str(path))


def parse_easyeda_source(raw,*,source_file='<memory>'):
    """Raw bytes are hashed unchanged; all converted spatial values are SI."""
    if isinstance(raw,str):raw=raw.encode('utf-8')
    digest=sha256(raw).hexdigest();records=[]
    def bad_constant(value):raise ValueError('non-finite JSON '+value)
    for index,line in enumerate(raw.decode('utf-8-sig').splitlines(),1):
        if not line.strip():continue
        try:
            record=json.loads(line,parse_constant=bad_constant)
            json.dumps(record,allow_nan=False)
        except (ValueError,TypeError) as exc:
            raise ConfigurationError(f'EasyEDA record {index}: malformed strict JSON: {exc}') from exc
        if not isinstance(record,list) or not record or not isinstance(record[0],str):
            raise ConfigurationError(f'EasyEDA record {index}: expected JSON primitive array.')
        records.append(dict(record_index=index,data=record))
    if not records or records[0]['data']!=['DOCTYPE','PCB','1.8']:
        raise ConfigurationError('EasyEDA unsupported DOCTYPE/version: supported PCB 1.8 only; units unresolved for other dialects.')
    heads=[r['data'] for r in records if r['data'][0]=='HEAD']
    if len(heads)!=1 or len(heads[0])!=2 or not isinstance(heads[0][1],dict):
        raise ConfigurationError('EasyEDA HEAD: expected one editor metadata object.')
    editor=heads[0][1].get('editorVersion','')
    if not isinstance(editor,str) or not editor.startswith('2.2.'):
        raise ConfigurationError(f'EasyEDA HEAD editorVersion {editor!r}: unsupported 1.8 dialect; units unresolved.')
    layers={};physical=[];nets=[];routes=[];vias=[];polygons=[];pours=[];poured=[]
    components=[];attrs=[];pad_nets=[];pads=[];retained=[];unsupported=[];display=None;ids=set()
    metadata={'ACTIVE_LAYER','RULE','RULE_TEMPLATE','RULE_SELECTOR','PRIMITIVE','SILK_OPTS',
              'PREFERENCE','PANELIZE_STAMP','PANELIZE_SIDE','ITEM_ORDER','GROUP','FONT'}
    for entry in records:
        r=entry['data'];index=entry['record_index'];kind=r[0]
        label=f'{kind} {r[1] if len(r)>1 else "?"} (record {index})'
        try:
            if kind in ('DOCTYPE','HEAD'):continue
            if kind=='CANVAS':
                if display is not None or r[3] not in ('mm','mil'):raise ValueError('one CANVAS display unit required')
                display=r[3]
            elif kind=='LAYER':
                if type(r[1]) is not int or r[1] in layers or not isinstance(r[2],str):raise ValueError('invalid/duplicate layer')
                layers[r[1]]=dict(id=r[1],type=r[2],name=r[3],state=r[4],record_index=index)
            elif kind=='NET':
                if not isinstance(r[1],str) or not r[1] or r[1] in nets:raise ValueError('invalid/duplicate net')
                nets.append(r[1])
            elif kind=='LAYER_PHYS':
                thickness=metres(r[3],label);er=number(r[4],label);loss=number(r[5],label)
                if min(thickness,er,loss)<0:raise ValueError('negative material value')
                physical.append(dict(layer_id=r[1],material=r[2],thickness_m=thickness,
                    epsilon_r=er,loss_tangent=loss,record_index=index))
            elif kind in ('LINE','ARC','VIA','POLY','POUR','POURED','COMPONENT','ATTR','PAD'):
                if not isinstance(r[1],str) or not r[1] or r[1] in ids:raise ValueError('invalid/duplicate primitive ID')
                ids.add(r[1])
                if kind in ('LINE','ARC'):
                    if len(r)!=(11 if kind=='LINE' else 12):raise ValueError('unsupported field count')
                    start=tuple(metres(v,label) for v in r[5:7]);stop=tuple(metres(v,label) for v in r[7:9])
                    sweep=None if kind=='LINE' else number(r[9],label)
                    center=None if sweep is None else arc_center(start,stop,sweep,label)
                    if start==stop:raise ValueError('collapsed route')
                    routes.append(SourceRoutePrimitive(r[1],index,kind,r[3],r[4],'unresolved',start,stop,
                        positive(r[9 if kind=='LINE' else 10],label),sweep,center,source_file,digest))
                elif kind=='VIA':
                    if not 13<=len(r)<=15:raise ValueError('unsupported VIA field count')
                    drill=positive(r[7],label);pad=positive(r[8],label)
                    if pad<=drill:raise ValueError('via pad diameter must exceed drill')
                    vias.append(SourceVia(r[1],index,r[3],tuple(metres(v,label) for v in r[5:7]),
                        drill,pad,r[4],source_file,digest))
                elif kind=='POLY':
                    polygons.append(dict(id=r[1],net=r[3],layer_id=r[4],width_m=positive(r[5],label),
                        ring_xy_m=polygon_ring(r[6],label),record_index=index))
                elif kind=='POUR':
                    if len(r)!=12 or not isinstance(r[9],list) or not r[9] or r[9][0]!='SOLID':
                        raise ValueError('only SOLID POUR supported')
                    rings=complex_polygon_rings(r[8],label)
                    pours.append(dict(id=r[1],net=r[3],layer_id=r[4],
                        rings_xy_m=rings,ring_xy_m=rings[0],record_index=index))
                elif kind=='POURED':
                    if len(r)!=6 or r[3]!=0 or r[4] not in (True,1):
                        raise ValueError('only filled, unstroked POURED supported')
                    rings=complex_polygon_rings(r[5],label,poured=True)
                    poured.append(dict(id=r[1],parent_id=r[2],
                        rings_xy_m=rings,ring_xy_m=rings[0],record_index=index))
                elif kind=='PAD':
                    if len(r)<11 or (r[9] is not None and r[9]!=['ROUND',0,0]):
                        raise ValueError('only no-hole absolute RECT PAD supported')
                    shape=r[10]
                    if not isinstance(shape,list) or len(shape) not in (3,4) or shape[0]!='RECT' or (len(shape)==4 and shape[3]!=0):
                        raise ValueError('only unrounded RECT PAD supported')
                    if len(r)>11 and r[11]:raise ValueError('special-layer PAD geometry unsupported')
                    x,y=(metres(v,label) for v in r[6:8]);w,h=(positive(v,label) for v in shape[1:3])
                    a=radians(number(r[8],label))
                    ring=tuple((x+u*cos(a)-v*sin(a),y+u*sin(a)+v*cos(a))
                               for u,v in ((-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)))
                    pads.append(dict(id=r[1],net=r[3],layer_id=r[4],pad_number=r[5],ring_xy_m=ring,record_index=index))
                elif kind=='COMPONENT':
                    if len(r) not in (9,10) or not isinstance(r[7],dict):raise ValueError('unsupported COMPONENT fields')
                    components.append(dict(id=r[1],layer_id=r[3],position_xy_m=[metres(v,label) for v in r[4:6]],
                        rotation_deg=number(r[6],label),properties=r[7],record_index=index))
                else:
                    if len(r)<9:raise ValueError('unsupported ATTR fields')
                    attrs.append(dict(id=r[1],parent_id=r[3],key=r[7],value=r[8],record_index=index))
            elif kind=='PAD_NET':
                if len(r) not in (4,5):raise ValueError('unsupported PAD_NET fields')
                pad_nets.append(dict(component_id=r[1],pad_number=r[2],net=r[3],pad_id=r[4] if len(r)>4 else None,record_index=index))
            elif kind=='PANELIZE':
                if r[1]!=0:unsupported.append(label+': active panelization')
            elif kind in metadata or kind.startswith('META_'):
                retained.append(dict(kind=kind,record_index=index,disposition='editor_metadata'))
            else:
                unsupported.append(label+': unsupported relevant/unknown record')
        except (IndexError,TypeError,ValueError) as exc:
            raise ConfigurationError(f'EasyEDA {label}: malformed/unsupported record: {exc}') from exc
    if display is None:raise ConfigurationError('EasyEDA missing CANVAS display metadata.')
    from dataclasses import replace
    def role(id):
        if id not in layers:raise ConfigurationError(f'EasyEDA unresolved LAYER {id!r}.')
        kind=layers[id]['type']
        return {'TOP':'top','BOTTOM':'bottom','OUTLINE':'outline'}.get(kind,'unsupported:'+kind)
    routes=tuple(replace(r,layer_role=role(r.layer_id)) for r in routes)
    for r in (*routes,*vias):
        if r.net not in nets:raise ConfigurationError(f'EasyEDA {r.id}: undeclared net {r.net!r}.')
    for r in physical:
        if r['layer_id'] not in layers:raise ConfigurationError(f"EasyEDA LAYER_PHYS {r['layer_id']}: undefined layer.")
    semantics=dict(units=UNITS,layers=list(layers.values()),layer_physics=physical,nets=nets,
        polygons=polygons,pours=pours,poured=poured,components=components,attributes=attrs,
        pad_nets=pad_nets,pads=pads,retained_metadata=retained,unsupported_records=unsupported,
        design_source='easyeda_source',manufacturing_validation='not_requested')
    return EasyEdaSource(source_file,digest,'1.8',editor,display,routes,tuple(vias),
        json.dumps(records,sort_keys=True,allow_nan=False),json.dumps(semantics,sort_keys=True,allow_nan=False))
