"""Source-only physical PCB image and canonical model. No Gerber file IO.

This adapter uses source routes, filled POURED results, and absolute RECT pads.
It never substitutes POUR boundaries for missing fill or fabricates footprints.
"""
from dataclasses import asdict, replace
from math import isfinite
from pathlib import Path
import json

from shapely import union_all, normalize
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import polygonize, unary_union

from antenna_lab.core.config import ConfigurationError
from .model import (BoardOutline,CopperPolygon,CopperLayer,DielectricLayer,Substrate,
                    PcbGeometry,PcbPort,PcbDrill)
from .source_ir import SourcePad
from .regions import copper_shape
from .validation import TOLERANCE_M,validate_pcb_geometry


def route_shape(route):
    # Shared geometric curve approximation, not a Gerber conversion/parser.
    from .gerber import _buffer,CURVE_ERROR_M
    if route.kind=='LINE':axis=LineString((route.start_xy_m,route.stop_xy_m))
    else:
        from gerbonara.utils import approximate_arc
        axis=LineString(list(approximate_arc(*route.center_xy_m,*route.start_xy_m,
            *route.stop_xy_m,route.signed_sweep_deg<0,max_error=CURVE_ERROR_M/2)))
    return _buffer(axis,route.width_m/2,CURVE_ERROR_M/2)


def _polygon(id,shape,z,role):
    if shape.geom_type!='Polygon' or not shape.is_valid or shape.is_empty:
        raise ConfigurationError(f'EasyEDA {id}: invalid canonical copper, no repair.')
    from .gerber import BOOLEAN_CLEANUP_M
    # Same existing boolean residue cleanup budget as import, no lattice snap.
    shape=normalize(shape.simplify(BOOLEAN_CLEANUP_M,preserve_topology=True))
    return CopperPolygon(id,tuple(shape.exterior.coords)[:-1],z,role,
                         tuple(tuple(h.coords)[:-1] for h in shape.interiors))



def _signed_ring_area(ring):
    return sum(a[0]*b[1] - b[0]*a[1]
               for a,b in zip(ring, (*ring[1:],ring[0]))) / 2.


def complex_copper_shape(rings, label):
    """Apply EasyEDA Pro V2's *nonzero* polygon winding rule.

    Union of independent rings would incorrectly fill holes. Subtracting all
    nested rings would incorrectly erase same-winding islands. Polygonize
    the exact planar boundaries, then include each face only when its total
    signed winding number is nonzero. No topological repair or guessed pour.
    """
    if not rings:
        raise ConfigurationError(f'EasyEDA {label}: no fill contours.')
    contours=[]
    for ring in rings:
        poly=Polygon(ring)
        area=_signed_ring_area(ring)
        if (len(ring)<3 or area==0 or not poly.is_valid or
                poly.is_empty or poly.area<=0):
            raise ConfigurationError(f'EasyEDA {label}: invalid fill contour.')
        contours.append((poly,1 if area>0 else -1))
    boundaries=unary_union([LineString([*poly.exterior.coords]) for poly,_ in contours])
    faces=list(polygonize(boundaries))
    filled=[]
    for face in faces:
        probe=face.representative_point()
        winding=sum(sign for poly,sign in contours if poly.covers(probe))
        if winding:
            filled.append(face)
    if not filled:
        raise ConfigurationError(f'EasyEDA {label}: empty nonzero fill.')
    shape=union_all(filled)
    if (shape.is_empty or not shape.is_valid or
            shape.geom_type not in ('Polygon','MultiPolygon')):
        raise ConfigurationError(f'EasyEDA {label}: invalid nonzero fill geometry.')
    return shape


