"""Strict EasyEDA Pro physicalStacking -> existing PCB physical schema.

Thickness in this export is mm. EM parameters are never inferred from Material.
"""
from math import isfinite
from antenna_lab.core.config import ConfigurationError, validate_schema
from .stackup import validate_stackup_sequence

OMITTED_TYPES = {'TOP_SILK', 'BOT_SILK', 'BOTTOM_SILK', 'TOP_PASTE_MASK',
                 'BOT_PASTE_MASK', 'BOTTOM_PASTE_MASK', 'TOP_SOLDER_MASK',
                 'BOT_SOLDER_MASK', 'BOTTOM_SOLDER_MASK'}
COPPER_TYPES = {'TOP', 'BOTTOM', 'SIGNAL', 'PLANE'}


def stackup_format(value):
    if not isinstance(value, dict): return None
    if 'layerManagement' in value and 'physicalStacking' in value:
        return 'easyeda_physical_stacking'
    if value.get('schema_version') in (1,2) and 'port' in value and (
        'stackup' in value or 'substrate' in value and 'copper' in value):
        return 'solver_v'+str(value['schema_version'])
    return None


def normalize_stackup(value):
    fmt = stackup_format(value)
    if fmt is None:
        raise ConfigurationError('Not a recognized PCB physical or EasyEDA stackup JSON.')
    if fmt != 'easyeda_physical_stacking':
        validate_schema(value, 'pcb-physical.schema.json')
        if value['schema_version']==2: validate_stackup_sequence(value)
        return value, dict(format=fmt, assumptions=[])
    if not isinstance(value['layerManagement'],list) or not isinstance(value['physicalStacking'],list):
        raise ConfigurationError('EasyEDA malformed layerManagement / physicalStacking.')
    management = {}
    for row in value['layerManagement']:
        v = row.get('values') if isinstance(row,dict) else None
        if (not isinstance(v,dict) or type(v.get('layerId')) is not int or
            not isinstance(v.get('layerType'),str) or v['layerId'] in management):
            raise ConfigurationError('EasyEDA malformed/duplicate layerManagement entry.')
        management[v['layerId']] = v
    layers, mapped, omitted, ids = [], [], [], set()
    for row in value['physicalStacking']:
        v = row.get('values') if isinstance(row,dict) else None
        if (not isinstance(v,dict) or type(v.get('Layer Id')) is not int or
            any(not isinstance(v.get(k),str) or not v[k].strip() for k in ('Layer','Layer Type','Type'))):
            raise ConfigurationError('EasyEDA malformed physicalStacking entry.')
        name, kind = v['Layer'], v['Layer Type']
        if v['Layer Id'] in ids:
            raise ConfigurationError(f'EasyEDA duplicate physical layer: {name}')
        ids.add(v['Layer Id'])
        if kind in OMITTED_TYPES:
            omitted.append(dict(source=v, disposition='omitted')); continue
        if kind not in COPPER_TYPES | {'SUBSTRATE'}:
            raise ConfigurationError(f'EasyEDA unsupported physical layer {name}: {kind}')
        if kind in COPPER_TYPES:
            m=management.get(v['Layer Id'])
            if not m or m.get('layerType')!=kind or m.get('status')!=1 or v['Type']!='Copper':
                raise ConfigurationError(f'EasyEDA inconsistent active copper layer: {name}')
        elif v['Type']!='Substrate':
            raise ConfigurationError(f'EasyEDA inconsistent dielectric type: {name}')
        def number(key, minimum, strict=False):
            x=v.get(key)
            if isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x) or (x<=minimum if strict else x<minimum):
                message = ('EM epsilon_r is required and was not inferred.' if key=='Permittivity' else 'physical numeric value required.')
                raise ConfigurationError(f'EasyEDA stackup {name} has {key}={x}; {message}')
            return x
        thickness=number('Thickness',0,True)
        if kind in COPPER_TYPES:
            role = {'TOP':'top','BOTTOM':'bottom'}.get(kind)
            if role is None: role='inner'+str(sum(l['type']=='copper' for l in layers))
            layer=dict(type='copper',role=role,thickness_um=thickness*1000,
                       model='conducting_sheet',conductivity_s_m=58e6)
        else:
            layer=dict(type='dielectric',name=name,thickness_mm=thickness,
                       epsilon_r=number('Permittivity',1),loss_tangent=number('Loss Tangent',0))
        layers.append(layer);mapped.append(dict(source=v,modeled=layer))
    if not layers or any(a['type']==b['type'] for a,b in zip(layers,layers[1:])):
        raise ConfigurationError('EasyEDA requires alternating copper / dielectric physical sequence.')
    result=dict(schema_version=2,stackup=layers,port=dict(mode='auto',layer='top'),
                drills=dict(pth_plating_um=25,pth_model='solid_pec_equivalent'))
    validate_schema(result,'pcb-physical.schema.json');validate_stackup_sequence(result)
    assumptions=['Copper conducting_sheet and conductivity 58e6 S/m: project assumptions, not EasyEDA values.',
                 'PTH plating 25 um, solid_pec_equivalent: project assumptions, not EasyEDA values.',
                 'Soldermask, paste and silkscreen omitted.']
    return result,dict(format=fmt,thickness_unit='mm',mapped_layers=mapped,omitted_layers=omitted,assumptions=assumptions)
