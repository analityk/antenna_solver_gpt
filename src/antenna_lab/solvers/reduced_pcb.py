"""Lossless quasi-static microstrip graph; no native modules or FDTD mesh.

Uniform zero-thickness sections use Hammerstad/Jensen (1980), as documented
in Qucs technical section 11.1, eqs 11.4, 11.6, 11.15–18:
https://qucs.github.io/tech/node75.html
Bends are ideal junctions. Radiation, loss, dispersion, pad/bend/end parasitics
are omitted, not estimated. Parallel separated runs require a coupling model
and are explicitly rejected by solve_reduced_model in this first checkpoint.
"""
from dataclasses import asdict, dataclass
from math import exp, hypot, isfinite, log, log10, pi, sqrt

import numpy as np
from shapely import union_all
from shapely.geometry import LineString, Point, Polygon, box

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.regions import copper_shape
from antenna_lab.pcb.validation import TOLERANCE_M, _contains_copper, validate_pcb_geometry
from .pcb_features import compact_features

C0 = 299792458.0
Z_VACUUM = 376.730313668
OMITTED_EFFECTS = (
    'free_space_radiation', 'far_field', 'conductor_loss', 'dielectric_loss',
    'finite_metal_thickness', 'frequency_dispersion', 'bend_discontinuities',
    'pad_and_open_end_fringing', 'finite_ground_edge_effects',
    'component_package_parasitics', 'nonlocal_cross_coupling',
)


def microstrip_parameters(width_m, height_m, epsilon_r):
    """Hammerstad/Jensen quasi-static, zero-thickness, infinite ground model.

    Conservative documented range: 0.01 <= w/h <= 100, 1 <= epsilon_r <= 128.
    L/C give the same Z0 and phase velocity, with no invented attenuation.
    """
    if any(isinstance(v, bool) or not isfinite(v) or v <= 0
           for v in (width_m, height_m, epsilon_r)):
        raise ConfigurationError('Reduced microstrip: positive finite width/height/epsilon required.')
    u = width_m / height_m
    if not .01 <= u <= 100 or not 1 <= epsilon_r <= 128:
        raise ConfigurationError('Reduced microstrip: outside model range w/h=[0.01,100], epsilon_r=[1,128].')
    a = 1 + log((u**4+(u/52)**2)/(u**4+.432))/49 + log(1+(u/18.1)**3)/18.7
    b = .564*((epsilon_r-.9)/(epsilon_r+3))**.053
    effective = (epsilon_r+1)/2 + (epsilon_r-1)/2*(1+10/u)**(-a*b)
    fu = 6 + (2*pi-6)*exp(-(30.666/u)**.7528)
    z0 = Z_VACUUM/(2*pi*sqrt(effective))*log(fu/u+sqrt(1+(2/u)**2))
    velocity = C0/sqrt(effective)
    return dict(model='Hammerstad_Jensen_quasi_static_zero_thickness', z0_ohm=z0,
                effective_epsilon_r=effective, velocity_m_s=velocity,
                inductance_h_m=z0/velocity, capacitance_f_m=1/(z0*velocity))


@dataclass(frozen=True)
class LineSection:
    id: str
    owner: str
    start_xy_m: tuple[float, float]
    stop_xy_m: tuple[float, float]
    width_m: float
    feature_ids: tuple[str, ...]

    @property
    def length_m(self):
        return hypot(*(b-a for a,b in zip(self.start_xy_m,self.stop_xy_m)))

    @property
    def axis(self):
        return 0 if self.start_xy_m[1] == self.stop_xy_m[1] else 1


def _same_shape(a, b):
    # Only numerical boundary tolerance, never a geometry-resolution allowance.
    return a.difference(b).area + b.difference(a).area <= TOLERANCE_M*(a.length+b.length)


def _strip(section):
    a,b=section.start_xy_m,section.stop_xy_m; t=1-section.axis;half=section.width_m/2
    low=[min(a[i],b[i]) for i in range(2)];high=[max(a[i],b[i]) for i in range(2)]
    low[t]-=half;high[t]+=half
    return box(*low,*high)


