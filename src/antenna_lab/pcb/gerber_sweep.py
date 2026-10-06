"""Frequency sampling and sampled diagnostics; no solver or mesh operations."""
from decimal import Decimal
from math import isfinite

from antenna_lab.core.config import ConfigurationError


def sweep_frequencies_hz(start_mhz, stop_mhz, step_mhz):
    """Regular inclusive grid: include stop only if reached by an integer step.

    Decimal arithmetic avoids repeated binary addition. A non-divisible stop is
    not appended; the last sample is the largest regular-grid value below it.
    """
    if not all(isfinite(v) for v in (start_mhz, stop_mhz, step_mhz)):
        raise ConfigurationError('Sweep start/stop/step must be finite.')
    if start_mhz <= 0 or stop_mhz <= start_mhz or step_mhz <= 0:
        raise ConfigurationError('Sweep requires start > 0, stop > start, step > 0.')
    start, stop, step = map(lambda v: Decimal(str(v)), (start_mhz, stop_mhz, step_mhz))
    count = int((stop-start)//step)+1
    if count < 2:
        raise ConfigurationError('Sweep requires at least two frequencies.')
    frequencies = tuple(float((start+i*step)*Decimal('1000000')) for i in range(count))
    if not all(isfinite(f) for f in frequencies) or any(a >= b for a,b in zip(frequencies,frequencies[1:])):
        raise ConfigurationError('Sweep frequencies cannot be represented as finite distinct Hz values.')
    return frequencies


def sampled_diagnostics(result):
    """Minima of samples only (first tie wins); adjacent brackets, no fitting.

    A bracket is recorded if either endpoint is exactly zero or signs differ.
    Thus an exact interior zero can occur in two adjacent brackets.
    """
    f, x = result['frequency_hz'], result['reactance_ohm']
    def row(index, keys):
        return {key: result[key][index] for key in ('frequency_hz', *keys)}
    s11 = min(range(len(f)), key=lambda i: result['s11_magnitude'][i])
    swr = min(range(len(f)), key=lambda i: result['swr'][i])
    nearest = min(range(len(f)), key=lambda i: abs(x[i]))
    return dict(
        minimum_s11=row(s11, ('s11_magnitude','s11_db','swr','resistance_ohm','reactance_ohm')),
        minimum_swr=row(swr, ('swr',)),
        minimum_abs_reactance=row(nearest, ('resistance_ohm','reactance_ohm')),
        reactance_crossings=[dict(frequency_low_hz=f[i], frequency_high_hz=f[i+1],
                                 x_low_ohm=a, x_high_ohm=b)
            for i,(a,b) in enumerate(zip(x,x[1:]))
            if a == 0 or b == 0 or (a < 0 < b) or (b < 0 < a)])


def print_sweep_summary(result):
    sweep = result['sweep']
    step = sweep.get('requested_step_hz')
    spacing = f', step {step/1e6:g} MHz' if step is not None else ', explicit frequencies'
    print(f"Sweep: {sweep['start_hz']/1e6:g}–{sweep['stop_hz']/1e6:g} MHz{spacing}, {sweep['point_count']} points")
    a,b,c = (result[k] for k in ('minimum_s11','minimum_swr','minimum_abs_reactance'))
    db = '-inf' if a['s11_db'] is None else f"{a['s11_db']:.4g}"
    print(f"Best |S11|: {a['s11_magnitude']:.5g} ({db} dB), {a['frequency_hz']/1e6:g} MHz\n"
          f"Minimum SWR: {b['swr']:.5g}, {b['frequency_hz']/1e6:g} MHz\n"
          f"Nearest X=0: X={c['reactance_ohm']:.5g} ohm, R={c['resistance_ohm']:.5g} ohm, {c['frequency_hz']/1e6:g} MHz\n"
          f"Reactance crossings: {len(result['reactance_crossings'])} adjacent brackets (no interpolation)")
