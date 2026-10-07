"""Compound paths keep copper holes transparent, without painting over islands."""
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from shapely.geometry.polygon import orient
from antenna_lab.pcb.regions import copper_shape


def copper_patch(copper, **style):
    polygon = orient(copper_shape(copper), sign=1.0)
    vertices, codes = [], []
    for ring in (polygon.exterior, *polygon.interiors):
        points = [(x*1e3,y*1e3) for x,y in ring.coords]
        vertices.extend(points)
        codes.extend([Path.MOVETO, *[Path.LINETO]*(len(points)-2), Path.CLOSEPOLY])
    return PathPatch(Path(vertices, codes), **style)