def build_source_layout(source):
    """Detached physical/semantic model even if no excitation has been supplied.

    Missing external component footprints are explicit dependencies, not pads
    guessed from nearby routes. Call source_layout_geometry to request a solve.
    """
    data=source.semantics
    if data['unsupported_records']:
        raise ConfigurationError('EasyEDA '+data['unsupported_records'][0])
    layers={r['id']:r for r in data['layers']}
    from .easyeda_stackup import describe_source_stackup
    stack=describe_source_stackup(data,source.source_sha256)
    role={i:stack['role_by_layer_id'].get(i,
          'outline' if r['type']=='OUTLINE' else
          'dielectric' if r['type']=='SUBSTRATE' else 'omitted')
          for i,r in layers.items()}
    boards=[p for p in data['polygons'] if role[p['layer_id']]=='outline']
    if len(boards)!=1:
        raise ConfigurationError('EasyEDA source board outline: require one closed POLY R/L contour.')
    board=BoardOutline(tuple(map(tuple,boards[0]['ring_xy_m'])))
    z={p['role']:p['z_m'] for p in stack['copper_layers']}
    # Unresolved CAD epsilon is allowed in source INSPECTION only.
    # A full-wave solve validates materials before canonical geometry.
    dielectric_layers=[dict(outline=asdict(board),z_min_m=d['z_min_m'],
          z_max_m=d['z_max_m'],epsilon_r=d['epsilon_r'],loss_tangent=d['loss_tangent'],
          name=d['name']) for d in stack['dielectric_layers']]
    dielectric=DielectricLayer(**dielectric_layers[0])
    sheets=tuple(CopperLayer(p['role'],p['z_m'],'pec',p['thickness_m'],
                           p['conductivity_s_m'],p['source_sha256'])
                 for p in stack['copper_layers'])
    shapes=[]
    def add(id,net,layer,shape,kind):
        if role[layer] not in z:raise ConfigurationError(f'EasyEDA {id}: unsupported physical layer {layer}.')
        if net not in data['nets']:raise ConfigurationError(f'EasyEDA {id}: undeclared net {net!r}.')
        if shape.is_empty or not shape.is_valid:raise ConfigurationError(f'EasyEDA {id}: invalid source shape.')
        shapes.append((id,net,role[layer],shape,kind))
    for route in source.routes:
        if route.layer_role not in z:
            raise ConfigurationError(f'EasyEDA {route.id}: source route on unsupported {route.layer_role}.')
        add(route.id,route.net,route.layer_id,route_shape(route),'route')
    for p in data['polygons']:
        if role[p['layer_id']]!='outline':
            raise ConfigurationError(f"EasyEDA POLY {p['id']}: only board-outline POLY supported, not implicit copper fill.")
    for p in data['pads']:
        add(p['id'],p['net'],p['layer_id'],Polygon(p['ring_xy_m'],p.get('holes_xy_m',())),'pad')
    parents={p['id']:p for p in data['pours']}
    for p in data['poured']:
        if p['parent_id'] not in parents:raise ConfigurationError(f"EasyEDA POURED {p['id']}: missing parent POUR.")
        parent=parents[p['parent_id']]
        shape=complex_copper_shape(
            p.get('rings_xy_m',(p['ring_xy_m'],)),f"POURED {p['id']}")
        boundary=complex_copper_shape(
            parent.get('rings_xy_m',(parent['ring_xy_m'],)),f"POUR {parent['id']}")
        if not boundary.buffer(TOLERANCE_M).covers(shape):
            raise ConfigurationError(f"EasyEDA POURED {p['id']}: filled image leaves its source POUR boundary.")
        # Distinct islands may belong to distinct canonical conductors.
        # Preserve the source POURED record as one record in source_semantics,
        # but give each physical island its own feature identity/ownership.
        islands = [shape] if shape.geom_type=='Polygon' else list(shape.geoms)
        for i,island in enumerate(sorted(islands, key=lambda geom: (geom.bounds, geom.area))):
            name=p['id'] if len(islands)==1 else f"{p['id']}:island_{i:03d}"
            add(name,parent['net'],parent['layer_id'],island,'pour')
    for p in data['pours']:
        if not any(s['parent_id']==p['id'] for s in data['poured']):
            raise ConfigurationError(f"EasyEDA POUR {p['id']}: materialized POURED geometry unavailable; boundary is not filled copper.")
    copper_layer_ids={role[i]:i for i in layers if role[i] in z}
    for via in source.vias:
        if via.span_rule!='':raise ConfigurationError(f'EasyEDA VIA {via.id}: unresolved/unsupported span rule {via.span_rule!r}; through only.')
        from .gerber import _buffer,CURVE_ERROR_M
        disk=_buffer(Point(via.centre_xy_m),via.pad_diameter_m/2,CURVE_ERROR_M)
        for r in z:add(via.id+':'+r,via.net,copper_layer_ids[r],disk,'via_pad')
    # Physical through holes remove planar copper on both sides, including pours.
    # Annuli stay intact; plating is a separate explicitly configured solver model.
    for drill in data.get('footprint_drills',()):
        from .gerber import _buffer,CURVE_ERROR_M
        hole=_buffer(Point(drill['centre_xy_m']),drill['drill_diameter_m']/2,CURVE_ERROR_M)
        shapes=[(id,net,r,shape.difference(hole),kind) for id,net,r,shape,kind in shapes]
    for id,net,r,shape,kind in shapes:
        if shape.is_empty or not shape.is_valid:
            raise ConfigurationError(f'EasyEDA {id}: drill removes/invalidates source copper.')
        if not Polygon(board.vertices_xy_m).buffer(TOLERANCE_M).covers(shape):
            raise ConfigurationError(f'EasyEDA {id}: physical copper outside board outline.')
    # Nets define intent but cannot conceal a physical short in source copper.
    for i,(id,net,r,shape,_) in enumerate(shapes):
        for oid,on,orr,other,_ in shapes[:i]:
            if r==orr and net!=on and shape.intersects(other):
                raise ConfigurationError(f'EasyEDA source short: {id}/{oid}, nets {net}/{on}.')
    copper=[];owners={};conductor_nets={}
    for r in z:
        for net in sorted({n for _,n,rr,_,_ in shapes if rr==r}):
            entries=[s for s in shapes if s[1]==net and s[2]==r]
            merged=union_all([s[3] for s in entries])
            parts=[merged] if merged.geom_type=='Polygon' else list(getattr(merged,'geoms',()))
            for shape in sorted(parts,key=lambda s:(s.bounds,s.area)):
                id=f'{r}:source_copper_{len(copper):04d}'
                c=_polygon(id,shape,z[r],r);copper.append(c);conductor_nets[id]=net
            for id,_,_,shape,_ in entries:
                matches=[c.id for c in copper if c.layer_role==r and
                         copper_shape(c).buffer(TOLERANCE_M).covers(shape)]
                if len(matches)!=1:raise ConfigurationError(f'EasyEDA {id}: source primitive has ambiguous physical conductor ownership.')
                owners[id]=matches[0]
    routes=tuple(replace(r,conductor_id=owners[r.id]) for r in source.routes)
    pads=tuple(SourcePad(p['id'],p['net'],role[p['layer_id']],tuple(map(tuple,p['ring_xy_m'])),owners[p['id']],p['record_index'],tuple(tuple(map(tuple,h)) for h in p.get('holes_xy_m',())))
               for p in data['pads'])
    dependencies=[]
    resolved_ids={c['component_id'] for c in data.get('resolved_components',())}
    for c in data['components']:
        if c['id'] in resolved_ids:continue
        attrs={a['key']:a['value'] for a in data['attributes'] if a['parent_id']==c['id']}
        footprint=attrs.get('Footprint');name=attrs.get('Designator',c['id'])
        candidate=None
        if isinstance(footprint,str) and footprint and Path(footprint).name==footprint:
            root=Path(source.source_file).parent
            candidate=next((p for p in (root/'FOOTPRINT'/f'{footprint}.efoo',root.parent/'FOOTPRINT'/f'{footprint}.efoo') if p.is_file()),None)
        dependencies.append(dict(component_id=c['id'],designator=name,footprint_id=footprint,
            status='external_footprint_not_supported' if candidate else 'footprint_geometry_unavailable',
            available_path=str(candidate) if candidate else None,
            message=f'source component {name} ({c["id"]}) footprint pad geometry '+
                    ('available externally but this subset does not instantiate it' if candidate else 'unavailable')+
                    f'; footprint={footprint!r}; no pads inferred from tracks'))
    assumptions=['source copper: PEC zero-thickness; supplied copper thickness retained as material metadata',
                 'dielectric layers: only SUBSTRATE; soldermask omitted pending effective-epsilon model',
                 'conductivity 58 MS/m is unused PEC metadata, not manufacturer-verified',
                 'soldermask/paste/silkscreen omitted; raw LAYER_PHYS retained',
                 'source absolute pads: ideal terminal regions; pad parasitics and internal lead impedance omitted']
    return dict(design_source='easyeda_source',manufacturing_validation='not_requested',
        outline=asdict(board),dielectric=asdict(dielectric),
        dielectric_layers=dielectric_layers,copper_layers=[asdict(s) for s in sheets],
        source_stackup=stack,
        copper=[asdict(c) for c in copper],routes=[asdict(r) for r in routes],pads=[asdict(p) for p in pads],
        vias=[asdict(v) for v in source.vias],conductor_nets=conductor_nets,
        feature_owners=owners,feature_kinds={id:kind for id,_,_,_,kind in shapes},source_semantics=data,assumptions=assumptions,
        missing_dependencies=dependencies,source_file=source.source_file,source_sha256=source.source_sha256,
        resolved_components=data.get('resolved_components',[]),footprint_drills=data.get('footprint_drills',[]),
        project_provenance=data.get('project_provenance'),source_pad_provenance=data['pads'],
        contact_audit=_contact_audit(shapes,owners,data,source))


