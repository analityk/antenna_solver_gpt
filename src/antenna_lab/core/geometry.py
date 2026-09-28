"""Physical geometry in metres. No antenna names or numerical engine imports."""

from dataclasses import asdict, dataclass, field
import math

import numpy as np

from .config import ConfigurationError

Point = tuple[float, float, float]


@dataclass(frozen=True)
class Wire:
    id: str
    start: Point
    stop: Point
    radius_m: float
    branch: str
    label: str

    @property
    def length_m(self):
        return math.dist(self.start, self.stop)


@dataclass(frozen=True)
class Plate:
    id: str
    start: Point
    stop: Point


@dataclass(frozen=True)
class Port:
    id: str
    negative: Point
    positive: Point
    transverse_size_m: float


@dataclass
class Geometry:
    model: str
    wires: list[Wire]
    plates: list[Plate]
    port: Port
    assumptions: list[str] = field(default_factory=list)

    @property
    def nodes(self):
        unique = {tuple(round(v, 12) for v in p): p for w in self.wires for p in (w.start, w.stop)}
        return [unique[key] for key in sorted(unique)]

    @property
    def bounds(self):
        low, high = [], []
        for w in self.wires:
            low.append(np.minimum(w.start, w.stop) - w.radius_m)
            high.append(np.maximum(w.start, w.stop) + w.radius_m)
        for p in self.plates:
            low.append(p.start)
            high.append(p.stop)
        return np.min(low, axis=0), np.max(high, axis=0)

    def as_dict(self):
        value = asdict(self)
        value.update(schema_version=2, units="m", coordinates="x horizontal, y long axis, z forward")
        return value


def segment_distance(a0, a1, b0, b1):
    """Closest distance of two closed 3-D segments, including parallel cases."""
    p, q = np.asarray(a0, float), np.asarray(b0, float)
    d1, d2 = np.subtract(a1, a0), np.subtract(b1, b0)
    r = p - q
    aa, ee = np.dot(d1, d1), np.dot(d2, d2)
    if aa == 0 or ee == 0:
        raise ConfigurationError("Odcinek o zerowej długości.")
    b, c, f = np.dot(d1, d2), np.dot(d1, r), np.dot(d2, r)
    denom = aa * ee - b * b
    s = np.clip((b * f - c * ee) / denom, 0, 1) if denom > aa * ee * 1e-12 else 0.0
    t = (b * s + f) / ee
    if t < 0:
        t, s = 0.0, np.clip(-c / aa, 0, 1)
    elif t > 1:
        t, s = 1.0, np.clip((b - c) / aa, 0, 1)
    return float(np.linalg.norm(r + s * d1 - t * d2))


def check_geometry(geometry):
    """Check actual connectivity and accidental wire contacts before meshing."""
    if not geometry.wires:
        raise ConfigurationError("Brak przewodów w geometrii.")
    graph = {}
    edges = set()
    key = lambda p: tuple(round(v, 12) for v in p)
    for wire in geometry.wires:
        if wire.radius_m <= 0 or wire.length_m <= 0:
            raise ConfigurationError(f"Nieprawidłowy przewód {wire.id}.")
        if not all(math.isfinite(v) for v in (*wire.start, *wire.stop, wire.radius_m)):
            raise ConfigurationError(f"Nieskończone współrzędne {wire.id}.")
        a, b = key(wire.start), key(wire.stop)
        edge = tuple(sorted((a, b)))
        if edge in edges:
            raise ConfigurationError(f"Powielony odcinek {wire.id}.")
        edges.add(edge)
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)
    visited, pending = set(), [next(iter(graph))]
    while pending:
        node = pending.pop()
        if node not in visited:
            visited.add(node)
            pending.extend(graph[node] - visited)
    if len(visited) != len(graph):
        raise ConfigurationError("Promiennik zawiera odłączony fragment.")
    for terminal in (geometry.port.negative, geometry.port.positive):
        if key(terminal) not in graph:
            raise ConfigurationError("Port nie jest połączony z promiennikiem.")
    for i, a in enumerate(geometry.wires):
        for b in geometry.wires[i + 1:]:
            if {key(a.start), key(a.stop)} & {key(b.start), key(b.stop)}:
                continue  # intended junction; finite-radius elbows overlap
            if segment_distance(a.start, a.stop, b.start, b.stop) < a.radius_m + b.radius_m - 1e-12:
                raise ConfigurationError(f"Przypadkowe zetknięcie przewodów: {a.id} i {b.id}.")
    branches = {}
    for wire in geometry.wires:
        branches[wire.branch] = branches.get(wire.branch, 0.0) + wire.length_m
    low, high = geometry.bounds
    warnings = []
    for plate in geometry.plates:
        radius = max(w.radius_m for w in geometry.wires)
        coords = np.asarray(geometry.nodes)
        if np.min(coords[:, 2]) - radius <= plate.stop[2]:
            raise ConfigurationError("Promiennik styka się z reflektorem.")
        if np.any(np.min(coords[:, :2], axis=0) - radius < np.asarray(plate.start)[:2]) or np.any(np.max(coords[:, :2], axis=0) + radius > np.asarray(plate.stop)[:2]):
            warnings.append("Promiennik wystaje poza obrys reflektora.")
    return {"geometry_status": "passed", "electromagnetic_status": "unverified", "wire_count": len(geometry.wires),
            "node_count": len(graph), "branch_lengths_m": branches, "bounds_m": [low.tolist(), high.tolist()],
            "warnings": warnings}
