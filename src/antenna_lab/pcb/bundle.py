"""Folder discovery and conservative rectangular-flash feed recognition.

Gerbonara owns parsing. Auto feed supports exactly two matching, aligned
rectangular flashes; full union determines the gap, never aperture edges alone.
"""
from hashlib import sha256
import json
from pathlib import Path
import re

from gerbonara import GerberFile
from gerbonara.layers import identify_file
from gerbonara.graphic_objects import Flash
from gerbonara.apertures import RectangleAperture
from gerbonara.utils import MM
from shapely.geometry import Polygon, LineString, box
from shapely import union_all

from antenna_lab.core.config import ConfigurationError, validate_schema
from .config import ResolvedPcbConfig
from .gerber import _read, _copper, _outline, ASSUMPTIONS
from .model import PcbGeometry, PcbPort, Substrate
from .validation import validate_pcb_geometry, TOLERANCE_M

DEFAULT_PHYSICAL = dict(schema_version=1,
    substrate=dict(thickness_mm=1.6, epsilon_r=4.3, loss_tangent=.018),
    copper=dict(thickness_um=35, conductivity_s_m=58000000, model='pec'),
    port=dict(mode='auto'))


def load_physical_config(path=None):
    value = (json.loads(Path(path).read_text(encoding='utf-8-sig')) if path else
             json.loads(json.dumps(DEFAULT_PHYSICAL)))
    validate_schema(value, 'pcb-physical.schema.json')
    return value


def _role(path):
    ext, name = path.suffix.lower(), path.stem.lower()
    roles = {'.gtl':'top_copper', '.gbl':'bottom_copper', '.gko':'outline',
             '.gts':'soldermask', '.gbs':'soldermask', '.gtp':'paste', '.gbp':'paste',
             '.gto':'silkscreen', '.gbo':'silkscreen', '.drl':'drill', '.xln':'drill',
             '.gml':'outline'}
    conventional = roles.get(ext)
    if re.fullmatch(r'\.g(?:[1-9][0-9]*|p[1-9][0-9]*)',ext):
        conventional = 'inner_copper'
    identified = identify_file(path.read_text(encoding='utf-8-sig', errors='replace'))
    if conventional == 'drill' or 'drill' in name or identified == 'excellon':
        return 'drill'
    gerber_like = conventional is not None or identified == 'gerber' or ext in ('.gbr','.ger','.pho')
    if not gerber_like:
        return 'unclassified'
    try:
        parsed = GerberFile.open(path, enable_includes=False)
    except (ValueError, SyntaxError, OSError) as exc:
        raise ConfigurationError(f'Cannot identify Gerber {path.name}: {exc}') from exc
    function = ','.join(parsed.file_attrs.get('.FileFunction',())).lower()
    metadata_role = None
    if 'copper' in function:
        metadata_role = ('top_copper' if 'top' in function else
                         'bottom_copper' if 'bot' in function else 'inner_copper')
    elif 'profile' in function: metadata_role = 'outline'
    elif 'soldermask' in function: metadata_role = 'soldermask'
    elif 'paste' in function: metadata_role = 'paste'
    elif 'legend' in function: metadata_role = 'silkscreen'
    elif 'drill' in function: metadata_role = 'drill'
    if metadata_role and conventional and metadata_role != conventional:
        raise ConfigurationError(f'{path.name}: filename role {conventional} conflicts with FileFunction {function}.')
    if metadata_role or conventional:
        return metadata_role or conventional
    for token, role in (('edge_cuts','outline'),('boardoutline','outline'),('f_cu','top_copper'),
                        ('toplayer','top_copper'),('b_cu','bottom_copper'),('bottomlayer','bottom_copper'),
                        ('mask','soldermask'),('paste','paste'),('silk','silkscreen')):
        if token in name: return role
    return 'unclassified_gerber'


def discover_bundle(directory):
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise ConfigurationError(f'Gerber directory not found: {directory}')
    records = []
    for path in sorted((p for p in directory.iterdir() if p.is_file()), key=lambda p:p.name):
        role = _role(path)
        records.append(dict(name=path.name, path=str(path), role=role,
            sha256=sha256(path.read_bytes()).hexdigest(),
            disposition='modeled' if role in ('top_copper','outline') else 'omitted'))
    selected = {}
    for role in ('top_copper','outline'):
        candidates = [r['path'] for r in records if r['role']==role]
        if len(candidates)!=1:
            raise ConfigurationError(f'Require exactly one {role}; candidates: '+
                (', '.join(Path(p).name for p in candidates) or '(none)'))
        selected[role] = Path(candidates[0])
    unsupported = [r['name'] for r in records if r['role'] in ('bottom_copper','inner_copper','drill','unclassified_gerber')]
    if unsupported:
        raise ConfigurationError('Unsupported PCB-v0 layers/features (not modeled): '+', '.join(unsupported))
    return selected, records