def _contact_audit(shapes, owners, data, source):
    """Physical same-layer contacts, after exact net-short and ownership checks.

    Open/unconnected pads are recorded as such, never promoted to connections.
    Via annuli must belong to their declared net on both physical layers.
    """
    pads=[]
    for id,net,role,shape,kind in shapes:
        if kind!='pad':continue
        contacts=[oid for oid,on,orr,other,ok in shapes if oid!=id and orr==role and shape.intersects(other)]
        pads.append(dict(pad_id=id,net=net,layer_role=role,conductor_id=owners[id],
                         physical_contacts=sorted(contacts),ownership_status='passed'))
    return dict(status='passed',meaning='physical ownership/short audit, not electromagnetic validation',
                pads=pads,via_pad_owners={v.id:{r:owners[v.id+':'+r] for r in sorted({role for id,net,role,shape,kind in shapes if id.startswith(v.id+':')})} for v in source.vias})


def source_layout_geometry(layout,override):
    """Canonical PcbGeometry for existing FAST, with explicit physical contacts.

    Overrides contain port (physical-config explicit convention) and optionally
    drills. They never contain filenames or silently override source materials.
    """
    if layout['missing_dependencies']:
        raise ConfigurationError('EasyEDA missing source dependency: '+layout['missing_dependencies'][0]['message'])
    if not isinstance(override,dict) or set(override)-{'port','drills','component_values','dielectrics'}:
        raise ConfigurationError('EasyEDA source override accepts port, drills, component_values and explicit dielectric material values only.')
    if sum(c['role']=='source' for c in layout.get('resolved_components',()))>1:
        raise ConfigurationError('EasyEDA FAST has one excitation; multiple CAD sources unsupported, not omitted.')
    p=override.get('port')
    if isinstance(p,dict) and p.get('mode')=='source':
        p=_source_port_config(layout,p)
    if not isinstance(p,dict) or p.get('mode')!='explicit':
        raise ConfigurationError('EasyEDA source excitation undefined: provide --source-config with explicit port negative_mm/positive_mm/width_mm; no automatic pad guess.')
    from .easyeda import number
    try:
        n=tuple(number(v,'port negative')*1e-3 for v in p['negative_mm'])
        pos=tuple(number(v,'port positive')*1e-3 for v in p['positive_mm'])
        width=number(p['width_mm'],'port width')*1e-3
        if len(n)!=2 or len(pos)!=2 or width<=0:raise ValueError('invalid XY/width')
    except (KeyError,TypeError,ValueError) as exc:raise ConfigurationError(f'EasyEDA explicit source port: {exc}') from exc
    board=BoardOutline(tuple(map(tuple,layout['outline']['vertices_xy_m'])))
    from .easyeda_stackup import describe_source_stackup
    stack=describe_source_stackup(layout['source_semantics'],layout['source_sha256'],
                                  override.get('dielectrics'),require_materials=True)
    dielectrics=tuple(DielectricLayer(board,d['z_min_m'],d['z_max_m'],d['epsilon_r'],
                        d['loss_tangent'],d['name']) for d in stack['dielectric_layers'])
    first=dielectrics[0]
    from .source_ir import SourceRoutePrimitive
    geometry=PcbGeometry('pcb',board,[CopperPolygon(**c) for c in layout['copper']],
        Substrate(board,first.z_min_m,first.z_max_m,first.epsilon_r,first.loss_tangent),
        PcbPort('easyeda_source',n,pos,width),
        assumptions=layout['assumptions'],dielectric_layers=dielectrics,
        copper_layers=tuple(CopperLayer(**c) for c in layout['copper_layers']),
        source_routes=tuple(SourceRoutePrimitive(**r) for r in layout['routes']),
        source_pads=tuple(SourcePad(**p) for p in layout['pads']),
        design_source=dict(kind='easyeda_source',source_file=layout['source_file'],source_sha256=layout['source_sha256'],
            conductor_nets=layout['conductor_nets'],feature_owners=layout['feature_owners'],
            feature_kinds=layout['feature_kinds'],resolved_components=layout.get('resolved_components',[]),
            project_provenance=layout.get('project_provenance'),source_pad_provenance=layout.get('source_pad_provenance',[]),
            contact_audit=layout.get('contact_audit'),manufacturing_validation='not_requested',
            resolved_source_stackup=stack,override=override))
    geometry.components=_source_components(layout,geometry,override.get('component_values',{}))
    if layout['vias'] or layout.get('footprint_drills'):
        settings=override.get('drills',{})
        plating=settings.get('pth_plating_um')
        needs_plating=bool(layout['vias']) or any(v['plated'] for v in layout.get('footprint_drills',()))
        if needs_plating and (settings.get('pth_model')!='solid_pec_equivalent' or isinstance(plating,bool) or not isinstance(plating,(int,float)) or not isfinite(plating) or plating<=0):
            raise ConfigurationError('EasyEDA VIA: source gives drill/pad diameters, not barrel plating; explicit drills.pth_plating_um and solid_pec_equivalent required.')
        from .drills import connected_layers
        drills=[]
        for v in layout['vias']:
            x,y=v['centre_xy_m'];radius=v['drill_diameter_m']/2+plating*1e-6
            if radius>v['pad_diameter_m']/2:raise ConfigurationError(f'EasyEDA VIA {v["id"]}: plating exceeds source pad radius.')
            drills.append(PcbDrill(v['id'],x,y,v['drill_diameter_m'],True,'PTH','EasyEDA VIA',v['source_sha256'],
                plating*1e-6,radius,connected_layers(geometry,x,y,radius)))
        for v in layout.get('footprint_drills',()):
            x,y=v['centre_xy_m'];diameter=v['drill_diameter_m']
            radius=diameter/2+plating*1e-6 if v['plated'] else None
            if not v['plated']:
                drills.append(PcbDrill(v['id'],x,y,diameter,False,'NPTH','EasyEDA PAD',v['source_sha256']))
                continue
            # Annular pads are actual copper; prove barrel contact and net on each layer.
            for role in ('top','bottom'):
                touched=[c for c in geometry.copper if c.layer_role==role and copper_shape(c).distance(Point(x,y))<=radius]
                if not touched or any(layout['conductor_nets'][c.id]!=v['net'] for c in touched):
                    raise ConfigurationError(f"EasyEDA PAD {v['id']}: PTH plating/contact conflicts with net {v['net']} on {role}.")
            drills.append(PcbDrill(v['id'],x,y,diameter,True,'PTH','EasyEDA PAD',v['source_sha256'],
                plating*1e-6,radius,connected_layers(geometry,x,y,radius)))
        geometry.drills=tuple(drills)
    validate_pcb_geometry(geometry)
    from .bundle import audit_physical_feed
    audit_physical_feed(geometry)
    return geometry


