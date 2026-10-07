"""Round through-drills parsed by Gerbonara; no NC-drill grammar lives here.

Filename/comment inspection is fabrication metadata only. A file must have one
unambiguous plating class and a through span. PTH uses a solid PEC equivalent,
not a resolved barrel wall. Original tool numbers come from Gerbonara's pinned
ExcellonParser tool map (the high-level file discards those numbers).
"""
from dataclasses import replace
from hashlib import sha256
from math import isfinite, hypot
from pathlib import Path
import re
import warnings

from gerbonara import ExcellonFile
from gerbonara.excellon import ExcellonParser
from gerbonara.apertures import ExcellonTool
from gerbonara.graphic_objects import Flash
from gerbonara.utils import MM
from shapely.geometry import Point, Polygon

from antenna_lab.core.config import ConfigurationError
from .model import PcbDrill, QuantizedPcbDrill
from .regions import copper_shape

PTH_MODEL_NOTE = 'PTH barrel model: solid PEC equivalent cylinder; plating losses and hollow barrel geometry are not modeled.'


def read_drill_source(path, layer_count):
    path = Path(path)
    try:
        with warnings.catch_warnings(record=True) as parser_warnings:
            warnings.simplefilter('always')
            parsed = ExcellonFile.open(path)
            parser = ExcellonParser(settings=parsed.import_settings)
            parser.do_parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    except (ValueError, SyntaxError, OSError, Warning) as exc:
        raise ConfigurationError(f'{path.name}: unsupported/invalid Excellon: {exc}') from exc
    compatibility_warnings = []
    # Match Gerbonara's complete diagnostic, including the actual statement.
    # No source rewriting or NC parsing; all other parser warnings stay fatal.
    accepted = re.compile(re.escape(str(path)) +
        r':\d+ "G90": G90 header statement found after end of header')
    for warning in parser_warnings:
        text = str(warning.message)
        if warning.category is not SyntaxWarning or accepted.fullmatch(text) is None:
            raise ConfigurationError(f'{path.name}: unsupported/invalid Excellon parser warning: {text}')
        record = dict(source_filename=path.name, statement='G90', warning_text=text,
                      disposition='accepted_gerbonara_compatibility_warning')
        # open() and the tool-ID parse can report the same source occurrence.
        if record not in compatibility_warnings:
            compatibility_warnings.append(record)
    if not parser.objects:
        raise ConfigurationError(f'{path.name}: empty drill source.')
    if any(not isinstance(o, Flash) or not isinstance(o.aperture, ExcellonTool) for o in parser.objects):
        raise ConfigurationError(f'{path.name}: routed/slot/non-round drills unsupported; round through drills only.')
    # Only comment metadata, never coordinates/tool syntax, is inspected here.
    comments = [line.strip()[1:].strip() for line in path.read_text(encoding='utf-8-sig').splitlines()
                if line.strip().startswith(';')]
    metadata = ' '.join(comments)
    if re.search(r'blind|buried|microvia', path.name+' '+metadata, re.I):
        raise ConfigurationError(f'{path.name}: blind/buried/microvia spans unsupported.')
    for a,b in re.findall(r'(?:^|[_. -])(?:L|layer)?[ _-]?(\d+)[ _-]+(?:L|layer)?[ _-]?(\d+)(?:$|[_. -])', path.stem, re.I):
        if (int(a),int(b)) != (1,layer_count):
            raise ConfigurationError(f'{path.name}: non-through drill span {a}-{b}.')
    classes = {o.plated for o in parser.objects if o.plated is not None}
    external = set()
    name = path.stem.lower()
    if re.search(r'(?:^|[_. -])(?:npth|non[ _-]?plated)(?:$|[_. -])',name): external.add(False)
    elif re.search(r'(?:^|[_. -])(?:pth|plated)(?:$|[_. -])',name): external.add(True)
    for comment in comments:
        if 'filefunction' in comment.lower():
            values = comment.strip('%* ').split(',')[1:]
            values = [v.strip('*% ').lower() for v in values]
            if not values or values[0] not in ('plated','nonplated'):
                raise ConfigurationError(f'{path.name}: unsupported/ambiguous drill FileFunction {comment}.')
            external.add(values[0]=='plated')
            if len(values)<3 or values[1:3] != ['1',str(layer_count)]:
                raise ConfigurationError(f'{path.name}: FileFunction requires through span 1-{layer_count}.')
            if any(v in ('route','rout','mixed') for v in values):
                raise ConfigurationError(f'{path.name}: routes/mixed drill functions unsupported.')
        if comment.lower().startswith('contents:'):
            if not re.match(r'Contents:\s*Thru\s*/\s*Drill\s*/',comment,re.I):
                raise ConfigurationError(f'{path.name}: non-through or routed Contents metadata unsupported.')
    classes |= external
    if len(classes)!=1 or (any(o.plated is None for o in parser.objects) and not external):
        raise ConfigurationError(f'Ambiguous/conflicting PTH/NPTH classification; candidates: {path.name}. Use explicit fabrication PTH/NPTH names/metadata.')
    plated=classes.pop(); role='PTH' if plated else 'NPTH'
    tools={id(tool):f'T{number:02d}' for number,tool in parser.tools.items()}
    holes=[];diameters={}
    for obj in parser.objects:
        tool=obj.aperture
        diameter=MM(tool.diameter,tool.unit)*1e-3
        x,y=MM(obj.x,obj.unit)*1e-3,MM(obj.y,obj.unit)*1e-3
        if not all(isfinite(v) for v in (x,y,diameter)) or diameter<=0:
            raise ConfigurationError(f'{path.name}: nonpositive/nonfinite round drill diameter or coordinate.')
        identifier=tools.get(id(tool))
        if identifier is None:
            raise ConfigurationError(f'{path.name}: cannot preserve source tool identity.')
        diameters[identifier]=diameter
        holes.append((x,y,diameter,identifier))
    info=dict(path=str(path.resolve()),sha256=sha256(path.read_bytes()).hexdigest(),
        classification=role,tool_diameters_m=diameters,hole_count=len(holes),span='through',
        compatibility_warnings=compatibility_warnings,
        classification_policy='Gerbonara plating metadata + X2 comments + conventional filename; conflicts rejected')
    return holes,info


