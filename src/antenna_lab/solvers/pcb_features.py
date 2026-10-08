"""Pure copper/mesh fidelity contract; never changes polygons or mesh lines.

Compacted widths and gaps use thirds or resolved subcell edge arrangements.
Curves retain continuous CSXCAD geometry and feature-scale vicinity resolution,
not a mesh plane for each tessellation vertex. Their final cell envelope
must bracket the modeled topology: fully covered cells and intersected cells
must both preserve regions/holes, with no possible inter-conductor contact.
This conservative sufficient test may reject a usable mesh; it is not a native
Yee occupancy or electromagnetic convergence claim.
"""
from bisect import bisect_left, bisect_right
from math import hypot, ulp

from shapely import box, covers, intersection, area, union_all
from shapely.geometry import LineString, Polygon

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.regions import copper_shape
from antenna_lab.pcb.validation import TOLERANCE_M

MAX_FIDELITY_CELLS = 1_000_000


def represented_coordinate(value, ordered, scale_m=0.):
    """Exact first; only binary arithmetic residue may share an existing line.

    Eight ULPs at board/coordinate magnitude cover translation cancellation;
    capped by the existing geometry tolerance, unrelated to wavelength or CAD
    resolution. No geometry is moved. Distinct physical features outside this
    machine-arithmetic allowance must retain their own exact coordinates.
    """
    index=bisect_left(ordered,value)
    candidates=ordered[max(0,index-1):index+1]
    if value in candidates:return value
    matches=[v for v in candidates if abs(v-value)<=min(TOLERANCE_M,8*ulp(max(abs(v),abs(value),scale_m)))]
    return min(matches,key=lambda v:(abs(v-value),v)) if matches else None


def copper_features(geometry):
    """Merge continuous collinear runs; never turn vertex coordinates into lines."""
    records, curved = [], []
    for c in geometry.copper:
        for ri, ring in enumerate((c.vertices_xy_m, *c.holes_xy_m)):
            base = dict(copper_id=c.id, layer_role=c.layer_role, ring=ri)
            groups={}; oblique=False
            for a,b in zip(ring, (*ring[1:],ring[0])):
                if a==b:continue
                if a[0]==b[0] or a[1]==b[1]:
                    axis=0 if a[0]==b[0] else 1
                    groups.setdefault((axis,a[axis]),[]).append(sorted((a[1-axis],b[1-axis])))
                else:oblique=True
            for (axis,v),spans in sorted(groups.items()):
                merged=[]
                for lo,hi in sorted(spans):
                    if merged and lo<=merged[-1][1]:merged[-1][1]=max(hi,merged[-1][1])
                    else:merged.append([lo,hi])
                records.extend(dict(base,kind='physical_boundary_run',axis='xy'[axis],
                    coordinate_m=v,span_m=span) for span in merged)
            if oblique:
                curved.append(dict(base,policy='cell_envelope_topology',bounds_m=[
                    min(p[0] for p in ring),min(p[1] for p in ring),
                    max(p[0] for p in ring),max(p[1] for p in ring)]))
    return records,curved


