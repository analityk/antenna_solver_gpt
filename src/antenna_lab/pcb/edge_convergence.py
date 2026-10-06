"""Opt-in feed-edge A/B experiment; aligned remains the production default."""

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from pathlib import Path
import sys
from tempfile import mkdtemp

from antenna_lab.core.config import ConfigurationError
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh, pcb_port_edge_policy
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from .control import make_synthetic_control_case, run_control_model, add_frequency_arguments, frequency_arguments_hz
from .spatial_convergence import make_spatial_levels, compare_spatial_results, engineering_gate, MESH_KEYS
from .convergence import equivalent_capacitance

VARIANT_NAMES=('aligned_L2','aligned_L3','thirds_L2','thirds_L3')


def make_edge_variants(baseline):
    levels=make_spatial_levels(baseline)
    return tuple((name,mode,level,levels[index][1]) for name,mode,level,index in (
        ('aligned_L2','aligned','L2',2),('aligned_L3','aligned','L3',3),
        ('thirds_L2','thirds','L2',2),('thirds_L3','thirds','L3',3)))


def audit_experiment_result(result,settings):
    """Require the temporal/passivity evidence before any A/B comparison."""
    stats=result['native_statistics']
    iterations=stats['number_of_iterations']
    if not isinstance(iterations,int) or isinstance(iterations,bool) or not 0<iterations<settings.max_timesteps:
        raise ConfigurationError('PCB edge: temporal termination not established.')
    for key in ('fdtd_timestep_s','total_numerical_time_s'):
        if not isfinite(stats[key]) or stats[key]<=0:
            raise ConfigurationError('PCB edge: invalid native termination statistics.')
    if result['run_options'] != dict(exact_endcriteria=True,dump_statistics=True):
        raise ConfigurationError('PCB edge: wymagane exact_endcriteria i dump_statistics.')
    if result['frequency_hz']!=list(settings.result_frequency_hz):
        raise ConfigurationError('PCB edge: wynik ma inne częstotliwości.')
    for key in ('resistance_ohm','reactance_ohm','s11_magnitude','swr'):
        if len(result[key])!=len(settings.result_frequency_hz) or not all(isfinite(v) for v in result[key]):
            raise ConfigurationError('PCB edge: malformed/nonfinite port results.')
    if any(not 0<=v<1 for v in result['s11_magnitude']):
        raise ConfigurationError('PCB edge: non-passive port results.')


def aligned_reproduction(comparison,baseline):
    """Historical-band-only diagnostic, broad factor-two range, never a gate."""
    previous={1.3e9:.0227238,1.42e9:.0235159,1.5e9:.0232459}
    same_band=(baseline.excitation_center_hz==1.42e9 and baseline.excitation_cutoff_hz==.2e9
               and baseline.loss_reference_frequency_hz==1.42e9)
    return [dict(frequency_hz=row['frequency_hz'],
        previous_relative_delta_Z=previous.get(row['frequency_hz']) if same_band else None,
        broadly_consistent=(.5*previous[row['frequency_hz']]<=row['relative_Z_magnitude']<=2*previous[row['frequency_hz']])
            if same_band and row['frequency_hz'] in previous else None)
        for row in comparison]


