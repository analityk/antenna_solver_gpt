"""Explicit V2 footprint subset; local pad -> side mirror -> CCW -> PCB SI.

Supported: unrounded RECT, circular ELLIPSE/ROUND, OVAL; SMD or round
through PAD with declared plating flag. Other physical primitives fail closed.
Curve polygonization uses the existing importer error budget, not new snapping.
"""
from math import cos, sin, radians
from shapely.geometry import Polygon, Point, LineString
from shapely.affinity import affine_transform
from antenna_lab.core.config import ConfigurationError
from .easyeda import metres, positive, number
from .gerber import _buffer, CURVE_ERROR_M


def rotation(angle):
    angle = number(angle, 'rotation') % 360
    if angle in (0, 90, 180, 270):
        return {0:(1.,0.),90:(0.,1.),180:(-1.,0.),270:(0.,-1.)}[angle]
    return cos(radians(angle)), sin(radians(angle))


def transform_xy(point, position, angle, bottom=False):
    """Source +Y-up: bottom reflects local Y before rotation (KiCad Pro parity)."""
    x,y=point
    if bottom:y=-y
    c,s=rotation(angle)
    return (position[0]+c*x-s*y, position[1]+s*x+c*y)


def _transform(shape, position, angle, bottom=False):
    c,s=rotation(angle);m=-1 if bottom else 1
    return affine_transform(shape,[c,-s*m,s,c*m,*position])


def _pad_shape(r, label):
    shape=r[10]
    if not isinstance(shape,list) or len(shape)<3:
        raise ConfigurationError(f'EasyEDA {label}: unsupported PAD shape {shape!r}.')
    typ=shape[0];w=positive(shape[1],label);h=positive(shape[2],label)
    if typ=='RECT' and len(shape) in (3,4) and (len(shape)==3 or shape[3]==0):
        return Polygon(((-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)))
    if typ in ('ROUND','ELLIPSE') and len(shape)==3 and w==h:
        return _buffer(Point(0,0),w/2,CURVE_ERROR_M)
    if typ=='OVAL' and len(shape)==3:
        if w==h:return _buffer(Point(0,0),w/2,CURVE_ERROR_M)
        ends=((-abs(w-h)/2,0),(abs(w-h)/2,0)) if w>h else ((0,-abs(w-h)/2),(0,abs(w-h)/2))
        return _buffer(LineString(ends),min(w,h)/2,CURVE_ERROR_M)
    raise ConfigurationError(f'EasyEDA {label}: unsupported PAD shape {shape!r}; no guessed contour.')


