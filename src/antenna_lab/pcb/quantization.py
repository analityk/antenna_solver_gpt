"""Detached projection and fail-closed topology audit. No mesh/native imports.

Counts cover spatial scalar occurrences in the modeled records (including
geometric dimensions); provenance and the legacy substrate alias are excluded.
XY maximum includes Euclidean point motion and absolute dimension changes.
Layer thicknesses are rounded independently and interfaces accumulated in ticks.
Circles use integer radius and derived diameter=2*radius, never a half-tick radius.
"""
from decimal import Decimal
import json
from math import hypot

from shapely.geometry import Polygon, Point, LineString
from shapely import union_all

from antenna_lab.core.config import ConfigurationError
from .validation import TOLERANCE_M, validate_pcb_geometry
from .grid import (PcbGrid, QuantizedPcbGeometry, TickCopper, TickDielectric,
                   TickCopperLayer, TickPort, TickDrill, TickComponent, TickSource)


class QuantizationError(ConfigurationError):
    """Failure with a detached, strict-JSON audit; no usable geometry returned."""
    def __init__(self, audit):
        self.audit=json.loads(json.dumps(audit,allow_nan=False))
        reasons=audit['collapsed_features']+audit['topology_changes']
        super().__init__('PCB quantization rejected: '+'; '.join(reasons[:3]))


class _Projection:
    def __init__(self, grid):
        self.grid=grid
        self.report=dict(quantum_um=grid.quantum_um,quantum_m=grid.quantum_m,
            total_spatial_values_examined=0,already_on_grid=0,adjusted=0,
            maximum_xy_displacement_m=0.,maximum_z_displacement_m=0.,
            collapsed_features=[],topology_changes=[],examples=[],
            rounding_policy='nearest; exact decimal ties away from zero; float boundary guard 2 ULP',
            circle_policy='nearest integer radius; diameter = 2 * radius; plating input retained only as provenance',
            example_limit=20,topology_status='not_audited')

    def value(self, raw, label, axis='xy', tick=None):
        g=self.grid;tick=g.nearest_tick(raw) if tick is None else tick
        if abs(tick)>2**52:
            raise ConfigurationError('PCB geometry exceeds exact-integer range of the topology audit backend.')
        source=Decimal(str(raw));modeled=Decimal(tick)*g.quantum_decimal_m
        delta=float(modeled-source)
        same=g._ticks_decimal(raw)==Decimal(tick)
        self.report['total_spatial_values_examined']+=1
        self.report['already_on_grid' if same else 'adjusted']+=1
        key='maximum_'+axis+'_displacement_m'
        self.report[key]=max(self.report[key],abs(delta))
        if not same and len(self.report['examples'])<20:
            self.report['examples'].append(dict(feature=label,source_m=float(source),tick=tick,
                modeled_m=float(modeled),delta_m=delta))
        return tick

    def point(self, p, label):
        result=tuple(self.value(v,f'{label}.{a}') for a,v in zip('xy',p))
        movement=hypot(*(self.grid.to_metres(v)-raw for v,raw in zip(result,p)))
        self.report['maximum_xy_displacement_m']=max(self.report['maximum_xy_displacement_m'],movement)
        return result

    def positive(self, raw, label, axis='xy'):
        tick=self.value(raw,label,axis)
        if tick<1:self.report['collapsed_features'].append(label+': nonzero dimension collapsed below one tick')
        return tick

    def ring(self, ring, label):
        result=[]
        for i,p in enumerate(ring):
            value=self.point(p,f'{label}[{i}]')
            if not result or result[-1]!=value:result.append(value)
        if len(result)>1 and result[-1]==result[0]:result.pop()  # Cyclic consecutive duplicate.
        if len(set(result))<3:
            self.report['collapsed_features'].append(label+': fewer than three unique tick vertices')
        return tuple(result)

    def issue(self, text):
        if text not in self.report['topology_changes']:self.report['topology_changes'].append(text)

    def finish(self):
        failed=bool(self.report['collapsed_features'] or self.report['topology_changes'])
        self.report['topology_status']='FAIL' if failed else 'PASS'
        if failed:raise QuantizationError(self.report)
        return json.loads(json.dumps(self.report,allow_nan=False))