def extract_trace_sections(geometry):
    """Recover rectilinear strips from compact_features, proving copper coverage.

    No raster skeleton or best-guess route. Only long physical width pairs are
    candidates. Orthogonal candidates can extend by half a width into a proven
    same-owner rectangular bend. Their reconstructed footprints must cover the
    complete supplied copper without creating metal. Branches/ambiguity fail.
    A U/meander may extract successfully but solving requires coupling support.
    """
    features,_,curved,_=compact_features(geometry)
    if any(r['layer_role']=='top' for r in curved):
        raise ConfigurationError('Reduced extraction: curved/oblique top copper unsupported; no guessed centerline.')
    shapes={c.id:copper_shape(c) for c in geometry.top_copper}
    candidates=[]
    for f in features:
        if f['layer_role']!='top' or f['kind']!='copper':continue
        transverse='xy'.index(f['axis']);axis=1-transverse
        lo,hi=f['modeled_boundaries_m'];mid=(lo+hi)/2;w=hi-lo
        for start,stop in f['spans_m']:
            if stop-start <= w+TOLERANCE_M:continue  # Square/short pad orientation is ambiguous.
            a=[0.,0.];b=[0.,0.];a[axis]=start;b[axis]=stop;a[transverse]=b[transverse]=mid
            s=LineSection('',f['owners'][0],tuple(a),tuple(b),w,(f['id'],))
            # compact_features can propose a broad pair spanning a U's empty
            # interior. It is not a uniform strip: keep only physically filled rectangles.
            if _strip(s).difference(shapes[s.owner]).area <= TOLERANCE_M*_strip(s).length:
                candidates.append(s)
    # Merge identical/overlapping collinear width pairs, with deterministic IDs.
    merged=[]
    for s in sorted(candidates,key=lambda s:(s.owner,s.axis,s.start_xy_m[1-s.axis],s.width_m,s.start_xy_m[s.axis])):
        if merged:
            p=merged[-1];axis=s.axis
            if (p.owner==s.owner and p.axis==axis and p.width_m==s.width_m
                    and p.start_xy_m[1-axis]==s.start_xy_m[1-axis]
                    and s.start_xy_m[axis] <= p.stop_xy_m[axis]):
                end=list(p.stop_xy_m);end[axis]=max(end[axis],s.stop_xy_m[axis])
                merged[-1]=LineSection('',p.owner,p.start_xy_m,tuple(end),p.width_m,
                                      tuple(sorted(set(p.feature_ids+s.feature_ids))))
                continue
        merged.append(s)
    sections=merged
    cuts=[{s.start_xy_m,s.stop_xy_m} for s in sections];bends=[]
    for i,a in enumerate(sections):
        for j in range(i+1,len(sections)):
            b=sections[j]
            if a.owner!=b.owner or a.axis==b.axis:continue
            point=tuple(a.start_xy_m[k] if k!=a.axis else b.start_xy_m[k] for k in range(2))
            if not all(s.start_xy_m[s.axis]-s.width_m/2-TOLERANCE_M <= point[s.axis] <=
                       s.stop_xy_m[s.axis]+s.width_m/2+TOLERANCE_M for s in (a,b)):continue
            if abs(a.width_m-b.width_m)>TOLERANCE_M:
                raise ConfigurationError('Reduced extraction: unequal-width orthogonal junction is ambiguous.')
            half=a.width_m/2
            corner=box(point[0]-half,point[1]-half,point[0]+half,point[1]+half)
            if corner.difference(shapes[a.owner]).area > TOLERANCE_M*corner.length:
                raise ConfigurationError('Reduced extraction: copper does not prove orthogonal junction.')
            cuts[i].add(point);cuts[j].add(point);bends.append((a.owner,corner))
    # Remove original end-of-pair cuts inside the bend, keeping only centerline
    # junctions and true physical terminal ends. They do not change electrical length.
    extended=[]
    for s,points in zip(sections,cuts):
        ordered=sorted(points,key=lambda p:p[s.axis]);a,b=ordered[0],ordered[-1]
        extended.append(LineSection('',s.owner,a,b,s.width_m,s.feature_ids))
    for owner,shape in shapes.items():
        pieces=[_strip(s) for s in extended if s.owner==owner]+[p for o,p in bends if o==owner]
        if not pieces or not _same_shape(union_all(pieces),shape):
            raise ConfigurationError(f'Reduced extraction: {owner} has unresolved pad/branch/width geometry; full copper coverage not proven.')
    # Split at all true centerline intersections, not raw CAD polygon vertices.
    points=[{s.start_xy_m,s.stop_xy_m} for s in extended]
    for i,a in enumerate(extended):
        for j,b in enumerate(extended[:i]):
            if a.owner!=b.owner:continue
            meet=LineString((a.start_xy_m,a.stop_xy_m)).intersection(LineString((b.start_xy_m,b.stop_xy_m)))
            if meet.is_empty:continue
            if meet.geom_type!='Point':
                raise ConfigurationError('Reduced extraction: ambiguous overlapping centerlines.')
            p=tuple(meet.coords[0]);points[i].add(p);points[j].add(p)
    result=[]
    for s,pts in zip(extended,points):
        ordered=sorted(pts,key=lambda p:p[s.axis])
        result.extend(LineSection('',s.owner,a,b,s.width_m,s.feature_ids) for a,b in zip(ordered,ordered[1:]))
    result=tuple(LineSection(f'line_{i:04d}',s.owner,s.start_xy_m,s.stop_xy_m,s.width_m,s.feature_ids)
                 for i,s in enumerate(sorted(result,key=lambda s:(s.owner,s.start_xy_m,s.stop_xy_m,s.width_m))))
    for owner in shapes:
        degree={}
        for s in result:
            if s.owner==owner:
                for p in (s.start_xy_m,s.stop_xy_m):degree[p]=degree.get(p,0)+1
        if any(d>2 for d in degree.values()):
            raise ConfigurationError(f'Reduced extraction: branched conductor {owner} unsupported.')
        # Coverage alone does not prove a single graph component.
        pending=set(degree);todo=[min(pending)] if pending else []
        while todo:
            p=todo.pop()
            if p not in pending:continue
            pending.remove(p)
            for s in result:
                if s.owner==owner and p in (s.start_xy_m,s.stop_xy_m):todo.extend((s.start_xy_m,s.stop_xy_m))
        if pending:raise ConfigurationError(f'Reduced extraction: disconnected graph inside {owner}.')
    return result, features