def instantiate_components(resolved, pcb_layers, nets):
    layer_ids={r['type']:r['id'] for r in pcb_layers if r['type'] in ('TOP','BOTTOM')}
    if set(layer_ids)!= {'TOP','BOTTOM'}:
        raise ConfigurationError('EasyEDA footprint instantiation requires top/bottom layers.')
    instances=[];pads=[];drills=[]
    for comp in resolved:
        fp=comp['footprint'];r=comp['component_record']['data'];cid=comp['component_id']
        label=f'{comp["designator"]} ({cid}), {fp["source_file"]}'
        if r[3] not in layer_ids.values():
            raise ConfigurationError(f'EasyEDA {label}: COMPONENT side must be top/bottom.')
        bottom=r[3]==layer_ids['BOTTOM'];pos=tuple(metres(v,label) for v in r[4:6]);angle=number(r[6],label)
        local_layers={e['data'][1]:e['data'][2] for e in fp['records'] if e['data'][0]=='LAYER'}
        bindings={b['pad_id']:b for b in comp['bindings']}
        ids=[]
        ignored=[]
        for entry in fp['records']:
            p=entry['data'];kind=p[0];plabel=f'{label}, {kind} {p[1] if len(p)>1 else "?"}, line {entry["record_index"]}'
            if kind in ('DOCTYPE','HEAD','LAYER','CANVAS','ACTIVE_LAYER','ATTR','FONT','PRIMITIVE'):
                continue
            if kind!='PAD':
                # Known artwork on nonphysical layers only. Unknown records fail.
                if kind in ('POLY','FILL','LINE','ARC','STRING') and len(p)>4 and local_layers.get(p[4]) not in (None,'TOP','BOTTOM','MULTI','SIGNAL','PLANE'):
                    ignored.append(dict(id=p[1],kind=kind,layer_id=p[4],disposition='non_electrical_artwork'))
                    continue
                raise ConfigurationError(f'EasyEDA {plabel}: unsupported footprint physical/unknown primitive.')
            if len(p)<12 or p[11]:
                raise ConfigurationError(f'EasyEDA {plabel}: per-layer PAD stack unsupported.')
            binding=bindings[p[1]];net=binding['net']
            if not isinstance(net,str) or net not in nets:
                raise ConfigurationError(f'EasyEDA {plabel}: undeclared/empty mapped net {net!r}.')
            if p[3] not in ('',net):
                raise ConfigurationError(f'EasyEDA {plabel}: local net conflicts with PAD_NET {net}.')
            local=tuple(metres(v,plabel) for v in p[6:8]);pad_angle=number(p[8],plabel)
            shape=_transform(_pad_shape(p,plabel),local,pad_angle)
            center=transform_xy(local,pos,angle,bottom)
            role=local_layers.get(p[4]);hole=p[9];hole_info=None;hole_shape=None
            if hole is not None and hole!=['ROUND',0,0]:
                if not isinstance(hole,list) or len(hole)!=3 or hole[0]!='ROUND' or hole[1]!=hole[2]:
                    raise ConfigurationError(f'EasyEDA {plabel}: only round through drills supported, not slots.')
                diameter=positive(hole[1],plabel)
                if role!='MULTI' or len(p)<16 or p[15] not in (0,1) or isinstance(p[15],bool):
                    raise ConfigurationError(f'EasyEDA {plabel}: explicit MULTI and plating flag 0/1 required.')
                offset=tuple(metres(v,plabel) for v in p[12:14])
                # Offset relative to PAD axes; circular drill rotation has no effect.
                hole_center=transform_xy(offset,local,pad_angle)
                hole_shape=_buffer(Point(hole_center),diameter/2,CURVE_ERROR_M)
                if not shape.contains(hole_shape):
                    raise ConfigurationError(f'EasyEDA {plabel}: drill not strictly inside pad.')
                hole_shape=_transform(hole_shape,pos,angle,bottom)
                hole_info=dict(id=f'{cid}:{p[1]}:drill',centre_xy_m=transform_xy(hole_center,pos,angle,bottom),
                    drill_diameter_m=diameter,plated=bool(p[15]),source_file=fp['source_file'],
                    source_sha256=fp['source_sha256'],component_id=cid,pad_id=p[1],net=net,
                    plating_thickness_m=None,model_status='requires_explicit_plating' if p[15] else 'npth')
                drills.append(hole_info)
                target_roles=('TOP','BOTTOM')
            else:
                if role not in ('TOP','BOTTOM'):
                    raise ConfigurationError(f'EasyEDA {plabel}: hole-free PAD requires TOP/BOTTOM.')
                target_roles=(('BOTTOM' if role=='TOP' else 'TOP') if bottom else role,)
            shape=_transform(shape,pos,angle,bottom)
            if hole_shape is not None:shape=shape.difference(hole_shape)
            if not shape.is_valid or shape.geom_type!='Polygon' or shape.is_empty:
                raise ConfigurationError(f'EasyEDA {plabel}: invalid transformed pad; no repair.')
            for target in target_roles:
                pid=f'{cid}:{p[1]}:{target.lower()}';ids.append(pid)
                pads.append(dict(id=pid,net=net,layer_id=layer_ids[target],pad_number=binding['pad_number'],
                    local_pad_id=p[1],component_id=cid,ring_xy_m=tuple(shape.exterior.coords)[:-1],
                    holes_xy_m=tuple(tuple(h.coords)[:-1] for h in shape.interiors),centre_xy_m=center,
                    record_index=entry['record_index'],source_file=fp['source_file'],source_sha256=fp['source_sha256'],
                    drill_id=hole_info['id'] if hole_info else None,
                    transform=dict(position_xy_m=pos,rotation_deg=angle,mirror_local_y=bottom,pad_rotation_deg=pad_angle)))
        instances.append({k:v for k,v in comp.items() if k not in ('footprint','component_record')})
        instances[-1].update(pad_ids=ids,source_file=fp['source_file'],source_sha256=fp['source_sha256'],
            ignored_artwork=ignored,transform=dict(position_xy_m=pos,rotation_deg=angle,mirror_local_y=bottom),
            pcb_record_index=comp['component_record']['record_index'])
    return instances,pads,drills
