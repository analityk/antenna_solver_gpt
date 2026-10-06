"""Reproducible synthetic PCB control; no Gerber or field/far-field processing."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from math import cos, sin, radians
from pathlib import Path
import sys
from tempfile import mkdtemp

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import BoardOutline, CopperPolygon, PcbGeometry, PcbPort, Substrate
from antenna_lab.pcb.simulation import PcbSimulationSettings, validate_pcb_simulation_settings
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.solvers.openems_pcb import prepare_pcb_xml_model, run_pcb_fdtd, write_pcb_port_results


def make_synthetic_control_case(
    *,
    excitation_center_hz: float = 1.42e9,
    excitation_cutoff_hz: float = .20e9,
    result_frequency_hz: tuple[float, ...] = (1.30e9, 1.42e9, 1.50e9),
    loss_reference_frequency_hz: float | None = None,
):
    """The PCB-008A native XML case, rigidly normalized exactly once, in SI."""
    # Rotate the complete source by 37 degrees, then normalize exactly once.
    angle = radians(37)
    c, s = cos(angle), sin(angle)
    def point(x, y):
        return (c*x-s*y+.012, s*x+c*y-.007)
    def polygon(vertices):
        return tuple(point(x,y) for x,y in vertices)
    outline = BoardOutline(polygon(((-.01,-.01),(.01,-.01),(.01,.01),(-.01,.01))))
    negative = CopperPolygon('negative_pad', polygon(((-.004,-.001),(-.0005,-.001),
                               (-.0005,.001),(-.004,.001))), 0.0)
    positive = CopperPolygon('positive_pad', polygon(((.0005,-.001),(.004,-.001),
                               (.004,.001),(.0005,.001))), 0.0)
    source = PcbGeometry('pcb', outline, [negative,positive],
                        Substrate(outline,-.0016,0.,4.3,.018),
                        PcbPort('native_smoke',point(-.0005,0.),point(.0005,0.),.002))
    geometry, _ = normalize_port_orientation(source)
    settings = make_control_settings(
        excitation_center_hz=excitation_center_hz, excitation_cutoff_hz=excitation_cutoff_hz,
        result_frequency_hz=result_frequency_hz, loss_reference_frequency_hz=loss_reference_frequency_hz)
    return geometry, settings


def make_control_settings(*, excitation_center_hz=1.42e9, excitation_cutoff_hz=.20e9,
                          result_frequency_hz=(1.30e9, 1.42e9, 1.50e9),
                          loss_reference_frequency_hz=None):
    """Shared economical single-run policy; independent of physical geometry."""
    settings = PcbSimulationSettings(
        schema_version=1, result_frequency_hz=tuple(result_frequency_hz),
        excitation_center_hz=excitation_center_hz, excitation_cutoff_hz=excitation_cutoff_hz,
        reference_impedance_ohm=50., cells_per_wavelength=20,
        min_substrate_cells_z=4, min_port_gap_cells=2, min_port_width_cells=2,
        growth_ratio_target=1.4, growth_ratio_limit=1.5, max_cells=20_000_000,
        loss_reference_frequency_hz=(excitation_center_hz if loss_reference_frequency_hz is None
                                     else loss_reference_frequency_hz), max_timesteps=100000,
        end_criteria=1e-5, threads=0, air_padding_wavelengths=.25, pml_cells=8)
    validate_pcb_simulation_settings(settings)
    return settings


def run_synthetic_control(output_dir, *,
    excitation_center_hz: float = 1.42e9,
    excitation_cutoff_hz: float = .20e9,
    result_frequency_hz: tuple[float, ...] = (1.30e9, 1.42e9, 1.50e9),
    loss_reference_frequency_hz: float | None = None,
) -> dict:
    """Require an empty/new run directory; retain native output even on failure."""
    geometry, settings = make_synthetic_control_case(
        excitation_center_hz=excitation_center_hz, excitation_cutoff_hz=excitation_cutoff_hz,
        result_frequency_hz=result_frequency_hz, loss_reference_frequency_hz=loss_reference_frequency_hz)
    return run_control_model(geometry, settings, output_dir)


def run_control_model(geometry: PcbGeometry, settings: PcbSimulationSettings, output_dir, *,
                      port_edge_mode='aligned', exact_endcriteria=False, dump_statistics=False, gerber_quality=None, field_frequency_hz=()) -> dict:
    """Run a supplied control geometry/settings pair in an isolated directory."""
    validate_pcb_simulation_settings(settings)
    output = Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ConfigurationError(f'PCB control: katalog musi być pusty lub nowy: {output}')
    output.mkdir(parents=True, exist_ok=True)
    native = output/'native'
    native.mkdir()  # also prevents concurrent runs from claiming the same directory
    mode_options = {} if port_edge_mode == 'aligned' else {'port_edge_mode': port_edge_mode}
    if gerber_quality is not None:
        mode_options['gerber_quality'] = gerber_quality
    if field_frequency_hz:
        mode_options['field_frequency_hz'] = field_frequency_hz
    engine, csx, port, mesh, spec, metadata = prepare_pcb_xml_model(geometry, settings, native/'model.xml', **mode_options)
    run_options = {}
    if exact_endcriteria: run_options['exact_endcriteria'] = True
    if dump_statistics: run_options['dump_statistics'] = True
    if field_frequency_hz: run_options['field_frequency_hz'] = field_frequency_hz
    result = run_pcb_fdtd(engine, csx, port, mesh, settings, native, **run_options)
    result['mesh'].update(min_step_m=mesh.min_step_m, max_step_m=mesh.max_step_m,
                          worst_growth_ratio=mesh.worst_growth_ratio)
    result['preparation'] = metadata
    result['simulation_settings'] = asdict(settings)
    if field_frequency_hz:
        from antenna_lab.solvers.pcb_fields import finish_pcb_fields
        result['fields'] = finish_pcb_fields(geometry, mesh, metadata['fields']['planes'],
            metadata['fields']['frequency_hz'], result['field_port_reference'], output)
    return write_pcb_port_results(result, output)


def add_frequency_arguments(parser):
    parser.add_argument('--center-mhz', type=float, default=1420.)
    parser.add_argument('--cutoff-mhz', type=float, default=200.)
    parser.add_argument('--frequencies-mhz', type=float, nargs='+', default=[1300., 1420., 1500.])
    parser.add_argument('--loss-reference-mhz', type=float)


def frequency_arguments_hz(args):
    # MHz exists only at this command-line boundary; all downstream values are Hz.
    return dict(excitation_center_hz=args.center_mhz*1e6,
                excitation_cutoff_hz=args.cutoff_mhz*1e6,
                result_frequency_hz=tuple(f*1e6 for f in args.frequencies_mhz),
                loss_reference_frequency_hz=(args.center_mhz if args.loss_reference_mhz is None
                                             else args.loss_reference_mhz)*1e6)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Synthetic PCB FDTD control (UNVERIFIED)')
    parser.add_argument('--output', type=Path)
    add_frequency_arguments(parser)
    args = parser.parse_args(argv)
    band = frequency_arguments_hz(args)
    try:
        output = args.output
        if output is None:
            root = Path('outcomes/pcb_control')
            root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_')
            output = Path(mkdtemp(prefix=stamp, dir=root))
        output = output.resolve()
        print(f'PCB synthetic FDTD control\nOutput: {output}', flush=True)
        print(f"Excitation center: {band['excitation_center_hz']/1e9:.3f} GHz\n"
              f"Excitation cutoff: {band['excitation_cutoff_hz']/1e9:.3f} GHz\n"
              f"Loss reference: {band['loss_reference_frequency_hz']/1e9:.3f} GHz\n"
              "Result frequencies: " + ', '.join(f'{f/1e9:.3f}' for f in band['result_frequency_hz']) + ' GHz',
              flush=True)
        result = run_synthetic_control(output, **band)
        for i, frequency in enumerate(result['frequency_hz']):
            db = result['s11_db'][i]
            print(f"\nFrequency: {frequency/1e9:.3f} GHz\n"
                  f"Z: {result['resistance_ohm'][i]:.9g} + j({result['reactance_ohm'][i]:.9g}) ohm\n"
                  f"|S11|: {result['s11_magnitude'][i]:.9g}\n"
                  f"S11: {'-inf' if db is None else format(db, '.9g')} dB\n"
                  f"SWR: {result['swr'][i]:.9g}")
        print('\nStatus: UNVERIFIED')
        for name in ('impedance.csv', 'summary.json', 'native/model.xml'):
            print(output/name)
        return 0
    except (ConfigurationError, RuntimeError, OSError, ValueError) as exc:
        print(f'PCB control: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
