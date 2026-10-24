"""Passive PCB planes, continuous geometric masks and 1 V port normalization.

Shares native FD reader/dump infrastructure with antenna fields. No mesh edits,
no accepted-power normalization, no volume/time dumps or extra solver runs.
"""
from copy import deepcopy
from math import isfinite, prod
import re
from pathlib import Path

import numpy as np
from shapely import points, distance, union_all, intersects_xy
from shapely.geometry import Polygon, box

from antenna_lab.pcb.regions import copper_shape
from antenna_lab.core.config import ConfigurationError, write_json
from .fields import CONVENTION, MAX_FIELD_POINTS, install_frequency_planes
from .power import _read_surface

PCB_PLANES = {'xy_air': 2, 'xz_feed': 1, 'yz_feed': 0}
FIELD_MODES = ('far', 'copper_surfaces')
COPPER_PROBE_OFFSET_M = 10e-6  # explicit 10 um; grid/CFL must be preflighted
ARRAY_ORDER = 'frequency,component_xyz,x,y,z'


def validate_field_frequencies(frequencies, settings):
    values = tuple(frequencies)
    if not values:
        return ()
    if len(values)>3 or any(isinstance(f,bool) or not isfinite(f) or f<=0 for f in values):
        raise ConfigurationError('PCB fields: require 1–3 finite positive frequencies.')
    if len(set(values))!=len(values):
        raise ConfigurationError('PCB fields: frequencies must be unique.')
    lo = settings.excitation_center_hz-settings.excitation_cutoff_hz
    hi = settings.excitation_center_hz+settings.excitation_cutoff_hz
    if any(not lo<=f<=hi for f in values):
        raise ConfigurationError(f'PCB fields: frequency outside excitation band [{lo:g}, {hi:g}] Hz.')
    return tuple(sorted(values))


def pcb_field_layout(geometry, mesh, settings, frequencies, *, mode='far', surface_probe_offset_m=0.):
    frequencies = validate_field_frequencies(frequencies,settings)
    if not frequencies:return []
    if mode not in FIELD_MODES:
        raise ConfigurationError(f'Unknown PCB field mode: {mode!r}.')
    if mode == 'copper_surfaces' and not surface_probe_offset_m:
        raise ConfigurationError('Copper surface mode requires a prepared near-face Z mesh.')
    axes = [np.asarray(getattr(mesh,a+'_lines_m')) for a in 'xyz']
    inside = [np.flatnonzero((a>mesh.pml_start_min_m[i]) & (a<mesh.pml_start_max_m[i])) for i,a in enumerate(axes)]
    if any(len(v)<2 for v in inside):
        raise ConfigurationError('PCB fields: insufficient ordinary mesh lines outside PML.')
    if mode == 'copper_surfaces':
        # Cropped acquisition: XY board region + 1 mm (not remote air),
        # Z exactly 10 um outside each physical copper sheet face.
        board = geometry.outline.vertices_xy_m
        bounds_xy = []
        for axis in range(2):
            low = min(p[axis] for p in board) - 1e-3
            high = max(p[axis] for p in board) + 1e-3
            eligible = inside[axis][(axes[axis][inside[axis]] >= low) &
                                    (axes[axis][inside[axis]] <= high)]
            if len(eligible) < 2:
                raise ConfigurationError('Copper surface field capture: insufficient XY board samples.')
            bounds_xy.append((int(eligible[0]), int(eligible[-1])))
        result=[]
        roles = geometry.copper_layers or ()
        for layer in sorted(roles, key=lambda item:-item.z_m):
            if not any(c.layer_role==layer.role for c in geometry.copper):
                continue  # physically empty sheet: nothing to map, never invent metal
            for face,sign in (('top',1),('bottom',-1)):
                target=layer.z_m+sign*surface_probe_offset_m
                indices=np.flatnonzero(np.isclose(axes[2],target,rtol=0,atol=1e-12))
                if len(indices)!=1 or indices[0] not in inside[2]:
                    raise ConfigurationError(f'Copper {layer.role} {face}: '
                                             'required Z sampling line absent from prepared mesh.')
                idx=int(indices[0])
                safe_role=re.sub(r'[^a-zA-Z0-9_]+','_',layer.role)
                name=f'copper_{safe_role}_{face}'
                bounds=(*bounds_xy,(idx,idx))
                result.append(dict(name=name,normal_axis='z',
                    requested_policy='explicit_surface_probe_node',
                    requested_position_m=float(target),actual_position_m=float(axes[2][idx]),
                    copper_layer_role=layer.role,copper_z_m=float(layer.z_m),
                    copper_face=face,measurement='copper_surface',offset_m=surface_probe_offset_m,
                    shape_xyz=[hi-lo+1 for lo,hi in bounds],
                    start_m=[float(a[lo]) for a,(lo,hi) in zip(axes,bounds)],
                    stop_m=[float(a[hi]) for a,(lo,hi) in zip(axes,bounds)],
                    native_files={k:f'fields_{name}_{k}.h5' for k in 'EH'}))
        if not result:
            raise ConfigurationError('No physical copper polygons for near-face E/H capture.')
        count=sum(prod(p['shape_xyz']) for p in result)*len(frequencies)
        if count>MAX_FIELD_POINTS:
            raise ConfigurationError(f'Copper surface E/H: {count} sampled points exceed {MAX_FIELD_POINTS}; '
                                     'reduce frequencies or domain size.')
        return result
    n,p = geometry.port.negative_xy_m,geometry.port.positive_xy_m
    midpoint = ((n[0]+p[0])/2,(n[1]+p[1])/2,0.)
    layout=[]
    for name,normal in PCB_PLANES.items():
        valid=inside[normal]
        requested=midpoint[normal]
        if name=='xy_air':
            positive=valid[axes[normal][valid]>0]
            if not len(positive):raise ConfigurationError('PCB fields: no positive-Z air line outside PML.')
            index=int(positive[0]);policy='first_existing_positive_z_outside_PML'
        else:
            index=int(valid[np.argmin(abs(axes[normal][valid]-requested))]);policy='nearest_existing_line_to_feed_midpoint'
        bounds=[(int(v[0]),int(v[-1])) for v in inside];bounds[normal]=(index,index)
        layout.append(dict(name=name,normal_axis='xyz'[normal],requested_policy=policy,
            requested_position_m=float(requested),actual_position_m=float(axes[normal][index]),
            shape_xyz=[hi-lo+1 for lo,hi in bounds],
            start_m=[float(a[lo]) for a,(lo,hi) in zip(axes,bounds)],
            stop_m=[float(a[hi]) for a,(lo,hi) in zip(axes,bounds)],
            native_files={k:f'fields_{name}_{k}.h5' for k in 'EH'}))
    count=sum(prod(p['shape_xyz']) for p in layout)*len(frequencies)
    if count>MAX_FIELD_POINTS:
        raise ConfigurationError(f'PCB fields: {count} points × frequencies exceeds {MAX_FIELD_POINTS}; reduce selected frequencies or domain settings explicitly.')
    return layout