def detect_coupled_sections(sections):
    """All separated parallel overlaps need coupling; no arbitrary gap cutoff."""
    rows=[]
    for i,a in enumerate(sections):
        for b in sections[i+1:]:
            if a.axis!=b.axis:continue
            axis=a.axis;t=1-axis
            start=max(a.start_xy_m[axis],b.start_xy_m[axis]);stop=min(a.stop_xy_m[axis],b.stop_xy_m[axis])
            if stop-start<=TOLERANCE_M:continue
            distance=abs(a.start_xy_m[t]-b.start_xy_m[t])
            gap=distance-(a.width_m+b.width_m)/2
            if gap<=TOLERANCE_M:
                raise ConfigurationError('Reduced extraction: overlapping parallel strip ownership is unresolved.')
            rows.append(dict(section_ids=[a.id,b.id],overlap_start_m=start,overlap_stop_m=stop,
                             overlap_length_m=stop-start,physical_gap_m=gap,
                             status='unsupported_requires_pairwise_quasi_tem_model'))
    return rows


def build_reduced_model(geometry):
    validate_pcb_geometry(geometry)
    if geometry.drills:
        raise ConfigurationError('Reduced v1: drills/via paths unsupported (not silently omitted).')
    if len(geometry.dielectrics)!=1 or {c.layer_role for c in geometry.copper}!={'top','bottom'}:
        raise ConfigurationError('Reduced v1 requires top microstrip, one homogeneous dielectric, continuous bottom ground.')
    board=Polygon(geometry.outline.vertices_xy_m)
    ground=[c for c in geometry.copper if c.layer_role=='bottom']
    if len(ground)!=1 or ground[0].holes_xy_m or not _same_shape(copper_shape(ground[0]),board):
        raise ConfigurationError('Reduced v1: bottom ground must be one continuous uncut board-covering plane.')
    if any(not board.covers(copper_shape(c)) for c in geometry.top_copper):
        raise ConfigurationError('Reduced v1: all traces must lie above the ground reference.')
    for i,c in enumerate(geometry.top_copper):
        if any(copper_shape(c).intersects(copper_shape(other)) for other in geometry.top_copper[:i]):
            raise ConfigurationError('Reduced v1: touching/overlapping separate top conductor records.')
    sections,features=extract_trace_sections(geometry)
    if not sections:raise ConfigurationError('Reduced v1: no resolvable trace sections.')
    substrate=geometry.dielectrics[0];h=substrate.z_max_m-substrate.z_min_m
    coords=sorted({p for s in sections for p in (s.start_xy_m,s.stop_xy_m)})
    nodes={p:f'n{i:04d}' for i,p in enumerate(coords)}
    lines=[]
    for s in sections:
        lines.append(dict(asdict(s),node_a=nodes[s.start_xy_m],node_b=nodes[s.stop_xy_m],
            length_m=s.length_m,substrate_height_m=h,parameters=microstrip_parameters(s.width_m,h,substrate.epsilon_r)))
    def terminal(p,label):
        owners=[c for c in geometry.top_copper if _contains_copper(p,c)]
        if len(owners)!=1:raise ConfigurationError(f'{label}: ambiguous terminal ownership.')
        matches=[q for q in coords if hypot(q[0]-p[0],q[1]-p[1])<=TOLERANCE_M and
                 any(s.owner==owners[0].id and q in (s.start_xy_m,s.stop_xy_m) for s in sections)]
        if len(matches)!=1:raise ConfigurationError(f'{label}: terminal must coincide with one physical trace centerline end/junction; no guessed lead length.')
        return nodes[matches[0]]
    def contact(a,b,width,label):
        axis=0 if abs(a[1]-b[1])<=TOLERANCE_M else 1;t=1-axis
        if abs(a[t]-b[t])>TOLERANCE_M or abs(a[axis]-b[axis])<=TOLERANCE_M:
            raise ConfigurationError(f'{label}: unresolved contact axis/gap.')
        mid=(a[t]+b[t])/2;lo,hi=sorted((a[axis],b[axis]));half=width/2
        def xy(u,v):return (u,v) if axis==0 else (v,u)
        surface=Polygon([xy(lo,mid-half),xy(hi,mid-half),xy(hi,mid+half),xy(lo,mid+half)])
        for c in geometry.top_copper:
            if surface.intersection(copper_shape(c)).area > TOLERANCE_M*surface.length:
                raise ConfigurationError(f'{label}: copper in physical gap.')
        for p in (a,b):
            owner=next(c for c in geometry.top_copper if _contains_copper(p,c))
            face=LineString((xy(p[axis],mid-half),xy(p[axis],mid+half)))
            if face.difference(copper_shape(owner).buffer(TOLERANCE_M)).length>TOLERANCE_M:
                raise ConfigurationError(f'{label}: incomplete transverse contact.')
        return terminal(a,label),terminal(b,label)
    n,p=geometry.port.negative_xy_m,geometry.port.positive_xy_m
    source=contact(n,p,geometry.port.width_m,geometry.port.id)
    components=[]
    for c in geometry.components:
        if c.kind not in ('R','L','C') or not isfinite(c.value_si) or c.value_si<=0 or c.layer!='top':
            raise ConfigurationError(f'{c.id}: invalid ideal component.')
        t=1-'xy'.index(c.axis);vs=[p[t] for p in c.contact_window_xy_m]
        na,nb=contact(c.gap_start_xy_m,c.gap_stop_xy_m,max(vs)-min(vs),c.id)
        components.append(dict(asdict(c),node_a=na,node_b=nb))
    coupled=detect_coupled_sections(sections)
    return dict(solver_model='reduced_quasi_tem',validation_status='approximate',
        unsupported_status='coupling_required' if coupled else None,
        ground_reference=dict(status='passed',id=ground[0].id,z_m=ground[0].z_m,
            treatment='ideal common reference; finite board edge fields omitted'),
        substrate_height_m=h,epsilon_r=substrate.epsilon_r,
        material_provenance=dict(loss_tangent=substrate.loss_tangent,
                                 copper_layers=[asdict(c) for c in geometry.copper_layers]),
        nodes=[dict(id=nodes[p],xy_m=p) for p in coords],line_sections=lines,
        physical_features=features,coupled_sections=coupled,lumped_components=components,
        source_port_nodes=list(source),source_port_id=geometry.port.id,
        total_centerline_length_m=sum(s.length_m for s in sections),
        width_classes_m=sorted({s.width_m for s in sections}),omitted_effects=list(OMITTED_EFFECTS),
        loss_model='lossless_lines; ideal_RLC_resistance_only',
        approximation_contract='quasi-static isolated microstrip, ideal bend junctions; no full-wave accuracy claim')


