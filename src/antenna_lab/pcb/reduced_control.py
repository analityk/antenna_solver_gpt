"""Explicit FAST/APPROX experiment, no openEMS profile/native/domain creation."""
import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import sys
from tempfile import mkdtemp

from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.reduced_pcb import build_reduced_model, solve_reduced_model
from .frequency import add_frequency_arguments, frequency_arguments_hz
from .gerber_sweep import sweep_frequencies_hz
from .geometry_resolution import apply_geometry_resolution
from .grid import PcbGrid
from .simulation import validate_frequency_band
from .transform import normalize_port_orientation


def _json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def run_reduced(input_path, output_dir, *, pcb_config=None, geometry_resolution_um=10,
                result_frequency_hz=(1.3e9,1.42e9,1.5e9),excitation_center_hz=1.42e9,
                excitation_cutoff_hz=.2e9,reference_impedance_ohm=50.,sweep_request=None):
    """Keep the same import/normalize/project boundaries; no 3-D mesh, no fallback.

    Failed extraction/coupling leaves a diagnostic summary, never impedance.csv.
    Saved geometry/provenance is detached and sufficient to inspect the rejection.
    """
    validate_frequency_band(result_frequency_hz,excitation_center_hz,excitation_cutoff_hz)
    if isinstance(geometry_resolution_um,bool) or geometry_resolution_um not in (100,10,1,.1):
        raise ConfigurationError('Geometry resolution requires 100,10,1,0.1 um.')
    grid=PcbGrid({100:100000,10:10000,1:1000,.1:100}[geometry_resolution_um])
    input_path=Path(input_path);output=Path(output_dir)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ConfigurationError('Reduced output must be empty/new; no old results overwritten.')
    output.mkdir(parents=True,exist_ok=True)
    summary=dict(solver_model='reduced_quasi_tem',validation_status='approximate',status='preparing',
        geometry_resolution_um=geometry_resolution_um,result_frequency_hz=list(result_frequency_hz),
        reference_impedance_ohm=reference_impedance_ohm,
        frequency_band=dict(center_hz=excitation_center_hz,cutoff_hz=excitation_cutoff_hz,
            meaning='shared sampling-band validation only; no time-domain excitation'),
        sweep_request_mhz=sweep_request,native_fdtd_runs=0)
    try:
        if input_path.suffix.lower()=='.zip':
            from .experiment import resolve_experiment,load_experiment_geometry
            config,source,provenance=load_experiment_geometry(resolve_experiment(input_path,pcb_config))
        elif input_path.is_dir():
            from .bundle import load_bundle_geometry
            config,source,provenance=load_bundle_geometry(input_path,pcb_config)
        else:
            raise ConfigurationError('Reduced CLI accepts Gerber ZIP/directory with explicit ground stackup; legacy top-only JSON unsupported.')
        _json(output/'geometry.source.json',source.as_dict())
        _json(output/'import.json',provenance)
        normalized,transform=normalize_port_orientation(source)
        geometry,_,audit=apply_geometry_resolution(normalized,grid)
        _json(output/'geometry.json',geometry.as_dict())
        summary.update(normalization=asdict(transform),quantization=audit,provenance=provenance)
        model=build_reduced_model(geometry)
        model.update(geometry_resolution_um=geometry_resolution_um,provenance=provenance,
                     frequency_hz=list(result_frequency_hz),reference_impedance_ohm=reference_impedance_ohm)
        _json(output/'reduced_model.json',model)
        print(f"Model: reduced_quasi_tem (approximate, lossless TL)\n"
              f"Sections: {len(model['line_sections'])}; length: {model['total_centerline_length_m']*1e3:.2f} mm\n"
              f"Width classes [mm]: {[round(w*1e3,6) for w in model['width_classes_m']]}\n"
              f"Parallel overlaps: {len(model['coupled_sections'])}; "
              f"length: {sum(c['overlap_length_m'] for c in model['coupled_sections'])*1e3:.2f} mm\n"
              f"Ideal components: {len(model['lumped_components'])}; frequencies: {len(result_frequency_hz)}\n"
              f"Omitted effects: {', '.join(model['omitted_effects'])}",flush=True)
        rows=solve_reduced_model(model,result_frequency_hz,reference_impedance_ohm)
        with (output/'impedance.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        summary.update(status='completed',approximation_contract=model['approximation_contract'],
                       omitted_effects=model['omitted_effects'],loss_model=model['loss_model'],
                       undefined_values='null/empty SWR = infinite lossless reflection; null S11 dB = -infinity at exact match',
                       results=rows)
    except (ConfigurationError,ValueError,OSError) as exc:
        summary.update(status='failed',error=str(exc))
        _json(output/'summary.json',summary)
        raise
    _json(output/'summary.json',summary)
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description='FAST approximate quasi-TEM PCB graph (no FDTD)')
    parser.add_argument('input',type=Path)
    parser.add_argument('--pcb-config',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--geometry-resolution-um',type=float,choices=(100,10,1,.1),default=10)
    parser.add_argument('--reference-impedance-ohm',type=float,default=50.)
    add_frequency_arguments(parser);parser.set_defaults(frequencies_mhz=None)
    for name in ('start','stop','step'):parser.add_argument(f'--sweep-{name}-mhz',type=float)
    args=parser.parse_args(argv)
    try:
        request=(args.sweep_start_mhz,args.sweep_stop_mhz,args.sweep_step_mhz)
        sweep=any(v is not None for v in request)
        if sweep and (not all(v is not None for v in request) or args.frequencies_mhz is not None):
            raise ConfigurationError('Provide all sweep start/stop/step values, without --frequencies-mhz.')
        if args.frequencies_mhz is None:args.frequencies_mhz=[1300.,1420.,1500.]
        band=frequency_arguments_hz(args);band.pop('loss_reference_frequency_hz')
        if sweep:band['result_frequency_hz']=sweep_frequencies_hz(*request)
        validate_frequency_band(band['result_frequency_hz'],band['excitation_center_hz'],band['excitation_cutoff_hz'])
        output=args.output
        if output is None:
            root=Path('outcomes/pcb_reduced');root.mkdir(parents=True,exist_ok=True)
            output=Path(mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_'),dir=root))
        result=run_reduced(args.input,output,pcb_config=args.pcb_config,
            geometry_resolution_um=args.geometry_resolution_um,reference_impedance_ohm=args.reference_impedance_ohm,
            sweep_request=request if sweep else None,**band)
        print(f"Status: {result['status']} / approximate\n{output.resolve()/'summary.json'}\n{output.resolve()/'impedance.csv'}")
        return 0
    except (ConfigurationError,ValueError,OSError) as exc:
        print(f'Reduced PCB: {exc}',file=sys.stderr);return 1


if __name__=='__main__':
    raise SystemExit(main())