def compact_features(geometry):
    """Dimension pairs on actual cross-sections, including inter-region gaps.

    Short stair-steps on polygonized curves are not independent thin traces.
    A straight pair must persist along >= half its width (rectilinear owners)
    or >= twice its width (curved owners). Remaining geometry is protected by
    the continuous-polygon cell-envelope audit, never deleted from CSXCAD.
    """
    runs,curved=copper_features(geometry)
    curved_ids={r['copper_id'] for r in curved}
    shapes={c.id:copper_shape(c) for c in geometry.copper}
    features={}
    for layer in sorted({c.layer_role for c in geometry.copper}):
        owners=[c.id for c in geometry.copper if c.layer_role==layer]
        for axis in range(2):
            edges=[r for r in runs if r['layer_role']==layer and r['axis']=='xy'[axis]]
            ends=sorted({v for r in edges for v in r['span_m']})
            for start,stop in zip(ends,ends[1:]):
                position=(start+stop)/2
                metal=sorted((a,b,owner) for owner in owners
                    for kind,a,b in _section_intervals(shapes[owner],axis,position) if kind=='copper')
                candidates=[('copper',a,b,(owner,)) for a,b,owner in metal]
                candidates.extend(('clearance',left[1],right[0],(left[2],right[2]))
                                  for left,right in zip(metal,metal[1:]) if left[1]<right[0])
                for kind,a,b,ids in candidates:
                    if b-a<=TOLERANCE_M:continue
                    paired=[]
                    for v,owner in ((a,ids[0]),(b,ids[-1])):
                        paired.append([r for r in edges if r['copper_id']==owner
                            and abs(r['coordinate_m']-v)<=TOLERANCE_M
                            and r['span_m'][0]<position<r['span_m'][1]])
                    if not all(paired):continue
                    span=(max(paired[0][0]['span_m'][0],paired[1][0]['span_m'][0]),
                          min(paired[0][0]['span_m'][1],paired[1][0]['span_m'][1]))
                    factor=2 if any(owner in curved_ids for owner in ids) else .5
                    if span[1]-span[0] < factor*(b-a)-TOLERANCE_M:continue
                    key=(layer,'xy'[axis],kind,ids,a,b)
                    if key not in features:
                        features[key]=dict(feature_type=kind,kind=kind,owners=list(ids),
                            copper_id=ids[0],layer_role=layer,axis='xy'[axis],
                            modeled_boundaries_m=[a,b],modeled_width_m=b-a,
                            section_position_m=position,spans_m=[])
                    if list(span) not in features[key]['spans_m']:features[key]['spans_m'].append(list(span))
    rows=[features[k] for k in sorted(features)]
    for i,row in enumerate(rows):row['id']=f'feature_{i:04d}'
    zones=[]
    for c in geometry.copper:
        shape=shapes[c.id]
        widths=[r['modeled_width_m'] for r in rows if r['kind']=='copper' and c.id in r['owners']]
        # Area/perimeter estimates only set candidate resolution; topology is
        # separately audited. They cannot authorize loss of a neck or hole.
        scale=min(widths) if widths else min(min(shape.bounds[2]-shape.bounds[0],shape.bounds[3]-shape.bounds[1]),
                                           2*shape.area/shape.length)
        for ri,ring in enumerate((c.vertices_xy_m,*c.holes_xy_m)):
            if c.id not in curved_ids:continue
            # Short runs around a bend belong to its vicinity, not vertex anchors.
            points=[]
            for a,b in zip(ring,(*ring[1:],ring[0])):
                if a==b:continue
                if (a[0]!=b[0] and a[1]!=b[1]) or hypot(b[0]-a[0],b[1]-a[1])<scale:
                    points.extend((a,b))
            if points:
                zones.append(dict(copper_id=c.id,ring=ri,scale_m=scale,
                    bounds_m=[min(p[0] for p in points),min(p[1] for p in points),
                              max(p[0] for p in points),max(p[1] for p in points)]))
    return rows,runs,curved,zones


def feature_axis_plan(geometry,axis,critical,maximum):
    """Economical hints with exact contact anchors taking unconditional priority.

    Thirds: inside metal h/3, outside 2h/3. Prefer h=3W/5 for a strip,
    3W/7 for a clearance: the three neighbouring cells then have equal widths.
    Conflicting hints are not promoted. Such features instead require resolved
    subcells (at most W/3); the final audit must prove the representation.
    """
    features,runs,curved,zones=compact_features(geometry)
    selected=[f for f in features if f['axis']=='xy'[axis]]
    lines=list(critical);pairs=[];decisions=[]
    for feature in sorted(selected,key=lambda f:(f['modeled_width_m'],f['id'])):
        a,b=feature['modeled_boundaries_m'];w=b-a
        h=min(w*(3/5 if feature['kind']=='copper' else 3/7),maximum/1.5)
        for edge,side in ((a,1),(b,-1)):
            if feature['kind']=='clearance':side=-side
            inside=edge+side*h/3;outside=edge-side*2*h/3
            lo,hi=sorted((inside,outside))
            equivalent=represented_coordinate(edge,sorted(lines),max(abs(v) for v in lines))
            if equivalent is not None:
                decisions.append(dict(feature_id=feature['id'],edge_m=edge,method='aligned_critical_or_existing'))
                continue
            # Entire edge cell and its immediate spacing must be compatible
            # with already fixed global coordinates. Never move a contact.
            if any(lo-h/3 < v < hi+h/3 for v in lines):
                decisions.append(dict(feature_id=feature['id'],edge_m=edge,method='resolved_subcell_fallback'))
                continue
            lines.extend((lo,hi));lines.sort()
            pairs.append((lo,hi))
            decisions.append(dict(feature_id=feature['id'],edge_m=edge,method='thirds_hint',
                                  metal_side=side,lines_m=[lo,hi]))
    supports=[]
    windows=[(f['modeled_width_m']/3,f['modeled_boundaries_m'][0]-f['modeled_width_m'],
              f['modeled_boundaries_m'][1]+f['modeled_width_m'],f['id']) for f in selected]
    windows.extend((z['scale_m']/3,z['bounds_m'][axis]-z['scale_m']/3,
                    z['bounds_m'][axis+2]+z['scale_m']/3,'curve:'+z['copper_id']) for z in zones)
    for step,lo,hi,owner in sorted(windows):
        for value in (lo,hi):
            if critical[0]<value<critical[-1] and all(abs(value-v)>=step/2 for v in lines):
                lines.append(value);lines.sort();supports.append(dict(coordinate_m=value,owner=owner))
    return tuple(lines),dict(features=features,compacted_runs=runs,curved_regions=curved,
        resolution_window_supports=supports,
        curved_zones=zones,edge_cells=pairs,edge_decisions=decisions)