def solve_network(nodes, lines, components, source, frequency_hz):
    """Nodal TL network referenced to 'ground'; 1 A differential test current.

    One extra current unknown per TL avoids cot(theta) singular stamps at
    integer half-waves. Exact line equations remain usable there. Genuine
    network singularities fail. Currents enter the start terminal of each TL.
    """
    if not isfinite(frequency_hz) or frequency_hz<=0:
        raise ConfigurationError('Reduced network: positive finite frequency required.')
    names=list(nodes)
    if len(set(names))!=len(names) or 'ground' in names:
        raise ConfigurationError('Reduced network: unique non-ground node names required.')
    index={n:i for i,n in enumerate(names)};size=len(names)+len(lines)
    matrix=np.zeros((size,size),complex);rhs=np.zeros(size,complex);w=2*pi*frequency_hz
    def idx(n):
        if n=='ground':return None
        if n not in index:raise ConfigurationError(f'Reduced network: unknown node {n}.')
        return index[n]
    def add(row,col,value):
        if row is not None and col is not None:matrix[row,col]+=value
    for k,line in enumerate(lines):
        a,b=idx(line['node_a']),idx(line['node_b']);i=len(names)+k
        length=line['length_m'];z=line['parameters']['z0_ohm'];v=line['parameters']['velocity_m_s']
        if any(not isfinite(x) or x<=0 for x in (length,z,v)):
            raise ConfigurationError('Reduced TL: length/Z0/velocity must be finite and positive.')
        phase=w*length/v;c=np.cos(phase);s=np.sin(phase)
        add(a,i,1);add(b,a,1j*s/z);add(b,i,-c)
        add(i,b,1);add(i,a,-c);add(i,i,1j*z*s)
    for component in components:
        a,b=idx(component['node_a']),idx(component['node_b'])
        value=component['value_si'];kind=component['kind']
        if not isfinite(value) or value<=0 or kind not in ('R','L','C'):
            raise ConfigurationError('Reduced RLC: positive finite interpreted value required.')
        y={'R':lambda:1/value,'L':lambda:1/(1j*w*value),'C':lambda:1j*w*value}[kind]()
        add(a,a,y);add(b,b,y);add(a,b,-y);add(b,a,-y)
    if source[0]==source[1]:raise ConfigurationError('Reduced source terminals shorted.')
    for n,sign in zip(source,(-1,1)):
        i=idx(n)
        if i is not None:rhs[i]+=sign
    try:answer=np.linalg.solve(matrix,rhs)
    except np.linalg.LinAlgError as exc:raise ConfigurationError(f'Reduced network singular at {frequency_hz:g} Hz.') from exc
    residual=np.linalg.norm(matrix@answer-rhs,np.inf)
    if not np.all(np.isfinite(answer)) or residual>1e-8:
        raise ConfigurationError(f'Reduced network invalid/ill-conditioned at {frequency_hz:g} Hz; residual={residual}.')
    voltage=lambda n:0j if n=='ground' else answer[index[n]]
    z=voltage(source[1])-voltage(source[0])
    if z.real < -1e-9*max(1,abs(z)):
        raise ConfigurationError('Reduced passive network produced negative resistance.')
    return complex(z)