def quantize_pcb_geometry(geometry, grid=PcbGrid()):
    """Return (immutable tick geometry, detached audit), or QuantizationError.

    Imported SI geometry, source values and material parameters are never edited.
    This API has intentionally no caller in the active PCB workflow.
    """
    project=_Projection(grid);p=project
    try:validate_pcb_geometry(geometry)
    except ConfigurationError as exc:
        p.issue('invalid raw geometry: '+str(exc));p.finish()
    source_json=json.dumps(geometry.as_dict(),sort_keys=True,allow_nan=False)
    outline=p.ring(geometry.outline.vertices_xy_m,'outline')
    dielectrics=[];interfaces={0.:0};top=0
    for i,d in enumerate(geometry.dielectrics):
        thickness=Decimal(str(d.z_max_m))-Decimal(str(d.z_min_m))
        count=p.positive(thickness,f'dielectric[{i}].thickness','z')
        bottom=top-count
        p.value(d.z_max_m,f'dielectric[{i}].top','z',top)
        p.value(d.z_min_m,f'dielectric[{i}].bottom','z',bottom)
        interfaces[d.z_max_m]=top;interfaces[d.z_min_m]=bottom
        dielectrics.append(TickDielectric(getattr(d,'name','substrate'),p.ring(d.outline.vertices_xy_m,
            f'dielectric[{i}].outline'),bottom,top,count,d.epsilon_r,d.loss_tangent))
        top=bottom
    layer_z={c.role:interfaces[c.z_m] for c in geometry.copper_layers}
    layers=tuple(TickCopperLayer(c.role,p.value(c.z_m,c.role+'.z','z',layer_z[c.role]),c.model,
                 c.thickness_m,c.conductivity_s_m,c.source_sha256) for c in geometry.copper_layers)
    copper=tuple(TickCopper(c.id,c.layer_role,p.value(c.z_m,c.id+'.z','z',layer_z.get(c.layer_role,0)),
        p.ring(c.vertices_xy_m,c.id+'.outer'),tuple(p.ring(h,f'{c.id}.hole[{i}]') for i,h in enumerate(c.holes_xy_m)))
        for c in geometry.copper)
    port=TickPort(geometry.port.id,p.point(geometry.port.negative_xy_m,'port.negative'),
                  p.point(geometry.port.positive_xy_m,'port.positive'),p.positive(geometry.port.width_m,'port.width'))
    if port.negative==port.positive:p.report['collapsed_features'].append('port: nonzero gap collapsed to zero ticks')
    drills=[]
    for d in geometry.drills:
        radius=p.positive(Decimal(str(d.drill_diameter_m))/2,d.id+'.radius')
        diameter=p.value(d.drill_diameter_m,d.id+'.diameter',tick=2*radius)
        outer=p.positive(d.equivalent_outer_radius_m,d.id+'.outer_radius') if d.plated else None
        if d.plated and outer<radius:p.issue(d.id+': equivalent via radius is smaller than drill radius')
        drills.append(TickDrill(d.id,p.point((d.x_m,d.y_m),d.id+'.centre'),radius,diameter,d.plated,outer,
            d.connected_layer_roles,d.source_file_role,d.source_tool,d.source_file_sha256,d.plating_thickness_m))
    components=[]
    for c in geometry.components:
        a,b=p.point(c.gap_start_xy_m,c.id+'.gap_start'),p.point(c.gap_stop_xy_m,c.id+'.gap_stop')
        pins=(p.point(c.pin1_xy_m,c.id+'.pin1'),p.point(c.pin2_xy_m,c.id+'.pin2'))
        if a==b or pins[0]==pins[1]:p.report['collapsed_features'].append(c.id+': nonzero terminal gap/pin spacing collapsed')
        components.append(TickComponent(c.id,c.kind,c.value_si,c.value_text,c.pin1_net,c.pin2_net,*pins,c.layer,
            c.axis,a,b,p.ring(c.contact_window_xy_m,c.id+'.contact_window'),c.source_sha256,c.flying_probe_sha256))
    source=None
    if geometry.source_port:
        s=geometry.source_port
        source=TickSource(s.source_refdes,s.source_pin_nets,p.point(s.pin1_xy_m,'source.pin1'),
            p.point(s.pin2_xy_m,'source.pin2'),s.enet_sha256,s.flying_probe_sha256)
    result=QuantizedPcbGeometry(grid,geometry.model,outline,copper,tuple(dielectrics),layers,port,
        tuple(drills),tuple(components),source,tuple(geometry.assumptions),source_json)
    _audit(geometry,result,p)
    return result,p.finish()


def _parts(shape):
    return [shape] if shape.geom_type=='Polygon' else [g for g in getattr(shape,'geoms',()) if g.geom_type=='Polygon']