def _component_terminals(layout, component):
    """Supported solver contact subset: exactly two top, axis-aligned RECT pads.

    The actual clear interval comes from final copper, not nominal aperture edges.
    """
    from .components import terminal_gap
    ids=component['pad_ids']
    entries=[p for p in layout['source_pad_provenance'] if p['id'] in ids]
    if len(entries)!=2 or {p['pad_number'] for p in entries}!={'1','2'}:
        raise ConfigurationError(f"EasyEDA {component['designator']}: solver contacts require exactly pads 1/2.")
    entries.sort(key=lambda p:p['pad_number']);placements=[]
    top_ids={p['id'] for p in layout['pads'] if p['layer_role']=='top'}
    for p in entries:
        shape=Polygon(p['ring_xy_m'],p.get('holes_xy_m',()))
        if p['id'] not in top_ids or p.get('drill_id') or not shape.equals(shape.envelope):
            raise ConfigurationError(f"EasyEDA {p['id']}: solver contact needs axis-aligned rectangular top SMD, not a guessed bbox.")
        x0,y0,x1,y1=shape.bounds
        placements.append((tuple(p['centre_xy_m']),(x1-x0,y1-y0)))
    copper=[CopperPolygon(**c) for c in layout['copper']]
    gap=terminal_gap(component['designator'],placements,copper)
    return entries,placements,gap