def feature_interval_limit(a,b,axis,maximum,plan):
    for f in plan['features']:
        if f['axis']!='xy'[axis]:continue
        lo,hi=f['modeled_boundaries_m'];w=hi-lo
        factor=(3/5 if f['kind']=='copper' else 3/7) if f['id'] in plan.get('thirds_feature_ids',()) else 1/3
        if (b>lo and a<hi) or lo-w<(a+b)/2<hi+w:
            maximum=min(maximum,w*factor)
    for z in plan['curved_zones']:
        lo,hi=z['bounds_m'][axis],z['bounds_m'][axis+2]
        if b>lo and a<hi:maximum=min(maximum,z['scale_m']/3)
    return maximum

def _topology(shape):
    if shape.is_empty:
        return (0,0)
    parts = [shape] if shape.geom_type == 'Polygon' else list(shape.geoms)
    if any(p.geom_type != 'Polygon' for p in parts):
        return (-1,-1)
    return len(parts),sum(len(p.interiors) for p in parts)


def _section_intervals(shape, axis, position):
    bounds=shape.bounds
    low=list(bounds[:2]);high=list(bounds[2:])
    low[1-axis]=high[1-axis]=position
    cut=shape.intersection(LineString((low,high)))
    parts=[cut] if cut.geom_type=='LineString' else getattr(cut,'geoms',())
    metal=sorted((p.bounds[axis],p.bounds[axis+2]) for p in parts
                 if p.geom_type=='LineString' and not p.is_empty)
    intervals=[]
    for i,(a,b) in enumerate(metal):
        if i and metal[i-1][1]<a:
            intervals.append(('clearance',metal[i-1][1],a))
        intervals.append(('copper',a,b))
    return intervals


def _cell_envelope(mask, xs, ys):
    """Union exact row runs, avoiding a general union of every individual cell."""
    rectangles=[]
    ny=len(ys)-1
    for j in range(ny):
        start=None
        for i in range(len(xs)):
            occupied=i<len(xs)-1 and bool(mask[i*ny+j])
            if occupied and start is None:
                start=i
            elif not occupied and start is not None:
                rectangles.append(box(xs[start],ys[j],xs[i],ys[j+1]))
                start=None
    return union_all(rectangles)