def detect_feed(gerber, copper):
    pads=[]
    for obj in gerber.objects:
        if isinstance(obj,Flash) and isinstance(obj.aperture,RectangleAperture):
            obj=obj.converted(MM)
            primitive=list(obj.to_primitives(unit=MM))
            if len(primitive)!=1 or getattr(primitive[0],'rotation',0)!=0 or obj.aperture.hole_dia:
                raise ConfigurationError('Auto feed requires solid axis-aligned rectangular pads; use explicit port.')
            pads.append((obj.x*1e-3,obj.y*1e-3,obj.aperture.w*1e-3,obj.aperture.h*1e-3))
    if len(pads)!=2:
        raise ConfigurationError(f'Auto feed requires exactly two rectangular flashed pads, found {len(pads)}; use --pcb-config with explicit port.')
    a,b=sorted(pads)
    tol=TOLERANCE_M
    if any(abs(a[i]-b[i])>tol for i in (2,3)):
        raise ConfigurationError('Auto feed: incompatible pad dimensions; use explicit port.')
    if abs(a[1]-b[1])<=tol and b[0]-a[0]>a[2]: axis=0
    elif abs(a[0]-b[0])<=tol and b[1]-a[1]>a[3]: axis=1
    else: raise ConfigurationError('Auto feed: pads must align horizontally or vertically with a nonzero gap; use explicit port.')
    transverse=1-axis
    centre=(a[transverse]+b[transverse])/2
    width=a[3 if axis==0 else 2]
    # Work in physical SI; swap coordinates for vertical feed, not geometry.
    shapes=[Polygon([(v[axis],v[transverse]) for v in c.vertices_xy_m]) for c in copper]
    merged=union_all(shapes)
    clear=LineString(((a[axis],centre),(b[axis],centre))).difference(merged)
    intervals=[clear] if clear.geom_type=='LineString' else list(getattr(clear,'geoms',()))
    intervals=[g for g in intervals if g.geom_type=='LineString' and g.length>tol]
    if len(intervals)!=1:
        raise ConfigurationError('Auto feed: expected one clear interval between pad centres; use explicit port.')
    lo,_,hi,_=intervals[0].bounds
    def xy(x,y): return (x,y) if axis==0 else (y,x)
    port=PcbPort('gerber_feed',xy(lo,centre),xy(hi,centre),width)
    return port, dict(mode='auto',axis='xy'[axis],gap_m=hi-lo,width_m=width,
        pad_centres_xy_m=[a[:2],b[:2]],method='rectangular_flashes_then_union_axis_gap')


def audit_physical_feed(geometry):
    """Continuous planar rectangular contact/gap check, independent of grid.

    Geometry tolerance permits rotation residue, never physical copper slivers.
    Same connected conductor is allowed around the exterior of the gap.
    """
    from math import hypot
    n,p=geometry.port.negative_xy_m,geometry.port.positive_xy_m
    length=hypot(p[0]-n[0],p[1]-n[1]); ux,uy=(p[0]-n[0])/length,(p[1]-n[1])/length
    def local(v):
        dx,dy=v[0]-n[0],v[1]-n[1]
        return (dx*ux+dy*uy,-dx*uy+dy*ux)
    shapes=[Polygon([local(v) for v in c.vertices_xy_m]) for c in geometry.copper]
    tol=TOLERANCE_M;half=geometry.port.width_m/2
    if length<=2*tol or half<=tol:
        raise ConfigurationError('Physical feed gap/width unresolved at geometry tolerance.')
    interior=box(tol,-half+tol,length-tol,half-tol)
    if any(s.intersects(interior) for s in shapes):
        raise ConfigurationError('Physical feed gap contains copper (miedź wewnątrz szczeliny).')
    for side,x in (('negative',0.),('positive',length)):
        face=LineString(((x,-half),(x,half)))
        owners=[s for s in shapes if s.buffer(tol).covers(face)]
        touching=[s for s in shapes if s.buffer(tol).intersects(face)]
        if len(owners)!=1 or len(touching)!=1:
            raise ConfigurationError(f'Physical feed {side}: incomplete or ambiguous full-width contact; use explicit port.')


def load_bundle_geometry(directory, physical_path=None):
    selected,records=discover_bundle(directory)
    value=load_physical_config(physical_path)
    top=_read(selected['top_copper'],'top copper')
    copper=_copper(top);outline=_outline(_read(selected['outline'],'board outline'))
    if value['port']['mode']=='auto': port,feed=detect_feed(top,copper)
    else:
        v=value['port']
        port=PcbPort('gerber_feed',tuple(x*1e-3 for x in v['negative_mm']),
                     tuple(x*1e-3 for x in v['positive_mm']),v['width_mm']*1e-3)
        feed=dict(mode='explicit')
    c,s=value['copper'],value['substrate']
    config=ResolvedPcbConfig(1,'pcb',selected['top_copper'],selected['outline'],
        c['thickness_um']*1e-6,c['conductivity_s_m'],c['model'],s['thickness_mm']*1e-3,
        s['epsilon_r'],s['loss_tangent'],port.negative_xy_m,port.positive_xy_m,port.width_m)
    origin='--pcb-config (unverified assumptions)' if physical_path else 'documented defaults (assumptions/unverified)'
    assumptions=[x for x in ASSUMPTIONS if x!='substrate parameters: from pcb.json']
    assumptions += ['substrate parameters: '+origin, 'finite copper thickness: omitted', 'copper roughness: omitted']
    geometry=PcbGeometry('pcb',outline,copper,Substrate(outline,-config.substrate_thickness_m,0.,
        config.substrate_epsilon_r,config.substrate_loss_tangent),port,assumptions)
    validate_pcb_geometry(geometry);audit_physical_feed(geometry)
    return config,geometry,dict(source_directory=str(Path(directory).resolve()),discovered_files=records,
        physical_config=value,physical_config_source=origin,feed_detection=feed)