def connected_layers(geometry, x, y, radius):
    point=Point(x,y)
    return tuple(layer.role for layer in geometry.copper_layers if any(
        point.distance(copper_shape(c)) <= radius for c in geometry.copper if c.layer_role==layer.role))


def load_drills(geometry, records, settings):
    from .validation import TOLERANCE_M
    drills=[];sources=[];parsed=[];owners=[]
    # Parse every source, including auxiliary exports, before deduplicating.
    # Lexical order puts Through.DRL before Through_Via.DRL, independent of
    # discovery/input order. Coordinates are retained from the owner, not averaged.
    records=sorted((r for r in records if r['role'] in ('PTH','NPTH')),
        key=lambda r:(Path(r['path']).name.casefold(),Path(r['path']).name,str(r['path'])))
    for record in records:
        holes,info=read_drill_source(record['path'],len(geometry.copper_layers))
        info.update(suppressed_duplicate_holes=[],modeled_hole_count=0)
        sources.append(info);parsed.append((record,holes,info))
    for record,holes,info in parsed:
        plated=info['classification']=='PTH'
        if plated and settings is None:
            raise ConfigurationError('PTH requires explicit v2 drills.pth_plating_um and pth_model=solid_pec_equivalent.')
        thickness=settings['pth_plating_um']*1e-6 if plated else None
        for index,(x,y,diameter,tool) in enumerate(holes,1):
            identifier=f'{Path(record["path"]).name}:{index}'
            canonical=next((d for d,source in owners
                if plated and d.plated and info['span']=='through' and source['span']=='through'
                and source['path']!=info['path']
                and hypot(x-d.x_m,y-d.y_m)<=TOLERANCE_M
                and abs(diameter-d.drill_diameter_m)<=TOLERANCE_M),None)
            if canonical is not None:
                info['suppressed_duplicate_holes'].append(dict(
                    source_filename=Path(record['path']).name,tool=tool,x_m=x,y_m=y,
                    drill_diameter_m=diameter,disposition='duplicate_pth_suppressed',
                    canonical_source=next(source['path'] for d,source in owners if d is canonical),
                    canonical_drill_id=canonical.id))
                continue
            radius=diameter/2+thickness if plated else None
            contacts=connected_layers(geometry,x,y,radius) if plated else ()
            drill=PcbDrill(identifier,x,y,diameter,plated,info['classification'],
                tool,info['sha256'],thickness,radius,contacts)
            drills.append(drill);owners.append((drill,info));info['modeled_hole_count']+=1
    result=replace(geometry,drills=tuple(drills))
    if drills: validate_drills(result)
    return result,sources


