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

# Source EPRO path below does not reuse manufacturing approximation defaults.
SOURCE_COPPER_TYPES = frozenset(('TOP','BOTTOM','SIGNAL','PLANE'))


def source_physical_stackup(data):
    """Ordered source LAYER_PHYS; editor/mask/paste/silk are not EM."""
    layers={v['id']:v for v in data['layers']}
    selected=[]; omitted=[]; seen=set()
    for entry in data['layer_physics']:
        lid=entry['layer_id']
        if lid in seen or lid not in layers:
            raise ConfigurationError(f'EasyEDA LAYER_PHYS {lid}: duplicate or undefined layer.')
        seen.add(lid)
        kind=layers[lid]['type']
        if kind in SOURCE_COPPER_TYPES or kind=='SUBSTRATE':
            if not isfinite(entry['thickness_m']) or entry['thickness_m']<=0:
                raise ConfigurationError(f'EasyEDA LAYER_PHYS {lid}: positive thickness required.')
            selected.append(dict(entry,kind=kind,name=layers[lid]['name']))
        elif (kind in OMITTED_TYPES or kind in
              {'TOP_PASTE','BOTTOM_PASTE','TOP_MASK','BOTTOM_MASK',
               'TOP_SILKSCREEN','BOTTOM_SILKSCREEN','COURTYARD','STENCIL'}):
            omitted.append(dict(layer_id=lid,kind=kind,name=layers[lid]['name'],
                                record_index=entry['record_index'],disposition='non_EM_layer'))
        else:
            raise ConfigurationError(f'EasyEDA LAYER_PHYS {lid}: unknown physical layer kind {kind}; '
                                     'no silent omission of material.')
    kinds=[x['kind'] for x in selected]
    if (len(kinds)<3 or kinds[0]!='TOP' or kinds[-1]!='BOTTOM' or
            any((a in SOURCE_COPPER_TYPES)==(b in SOURCE_COPPER_TYPES)
                for a,b in zip(kinds,kinds[1:]))):
        raise ConfigurationError('EasyEDA physical stackup must alternate TOP / SUBSTRATE / '
                                 'inner SIGNAL/PLANE / SUBSTRATE / BOTTOM.')
    conductors=[x for x in selected if x['kind'] in SOURCE_COPPER_TYPES]
    roles={x['layer_id']:('top' if i==0 else 'bottom' if i==len(conductors)-1
                          else f'inner{i}') for i,x in enumerate(conductors)}
    return dict(records=selected,role_by_layer_id=roles,ignored_layers=omitted)


def describe_source_stackup(data, source_sha256, overrides=None, *, require_materials=False):
    """Physical Z/provenance; do not guess an absent dielectric epsilon.

    Overrides use string layer IDs mapping to {epsilon_r, loss_tangent}.
    Inspection can report epsilon 0; FDTD must reject it.
    """
    src=source_physical_stackup(data)
    overrides=overrides or {}
    if not isinstance(overrides,dict):
        raise ConfigurationError('EasyEDA dielectrics overrides: require layer ID mapping.')
    allowed={str(x['layer_id']) for x in src['records'] if x['kind']=='SUBSTRATE'}
    if any(str(k) not in allowed for k in overrides):
        raise ConfigurationError('EasyEDA dielectric override: unknown/non-dielectric layer ID.')
    z=0.0; copper=[]; dielectric=[]; missing=[]
    for item in src['records']:
        lid=item['layer_id']
        if item['kind'] in SOURCE_COPPER_TYPES:
            copper.append(dict(layer_id=lid,name=item['name'],role=src['role_by_layer_id'][lid],
                z_m=z,model='pec',thickness_m=item['thickness_m'],conductivity_s_m=58e6,
                source_sha256=source_sha256))
        else:
            manual=overrides.get(str(lid),overrides.get(lid,{}))
            if not isinstance(manual,dict) or set(manual)-{'epsilon_r','loss_tangent'}:
                raise ConfigurationError(f'EasyEDA dielectric {lid}: override accepts epsilon_r/loss_tangent only.')
            eps=manual.get('epsilon_r',item['epsilon_r'])
            loss=manual.get('loss_tangent',item['loss_tangent'])
            if (any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v)
                    for v in (eps,loss)) or loss<0):
                raise ConfigurationError(f'EasyEDA dielectric {lid}: invalid material parameter.')
            if eps<1:
                missing.append(dict(layer_id=lid,name=item['name'],reason='epsilon_r missing/less than one'))
            bottom=z-item['thickness_m']
            if not bottom<z:
                raise ConfigurationError(f'EasyEDA dielectric {lid}: Z step collapsed.')
            dielectric.append(dict(layer_id=lid,material_label=item['material'],
                name=f"{item['name']}_{lid}",z_min_m=bottom,z_max_m=z,
                epsilon_r=eps,loss_tangent=loss,
                epsilon_origin='explicit_user_override' if 'epsilon_r' in manual else 'CAD_LayerPhys',
                loss_origin='explicit_user_override' if 'loss_tangent' in manual else 'CAD_LayerPhys'))
            z=bottom
    if require_materials and missing:
        ids=', '.join(str(v['layer_id']) for v in missing)
        raise ConfigurationError('EasyEDA dielectrics: epsilon_r not defined in CAD for layer IDs '
                                 f'{ids}. Supply explicit epsilon_r (no automatic FR4 assumption).')
    return dict(copper_layers=copper,dielectric_layers=dielectric,
                role_by_layer_id=src['role_by_layer_id'],
                ignored_layers=src['ignored_layers'],missing_materials=missing,
                soldermask_model='omitted; effective permittivity model deferred',
                copper_geometry_model='PEC surfaces; foil thickness is material metadata only')

def parse_source_dielectric_materials(specs):
    """CLI/GUI data grammar: LAYER_ID:epsilon_r:loss_tangent, no defaults."""
    result={}
    for value in specs:
        text=str(value)
        pieces=text.split(':')
        if len(pieces)!=3 or not pieces[0].isdigit():
            raise ConfigurationError(f'EasyEDA dielectric material {text!r}: '
                                     'expected LAYER_ID:epsilon_r:loss_tangent.')
        key=str(int(pieces[0]))
        if key in result:
            raise ConfigurationError(f'EasyEDA dielectric material: duplicate layer {key}.')
        try:
            eps=float(pieces[1]);loss=float(pieces[2])
        except ValueError as exc:
            raise ConfigurationError(f'EasyEDA dielectric {key}: invalid numeric material data.') from exc
        if not isfinite(eps) or eps<1 or not isfinite(loss) or loss<0:
            raise ConfigurationError(f'EasyEDA dielectric {key}: require epsilon_r>=1 and loss_tangent>=0.')
        result[key]=dict(epsilon_r=eps,loss_tangent=loss)
    return result
