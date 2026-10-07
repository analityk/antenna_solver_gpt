"""One shared conversion for live/saved planar copper, including interior rings."""

def copper_shape(copper, transform=None):
    from shapely.geometry import Polygon
    if isinstance(copper, dict):
        outer, holes = copper['vertices_xy_m'], copper.get('holes_xy_m', ())
    else:
        outer, holes = copper.vertices_xy_m, copper.holes_xy_m
    if transform is not None:
        outer = [transform(p) for p in outer]
        holes = [[transform(p) for p in ring] for ring in holes]
    return Polygon(outer, holes)