def install_pcb_fields(csx, geometry, mesh, settings, frequencies, *, mode='far', surface_probe_offset_m=0.):
    from .openems_pcb import _audit_port_grid
    layout=pcb_field_layout(geometry,mesh,settings,frequencies,
        mode=mode,surface_probe_offset_m=surface_probe_offset_m)
    _audit_port_grid(csx,mesh,context='before passive field dumps')
    install_frequency_planes(csx,layout,validate_field_frequencies(frequencies,settings))
    _audit_port_grid(csx,mesh,context='after passive field dumps')
    return dict(planes=layout,frequency_hz=list(validate_field_frequencies(frequencies,settings)),
        mode=mode,surface_probe_offset_m=surface_probe_offset_m,
        mesh_changed=mode=='copper_surfaces',additional_fdtd_runs=0,dump_mode=1,interpolation='node',
        effect=('Explicit near-face Z nodes added; FDTD CFL and cost may change. '
                'Source copper/dielectric geometry unchanged.' if mode=='copper_surfaces'
                else 'Passive frequency DFT/I/O only; geometry, mesh, port, excitation, PML and quality unchanged.'))


def pcb_sample_mask(lines, full_axes, geometry):
    """Bits 1 copper, 2 local copper halo, 4 port + halo, 8 ideal component + halo.

    Distances to continuous planar copper/source; not native Yee occupancy.
    Substrate volume is deliberately not masked. Native grids are not resampled.
    """
    shape=tuple(len(a) for a in lines)
    xyz=np.stack(np.meshgrid(*lines,indexing='ij'),axis=-1).reshape(-1,3)
    widths=[]
    for line,full in zip(lines,full_axes):
        full=np.asarray(full);indices=np.searchsorted(full,line)
        indices=np.clip(indices,1,len(full)-2)
        indices=np.where(abs(full[indices-1]-line)<abs(full[indices]-line),indices-1,indices)
        indices=np.clip(indices,1,len(full)-2)
        widths.append(np.maximum(full[indices]-full[indices-1],full[indices+1]-full[indices]))
    halo=np.sqrt(sum(w*w for w in np.meshgrid(*widths,indexing='ij'))).ravel()
    xy=points(xyz[:,:2]);z=xyz[:,2]
    mask=np.zeros(len(xyz),dtype=np.uint8)
    for plane_z in sorted({c.z_m for c in geometry.copper}):
        metal=union_all([copper_shape(c) for c in geometry.copper if c.z_m == plane_z])
        if geometry.drills:
            from shapely.geometry import Point
            for hole in geometry.drills:
                if not hole.plated:
                    metal=metal.difference(Point(hole.x_m,hole.y_m).buffer(hole.drill_diameter_m/2,quad_segs=128))
        d=np.hypot(distance(xy,metal),z-plane_z)
        mask[d<=1e-12]|=1;mask[d<=halo]|=2
    bottom=min(d.z_min_m for d in geometry.dielectrics)
    for hole in geometry.drills:
        if not hole.plated: continue
        radial=np.maximum(np.hypot(xyz[:,0]-hole.x_m,xyz[:,1]-hole.y_m)-hole.equivalent_outer_radius_m,0)
        vertical=np.maximum(np.maximum(bottom-z,z),0)
        d=np.hypot(radial,vertical)
        mask[d<=1e-12]|=1;mask[d<=halo]|=2
    n,p=geometry.port.negative_xy_m,geometry.port.positive_xy_m
    ym=(n[1]+p[1])/2;half=geometry.port.width_m/2
    source=box(n[0],ym-half,p[0],ym+half)
    mask[np.hypot(distance(xy,source),z)<=halo]|=4
    from .pcb_components import resolve_component_boxes
    for region in resolve_component_boxes(geometry, full_axes):
        lower,upper=np.asarray(region.start_m),np.asarray(region.stop_m)
        d=np.linalg.norm(np.maximum(np.maximum(lower-xyz,xyz-upper),0),axis=1)
        mask[d<=halo]|=8  # Same local diagonal halo; separate ideal-component bit.
    return mask.reshape(shape)