def validate_drills(geometry):
    if not geometry.copper_layers:
        raise ConfigurationError('Drill modeling requires physical schema v2 stackup.')
    board=Polygon(geometry.outline.vertices_xy_m)
    n,p=geometry.port.negative_xy_m,geometry.port.positive_xy_m
    length=hypot(p[0]-n[0],p[1]-n[1]);half=geometry.port.width_m/2
    if not isfinite(length) or length<=0:
        raise ConfigurationError('Drill audit requires a valid nonzero physical port.')
    dx,dy=-(p[1]-n[1])/length*half,(p[0]-n[0])/length*half
    feed=Polygon([(n[0]+dx,n[1]+dy),(p[0]+dx,p[1]+dy),(p[0]-dx,p[1]-dy),(n[0]-dx,n[1]-dy)])
    ids=set()
    for d in geometry.drills:
        if d.id in ids: raise ConfigurationError('Duplicate drill id: '+d.id)
        ids.add(d.id)
        if not all(isfinite(v) for v in (d.x_m,d.y_m,d.drill_diameter_m)) or d.drill_diameter_m<=0:
            raise ConfigurationError(f'{d.id}: invalid drill dimensions.')
        point=Point(d.x_m,d.y_m)
        radius=d.drill_diameter_m/2
        resolution = None
        if isinstance(d, QuantizedPcbDrill):
            from decimal import Decimal
            from .grid import PcbGrid
            resolution = PcbGrid(d.geometry_resolution_nm)
            source_diameter = d.source_drill_diameter_m
            if source_diameter is None or not isfinite(source_diameter) or source_diameter <= 0:
                raise ConfigurationError(f'{d.id}: geometry resolution requires a positive finite source drill diameter.')
            tick_radius = resolution.nearest_tick(Decimal(str(source_diameter))/2)
            if tick_radius < 1 or d.drill_diameter_m != resolution.to_metres(2*tick_radius):
                raise ConfigurationError(f'{d.id}: modeled drill diameter does not match geometry-resolution projection.')
        if d.plated:
            if d.plating_thickness_m is None or not isfinite(d.plating_thickness_m) or d.plating_thickness_m<=0:
                raise ConfigurationError(f'{d.id}: positive finite PTH plating required.')
            radius+=d.plating_thickness_m
            if resolution is not None:
                # Reproduce PCB-012A projection of the physical solid-equivalent
                # radius. Do not restore source dimensions or loosen topology.
                outer_tick = resolution.nearest_tick(d.source_drill_diameter_m/2+d.plating_thickness_m)
                if outer_tick < tick_radius:
                    raise ConfigurationError(f'{d.id}: modeled PTH outer radius smaller than drill radius.')
                radius = resolution.to_metres(outer_tick)
            if d.equivalent_outer_radius_m != radius:
                raise ConfigurationError(f'{d.id}: inconsistent PTH equivalent radius.')
            contacts=connected_layers(geometry,d.x_m,d.y_m,radius)
            if len(contacts)<2: raise ConfigurationError(f'{d.id}: orphan PTH: fewer than two geometric copper-layer contacts.')
            if contacts!=d.connected_layer_roles: raise ConfigurationError(f'{d.id}: stale geometric PTH contacts.')
        elif d.equivalent_outer_radius_m is not None or d.plating_thickness_m is not None or d.connected_layer_roles:
            raise ConfigurationError(f'{d.id}: NPTH cannot have conductor radius, plating or contacts.')
        if not board.contains(point) or point.distance(board.boundary)<radius:
            raise ConfigurationError(f'{d.id}: round through drill extends outside board.')
        if point.distance(feed)<=radius:
            raise ConfigurationError(f'{d.id}: drill intersects physical port gap/contact; relocate explicit feed.')
    # Overlapping holes cannot be represented as independent barrel/void topology.
    for i,a in enumerate(geometry.drills):
        for b in geometry.drills[i+1:]:
            ra=a.equivalent_outer_radius_m or a.drill_diameter_m/2
            rb=b.equivalent_outer_radius_m or b.drill_diameter_m/2
            if hypot(a.x_m-b.x_m,a.y_m-b.y_m)<=ra+rb:
                raise ConfigurationError(f'Overlapping through drills unsupported: {a.id}, {b.id}.')