def solve_reduced_model(model, frequencies, reference_impedance_ohm=50.):
    if model['coupled_sections']:
        raise ConfigurationError(f"Reduced PARTIAL: {len(model['coupled_sections'])} parallel overlaps require a pairwise coupling solver; coupling is NOT silently omitted.")
    if not isfinite(reference_impedance_ohm) or reference_impedance_ohm<=0:
        raise ConfigurationError('Reduced reference impedance must be positive finite.')
    f=tuple(frequencies)
    if not f or any(not isfinite(x) or x<=0 for x in f) or any(a>=b for a,b in zip(f,f[1:])):
        raise ConfigurationError('Reduced frequencies must be positive finite, strictly increasing.')
    rows=[]
    for frequency in f:
        z=solve_network([n['id'] for n in model['nodes']],model['line_sections'],model['lumped_components'],model['source_port_nodes'],frequency)
        reflection=(z-reference_impedance_ohm)/(z+reference_impedance_ohm);magnitude=abs(reflection)
        if not isfinite(magnitude) or magnitude>1+1e-9:
            raise ConfigurationError('Reduced passive model: invalid reflection magnitude.')
        rows.append(dict(frequency_hz=frequency,resistance_ohm=z.real,reactance_ohm=z.imag,
            s11_real=reflection.real,s11_imag=reflection.imag,s11_magnitude=magnitude,
            s11_db=20*log10(magnitude) if magnitude>0 else None,
            swr=None if abs(magnitude-1)<=1e-12 else (1+magnitude)/(1-magnitude)))
    return rows
