"""Detached integer PCB domain mesher (PCB-012B), not the production path.

The caller supplies reviewed integer anchors and the existing EM policy. This
module does not project raw geometry, select/suppress copper anchors, or change
CLI defaults. All construction/audits use ticks; only ``to_domain_mesh`` and
descriptive metadata export metres. No native dependencies or solver calls.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import isfinite, prod

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.solvers.pcb_mesh import PcbDomainMesh, PcbPhysicalMeshPolicy


@dataclass(frozen=True)
class PcbLatticeAnchorPlan:
    """Required core lines in ticks, including board/layer/contact boundaries.

    Port ranges contain their two boundaries and integer midpoint. Z spans
    substrate bottom through exact top tick 0. Duplicate ticks are identical,
    not tolerance clusters. Anchor selection/geometry migration is PCB-012C.
    """
    x_required_ticks: tuple[int, ...]
    y_required_ticks: tuple[int, ...]
    z_required_ticks: tuple[int, ...]
    port_x_ticks: tuple[int, int]
    port_y_ticks: tuple[int, int]
    drill_centres_xy_ticks: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class PcbLatticeDomainMesh:
    grid: PcbGrid
    x_lines_ticks: tuple[int, ...]
    y_lines_ticks: tuple[int, ...]
    z_lines_ticks: tuple[int, ...]
    shape_cells: tuple[int, int, int]
    cell_count: int
    pml_start_min_ticks: tuple[int, int, int]
    pml_start_max_ticks: tuple[int, int, int]
    pml_cells: int
    min_cell_ticks: int
    max_cell_ticks: int
    worst_growth_ratio: float
    drill_centres_xy_ticks: tuple[tuple[int, int], ...] = ()

    @property
    def axes_ticks(self):
        return self.x_lines_ticks, self.y_lines_ticks, self.z_lines_ticks

    def metadata(self):
        """Detached audit description; metre steps derive from integer widths."""
        return {
            'grid_quantum_um': self.grid.quantum_um,
            'min_cell_ticks': self.min_cell_ticks,
            'max_cell_ticks': self.max_cell_ticks,
            'min_step_m': self.grid.to_metres(self.min_cell_ticks),
            'max_step_m': self.grid.to_metres(self.max_cell_ticks),
            'off_grid_line_count': sum(type(t) is not int for axis in self.axes_ticks for t in axis),
            'shape_cells': list(self.shape_cells), 'cell_count': self.cell_count,
            'worst_growth_ratio': self.worst_growth_ratio, 'pml_cells': self.pml_cells,
        }

    def to_domain_mesh(self) -> PcbDomainMesh:
        """Single SI/native boundary. Floats are an export, never authoritative.

        Reject loss of distinct lines at unrepresentably large offsets. Do not
        reconstruct ticks by dividing exported binary floats by quantum_m.
        """
        axes = tuple(tuple(self.grid.to_metres(t) for t in axis) for axis in self.axes_ticks)
        if any(not isfinite(t) for axis in axes for t in axis) or any(
                a >= b for axis in axes for a, b in zip(axis, axis[1:])):
            raise ConfigurationError('PCB lattice: SI export cannot represent distinct finite mesh lines.')
        convert = lambda values: tuple(self.grid.to_metres(t) for t in values)
        return PcbDomainMesh(
            *axes, self.shape_cells, self.cell_count,
            convert(self.pml_start_min_ticks), convert(self.pml_start_max_ticks),
            tuple(axis[0] for axis in axes), tuple(axis[-1] for axis in axes),
            self.pml_cells, self.grid.to_metres(self.min_cell_ticks),
            self.grid.to_metres(self.max_cell_ticks), self.worst_growth_ratio,
            tuple(convert(xy) for xy in self.drill_centres_xy_ticks),
        )


def _positive_int(value, name):
    if type(value) is not int or value < 1:
        raise ConfigurationError(f'PCB lattice: {name} must be a positive integer.')
    return value


def _maximum_ticks(grid, maximum_m):
    # Unlike source coordinate projection, a physical bound must not be rounded
    # upward by the grid's float tie/residue guard. Project its decimal value.
    ticks = grid.floor_tick(str(maximum_m))
    if ticks < 1:
        raise ConfigurationError(
            'PCB lattice: selected grid quantum is coarser than required EM resolution '
            f'(maximum step {maximum_m} m). Choose a finer quantum.')
    return ticks


def _anchors(values):
    if any(type(v) is not int for v in values):
        raise ConfigurationError('PCB lattice: required anchors must be integer ticks; no implicit projection.')
    result = tuple(sorted(set(values)))
    if len(result) < 2:
        raise ConfigurationError('PCB lattice: each core axis requires two distinct tick anchors.')
    return result


def _count(length, maximum):
    return (length + maximum - 1) // maximum


def _subdivide_ticks(anchors, maxima):
    """Balanced quotient/remainder cells, larger cells first in each interval."""
    result = [anchors[0]]
    for a, b, maximum in zip(anchors, anchors[1:], maxima):
        count = _count(b - a, maximum)
        width, remainder = divmod(b - a, count)
        position = a
        for i in range(count - 1):
            position += width + (i < remainder)
            result.append(position)
        result.append(b)  # Original endpoint, exactly; no reconstruction drift.
    return tuple(result)


def _growth_fraction(value):
    if isinstance(value, bool) or not isfinite(value) or value <= 1:
        raise ConfigurationError('PCB lattice: growth ratios must be finite and greater than 1.')
    return Fraction(str(value))


def _grade_ticks(lines, target, cell_budget):
    """Split only, using rational comparisons and deterministic integer floors.

    The desired piece adjacent to the small cell is capped at L*r/(1+r),
    avoiding a vanishing remainder. A one-tick split is the smallest fallback.
    Both sides are rechecked. Target is enforced (therefore also the limit).
    Integer granularity can force substantial refinement, even all one-tick
    cells; the budget is a hard failure, never permission to go off-grid.

    Termination: each iteration advances or inserts a strictly interior tick.
    Insertions are bounded by both the finite tick span and cell_budget.
    """
    lines = list(lines)
    numerator, denominator = target.numerator, target.denominator
    i = 1
    while i < len(lines) - 1:
        left, right = lines[i] - lines[i-1], lines[i+1] - lines[i]
        large, small = max(left, right), min(left, right)
        if large * denominator <= small * numerator:
            i += 1
            continue
        if len(lines) - 1 >= cell_budget:
            raise ConfigurationError(
                'PCB lattice grading: cannot satisfy growth on this quantum within max_cells; '
                'choose another quantum or increase the explicit cell budget.')
        adjacent = max(1, min(small*numerator // denominator,
                              large*numerator // (numerator+denominator)))
        if not 1 <= adjacent < large:
            raise ConfigurationError('PCB lattice grading: no legal interior tick satisfies the split.')
        index = i if left > right else i+1
        point = lines[i] - adjacent if left > right else lines[i] + adjacent
        lines.insert(index, point)
        i = max(1, index-1)
    return tuple(lines)


def _cell_guard(shape, maximum):
    count = prod(shape)
    if any(n < 1 for n in shape) or count > maximum:
        raise ConfigurationError(f'PCB lattice: shape={tuple(shape)}, cell_count={count}, max_cells={maximum}.')
    return count


def _audit_axis(lines, boundaries, maxima, growth):
    if any(type(v) is not int for v in lines):
        raise ConfigurationError('PCB lattice audit: off-grid line.')
    widths = tuple(b-a for a, b in zip(lines, lines[1:]))
    if not widths or min(widths) < 1:
        raise ConfigurationError('PCB lattice audit: zero/sub-quantum cell.')
    if not set(boundaries).issubset(lines):
        raise ConfigurationError('PCB lattice audit: required anchor or PML start lost.')
    if any(max(a,b)*growth.denominator > min(a,b)*growth.numerator
           for a,b in zip(widths, widths[1:])):
        raise ConfigurationError('PCB lattice audit: growth limit exceeded.')
    interval = 0
    for a,b,width in zip(lines, lines[1:], widths):
        while interval < len(maxima)-1 and a >= boundaries[interval+1]:
            interval += 1
        if b > boundaries[interval+1] or width > maxima[interval]:
            raise ConfigurationError('PCB lattice audit: local maximum step exceeded.')
    return widths


def make_pcb_lattice_domain_mesh(
    plan: PcbLatticeAnchorPlan, policy: PcbPhysicalMeshPolicy, grid: PcbGrid,
    *, substrate_z_max_steps_m: tuple[float, ...] | None = None,
) -> PcbLatticeDomainMesh:
    """Explicit internal path. No change to make_pcb_domain_mesh or native XML.

    Physical limits come from the existing policy (and thus quality settings).
    Optional per-Z-interval limits describe heterogeneous dielectric layers;
    without them the conservative shortest-dielectric policy applies. Geometry
    thickness/port cell minima are additionally checked in integer arithmetic.
    No material thickness creates geometry or anchors here.
    """
    if not isinstance(grid, PcbGrid):
        raise ConfigurationError('PCB lattice: PcbGrid required.')
    maximum = _positive_int(policy.max_cells, 'max_cells')
    pml = _positive_int(policy.pml_cells, 'pml_cells')
    if not 6 <= pml <= 20:
        raise ConfigurationError('PCB lattice: pml_cells must be in 6..20.')
    target, limit = map(_growth_fraction, (policy.growth_ratio_target, policy.growth_ratio_limit))
    if target > limit:
        raise ConfigurationError('PCB lattice: growth target exceeds limit.')
    minima = tuple(_positive_int(v, 'minimum feature cells') for v in (
        policy.min_port_gap_cells, policy.min_port_width_cells, policy.min_substrate_cells_z))
    anchors = tuple(_anchors(a) for a in (
        plan.x_required_ticks, plan.y_required_ticks, plan.z_required_ticks))
    ranges = (plan.port_x_ticks, plan.port_y_ticks)
    for axis, bounds in zip(anchors, ranges):
        if len(bounds) != 2 or any(type(v) is not int for v in bounds) or bounds[0] >= bounds[1]:
            raise ConfigurationError('PCB lattice: port boundaries must be increasing integer ticks.')
        if sum(bounds) % 2 or not {bounds[0], sum(bounds)//2, bounds[1]}.issubset(axis):
            raise ConfigurationError('PCB lattice: exact port boundaries/midpoint must be required integer ticks.')
    if anchors[2][-1] != 0 or anchors[2][0] >= 0:
        raise ConfigurationError('PCB lattice: substrate must span bottom through exact top tick 0.')
    for xy in plan.drill_centres_xy_ticks:
        if len(xy) != 2 or any(type(t) is not int or t not in axis for t,axis in zip(xy,anchors)):
            raise ConfigurationError('PCB lattice: every drill centre must be an exact required XY tick.')

    air = _maximum_ticks(grid, policy.max_air_step_m)
    xy = _maximum_ticks(grid, policy.max_substrate_xy_step_m)
    port_steps = tuple(_maximum_ticks(grid, v) for v in (
        policy.max_port_gap_step_m, policy.max_port_width_step_m))
    # Integer physical sizes, not their exported floating-point subtraction.
    feature_steps = tuple((hi-lo)//n for (lo,hi),n in zip(ranges,minima))
    z_cells_step = (anchors[2][-1]-anchors[2][0])//minima[2]
    if min(*feature_steps,z_cells_step) < 1:
        raise ConfigurationError('PCB lattice: selected grid quantum is coarser than required EM resolution (feature cells).')
    if substrate_z_max_steps_m is None:
        z_limits = (_maximum_ticks(grid,policy.max_substrate_z_step_m),)*(len(anchors[2])-1)
    else:
        if len(substrate_z_max_steps_m) != len(anchors[2])-1:
            raise ConfigurationError('PCB lattice: one physical Z limit is required per substrate interval.')
        z_limits = tuple(_maximum_ticks(grid,v) for v in substrate_z_max_steps_m)
    z_limits = tuple(min(v,z_cells_step) for v in z_limits)
    padding = grid.ceil_tick(str(policy.air_padding_m))
    if padding < 1 or policy.air_padding_m <= 0:
        raise ConfigurationError('PCB lattice: positive air clearance required.')

    boundaries, maxima, shape = [], [], []
    for dim, axis in enumerate(anchors):
        edges = (axis[0]-padding,*axis,axis[-1]+padding)
        if dim < 2:
            low, high = ranges[dim]
            local = tuple(min(xy,port_steps[dim],feature_steps[dim])
                          if a >= low and b <= high else xy
                          for a,b in zip(axis,axis[1:]))
        else:
            local = z_limits
        sizes = (air,*local,air)
        boundaries.append(edges); maxima.append(sizes)
        shape.append(sum(_count(b-a,m) for a,b,m in zip(edges,edges[1:],sizes))+2*pml)
    _cell_guard(shape,maximum)  # Before allocating even the one-dimensional axes.
    ordinary = []
    for dim,(edges,sizes) in enumerate(zip(boundaries,maxima)):
        axis = _subdivide_ticks(edges,sizes)
        budget = maximum // prod(n for i,n in enumerate(shape) if i != dim) - 2*pml
        axis = _grade_ticks(axis,target,budget)
        _audit_axis(axis,edges,sizes,limit)
        shape[dim] = len(axis)-1+2*pml
        _cell_guard(shape,maximum)
        ordinary.append(axis)

    axes, all_widths = [], []
    for axis,edges,sizes in zip(ordinary,boundaries,maxima):
        left, right = axis[1]-axis[0], axis[-1]-axis[-2]
        full = (tuple(axis[0]-i*left for i in range(pml,0,-1)) + axis
                + tuple(axis[-1]+i*right for i in range(1,pml+1)))
        widths = _audit_axis(full,(full[0],*edges,full[-1]),(left,*sizes,right),limit)
        if full.index(axis[0]) != pml or len(full)-1-full.index(axis[-1]) != pml or (
                widths[:pml] != (left,)*pml or widths[-pml:] != (right,)*pml):
            raise ConfigurationError('PCB lattice audit: PML count/constant step mismatch.')
        axes.append(full); all_widths.append(widths)
    shape = tuple(len(axis)-1 for axis in axes)
    count = _cell_guard(shape,maximum)
    flat = tuple(w for widths in all_widths for w in widths)
    worst = max((Fraction(max(a,b),min(a,b)) for widths in all_widths
                 for a,b in zip(widths,widths[1:])),default=Fraction(1))
    return PcbLatticeDomainMesh(
        grid,*axes,shape,count,tuple(a[0] for a in ordinary),tuple(a[-1] for a in ordinary),
        pml,min(flat),max(flat),float(worst),tuple(tuple(xy) for xy in plan.drill_centres_xy_ticks),
    )
