import math

from antenna_lab.core.config import ConfigurationError, validate_schema
from antenna_lab.core.geometry import Geometry, Plate, Port, Wire, check_geometry


def build(parameters, reflector=True):
    validate_schema(parameters, "quados8-parameters.schema.json")
    d = parameters["dimensions_m"]
    radius = d["wire_diameter"] / 2
    q, gap, height = d["E"] / math.sqrt(2), d["G"], d["H"]
    if gap <= 2 * radius:
        raise ConfigurationError("G musi być większe od średnicy drutu.")
    if reflector and height <= radius:
        raise ConfigurationError("H musi być większe od promienia drutu.")
    if d["F"] <= gap / 2 + q:
        raise ConfigurationError("F musi być większe od G/2 + E/sqrt(2), aby domknąć wierzchołek.")
    moves = []
    for label in ("A", "B", "C", "D"):
        moves.append((label, 0, d[label]))
        moves.append(("E", q, q))
        if label != "D":
            moves.append(("E", -q, q))
    moves.append(("F", -(gap / 2 + q), math.sqrt(d["F"] ** 2 - (gap / 2 + q) ** 2)))
    wires = []
    for sx, sy, branch in ((1, 1, "RU"), (-1, 1, "LU"), (1, -1, "RD"), (-1, -1, "LD")):
        x, y = gap / 2, 0.0
        for i, (label, dx, dy) in enumerate(moves):
            start = (sx * x, sy * y, height)
            x, y = x + dx, y + dy
            if label == "F":
                x = 0.0  # identical shared endpoint on the symmetry axis
            wires.append(Wire(f"{branch}_{i:02}_{label}", start, (sx * x, sy * y, height), radius, branch, label))
    plates = [Plate("reflector", (-d["reflector_width"] / 2, -d["reflector_length"] / 2, -d["reflector_thickness"]),
                    (d["reflector_width"] / 2, d["reflector_length"] / 2, 0.0))] if reflector else []
    geometry = Geometry("quados8", wires, plates,
                        Port("feed", (-gap / 2, 0.0, height), (gap / 2, 0.0, height), 2 * radius),
                        ["Four branches reconstructed from the supplied YU1AW drawing.",
                         "Straight E segments at 45 degrees; F closes each end with its own angle.",
                         "PEC cylinders and spherical joints; construction lengths refer to wire axes.",
                         "Finite PEC reflector plate when enabled; no balun, coax, supports, ground or material losses.",
                         "Ideal differential lumped port; reference resistance is not an assumed antenna impedance."])
    check_geometry(geometry)
    return geometry
