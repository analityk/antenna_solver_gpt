"""PCB-002: simple planar polygons, without unions or Gerber connectivity."""

from math import hypot, isfinite

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import PcbGeometry

# Absolute distance tolerance in metres (0.1 nm), including plane membership.
# Coordinates are never snapped or modified.
TOLERANCE_M = 1e-10


def _require(condition, message):
    if not condition:
        raise ConfigurationError(message)


def _finite(value):
    try:
        return not isinstance(value, bool) and isfinite(value)
    except (TypeError, ValueError, OverflowError):
        return False


def _point(point, label):
    _require(isinstance(point, (tuple, list)) and len(point) == 2
             and all(_finite(v) for v in point), f"{label}: wymagane skończone współrzędne XY.")


def _distance(a, b):
    return hypot(a[0] - b[0], a[1] - b[1])


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(p, a, b):
    length = _distance(a, b)
    if length <= TOLERANCE_M:
        return _distance(p, a) <= TOLERANCE_M
    if abs(_cross(a, b, p)) > TOLERANCE_M * length:
        return False
    projection = ((p[0] - a[0]) * (b[0] - a[0])
                  + (p[1] - a[1]) * (b[1] - a[1])) / length
    return -TOLERANCE_M <= projection <= length + TOLERANCE_M


def _intersect(a, b, c, d):
    if any((_on_segment(c, a, b), _on_segment(d, a, b),
            _on_segment(a, c, d), _on_segment(b, c, d))):
        return True
    return ((_cross(a, b, c) > 0) != (_cross(a, b, d) > 0)
            and (_cross(c, d, a) > 0) != (_cross(c, d, b) > 0))


def _polygon(vertices, label):
    _require(isinstance(vertices, (tuple, list)) and len(vertices) >= 3,
             f"{label}: wymagane co najmniej trzy wierzchołki.")
    for point in vertices:
        _point(point, label)
    points = [tuple(p) for p in vertices]
    if points[-1] == points[0]:
        points.pop()  # Logical closure only; supplied geometry is unchanged.
    _require(len(set(points)) >= 3, f"{label}: wymagane trzy unikalne wierzchołki.")
    edges = list(zip(points, points[1:] + points[:1]))
    lengths = [_distance(a, b) for a, b in edges]
    _require(all(length > TOLERANCE_M for length in lengths),
             f"{label}: zdegenerowana krawędź.")
    # Shifted shoelace formula avoids cancellation far from the origin.
    twice_area = sum(_cross(points[0], a, b) for a, b in edges)
    _require(isfinite(twice_area) and abs(twice_area) > TOLERANCE_M * sum(lengths),
             f"{label}: zerowe lub numerycznie zdegenerowane pole.")
    # GEOS rejects true intersections without the quadratic Python edge scan.
    # No repair, snapping or geometry replacement is performed.
    from shapely.geometry import LineString, Polygon
    from shapely.strtree import STRtree
    _require(Polygon(points).is_valid,
             f"{label}: obrys musi być prosty, bez samoprzecięć.")
    # Retain the historical tolerance for near contacts. Spatial queries visit
    # only neighbouring edges, not every pair of edges in a large CAD ring.
    segments = [LineString(edge) for edge in edges]
    tree = STRtree(segments)
    for i, (a, b) in enumerate(edges):
        c = points[(i + 2) % len(points)]
        _require(not (_on_segment(c, a, b) or _on_segment(a, b, c)),
                 f"{label}: nakładające się sąsiednie krawędzie.")
        for j in tree.query(segments[i], predicate="dwithin", distance=2 * TOLERANCE_M):
            if j <= i:
                continue
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            _require(not _intersect(a, b, *edges[j]),
                     f"{label}: obrys musi być prosty, bez samoprzecięć.")
    return points


def _contains(point, polygon):
    inside = False
    x, y = point
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if _on_segment(point, a, b):
            return True
        if (a[1] > y) != (b[1] > y):
            crossing_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < crossing_x:
                inside = not inside
    return inside


def _contains_copper(point, copper):
    """Boundary-inclusive metal contact; interiors of cutouts are not metal.

    A hole edge belongs to the metal face, matching outer-edge contact semantics.
    The existing distance tolerance only handles numerical boundary residue.
    """
    if not _contains(point, copper.vertices_xy_m):
        return False
    for ring in copper.holes_xy_m:
        if _contains(point, ring) and not any(_on_segment(point,a,b)
                for a,b in zip(ring, ring[1:]+ring[:1])):
            return False
    return True


def _same_outline(a, b):
    # Accept cyclic shifts, reverse winding and optional closing vertex.
    # Different vertex subdivisions are conservatively rejected in v0.
    if len(a) != len(b):
        return False
    return any(all(_distance(p, b[(start + direction * i) % len(b)]) <= TOLERANCE_M
                   for i, p in enumerate(a))
               for start in range(len(b)) for direction in (1, -1))


