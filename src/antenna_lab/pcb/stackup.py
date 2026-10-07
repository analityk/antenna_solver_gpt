"""Explicit SI layer stack, top z=0 and dielectric depth toward negative Z.

Copper thickness is a surface-material input only. No geometry is extruded.
"""
from dataclasses import dataclass, asdict
from math import isfinite, pi
from pathlib import Path

from antenna_lab.core.config import ConfigurationError
from .model import CopperLayer, DielectricLayer

EPS0 = 8.8541878128e-12


@dataclass(frozen=True)
class ResolvedPcbStackupConfig:
    schema_version: int
    model: str
    copper_top_path: Path
    board_outline_path: Path
    copper_layers: tuple[CopperLayer, ...]
    dielectric_layers: tuple[DielectricLayer, ...]
    port_negative_xy_m: tuple[float, float]
    port_positive_xy_m: tuple[float, float]
    port_width_m: float


def validate_stackup_sequence(value):
    layers = value['stackup']
    kinds = [layer['type'] for layer in layers]
    if (kinds[0] != 'copper' or kinds[-1] != 'copper' or
            any(a == b == 'copper' for a,b in zip(kinds,kinds[1:]))):
        raise ConfigurationError('PCB stackup requires top/bottom copper and a dielectric separation between copper sheets.')
    roles = [layer['role'] for layer in layers if layer['type'] == 'copper']
    expected = ['top', *[f'inner{i}' for i in range(1, len(roles)-1)], 'bottom']
    if roles != expected:
        raise ConfigurationError(f'PCB stackup roles must follow {expected}; received {roles}.')
    names = [layer['name'] for layer in layers if layer['type'] == 'dielectric']
    if len(set(names)) != len(names) or any(not n.strip() for n in names):
        raise ConfigurationError('PCB dielectric names must be nonempty and unique.')


def resolve_stackup(value, outline, hashes):
    validate_stackup_sequence(value)
    copper, dielectric, z = [], [], 0.0
    for layer in value['stackup']:
        if layer['type'] == 'copper':
            copper.append(CopperLayer(layer['role'], z, layer['model'],
                layer['thickness_um']*1e-6, layer['conductivity_s_m'], hashes[layer['role']]))
        else:
            bottom = z-layer['thickness_mm']*1e-3
            if not isfinite(bottom) or bottom >= z:
                raise ConfigurationError('PCB stackup: dielectric thickness is not representable in SI coordinates.')
            dielectric.append(DielectricLayer(outline, bottom, z,
                layer['epsilon_r'], layer['loss_tangent'], layer['name']))
            z = bottom
    return tuple(copper), tuple(dielectric)


def resolved_stackup_metadata(geometry, loss_reference_frequency_hz):
    """Detached solver/material description sufficient for offline reports."""
    layers = []
    for copper in geometry.copper_layers:
        conductance = copper.conductivity_s_m*copper.thickness_m
        if not isfinite(conductance) or conductance <= 0:
            raise ConfigurationError('PCB sheet conductance must be positive and finite.')
        layers.append(dict(type='copper', **asdict(copper), sheet_conductance_s=conductance,
            inputs_used_by_solver=copper.model == 'conducting_sheet',
            geometric_thickness_m=0.0, extra_z_cells=0))
    for d in geometry.dielectric_layers:
        kappa = 2*pi*loss_reference_frequency_hz*EPS0*d.epsilon_r*d.loss_tangent
        if not isfinite(kappa):
            raise ConfigurationError('PCB dielectric kappa must be finite.')
        layers.append(dict(type='dielectric', name=d.name, z_min_m=d.z_min_m,
            z_max_m=d.z_max_m, thickness_m=d.z_max_m-d.z_min_m,
            epsilon_r=d.epsilon_r, loss_tangent=d.loss_tangent,
            kappa_s_per_m=kappa, loss_model='constant_kappa'))
    layers.sort(key=lambda layer: (-layer.get('z_m',layer.get('z_max_m')), layer['type'] != 'copper'))
    return dict(total_dielectric_thickness_m=-geometry.dielectric_layers[-1].z_min_m,
        loss_reference_frequency_hz=loss_reference_frequency_hz, layers=layers,
        copper_thickness_is_geometric=False, validation_status='unverified')
