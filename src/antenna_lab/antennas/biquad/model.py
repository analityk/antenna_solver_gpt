"""Two near-square loops, eight equal wire segments and a differential gap."""

import math

from antenna_lab.core.config import ConfigurationError, validate_schema
from antenna_lab.core.geometry import Geometry, Plate, Port, Wire, check_geometry


def build(parameters, reflector=True):
    validate_schema(parameters, "biquad-parameters.schema.json")
    d = parameters["dimensions_m"]
    side, gap, height = d["S"], d["G"], d["H"]
    radius = d["wire_diameter"] / 2
    if gap <= 2 * radius:
        raise ConfigurationError("G musi być większe od średnicy drutu.")
    if reflector and height <= radius:
        raise ConfigurationError("H musi być większe od promienia drutu.")
    q = side / math.sqrt(2)
    half_width = q + gap / 2
    if half_width >= side:
        raise ConfigurationError("Szczelina G jest za duża względem boku S, aby domknąć biquad.")
    tip_height = q + math.sqrt(side * side - half_width * half_width)
    negative, positive = (-gap / 2, 0.0, height), (gap / 2, 0.0, height)
    wires = []
    for sign, branch in ((1, "upper"), (-1, "lower")):
        points = [negative, (-half_width, sign * q, height),
                  (0.0, sign * tip_height, height), (half_width, sign * q, height), positive]
        for i, (start, stop) in enumerate(zip(points, points[1:])):
            wires.append(Wire(f"{branch}_{i:02}", start, stop, radius, branch, "S"))
    plates = [Plate("reflector", (-d["reflector_width"] / 2, -d["reflector_length"] / 2, -d["reflector_thickness"]),
                    (d["reflector_width"] / 2, d["reflector_length"] / 2, 0.0))] if reflector else []
    geometry = Geometry("biquad", wires, plates, Port("feed", negative, positive, 2 * radius),
                        ["Classic two-loop biquad; two four-segment paths connect the same differential terminals.",
                         "All eight centreline segments have length S. Finite G deforms the square corners slightly; no metal bridges the feed gap.",
                         "H is measured from the reflector front surface to the wire axes. PEC cylinders and spherical joints.",
                         "Finite PEC plate; ideal x-directed differential port. No coax, balun, supports, ground or material losses.",
                         "Starting dimensions are not tuned or electromagnetically validated."])
    check_geometry(geometry)
    return geometry
