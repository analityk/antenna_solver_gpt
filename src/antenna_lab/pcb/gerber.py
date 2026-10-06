"""Positive RS-274X top copper and one outline; Gerbonara parses, Shapely unions.

Gerbonara graphics are requested in mm and converted here to SI. Curves are
polygonized with a 0.1 um geometric approximation budget (not FDTD accuracy).
PCB-v0 cannot represent holes or point-only conductor junctions; reject these
rather than fill holes, split a connected conductor, or repair invalid shapes.
"""

from math import acos, ceil, pi
from pathlib import Path
import warnings

from gerbonara import GerberFile
from gerbonara import graphic_objects as go, graphic_primitives as gp
from gerbonara.apertures import CircleAperture
from gerbonara.utils import MM, approximate_arc
from shapely import normalize, union_all
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize_full

from antenna_lab.core.config import ConfigurationError
from .config import ResolvedPcbConfig
from .model import BoardOutline, CopperPolygon, PcbGeometry, PcbPort, Substrate
from .validation import validate_pcb_geometry

CURVE_ERROR_M = 1e-7
# Remove only sub-picometre boolean/curve residues, never snap to a mesh/grid.
BOOLEAN_CLEANUP_M = 1e-12
ASSUMPTIONS = (
    'top copper: PEC, zero thickness in solver', 'soldermask: omitted',
    'silkscreen: omitted', 'paste: omitted', 'no bottom copper', 'no vias',
    'substrate parameters: from pcb.json', 'validation_status: unverified',
    'GKO board boundary: stroke centreline, not aperture outer edge',
    f'curve polygonization maximum geometric error budget: {CURVE_ERROR_M} m',
    f'boolean contour cleanup tolerance: {BOOLEAN_CLEANUP_M} m',
)


def _read(path, role):
    path = Path(path)
    if role == 'top copper' and path.suffix.lower() in {
            '.gtp', '.gto', '.gts', '.gbl', '.gbp', '.gbo', '.gbs', '.drl', '.gko'}:
        raise ConfigurationError(f'{path}: expected top copper, not mask/paste/silk/bottom/drill/outline.')
    try:
        with warnings.catch_warnings():
            # Gerbonara can otherwise ignore unknown commands or missing EOF.
            warnings.simplefilter('error')
            gerber = GerberFile.open(path, enable_includes=False)
    except (OSError, ValueError, SyntaxError, Warning) as exc:
        raise ConfigurationError(f'{role}: cannot parse {path}: {exc}') from exc
    if not gerber.objects:
        raise ConfigurationError(f'{role}: empty Gerber {path}.')
    function = ','.join(gerber.file_attrs.get('.FileFunction', ())).lower()
    if role == 'top copper' and function and ('copper' not in function or 'top' not in function):
        raise ConfigurationError(f'{path}: FileFunction is not top copper: {function}.')
    if any(not obj.polarity_dark for obj in gerber.objects):
        raise ConfigurationError(f'{path}: clear/negative polarity is unsupported in PCB-v0.')
    return gerber


def _buffer(shape, radius, error_mm):
    if radius <= 0:
        raise ConfigurationError('Copper stroke/flash must have positive width.')
    # Maximum chord sagitta for each quarter-circle in Shapely's round buffer.
    count = max(1, ceil(pi / (4 * acos(1 - min(error_mm / radius, 1.)))))
    return shape.buffer(radius, quad_segs=count)


def _primitive_polygon(primitive):
    error = CURVE_ERROR_M * 1e3
    if not primitive.polarity_dark:
        raise ConfigurationError('Clear aperture primitives/holes are unsupported in PCB-v0.')
    if isinstance(primitive, gp.Circle):
        return _buffer(Point(primitive.x, primitive.y), primitive.r, error)
    if isinstance(primitive, gp.Line):
        a, b = (primitive.x1, primitive.y1), (primitive.x2, primitive.y2)
        shape = Point(a) if a == b else LineString((a,b))
        return _buffer(shape, primitive.width/2, error)
    if isinstance(primitive, gp.Arc):
        # Shared Gerbonara arc tessellation; split the budget between path/caps.
        points = list(approximate_arc(primitive.cx, primitive.cy,
            primitive.x1, primitive.y1, primitive.x2, primitive.y2,
            primitive.clockwise, max_error=error/2))
        return _buffer(LineString(points), primitive.width/2, error/2)
    polygon = primitive.to_arc_poly().approximate_arcs(max_error=error)
    return Polygon(polygon.outline)