def validate_pcb_geometry(geometry: PcbGeometry):
    """Return a geometry-only result or raise ConfigurationError.

    Each CopperPolygon record is treated as one conductor. Endpoint membership
    in several records is rejected as ambiguous; unions/nets are not inferred.
    A remote conductive path may join both terminals. Physical and solver-grid
    feed audits, not conductor IDs, establish whether the local gap is clear.
    This check does not establish physical validity or solver convergence.
    """
    _require(geometry.model == "pcb", "model: wymagane 'pcb'.")
    _require(geometry.outline is not None, "outline: brak obrysu PCB.")
    board = _polygon(geometry.outline.vertices_xy_m, "outline")
    substrate = geometry.substrate
    _require(substrate is not None and substrate.outline is not None,
             "substrate: brak laminatu lub obrysu.")
    for name in ("z_min_m", "z_max_m", "epsilon_r", "loss_tangent"):
        _require(_finite(getattr(substrate, name)), f"substrate.{name}: wartość musi być skończona.")
    _require(substrate.z_max_m > substrate.z_min_m, "substrate: grubość musi być dodatnia.")
    _require(abs(substrate.z_max_m) <= TOLERANCE_M, "substrate.z_max_m: PCB v0 wymaga z=0.")
    _require(substrate.epsilon_r >= 1, "substrate.epsilon_r: wymagane >= 1.")
    _require(substrate.loss_tangent >= 0, "substrate.loss_tangent: wymagane >= 0.")
    substrate_outline = _polygon(substrate.outline.vertices_xy_m, "substrate.outline")
    _require(_same_outline(board, substrate_outline), "substrate.outline: obrys nie zgadza się z PCB.")

    if geometry.dielectric_layers or geometry.copper_layers:
        layers, sheets = geometry.dielectric_layers, geometry.copper_layers
        _require(bool(layers) and 2 <= len(sheets) <= len(layers)+1, 'stackup: inconsistent dielectric/copper layer count.')
        _require([c.role for c in sheets] == ['top', *[f'inner{i}' for i in range(1,len(sheets)-1)], 'bottom'],
                 'stackup: invalid copper role ordering.')
        _require(len({d.name for d in layers}) == len(layers), 'stackup: duplicate dielectric names.')
        _require(all(getattr(substrate,k) == getattr(layers[0],k)
                     for k in ('outline','z_min_m','z_max_m','epsilon_r','loss_tangent')),
                 'substrate: legacy view must equal first actual dielectric material.')
        top = 0.0
        for layer in layers:
            _require(bool(layer.name.strip()), 'stackup: empty dielectric name.')
            _require(all(_finite(getattr(layer,k)) for k in ('z_min_m','z_max_m','epsilon_r','loss_tangent')),
                     'stackup: finite dielectric coordinates/material required.')
            _require(layer.z_max_m == top and layer.z_min_m < top, 'stackup: dielectric gap, overlap or invalid thickness.')
            _require(layer.epsilon_r >= 1 and layer.loss_tangent >= 0, 'stackup: invalid dielectric material.')
            _require(_same_outline(board, _polygon(layer.outline.vertices_xy_m, layer.name)), 'stackup: outline mismatch.')
            top = layer.z_min_m
        interfaces = {v for d in layers for v in (d.z_min_m,d.z_max_m)}
        _require(sheets[0].z_m == 0.0 and sheets[-1].z_m == top, 'stackup: top/bottom copper/interface mismatch.')
        _require(all(c.z_m in interfaces for c in sheets) and
                 all(a.z_m > b.z_m for a,b in zip(sheets,sheets[1:])), 'stackup: copper/interface mismatch or order.')
        for sheet in sheets:
            _require(sheet.model in ('pec','conducting_sheet'), 'stackup: unsupported copper model.')
            _require(all(_finite(v) and v > 0 for v in (sheet.thickness_m,sheet.conductivity_s_m)),
                     'stackup: positive finite copper inputs required.')
        _require(len({c.id for c in geometry.copper}) == len(geometry.copper), 'stackup: duplicate copper polygon ids.')
        _require({c.layer_role for c in geometry.copper} == {c.role for c in sheets}, 'stackup: missing/extra polygon layer.')

    _require(bool(geometry.copper), "copper: wymagana co najmniej jedna wyspa miedzi.")
    polygons = []
    for index, copper in enumerate(geometry.copper):
        label = f"copper[{index}]"
        _require(isinstance(copper.id, str) and bool(copper.id.strip()), f"{label}.id: puste ID.")
        plane = next((c.z_m for c in geometry.copper_layers if c.role == copper.layer_role), None) if geometry.copper_layers else 0.0
        _require(copper.layer_role == 'top' or bool(geometry.copper_layers), f'{label}: unexpected non-top layer.')
        _require(plane is not None and _finite(copper.z_m) and abs(copper.z_m-plane) <= TOLERANCE_M,
                 f"{label}.z_m: required finite copper layer plane.")
        polygons.append(_polygon(copper.vertices_xy_m, label))
        for h, ring in enumerate(copper.holes_xy_m):
            _polygon(ring, f'{label}.holes[{h}]')
        if copper.holes_xy_m:
            from .regions import copper_shape
            _require(copper_shape(copper).is_valid,
                     f'{label}: holes must be valid, disjoint interior rings within the outer ring; no repair.')

    port = geometry.port
    _require(port is not None, "port: brak portu.")
    _require(isinstance(port.id, str) and bool(port.id.strip()), "port.id: puste ID.")
    _point(port.negative_xy_m, "port.negative_xy_m")
    _point(port.positive_xy_m, "port.positive_xy_m")
    _require(_finite(port.width_m) and port.width_m > 0, "port.width_m: wymagana dodatnia skończona szerokość.")
    _require(_distance(port.negative_xy_m, port.positive_xy_m) > TOLERANCE_M,
             "port: końce muszą być różne.")
    for name, point in (("negative", port.negative_xy_m), ("positive", port.positive_xy_m)):
        _require(_contains(point, board), f"port.{name}: koniec poza obrysem PCB.")
        members = [i for i, polygon in enumerate(polygons) if geometry.copper[i].layer_role == "top" and _contains_copper(point, geometry.copper[i])]
        _require(len(members) == 1, f"port.{name}: wymagana przynależność do dokładnie jednej wyspy miedzi.")
    if geometry.drills:
        from .drills import validate_drills
        validate_drills(geometry)
    return {"geometry_status": "passed", "electromagnetic_status": "unverified",
            "copper_count": len(polygons)}