def audit_copper_mesh(geometry, mesh, *, source_geometry=None):
    """Paired dimensions and edge-cell fractions plus a cell-envelope topology audit.

    Each record includes modeled and retained coordinates (metres), so internal
    strip/gap dimensions can be reconstructed without raw Gerbers. Source values
    remain in geometry.normalized_source.json, never used to derive mesh lines.
    """
    features,records,curved,zones=compact_features(geometry)
    scale=max(abs(v) for bound in geometry.bounds for v in bound[:2])
    axes=(mesh.x_lines_m,mesh.y_lines_m)
    report=dict(policy='feature_aware_copper_v3',status='PASS',features=[],boundaries=[],
        sections=[],curved_regions=[],suppressed_physical_feature_coordinates=0,
        physical_feature_coordinate_count=len({(r['axis'],r['coordinate_m']) for r in records}),
        note='Thirds/aligned/resolved subcell geometry audit; not an EM convergence certificate.')
    raw={c.id:copper_shape(c) for c in source_geometry.copper} if source_geometry else {}
    for feature in features:
        row=dict(feature);axis='xy'.index(row['axis']);lines=axes[axis]
        a,b=row['modeled_boundaries_m'];w=b-a;edge_rows=[]
        for edge,side in ((a,1),(b,-1)):
            if row['kind']=='clearance':side=-side
            exact=represented_coordinate(edge,lines,scale)
            if exact is not None:
                edge_rows.append(dict(coordinate_m=edge,method='aligned',nearby_lines_m=[exact],reconstructed_edge_m=exact,
                    preserved=True,reason='existing exact/contact mesh line'))
                continue
            index=bisect_left(lines,edge)
            if index==0 or index==len(lines):
                raise ConfigurationError(f"PCB feature {row['id']}: edge {edge} outside mesh.")
            lo,hi=lines[index-1:index+1];cell=hi-lo
            fraction=(hi-edge)/cell if side>0 else (edge-lo)/cell
            thirds=abs(fraction-1/3)<=1e-9
            resolved=cell<=w/2*(1+1e-10)
            if not (thirds or resolved):
                raise ConfigurationError(f"PCB feature {row['id']} {row['owners']}: unresolved {row['kind']} "
                    f"width {w:g} m, edge {edge:g}, cell {cell:g}, metal fraction {fraction:g}.")
            edge_rows.append(dict(coordinate_m=edge,method='thirds' if thirds else 'resolved_subcell',
                nearby_lines_m=[lo,hi],cell_width_m=cell,metal_fraction=fraction,
                target_metal_fraction=1/3,metal_side=side,
                reconstructed_edge_m=hi-fraction*cell if side>0 else lo+fraction*cell,preserved=True,
                reason='metal 1/3, air 2/3' if thirds else 'conflicting global constraints; cell <= half feature width'))
        interior=[v for v in lines if a+TOLERANCE_M<v<b-TOLERANCE_M]
        if len(interior)<2:
            raise ConfigurationError(f"PCB feature {row['id']} {row['owners']}: {row['kind']} width {w:g} "
                                     'requires at least two distinct interior mesh lines.')
        largest=max(y-x for x,y in zip(interior,interior[1:]))
        if largest>w*.6*(1+1e-10):
            raise ConfigurationError(f"PCB feature {row['id']}: unresolved interior cell {largest:g} m for width {w:g} m.")
        row.update(mesh_edges=edge_rows,interior_lines_m=interior,maximum_interior_cell_m=largest,preserved=True,
            representation='continuous_polygon_with_audited_edge_cells',
            solver_facing_width_m=edge_rows[1]['reconstructed_edge_m']-edge_rows[0]['reconstructed_edge_m'])
        # The physical width is reconstructed from the subcell edge coordinates,
        # not relabelled as a difference of nearest snapped grid coordinates.
        if len(set(row['owners']))==1 and row['owners'][0] in raw:
            intervals=_section_intervals(raw[row['owners'][0]],axis,row['section_position_m'])
            source=min((r for r in intervals if r[0]==row['kind']),
                       key=lambda r:abs(r[1]-a)+abs(r[2]-b),default=None)
            if source:row.update(source_width_m=source[2]-source[1],source_boundaries_m=list(source[1:]))
        report['features'].append(row);report['sections'].append(row)
        report['boundaries'].extend(dict(e,copper_id=row['copper_id'],axis=row['axis']) for e in edge_rows)
    report['metal_edge_representation_counts']={method:sum(e['method']==method for e in report['boundaries'])
        for method in ('thirds','aligned','resolved_subcell')}
    report['minimum_steps']={}
    for axis,lines in zip('xy',axes):
        i=min(range(len(lines)-1),key=lambda i:lines[i+1]-lines[i])
        from .pcb_mesh import component_terminal_anchors
        ai='xy'.index(axis);n,p=geometry.port.negative_xy_m,geometry.port.positive_xy_m
        mid=(n[ai]+p[ai])/2
        port_values=(n[0],mid,p[0]) if ai==0 else (mid-geometry.port.width_m/2,mid,mid+geometry.port.width_m/2)
        critical=[dict(coordinate_m=v,owner='port') for v in port_values]
        critical.extend(dict(coordinate_m=(d.x_m,d.y_m)[ai],owner='drill:'+d.id) for d in geometry.drills)
        critical.extend(dict(coordinate_m=v,owner='component_contact') for v in component_terminal_anchors(geometry,ai))
        nearest=sorted(critical,key=lambda r:(min(abs(r['coordinate_m']-v) for v in lines[i:i+2]),r['owner']))[:4]
        report['minimum_steps'][axis]=dict(step_m=lines[i+1]-lines[i],bounds_m=list(lines[i:i+2]),
            nearest_critical_constraints=nearest,
            nearby_feature_ids=[f['id'] for f in features if f['axis']==axis and
                f['modeled_boundaries_m'][0]-f['modeled_width_m']<=lines[i+1] and
                f['modeled_boundaries_m'][1]+f['modeled_width_m']>=lines[i]])
    if source_geometry is not None:report['source_boundaries']=copper_features(source_geometry)[0]
    # Audit every region, including narrow necks and gaps not classified as
    # long straight pairs. No inter-conductor contact in the outer envelope.
    layers = {c.layer_role for c in geometry.copper}
    envelopes = []
    total = 0
    for c in geometry.copper:
        if c.layer_role not in layers:
            continue
        shape = copper_shape(c)
        xmin,ymin,xmax,ymax = shape.bounds
        xs = axes[0][max(0,bisect_right(axes[0],xmin)-1):bisect_left(axes[0],xmax)+1]
        ys = axes[1][max(0,bisect_right(axes[1],ymin)-1):bisect_left(axes[1],ymax)+1]
        count = (len(xs)-1)*(len(ys)-1)
        total += count
        if total > MAX_FIDELITY_CELLS:
            raise ConfigurationError(f'PCB copper fidelity: {c.id} exceeds {MAX_FIDELITY_CELLS} audit cells; '
                                     'cannot prove curved feature preservation within the explicit audit budget.')
        cells = box([a for a,b in zip(xs,xs[1:]) for _ in ys[:-1]],
                    [a for _ in xs[:-1] for a,b in zip(ys,ys[1:])],
                    [b for a,b in zip(xs,xs[1:]) for _ in ys[:-1]],
                    [b for _ in xs[:-1] for a,b in zip(ys,ys[1:])])
        # Only the pre-existing geometry tolerance handles boolean arithmetic
        # residue. No wavelength/geometry-quantum erosion or silent repair.
        inner = _cell_envelope(covers(shape.buffer(TOLERANCE_M),cells),xs,ys)
        outer = _cell_envelope(area(intersection(shape,cells)) > TOLERANCE_M**2,xs,ys)
        expected = (1,len(c.holes_xy_m))
        if _topology(inner) != expected or _topology(outer) != expected:
            raise ConfigurationError(f'PCB copper fidelity: {c.id} curved/non-orthogonal cell envelopes '
                f'do not preserve regions/holes: modeled={expected}, inner={_topology(inner)}, outer={_topology(outer)}; '
                'review explicit EM resolution; no physical boundary was suppressed.')
        # Equal counts alone are insufficient: every modeled hole must map
        # one-to-one to a hole in BOTH envelopes, not a newly enclosed air pocket.
        holes=[Polygon(r) for r in c.holes_xy_m]
        for label,envelope in (('inner',inner),('outer',outer)):
            envelope_holes=[Polygon(r) for r in envelope.interiors]
            matches=[[i for i,h in enumerate(holes) if h.intersection(e).area>TOLERANCE_M**2]
                     for e in envelope_holes]
            if any(len(m)!=1 for m in matches) or sorted(m[0] for m in matches)!=list(range(len(holes))):
                raise ConfigurationError(f'PCB copper fidelity: {c.id} {label} envelope changes hole ownership; '
                                         'cannot prove curved clearance preservation.')
        for other, envelope in envelopes:
            if other.layer_role == c.layer_role and outer.intersects(envelope):
                raise ConfigurationError(f'PCB copper fidelity: possible curved-grid short between {other.id} and {c.id}; '
                                         'review explicit EM resolution, not silent geometry simplification.')
        envelopes.append((c,outer))
        report['curved_regions'].append(dict(copper_id=c.id,layer_role=c.layer_role,
            modeled_regions=1,modeled_holes=expected[1],inner_topology=list(_topology(inner)),
            outer_topology=list(_topology(outer)),preserved=True,examined_cells=count,
            maximum_boundary_cell_diagonal_m=hypot(max(b-a for a,b in zip(xs,xs[1:])),
                                                   max(b-a for a,b in zip(ys,ys[1:])))))
    return report