def _source_port_config(layout, config):
    index=config.get('source_index')
    if type(index) is not int or index<0:
        raise ConfigurationError('EasyEDA port mode=source requires explicit source_index integer.')
    candidates=[c for c in layout['resolved_components'] if c['role']=='source' and c['source_index']==index]
    if len(candidates)!=1:
        raise ConfigurationError(f'EasyEDA source index {index}: missing/ambiguous explicit CAD source.')
    if sum(c['role']=='source' for c in layout['resolved_components'])!=1:
        raise ConfigurationError('EasyEDA FAST currently has one excitation; multiple CAD sources unsupported, not omitted.')
    _,_,(_,start,stop,_,width)=_component_terminals(layout,candidates[0])
    return dict(mode='explicit',negative_mm=[v*1e3 for v in start],positive_mm=[v*1e3 for v in stop],width_mm=width*1e3)


def _source_components(layout,geometry,values):
    from .components import ideal_value
    from .model import PcbLumpedComponent
    if not isinstance(values,dict):raise ConfigurationError('EasyEDA component_values must be an object.')
    known={c['designator']:c for c in layout.get('resolved_components',()) if c['role']!='source'}
    if set(values)-set(known):raise ConfigurationError('EasyEDA component_values names unknown component or source.')
    result=[]
    for name,setting in sorted(values.items()):
        if not isinstance(setting,dict) or set(setting)!={'kind','value'} or setting['kind'] not in ('R','L','C'):
            raise ConfigurationError(f'EasyEDA {name}: explicit ideal kind R/L/C and value with unit required.')
        value=ideal_value(setting['kind'],setting['value'])
        entries,placements,(axis,start,stop,window,width)=_component_terminals(layout,known[name])
        digest=layout['source_sha256']
        result.append(PcbLumpedComponent(name,setting['kind'],value,setting['value'],entries[0]['net'],entries[1]['net'],
            placements[0][0],placements[1][0],'top',axis,start,stop,window,digest,digest))
    return tuple(result)
