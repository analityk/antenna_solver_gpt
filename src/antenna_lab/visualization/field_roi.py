"""Presentation-only ROI in millimetres; never changes saved complex fields."""
from dataclasses import dataclass
from math import isfinite
import numpy as np


@dataclass(frozen=True)
class FieldCrop:
    mode: str = 'active+geometry'
    threshold_db: float = -40.
    margin_mm: float = 1.

    def __post_init__(self):
        if self.mode not in ('domain','board','active','active+geometry'):
            raise ValueError('Unknown field view mode.')
        if not isfinite(self.threshold_db) or self.threshold_db > 0:
            raise ValueError('field_crop_threshold_db must be finite and <= 0.')
        if not isfinite(self.margin_mm) or self.margin_mm < 0:
            raise ValueError('field_crop_margin_mm must be finite and >= 0.')


def add_crop_arguments(parser):
    parser.add_argument('--field-view',choices=('domain','board','active','active+geometry'),default='active+geometry')
    parser.add_argument('--field-crop-threshold-db',type=float,default=-40.)
    parser.add_argument('--field-crop-margin-mm',type=float,default=1.)


def crop_arguments(args):
    return dict(field_view=args.field_view,field_crop_threshold_db=args.field_crop_threshold_db,
                field_crop_margin_mm=args.field_crop_margin_mm)


def phase_peak(components):
    """Exact max over the entire RF period of norm(real(F exp(j phase))).

    Largest eigenvalue of the 2x2 real/imag Gram matrix. Includes every
    available phase, without discretization error or dependence on slider step.
    """
    values=np.asarray(components)
    scale=np.max(np.abs(values),axis=0)
    valid=np.isfinite(values).all(axis=0)
    scaled=np.divide(values,scale,where=valid & (scale>0),out=np.zeros_like(values))
    a=np.sum(scaled.real**2,axis=0);b=np.sum(scaled.imag**2,axis=0)
    cross=np.sum(scaled.real*scaled.imag,axis=0)
    peak=np.where(valid,scale,0.)*np.sqrt((a+b+np.hypot(a-b,2*cross))/2)
    return np.where(valid,peak,0.)


def field_roi(view, paths, crop=FieldCrop()):
    """One union ROI for both E/H panels, all phases, one plane/frequency.

    Separate relative E/H thresholds avoid comparing unlike SI units. Geometry
    uses physical overlays (not the board outline or buried XY ground). Broad
    NaN/interpolation halos are not metal occupancy and do not define the ROI.
    Empty active masks fall back to physical geometry, then board, then domain.
    """
    u,v=np.asarray(view['u']),np.asarray(view['v'])
    full=((float(u[0]),float(u[-1])),(float(v[0]),float(v[-1])))
    bounds=[];reason=crop.mode
    def geometry(board=False):
        arrays=[]
        for path in paths:
            role=path.get('role','geometry')
            if (board and role not in ('board','substrate')) or (not board and role in ('board','substrate')):
                continue
            points=np.asarray(path.get('points',[]),float)
            if points.ndim==2 and points.shape[1]==2:
                points=points[np.isfinite(points).all(axis=1)]
                if len(points):arrays.append(points)
        if not arrays:return []
        points=np.vstack(arrays)
        return [(points.min(axis=0),points.max(axis=0))]
    if crop.mode=='domain':
        return dict(u=full[0],v=full[1],mode=crop.mode,reason='domain',threshold_db=crop.threshold_db,margin_mm=crop.margin_mm)
    if crop.mode=='board':bounds=geometry(True)
    else:
        active=np.zeros((len(v),len(u)),bool)
        for amplitude in (phase_peak([view['eu'],view['ev']]),phase_peak([view['magnetic']])):
            maximum=float(amplitude.max())
            if maximum>0:
                active |= (amplitude>0) & (amplitude>=maximum*10**(crop.threshold_db/20))
        if active.any():
            rows,cols=np.nonzero(active)
            bounds.append(((u[cols.min()],v[rows.min()]),(u[cols.max()],v[rows.max()])))
        if crop.mode=='active+geometry':bounds.extend(geometry())
    if not bounds:
        bounds=geometry();reason='fallback_geometry'
    if not bounds:
        bounds=geometry(True);reason='fallback_board'
    if not bounds:
        return dict(u=full[0],v=full[1],mode=crop.mode,reason='fallback_domain',threshold_db=crop.threshold_db,margin_mm=crop.margin_mm)
    low=np.min([b[0] for b in bounds],axis=0)-crop.margin_mm
    high=np.max([b[1] for b in bounds],axis=0)+crop.margin_mm
    result=[]
    for i,axis in enumerate((u,v)):
        # Outward to existing samples: shared exact limits in PNG and browser.
        lo=max(0,min(len(axis)-1,int(np.searchsorted(axis,low[i],side='right'))-1))
        hi=max(0,min(len(axis)-1,int(np.searchsorted(axis,high[i],side='left'))))
        if hi<=lo:lo=max(0,lo-1);hi=min(len(axis)-1,hi+1)
        result.append((float(axis[lo]),float(axis[hi])))
    return dict(u=result[0],v=result[1],mode=crop.mode,reason=reason,
                threshold_db=crop.threshold_db,margin_mm=crop.margin_mm)
