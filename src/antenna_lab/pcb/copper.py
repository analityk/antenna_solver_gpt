"""Copper material metadata, independent of planar geometry and mesh policy."""
from math import isfinite
from antenna_lab.core.config import ConfigurationError
from .config import ResolvedPcbConfig


def copper_metadata(config: ResolvedPcbConfig | None = None) -> dict:
    """Absent physical config preserves synthetic PEC; supplied SI inputs are audited."""
    model = config.copper_model if config is not None else 'pec'
    thickness = config.copper_thickness_m if config is not None else None
    conductivity = config.copper_conductivity_s_m if config is not None else None
    if model not in ('pec', 'conducting_sheet'):
        raise ConfigurationError('PCB copper model must be pec or conducting_sheet.')
    if config is not None:
        for name, value in (('thickness', thickness), ('conductivity', conductivity)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
                raise ConfigurationError(f'PCB copper {name} must be finite and positive in SI units.')
    conductance = None if config is None else conductivity * thickness
    if conductance is not None and (not isfinite(conductance) or conductance <= 0):
        raise ConfigurationError('PCB copper sheet conductance must be finite and positive.')
    sheet = model == 'conducting_sheet'
    return dict(copper_model=model, copper_thickness_m=thickness,
        copper_conductivity_s_m=conductivity, copper_sheet_conductance_s=conductance,
        copper_inputs_used_by_solver=sheet,
        finite_conductivity='modeled' if sheet else 'not modeled (PEC)',
        finite_physical_thickness=('represented by conducting-sheet surface model' if sheet
                                 else 'not used by PEC solver model'),
        geometric_copper_thickness_m=0.0, extra_copper_z_cells=0)
