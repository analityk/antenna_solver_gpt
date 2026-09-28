"""Align the lumped source box to its mesh anchors, with an explicit audit.

openEMS snaps the resistor to the mesh but selects excitation edges by box
membership. Even sub-picometre rounding can exclude a whole boundary layer.
This module handles one Cartesian, x-directed lumped port, not general ports.
"""

import math

import numpy as np

from antenna_lab.core.config import ConfigurationError

# mesh._axis rounds anchors to 12 decimal places in metres. This permits only
# that numerical rounding, never an appreciable move to an arbitrary cell.
ANCHOR_TOLERANCE_M = 1e-12


def nominal_bounds(port):
    if port.negative[1:] != port.positive[1:] or port.negative[0] >= port.positive[0]:
        raise ConfigurationError("Adapter wymaga obecnie portu skierowanego w +x.")
    half = port.transverse_size_m / 2
    start = [port.negative[0], port.negative[1] - half, port.negative[2] - half]
    stop = [port.positive[0], port.positive[1] + half, port.positive[2] + half]
    if not np.isfinite([start, stop]).all() or np.any(np.asarray(stop) <= start):
        raise ConfigurationError("Port musi mieć dodatnie, skończone wymiary.")
    return start, stop


def resolve_feed(port, axes, alignment="legacy"):
    """Return the exact AddLumpedPort bounds and a geometric coverage audit.

    Legacy preserves the original experiment. mesh_anchors fixes only bounds
    differing from existing anchors by <= 1 pm. Neither mode modifies axes.
    Counts describe box membership before building the native operator; they
    are not a measurement of excitation strength or a field validation.
    """
    if alignment not in ("legacy", "mesh_anchors"):
        raise ConfigurationError("Nieznany tryb port_mesh_alignment.")
    nominal_start, nominal_stop = nominal_bounds(port)
    indices, snapped_start, snapped_stop = [], [], []
    for n, axis in enumerate("xyz"):
        lines = np.asarray(axes[axis], float)
        if (lines.ndim != 1 or len(lines) < 2 or not np.isfinite(lines).all()
                or np.any(np.diff(lines) <= 0)):
            raise ConfigurationError("Nieprawidłowe linie siatki portu.")
        first = int(np.argmin(abs(lines - nominal_start[n])))
        last = int(np.argmin(abs(lines - nominal_stop[n])))
        if first >= last:
            raise ConfigurationError("Siatka nie rozdziela granic portu.")
        indices.append((first, last))
        snapped_start.append(float(lines[first]))
        snapped_stop.append(float(lines[last]))
    rounding = np.array([snapped_start, snapped_stop]) - [nominal_start, nominal_stop]
    if alignment == "mesh_anchors" and np.max(abs(rounding)) > ANCHOR_TOLERANCE_M:
        raise ConfigurationError("Granice portu nie są kotwicami siatki (odchyłka > 1e-12 m). "
                                 "Nie przesunięto źródła do odległej komórki.")
    start, stop = ((snapped_start, snapped_stop) if alignment == "mesh_anchors"
                   else (nominal_start, nominal_stop))
    included, excluded, shape = {}, {}, []
    for n, axis in enumerate("xyz"):
        first, last = indices[n]
        # E_x is at x half-steps, but at the primary y/z lines.
        ids = np.arange(first, last if n == 0 else last + 1)
        lines = np.asarray(axes[axis], float)
        positions = (lines[ids] + lines[ids + 1]) / 2 if n == 0 else lines[ids]
        inside = (positions >= start[n]) & (positions <= stop[n])
        shape.append(len(ids))
        included[axis] = ids[inside].tolist()
        excluded[axis] = ids[~inside].tolist()
    count = math.prod(len(included[a]) for a in "xyz")
    total = math.prod(shape)
    if alignment == "mesh_anchors" and count != total:
        raise ConfigurationError("Wymuszenie nie obejmuje wszystkich krawędzi portu.")
    adjustment = np.array([start, stop]) - [nominal_start, nominal_stop]
    return {
        "alignment": alignment, "direction": "+x", "square_caps": True,
        "nominal_start_m": nominal_start, "nominal_stop_m": nominal_stop,
        "start_m": start, "stop_m": stop,
        "mesh_start_index": [pair[0] for pair in indices],
        "mesh_stop_index": [pair[1] for pair in indices],
        "anchor_tolerance_m": ANCHOR_TOLERANCE_M,
        "max_coordinate_adjustment_m": float(np.max(abs(adjustment))),
        "edge_shape": shape, "resistor_edge_count": total,
        "excitation_box_edge_count": count, "excluded_edge_count": total - count,
        "included_axis_indices": included, "excluded_axis_indices": excluded,
        "method": "cartesian_box_membership_at_x_directed_yee_edges",
        "scope": "geometric_coverage_before_native_operator_build_not_field_validation",
    }