def _audit(raw, modeled, p):
    """No make_valid/buffer repair. Buffers below represent NPTH circles only.

    Polygon topology operates in integer tick units (double backend, <=2**52).
    Raw membership retains the existing numerical tolerance; modeled membership
    uses exact tick geometry. PTH contacts use analytic point-to-region distance.
    """
    q=modeled.grid.quantum_m;raw_tol=TOLERANCE_M/q
    def xy(point):return tuple(v/q for v in point)
    def raw_shape(c):return Polygon(tuple(map(xy,c.vertices_xy_m)),[tuple(map(xy,h)) for h in c.holes_xy_m])
    def valid_polygon(outer,holes,label):
        if len(set(outer))<3 or any(len(set(h))<3 for h in holes):return None
        s=Polygon(outer,holes)
        if s.is_empty or not s.is_valid or s.area<=0:
            p.issue(label+': invalid quantized polygon topology (no repair)');return None
        return s
    board=valid_polygon(modeled.outline,(),'board outline')
    raw_board=Polygon(tuple(map(xy,raw.outline.vertices_xy_m)))
    for d in modeled.dielectrics:
        ds=valid_polygon(d.outline,(),d.name+' outline')
        if ds is not None and board is not None and not ds.equals(board):p.issue(d.name+': quantized outline differs from board')
    old={c.id:raw_shape(c) for c in raw.copper}
    new={c.id:valid_polygon(c.outer,c.holes,c.id) for c in modeled.copper}
    for c in modeled.components:
        valid_polygon(c.contact_window,(),c.id+' contact window')
    if any(s is None for s in new.values()) or board is None or p.report['collapsed_features']:
        return  # All scalar projection counts complete; dependent topology cannot be evaluated.
    roles={c.id:c.layer_role for c in raw.copper}
    # Drills cut the physical image. Circular voids use the existing 128-segment
    # quadrant approximation; this is circle construction, never polygon repair.
    for d in raw.drills:
        if not d.plated:
            disk=Point(xy((d.x_m,d.y_m))).buffer(d.drill_diameter_m/2/q,quad_segs=128)
            old={key:s.difference(disk) for key,s in old.items()}
    for d in modeled.drills:
        if not d.plated:
            disk=Point(d.centre).buffer(d.radius,quad_segs=128)
            new={key:s.difference(disk) for key,s in new.items()}
    for key in old:
        old_parts,new_parts=_parts(old[key]),_parts(new[key])
        if (len(old_parts),sum(len(s.interiors) for s in old_parts)) != (len(new_parts),sum(len(s.interiors) for s in new_parts)):
            p.issue(key+': individual conductor connectivity/holes changed')
    def counts(shapes,role):
        merged=union_all([s for key,s in shapes.items() if roles[key]==role])
        parts=_parts(merged)
        return dict(conductor_regions=len(parts),holes=sum(len(s.interiors) for s in parts))
    p.report['layers']={}
    for role in sorted(set(roles.values())):
        before,after=counts(old,role),counts(new,role)
        p.report['layers'][role]=dict(source=before,modeled=after)
        if before!=after:p.issue(role+': conductor region/hole count changed')
    # Identity-level contacts catch touching-point shorts and changes hidden by
    # unchanged aggregate region counts (including wrong-net contacts).
    ids=list(old)
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            if roles[a]==roles[b] and old[a].intersects(old[b])!=new[a].intersects(new[b]):
                p.issue(f'{a}/{b}: conductor contact changed')
    def members(point,shapes,layer,tolerance):
        pt=Point(point)
        return tuple(key for key,s in shapes.items() if roles[key]==layer and (s.covers(pt) or s.distance(pt)<=tolerance))
    terminals=[]
    def terminal(label,a,b,layer='top'):
        terminals.append((label,a,b,layer))
        before=members(a,old,layer,raw_tol);after=members(b,new,layer,0.)
        if len(before)!=1 or before!=after:p.issue(f'{label}: terminal ownership {before} -> {after}')
        if raw_board.covers(Point(a)) and not board.covers(Point(b)):
            p.issue(label+': terminal moved outside board')
    def gap(label,a,b,qa,qb,layer='top'):
        if qa==qb:return
        before=LineString((a,b));after=LineString((qa,qb))
        raw_length=sum(before.intersection(s).length for k,s in old.items() if roles[k]==layer)
        new_length=sum(after.intersection(s).length for k,s in new.items() if roles[k]==layer)
        if raw_length<=raw_tol and new_length>0:p.issue(label+': previously empty gap now contains copper')
    terminal('port.negative',xy(raw.port.negative_xy_m),modeled.port.negative)
    terminal('port.positive',xy(raw.port.positive_xy_m),modeled.port.positive)
    gap('port',xy(raw.port.negative_xy_m),xy(raw.port.positive_xy_m),modeled.port.negative,modeled.port.positive)
    for c,t in zip(raw.components,modeled.components):
        for name,a,b in [('pin1',c.pin1_xy_m,t.pin1),('pin2',c.pin2_xy_m,t.pin2),
                         ('gap_start',c.gap_start_xy_m,t.gap_start),('gap_stop',c.gap_stop_xy_m,t.gap_stop)]:
            terminal(c.id+'.'+name,xy(a),b,c.layer)
        gap(c.id,xy(c.gap_start_xy_m),xy(c.gap_stop_xy_m),t.gap_start,t.gap_stop,c.layer)
    if raw.source_port:
        terminal('source.pin1',xy(raw.source_port.pin1_xy_m),modeled.source_port.pin1)
        terminal('source.pin2',xy(raw.source_port.pin2_xy_m),modeled.source_port.pin2)
    # Region totals alone cannot detect a moving NPTH cut which disconnects a
    # different terminal pair while leaving the number of fragments unchanged.
    def terminal_network(shapes, drilled, quantized):
        nodes=[(key,part) for key,s in shapes.items() for part in _parts(s)]
        parent=list(range(len(nodes)))
        def root(i):
            while parent[i]!=i:
                parent[i]=parent[parent[i]];i=parent[i]
            return i
        def join(a,b):parent[root(b)]=root(a)
        for i,(ka,a) in enumerate(nodes):
            for j,(kb,b) in enumerate(nodes[:i]):
                if roles[ka]==roles[kb] and a.intersects(b):join(i,j)
        for d in drilled:
            if not d.plated:continue
            point=Point(d.centre if quantized else xy((d.x_m,d.y_m)))
            radius=d.outer_radius if quantized else d.equivalent_outer_radius_m/q
            touching=[i for i,(_,shape) in enumerate(nodes) if point.distance(shape)<=radius]
            for i in touching[1:]:join(touching[0],i)
        tolerance=0. if quantized else raw_tol
        return [{root(i) for i,(key,shape) in enumerate(nodes)
                 if roles[key]==layer and shape.distance(Point(b if quantized else a))<=tolerance}
                for _,a,b,layer in terminals]
    before_network=terminal_network(old,raw.drills,False)
    after_network=terminal_network(new,modeled.drills,True)
    for i,(name,*_) in enumerate(terminals):
        for j in range(i):
            if bool(before_network[i]&before_network[j])!=bool(after_network[i]&after_network[j]):
                p.issue(f'{name}/{terminals[j][0]}: terminal connectivity changed (short/disconnection)')
    def contacts(centre,radius,shapes):
        pt=Point(centre)
        return tuple(k for k,s in shapes.items() if pt.distance(s)<=radius)
    p.report['drill_contacts']={}
    for d,t in zip(raw.drills,modeled.drills):
        before_radius=(d.equivalent_outer_radius_m if d.plated else d.drill_diameter_m/2)/q
        after_radius=t.outer_radius if t.plated else t.radius
        centre=Point(t.centre)
        if not board.contains(centre) or centre.distance(board.boundary)<after_radius:
            p.issue(d.id+': drill extends outside quantized board')
        if t.plated:
            before=contacts(xy((d.x_m,d.y_m)),before_radius,old);after=contacts(t.centre,after_radius,new)
            before_roles=tuple(sorted({roles[k] for k in before}));after_roles=tuple(sorted({roles[k] for k in after}))
            p.report['drill_contacts'][d.id]=dict(source=before_roles,modeled=after_roles)
            if before!=after or before_roles!=after_roles:p.issue(d.id+': via copper/layer contacts changed')
            if len(after_roles)<2:p.issue(d.id+': orphan quantized PTH')
        for other in modeled.drills:
            if t.id<other.id and hypot(*(a-b for a,b in zip(t.centre,other.centre)))<=after_radius+(other.outer_radius if other.plated else other.radius):
                p.issue(f'{t.id}/{other.id}: quantized drills overlap')
    # Full physical source rectangle safety, including transverse contact.
    a,b=modeled.port.negative,modeled.port.positive
    length=hypot(b[0]-a[0],b[1]-a[1])
    if length:
        nx,ny=-(b[1]-a[1])*modeled.port.width/(2*length),(b[0]-a[0])*modeled.port.width/(2*length)
        corners=[(a[0]+nx,a[1]+ny),(b[0]+nx,b[1]+ny),(b[0]-nx,b[1]-ny),(a[0]-nx,a[1]-ny)]
        region=Polygon(corners)
        for key,s in new.items():
            if roles[key]=='top' and region.intersection(s).area>0:p.issue('port: quantized source rectangle intersects copper')
        for label,face,point in [('negative',LineString((corners[0],corners[3])),a),('positive',LineString((corners[1],corners[2])),b)]:
            own=members(point,new,'top',0.)
            if len(own)==1 and not new[own[0]].covers(face):p.issue('port.'+label+': full-width contact disconnected')
        for d in modeled.drills:
            if Point(d.centre).distance(region)<=(d.outer_radius if d.plated else d.radius):p.issue(d.id+': quantized drill intersects source')
