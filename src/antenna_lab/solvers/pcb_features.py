"""Pure copper/mesh fidelity contract; never changes polygons or mesh lines.

Rectilinear boundary runs (outer and hole rings) require exact normal mesh
coordinates. Curves keep continuous CSXCAD geometry, ring extrema and a bounded
set of support lines, not all tessellation vertices. Their final cell envelope
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
    records, curved = [], []
    for c in geometry.copper:
        for ri, ring in enumerate((c.vertices_xy_m, *c.holes_xy_m)):
            base = dict(copper_id=c.id, layer_role=c.layer_role, ring=ri)
            oblique = False
            for a,b in zip(ring, (*ring[1:], ring[0])):
                if a == b:
                    continue
                if a[0] == b[0] or a[1] == b[1]:
                    axis = 0 if a[0] == b[0] else 1
                    records.append(dict(base, kind='physical_boundary_run', axis='xy'[axis],
                        coordinate_m=a[axis], span_m=sorted((a[1-axis],b[1-axis]))))
                else:
                    oblique = True
            if oblique:
                curved.append(dict(base, policy='cell_envelope_topology',
                    bounds_m=[min(p[0] for p in ring),min(p[1] for p in ring),
                              max(p[0] for p in ring),max(p[1] for p in ring)]))
                for axis in range(2):
                    lo,hi = min(p[axis] for p in ring),max(p[axis] for p in ring)
                    for v in (lo,hi):
                        records.append(dict(base,kind='physical_ring_extremum',axis='xy'[axis],coordinate_m=v))
    return records, curved


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


def _rectilinear_sections(geometry, axes, records, curved, source_geometry):
    """Dimension evidence inside connected polygons, not just whole bboxes."""
    scale=max(abs(v) for bound in geometry.bounds for v in bound[:2])
    result=[];curved_ids={r['copper_id'] for r in curved}
    raw={c.id:copper_shape(c) for c in source_geometry.copper} if source_geometry else {}
    for c in geometry.copper:
        if c.id in curved_ids:continue
        shape=copper_shape(c)
        for axis in range(2):
            runs=[r for r in records if r['copper_id']==c.id and r['axis']=='xy'[axis]]
            ends=sorted({v for r in runs for v in r['span_m']})
            for start,stop in zip(ends,ends[1:]):
                position=(start+stop)/2
                intervals=_section_intervals(shape,axis,position)
                source=_section_intervals(raw[c.id],axis,position) if c.id in raw else []
                for i,(kind,a,b) in enumerate(intervals):
                    represented=[represented_coordinate(v,axes[axis],scale) for v in (a,b)]
                    if None in represented:
                        raise ConfigurationError(f'PCB copper fidelity: {c.id} lost {kind} section boundaries {a!r}, {b!r}.')
                    row=dict(copper_id=c.id,layer_role=c.layer_role,kind=kind,axis='xy'[axis],
                        section_position_m=position,modeled_boundaries_m=[a,b],retained_boundaries_m=represented,
                        modeled_width_m=b-a,solver_facing_width_m=represented[1]-represented[0],preserved=True)
                    if len(source)==len(intervals) and source[i][0]==kind:
                        row['source_width_m']=source[i][2]-source[i][1]
                        row['source_boundaries_m']=list(source[i][1:])
                    result.append(row)
    return result


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
    """Exact orthogonal features; conservative inner/outer cell proof otherwise.

    Each record includes modeled and retained coordinates (metres), so internal
    strip/gap dimensions can be reconstructed without raw Gerbers. Source values
    remain in geometry.normalized_source.json, never used to derive mesh lines.
    """
    records, curved = copper_features(geometry)
    scale=max(abs(v) for bound in geometry.bounds for v in bound[:2])
    axes = (mesh.x_lines_m,mesh.y_lines_m)
    report = dict(policy='modeled_copper_features_v2',status='PASS',
        physical_feature_coordinate_count=len({(r['axis'],r['coordinate_m']) for r in records}),
        suppressed_physical_feature_coordinates=0, boundaries=[], curved_regions=[],
        note='Exact rectilinear boundaries; curved cell-envelope topology proof, not native occupancy or EM convergence.')
    for r in records:
        actual = represented_coordinate(r['coordinate_m'], axes['xy'.index(r['axis'])],scale)
        present = actual is not None
        report['boundaries'].append(dict(r,retained_mesh_coordinate_m=actual, preserved=present,
            reason=('exact_line' if actual==r['coordinate_m'] else 'floating_point_boundary_equivalence') if present else 'missing_exact_line'))
        if not present:
            raise ConfigurationError(f"PCB copper fidelity: {r['copper_id']} ring {r['ring']} "
                f"missing exact {r['axis']} physical boundary {r['coordinate_m']!r} m; "
                "modeled geometry must not be simplified by the EM mesh.")
    report['sections']=_rectilinear_sections(geometry,axes,records,curved,source_geometry)
    if source_geometry is not None:
        report['source_boundaries'] = copper_features(source_geometry)[0]
    if not curved:
        return report
    # Audit every region on layers with a curved boundary, also ruling out
    # contact with a neighbouring rectangular conductor in the outer envelope.
    layers = {r['layer_role'] for r in curved}
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
