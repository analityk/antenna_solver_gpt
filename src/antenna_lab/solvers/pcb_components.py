"""Pure component-box resolution and native ideal R/C/L installation.

Use existing transverse/Z cells. Volumetric AddBox with caps=True connects the
above-plane lumped region to planar terminal faces at z=0. No package geometry,
parasitics or new Z anchors. LEtype=1 (series) supports a pure ideal inductor.
"""
from dataclasses import asdict, dataclass
from math import isfinite
from shapely.geometry import LineString, Point, box

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.regions import copper_shape
from antenna_lab.pcb.validation import TOLERANCE_M


@dataclass(frozen=True)
class PcbComponentSpec:
    id: str
    kind: str
    value_si: float
    direction: str
    start_m: tuple[float, float, float]
    stop_m: tuple[float, float, float]
    priority: int = 5
    caps: bool = True
    LEtype: int = 1


def resolve_component_boxes(geometry, axes):
    """Smallest legal existing transverse interval; exact longitudinal faces.

    Continuous contact/gap audit protects unrelated copper. Components cannot
    overlap another component, source or drill. Failure never edits the mesh.
    """
    if not geometry.components: return ()
    axes=tuple(tuple(a) for a in axes)
    if 0. not in axes[2] or not any(v>0 for v in axes[2]):
        raise ConfigurationError('Components require exact z=0 and an existing positive air line.')
    height=next(v for v in axes[2] if v>0)
    shapes=[copper_shape(c) for c in geometry.top_copper]
    n,p=geometry.port.negative_xy_m,geometry.port.positive_xy_m
    my=(n[1]+p[1])/2;half=geometry.port.width_m/2
    occupied=[('CSRC/source',box(n[0],my-half,p[0],my+half))]
    result=[]
    for c in geometry.components:
        if c.kind not in ('R','C','L') or not isfinite(c.value_si) or c.value_si<=0 or c.layer!='top':
            raise ConfigurationError(f'{c.id}: unsupported/invalid ideal component.')
        axis='xy'.index(c.axis);trans=1-axis
        start,stop=c.gap_start_xy_m,c.gap_stop_xy_m
        if abs(start[trans]-stop[trans])>TOLERANCE_M:
            raise ConfigurationError(f'{c.id}: normalized component must be axis aligned.')
        low,high=sorted((start[axis],stop[axis]))
        if high-low<=TOLERANCE_M or low not in axes[axis] or high not in axes[axis]:
            raise ConfigurationError(f'{c.id}: missing exact longitudinal terminal mesh lines.')
        owners=[]
        for pin in (c.pin1_xy_m,c.pin2_xy_m):
            found=[i for i,s in enumerate(shapes) if s.buffer(TOLERANCE_M).covers(Point(pin))]
            if len(found)!=1: raise ConfigurationError(f'{c.id}: ambiguous/missing pin contact.')
            owners.append(found[0])
        if start[axis]>stop[axis]: owners.reverse()
        lo=min(p[trans] for p in c.contact_window_xy_m);hi=max(p[trans] for p in c.contact_window_xy_m)
        def xy(u,v):return (u,v) if axis==0 else (v,u)
        candidates=[]
        for a,b in zip(axes[trans],axes[trans][1:]):
            if a<lo or b>hi or b<=a: continue
            faces=[LineString((xy(u,a),xy(u,b))) for u in (low,high)]
            if any([i for i,s in enumerate(shapes) if s.buffer(TOLERANCE_M).intersects(face)]!=[owner]
                   or not shapes[owner].buffer(TOLERANCE_M).covers(face)
                   for face,owner in zip(faces,owners)):continue
            x0,y0=xy(low,a);x1,y1=xy(high,b);region=box(x0,y0,x1,y1)
            interior=region.buffer(-TOLERANCE_M,join_style=2)
            if interior.is_empty or any(s.intersects(interior) for s in shapes):continue
            if any(region.intersects(other) for _,other in occupied):continue
            if any(region.distance(Point(d.x_m,d.y_m)) <= (d.equivalent_outer_radius_m if d.plated else d.drill_diameter_m/2)
                   for d in geometry.drills):continue
            candidates.append((b-a,abs((a+b)-(lo+hi)),a,b,region))
        if not candidates:
            raise ConfigurationError(f'{c.id}: no legal existing transverse cell with full terminal contact and empty gap; '
                                     'choose an explicitly finer quality/resolution or revise pad geometry (no hidden refinement).')
        _,_,a,b,region=min(candidates,key=lambda v:v[:3])
        lower=xy(low,a)+(0.,);upper=xy(high,b)+(height,)
        result.append(PcbComponentSpec(c.id,c.kind,c.value_si,c.axis,lower,upper))
        occupied.append((c.id,region))
    return tuple(result)


def install_components(csx, specs):
    """Caller audits the frozen grid before/after; metadata contains no natives."""
    result=[]
    for s in specs:
        parameters=dict(ny='xyz'.index(s.direction),caps=s.caps,LEtype=s.LEtype,**{s.kind:s.value_si})
        prop=csx.AddLumpedElement('pcb_component_'+s.id,**parameters)
        if prop is None: raise ConfigurationError(f'{s.id}: native AddLumpedElement returned None.')
        prop.AddBox(start=list(s.start_m),stop=list(s.stop_m),priority=s.priority)
        result.append(dict(asdict(s),native_parameters=parameters,model='ideal_lumped',
            contact_policy='existing first air Z cell; PEC end caps connect planar terminal faces'))
    return result