def _simple_polygon(polygon, label):
    if polygon.is_empty or polygon.geom_type != 'Polygon' or not polygon.is_valid or polygon.area <= 0:
        raise ConfigurationError(f'{label}: invalid/degenerate polygon; no automatic repair.')
    if polygon.interiors:
        raise ConfigurationError(f'{label}: holes/cutouts are unsupported by PCB-v0 polygons.')
    return polygon


def _vertices(polygon):
    # GEOS normalize makes winding, ring start and conductor ordering repeatable.
    polygon = normalize(polygon.simplify(BOOLEAN_CLEANUP_M*1e3, preserve_topology=True))
    return tuple((float(x)*1e-3, float(y)*1e-3) for x,y in polygon.exterior.coords[:-1])


def _copper(gerber):
    shapes = []
    for obj in gerber.objects:
        if isinstance(obj, (go.Line, go.Arc)) and not isinstance(obj.aperture, CircleAperture):
            raise ConfigurationError('PCB-v0 supports circular-aperture strokes only; do not approximate other strokes.')
        for primitive in obj.to_primitives(unit=MM):
            shape = _primitive_polygon(primitive)
            if shape.is_empty or not shape.is_valid or shape.area <= 0:
                raise ConfigurationError('Invalid copper primitive; no automatic repair.')
            shapes.append(shape)
    merged = union_all(shapes)
    if merged.geom_type not in ('Polygon', 'MultiPolygon'):
        raise ConfigurationError('Copper union is not polygonal.')
    polygons = [merged] if merged.geom_type == 'Polygon' else list(merged.geoms)
    for i, polygon in enumerate(polygons):
        _simple_polygon(polygon, 'copper')
        if any(polygon.intersects(other) for other in polygons[i+1:]):
            raise ConfigurationError('Point-only copper contact cannot be represented as one simple PCB-v0 conductor.')
    polygons.sort(key=lambda p: (p.bounds, normalize(p).wkb))
    return [CopperPolygon(f'copper_{i+1:04d}', _vertices(p), 0.) for i,p in enumerate(polygons)]


def _outline(gerber):
    lines, regions = [], []
    for obj in gerber.objects:
        obj = obj.converted(MM)
        if isinstance(obj, go.Line):
            lines.append(LineString((obj.p1, obj.p2)))
        elif isinstance(obj, go.Arc):
            segments = obj.approximate(max_error=CURVE_ERROR_M*1e3, unit=MM)
            lines.append(LineString([segments[0].p1, *(s.p2 for s in segments)]))
        elif isinstance(obj, go.Region):
            regions.extend(_primitive_polygon(p) for p in obj.to_primitives(unit=MM))
        else:
            raise ConfigurationError('GKO: expected contour lines/arcs or one region, not flashed pads.')
    if regions:
        if lines or len(regions) != 1:
            raise ConfigurationError('GKO: ambiguous mixed/disconnected outline geometry.')
        polygon = regions[0]
    else:
        polygons, cuts, dangles, invalid = polygonize_full(lines)
        if len(polygons.geoms) != 1 or any(not g.is_empty for g in (cuts,dangles,invalid)):
            raise ConfigurationError('GKO: require one closed outer contour, no branches, gaps or disconnected contours.')
        polygon = polygons.geoms[0]
    return BoardOutline(_vertices(_simple_polygon(polygon, 'GKO')))


def load_pcb_geometry(config: ResolvedPcbConfig) -> PcbGeometry:
    """Import and validate source coordinates in SI; never normalize or infer a port."""
    if config.copper_model != 'pec':
        raise ConfigurationError('PCB-v0 Gerber copper model must be pec.')
    try:
        outline = _outline(_read(config.board_outline_path, 'board outline'))
        copper = _copper(_read(config.copper_top_path, 'top copper'))
    except (GEOSException, ValueError, NotImplementedError) as exc:
        raise ConfigurationError(f'Gerber geometry conversion failed: {exc}') from exc
    geometry = PcbGeometry('pcb', outline, copper,
        Substrate(outline, -config.substrate_thickness_m, 0.,
                  config.substrate_epsilon_r, config.substrate_loss_tangent),
        PcbPort('gerber_feed', config.port_negative_xy_m, config.port_positive_xy_m, config.port_width_m),
        list(ASSUMPTIONS))
    validate_pcb_geometry(geometry)
    return geometry