def copper_surface_mask(lines, geometry, layer_role):
    """Only samples above actual copper; no one-cell halo hides the signal.

    Masks outside the footprint, not the conductor face. The field is sampled
    in a dielectric/air plane offset from, never inside, the PEC sheet.
    """
    copper=[copper_shape(c) for c in geometry.copper if c.layer_role==layer_role]
    if not copper:
        raise ConfigurationError(f'Copper surface {layer_role}: no materialized copper.')
    x,y=np.meshgrid(lines[0],lines[1],indexing='ij')
    inside=intersects_xy(union_all(copper),x,y)
    if not np.any(inside):
        raise ConfigurationError(f'Copper surface {layer_role}: no copper samples at selected XY nodes.')
    return (~inside)[:,:,None].astype(np.uint8)


def voltage_scale(voltage):
    voltage=np.asarray(voltage,dtype=complex)
    if voltage.ndim!=1 or not np.isfinite(voltage).all() or np.any(voltage==0):
        raise ConfigurationError('PCB fields: zero/non-finite total port-voltage phasor.')
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):scale=1/voltage
    if not np.isfinite(scale).all():raise ConfigurationError('PCB fields: non-finite 1 V normalization factor.')
    return scale


def finish_pcb_fields(geometry,mesh,layout,frequencies,reference,output, *, native_dir=None):
    """Read raw native HDF5 unchanged; save full complex Cartesian components."""
    frequencies=np.asarray(frequencies,float);layout=deepcopy(layout);output=Path(output)
    native_dir = Path(native_dir) if native_dir is not None else output/'native'
    if not np.array_equal(frequencies,np.asarray(reference['frequency_hz'])):
        raise ConfigurationError('PCB fields: voltage reference frequencies do not match field frequencies.')
    voltage=np.asarray(reference['voltage_real'])+1j*np.asarray(reference['voltage_imag'])
    if voltage.shape!=frequencies.shape:raise ConfigurationError('PCB fields: voltage reference shape mismatch.')
    scale=voltage_scale(voltage)
    axes=[np.asarray(getattr(mesh,a+'_lines_m')) for a in 'xyz']
    folder=output/'fields';folder.mkdir()
    for plane in layout:
        fields={k:[] for k in 'EH'};reference_lines=None
        for i,f in enumerate(frequencies):
            for kind in 'EH':
                lines,raw=_read_surface(native_dir/plane['native_files'][kind],f)
                if reference_lines is None:
                    for a,line,lo,hi in zip(axes,lines,plane['start_m'],plane['stop_m']):
                        expected=a[(a>=lo)&(a<=hi)]
                        # Native HDF5 mesh coordinates may use float32. This is
                        # a readback precision check, never interpolation/snap.
                        if (len(line)!=len(expected) or np.any(np.diff(line)<=0) or
                            not np.allclose(line,expected,rtol=1e-6,atol=1e-10)):
                            raise ConfigurationError(f'PCB fields: incompatible native grid {plane["name"]}.')
                    reference_lines=lines
                if not all(np.array_equal(a,b) for a,b in zip(lines,reference_lines)):
                    raise ConfigurationError('PCB fields: incompatible E/H/frequency grids; no interpolation performed.')
                fields[kind].append(raw*scale[i])
        surface=plane.get('measurement')=='copper_surface'
        mask=(copper_surface_mask(reference_lines,geometry,plane['copper_layer_role'])
              if surface else pcb_sample_mask(reference_lines,axes,geometry))
        electric,magnetic=(np.asarray(fields[k]) for k in 'EH')
        if not np.isfinite(electric).all() or not np.isfinite(magnetic).all():
            raise ConfigurationError('PCB fields: non-finite normalized fields.')
        electric[:,:,mask!=0]=np.nan;magnetic[:,:,mask!=0]=np.nan
        extra={}
        if surface:
            # Approximate one-face equivalent sheet-current from sampled H,
            # not an exact PEC surface limit nor a copper loss/skin model.
            sign=1 if plane['copper_face']=='top' else -1
            current=np.zeros_like(magnetic)
            current[:,0]=-sign*magnetic[:,1]  # n x H: Kx = -n Hy
            current[:,1]= sign*magnetic[:,0]  # n x H: Ky =  n Hx
            current[:,2]=0
            extra['K_proxy_a_per_m']=current
        np.savez_compressed(folder/(plane['name']+'.npz'),frequency_hz=frequencies,
            x_m=reference_lines[0],y_m=reference_lines[1],z_m=reference_lines[2],
            E_v_per_m=electric,H_a_per_m=magnetic,mask=mask,
            normalization_factor=scale,port_voltage_phasor=voltage,reference_voltage_v=1.,
            phasor_convention=CONVENTION,array_order=ARRAY_ORDER,**extra)
        plane['masked_samples']=int(np.count_nonzero(mask))
    from dataclasses import asdict
    from .pcb_components import resolve_component_boxes
    component_regions=[asdict(s) for s in resolve_component_boxes(geometry,axes)]
    mode='copper_surfaces' if layout and layout[0].get('measurement')=='copper_surface' else 'far'
    metadata=dict(component_regions=component_regions, schema_version=1,model='pcb',mode=mode,planes=layout,frequency_hz=frequencies.tolist(),
        units=dict(E='V/m per 1 V port',H='A/m per 1 V port',coordinates='m'),
        phasor_convention=CONVENTION,array_order=ARRAY_ORDER,
        normalization='total port voltage = 1∠0 V; not accepted-power normalization',
        reference_source='native LumpedPort.uf_tot evaluated by the single CalcPort call',
        port_voltage_phasor=[dict(real=float(v.real),imag=float(v.imag)) for v in voltage],
        normalization_factor=[dict(real=float(v.real),imag=float(v.imag)) for v in scale],
        reference_voltage_v=1.,mesh_changed=mode=='copper_surfaces',additional_fdtd_runs=0,
        effect=('Near-face Z mesh refinement; changes CFL/cell cost, not copper geometry or materials.'
                if mode=='copper_surfaces' else 'Passive DFT/I/O only; physical model, port, excitation, PML and quality unchanged.'),
        native_coordinate_comparison=dict(rtol=1e-6,atol_m=1e-10,interpolation=False),
        mask_bits=({'1':'outside actual copper XY footprint; no near-face halo'} if mode=='copper_surfaces' else
                   {'1':'copper sheets and solid PTH cylinders','2':'one local cell diagonal around copper','4':'planar port and halo','8':'ideal lumped component box and same local halo'}),
        mask_note=('Copper-footprint-only mask; 10 um offset planes; raw H at the saved plane, not exact H at PEC boundary. '
                   'K_proxy is n x H at offset (approximate), never validated surface loss.' if mode=='copper_surfaces' else
                   'Conservative geometric/interpolation mask, not native Yee-cell occupancy. Substrate not masked. Raw native/*.h5 untouched.'),
        validation_status='unverified')
    write_json(folder/'metadata.json',metadata)
    return metadata