def _write_report(study,output):
    text=json.dumps(study,indent=2,allow_nan=False)
    temp=output/'edge_convergence.json.tmp'
    temp.write_text(text+'\n',encoding='utf-8');temp.replace(output/'edge_convergence.json')
    comparisons=('aligned_L3_vs_L2','thirds_L3_vs_L2','thirds_vs_aligned_at_L2','thirds_vs_aligned_at_L3')
    metrics=('delta_R_ohm','delta_X_ohm','relative_R','relative_X','delta_Z_magnitude_ohm','relative_Z_magnitude')
    targets={'aligned_L3_vs_L2':'aligned_L3','thirds_L3_vs_L2':'thirds_L3',
             'thirds_vs_aligned_at_L2':'thirds_L2','thirds_vs_aligned_at_L3':'thirds_L3'}
    header=['variant','edge_mode','level','frequency_hz','resistance_ohm','reactance_ohm','s11_magnitude',
            'swr','equivalent_capacitance_f','mesh_shape_x','mesh_shape_y','mesh_shape_z','cell_count',
            'min_step_m','max_step_m','worst_growth_ratio','number_of_iterations','fdtd_timestep_s','total_numerical_time_s']
    header += [f'{key}_{name}' for name in comparisons for key in metrics]
    with (output/'edge_convergence.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(header)
        for name,v in study['variants'].items():
            if v['status']!='completed': continue
            r=v['result'];m=v['mesh'];stats=r['native_statistics']
            for i,f in enumerate(r['frequency_hz']):
                row=[name,v['edge_mode'],v['level'],f,*[r[key][i] for key in
                     ('resistance_ohm','reactance_ohm','s11_magnitude','swr')],v['equivalent_capacitance_f'][i],
                     *m['shape_cells'],*[m[key] for key in ('cell_count','min_step_m','max_step_m','worst_growth_ratio')],
                     *[stats[key] for key in ('number_of_iterations','fdtd_timestep_s','total_numerical_time_s')]]
                for comp in comparisons:
                    rows=study['comparisons'].get(comp)
                    row += [rows[i][key] if rows and targets[comp]==name else None for key in metrics]
                writer.writerow(row)


def run_edge_study(output_dir,**frequency_settings):
    geometry,baseline=make_synthetic_control_case(**frequency_settings)
    variants=make_edge_variants(baseline)
    identity=geometry.as_dict();encoded=json.dumps(identity,sort_keys=True,allow_nan=False)
    output=Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ConfigurationError(f'PCB edge: wymagany pusty/nowy katalog {output}.')
    output.mkdir(parents=True,exist_ok=True)
    with (output/'edge_convergence.json').open('x',encoding='utf-8') as stream: stream.write('{}\n')
    base=asdict(baseline)
    study=dict(status='running',candidate_thirds_converged=False,
        frequency_configuration={k:base[k] for k in ('excitation_center_hz','excitation_cutoff_hz',
            'result_frequency_hz','loss_reference_frequency_hz')},
        geometry={'model':geometry.model,'sha256':hashlib.sha256(encoded.encode()).hexdigest(),'normalized_geometry':identity},
        variants={},comparisons={},aligned_reproduction=[],thirds_change_smaller=[],notes=[
            'Experimental synthetic feed region only. aligned remains the production default.',
            'Candidate thresholds (relative Z/X <= 1%, R <= 5%) are engineering criteria, not physical validation.',
            'Two rectangular terminal pads only; exact z=0, physical copper and port are unchanged.',
            'Active Ex counts are a project grid-centre audit, not native resistor/source verification.',
            'Both thirds runs must return finite passive spectra and stop before max_timesteps.',
            'Aligned reproduction uses a broad factor-two historical range, only in the historical band; it is not a gate.',
            'Deterministic end-criteria evaluation does not guarantee bitwise equivalence across hardware/builds.'])
    for name,mode,level,settings in variants:
        study['variants'][name]=dict(status='pending',edge_mode=mode,level=level,settings=asdict(settings),output_directory=name)
    current=None
    _write_report(study,output)
    try:
        for i,(name,mode,level,settings) in enumerate(variants,1):
            current=study['variants'][name];current['status']='preflight'
            _write_report(study,output)
            print(f'[{i}/4] {name}',flush=True)
            mesh=make_pcb_domain_mesh(geometry,settings,port_edge_mode=mode)
            resolve_pcb_lumped_port(geometry,mesh,settings,port_edge_mode=mode)
            current['edge_policy']=pcb_port_edge_policy(geometry,settings,mode)
            current['mesh']={k:getattr(mesh,k) for k in MESH_KEYS}
            print(f'mesh: {mesh.shape_cells}, cells={mesh.cell_count}',flush=True)
            current['status']='running';_write_report(study,output)
            result=run_control_model(geometry,settings,output/name,port_edge_mode=mode,
                                     exact_endcriteria=True,dump_statistics=True)
            if geometry.as_dict()!=identity: raise ConfigurationError('PCB edge: geometria zmieniona przez przebieg.')
            audit_experiment_result(result,settings)
            json.dumps(result,allow_nan=False)
            if json.dumps(current['mesh'],sort_keys=True)!=json.dumps({k:result['mesh'][k] for k in MESH_KEYS},sort_keys=True):
                raise ConfigurationError('PCB edge: siatka solvera nie odpowiada preflight.')
            caps=[equivalent_capacitance(f,x) for f,x in zip(result['frequency_hz'],result['reactance_ohm'])]
            json.dumps(caps,allow_nan=False)
            current.update(status='completed',result=result,equivalent_capacitance_f=caps)
            _write_report(study,output)
        current=None
        for name,new,old in (('aligned_L3_vs_L2','aligned_L3','aligned_L2'),
                ('thirds_L3_vs_L2','thirds_L3','thirds_L2'),
                ('thirds_vs_aligned_at_L2','thirds_L2','aligned_L2'),
                ('thirds_vs_aligned_at_L3','thirds_L3','aligned_L3')):
            study['comparisons'][name]=compare_spatial_results(study['variants'][new]['result'],study['variants'][old]['result'])
        aligned,thirds=study['comparisons']['aligned_L3_vs_L2'],study['comparisons']['thirds_L3_vs_L2']
        study['aligned_reproduction']=aligned_reproduction(aligned,baseline)
        study['thirds_change_smaller']=[dict(frequency_hz=a['frequency_hz'],
            smaller=b['relative_Z_magnitude']<a['relative_Z_magnitude']) for a,b in zip(aligned,thirds)]
        candidate=engineering_gate(thirds)
        study['candidate_thirds_converged']=candidate
        study['status']='diagnostic_candidate_converged' if candidate else 'diagnostic_not_converged'
        _write_report(study,output)
    except (Exception,KeyboardInterrupt) as exc:
        study['status']='failed'
        if current is not None and current['status']!='completed': current['status']='failed'
        study['error']=f'{type(exc).__name__}: {exc}'
        _write_report(study,output)
        raise
    for a,b in zip(aligned,thirds):
        print(f"{a['frequency_hz']/1e9:.3f} GHz: aligned delta Z={100*a['relative_Z_magnitude']:.6g}%, "
              f"thirds delta Z={100*b['relative_Z_magnitude']:.6g}%")
    return json.loads(json.dumps(study,allow_nan=False))


def main(argv=None):
    parser=argparse.ArgumentParser(description='Experimental PCB feed-edge aligned/thirds A/B')
    parser.add_argument('--output',type=Path);add_frequency_arguments(parser)
    args=parser.parse_args(argv)
    try:
        output=args.output
        if output is None:
            root=Path('outcomes/pcb_edge_convergence');root.mkdir(parents=True,exist_ok=True)
            output=Path(mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_'),dir=root))
        output=output.resolve();print(f'PCB feed-edge experiment\nOutput: {output}',flush=True)
        study=run_edge_study(output,**frequency_arguments_hz(args))
        print(f"Status: {study['status']}\nCandidate thirds: {study['candidate_thirds_converged']}\n"
              f"{output/'edge_convergence.json'}\n{output/'edge_convergence.csv'}")
        return 0
    except (ConfigurationError,RuntimeError,OSError,ValueError,KeyboardInterrupt) as exc:
        print(f'PCB edge: {exc}',file=sys.stderr);return 1


if __name__=='__main__': raise SystemExit(main())
