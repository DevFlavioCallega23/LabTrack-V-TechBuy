"""Helpers compartilhados dos protocolos: parsing de formulários e validação."""
import json
from datetime import datetime

from app import db
from app.models import Protocol, Component, Defect, WindowsKey

def gerar_numero_protocolo():
    """PRO-ANO-NNNN com contagem reiniciando a cada ano (0001 em diante)."""
    ano = datetime.utcnow().year
    prefixo = f'PRO-{ano}-'
    numeros = [n[0] for n in db.session.query(Protocol.protocol_number)
               .filter(Protocol.protocol_number.like(prefixo + '%')).all()]
    maior = 0
    for num in numeros:
        sufixo = num[len(prefixo):]
        if sufixo.isdigit():
            maior = max(maior, int(sufixo))
    return f'{prefixo}{maior + 1:04d}'

def parse_date_br(text):
    if not text or not text.strip():
        return None
    text = text.strip().replace('/', '-')
    for fmt in ['%d-%m-%Y', '%d-%m-%y', '%Y-%m-%d']:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None

def build_validation_messages(form):
    """Gera lista de mensagens de erro específicas para exibição."""
    msgs = []
    if not form.type.data:
        msgs.append('O campo Tipo de Protocolo é obrigatório.')
    for field_name, errors in form.errors.items():
        label = getattr(getattr(form, field_name, None), 'label', None)
        label_text = label.text if label else field_name
        for err in errors:
            msgs.append(f'{label_text}: {err}')
    return msgs

def parse_components(request_form, protocol_type=None):
    components = []
    seen_units = set()
    ns_optional = protocol_type in ('rma', 'servico')
    material_comum = request_form.get('material_comum') == 'on'
    for key in request_form.keys():
        if key.startswith('comp_type_') and key.endswith('[]'):
            unit = key[len('comp_type_'):-2]
            seen_units.add(unit)
    for unit in sorted(seen_units):
        types = request_form.getlist(f'comp_type_{unit}[]')
        models = request_form.getlist(f'comp_model_{unit}[]')
        serials = request_form.getlist(f'comp_serial_{unit}[]')
        product_ids = request_form.getlist(f'comp_product_id_{unit}[]')
        cabo_fontes = request_form.getlist(f'comp_serial_fonte_{unit}[]')
        machine_name = request_form.get(f'machine_name_{unit}', '').strip() or f'Máquina {unit}'
        is_prebuilt = request_form.get(f'pe_switch_{unit}') == 'on'
        for i in range(len(types)):
            ct = types[i].strip()
            serial = serials[i].strip() if i < len(serials) else ''
            if ct:
                if not is_prebuilt and not serial and not ns_optional:
                    continue
                model = models[i].strip() if i < len(models) else ''
                product_id = None
                if not material_comum and product_ids:
                    pid = product_ids[i].strip() if i < len(product_ids) else ''
                    if pid and pid.isdigit():
                        product_id = int(pid)
                components.append(Component(
                    component_type=ct,
                    specification=model,
                    serial_number=serial or None,
                    unit=unit,
                    machine_name=machine_name,
                    sort_order=int(unit) * 100 + i,
                    is_prebuilt=is_prebuilt,
                    product_id=product_id,
                    material_comum=material_comum
                ))
    return components

def parse_power_cables(request_form):
    data = {}
    for key in request_form.keys():
        if key.startswith('machine_power_cable_'):
            unit = key[len('machine_power_cable_'):]
            cable = request_form.get(key, 'OK').strip()
            data[unit] = {'cable': cable}
    return json.dumps(data) if data else None

def parse_rma_equip(request_form):
    """Parse RMA equipment JSON from form."""
    raw = request_form.get('rma_equip_json', '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        cleaned = {k: v for k, v in data.items() if v.get('components')}
        return json.dumps(cleaned) if cleaned else None
    except (json.JSONDecodeError, TypeError):
        return None

def build_rma_equip_data(protocol):
    """Build RMA equipment JSON from protocol for editing."""
    if not protocol.rma_equip_itens:
        return '{}'
    try:
        data = json.loads(protocol.rma_equip_itens)
        return json.dumps(data)
    except (json.JSONDecodeError, TypeError):
        return '{}'

def build_rma_equip_data_from_form(request_form):
    """Build RMA equipment JSON from submitted form data for preserving on validation error."""
    data = {}
    for key in request_form.keys():
        if key.startswith('rma_comp_type_') and key.endswith('[]'):
            unit = key[len('rma_comp_type_'):-2]
            if unit in data:
                continue
            types = request_form.getlist(f'rma_comp_type_{unit}[]')
            models = request_form.getlist(f'rma_comp_model_{unit}[]')
            serials = request_form.getlist(f'rma_comp_serial_{unit}[]')
            machine_name = request_form.get(f'rma_machine_name_{unit}', '').strip() or f'Computador {unit}'
            comps = []
            for i in range(len(types)):
                if types[i].strip():
                    comps.append({
                        'type': types[i].strip(),
                        'model': models[i].strip() if i < len(models) else '',
                        'serial': serials[i].strip() if i < len(serials) else ''
                    })
            data[unit] = {'name': machine_name, 'components': comps}
    return json.dumps(data)

def parse_rma_test_items(request_form):
    """Parse RMA test items from JSON hidden field."""
    raw = request_form.get('rma_test_json', '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return json.dumps(data)
    except (json.JSONDecodeError, TypeError):
        return None

def build_rma_test_data_from_form(request_form):
    """Build RMA test items from submitted form data for preserving on validation error."""
    machines = request_form.getlist('rma_test_machine[]')
    comps = request_form.getlist('rma_test_comp[]')
    models = request_form.getlist('rma_test_model[]')
    serials = request_form.getlist('rma_test_serial[]')
    defeitos = request_form.getlist('rma_test_defeito[]')
    pedidos = request_form.getlist('rma_test_pedido[]')
    datas_compra = request_form.getlist('rma_test_data_compra[]')
    statuses = request_form.getlist('rma_test_status[]')
    items = []
    for i in range(len(comps)):
        if comps[i].strip():
            items.append({
                'machine': machines[i].strip() if i < len(machines) else '',
                'component': comps[i].strip(),
                'model': models[i].strip() if i < len(models) else '',
                'serial': serials[i].strip() if i < len(serials) else '',
                'defeito': defeitos[i].strip() if i < len(defeitos) else '',
                'pedido': pedidos[i].strip() if i < len(pedidos) else '',
                'data_compra': datas_compra[i].strip() if i < len(datas_compra) else '',
                'status': statuses[i].strip() if i < len(statuses) else ''
            })
    return json.dumps(items) if items else None

def parse_rma_trocados(request_form):
    """Parse Equipamentos Mudados from JSON hidden field (card-based structure)."""
    raw = request_form.get('rma_trocados_json', '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        cleaned = {k: v for k, v in data.items() if v.get('components')}
        return json.dumps(cleaned) if cleaned else None
    except (json.JSONDecodeError, TypeError):
        return None

def build_rma_trocados_data_from_form(request_form):
    """Build Equipamentos Mudados from submitted form data for preserving on validation error."""
    data = {}
    for key in request_form.keys():
        if key.startswith('trocado_comp_type_') and key.endswith('[]'):
            unit = key[len('trocado_comp_type_'):-2]
            if unit in data:
                continue
            types = request_form.getlist(f'trocado_comp_type_{unit}[]')
            models = request_form.getlist(f'trocado_comp_model_{unit}[]')
            serials = request_form.getlist(f'trocado_comp_serial_{unit}[]')
            machine_name = request_form.get(f'trocado_machine_name_{unit}', '').strip() or f'Computador {unit}'
            comps = []
            for i in range(len(types)):
                if types[i].strip():
                    comps.append({
                        'type': types[i].strip(),
                        'model': models[i].strip() if i < len(models) else '',
                        'serial': serials[i].strip() if i < len(serials) else ''
                    })
            data[unit] = {'name': machine_name, 'components': comps}
    return json.dumps(data)

def parse_windows_keys(request_form):
    raw = request_form.get('windows_keys_json', '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return [WindowsKey(
            chave=item.get('chave', ''),
            fonte=item.get('fonte', ''),
            ativo=item.get('ativo', False),
            sort_order=i
        ) for i, item in enumerate(data)]
    except (json.JSONDecodeError, TypeError):
        return None

def build_windows_key_data_from_form(request_form):
    raw = request_form.get('windows_keys_json', '').strip()
    if raw:
        return raw
    return '[]'

def build_windows_key_data(protocol):
    if protocol.windows_keys:
        return json.dumps([{
            'chave': k.chave or '',
            'fonte': k.fonte or '',
            'ativo': k.ativo
        } for k in protocol.windows_keys])
    return '[]'

def parse_defects(request_form):
    defects = []
    types = request_form.getlist('defect_type[]')
    descs = request_form.getlist('defect_desc[]')
    serials = request_form.getlist('defect_serial[]')
    models = request_form.getlist('defect_model[]')
    responsaveis = request_form.getlist('defect_resp[]')
    statuses = request_form.getlist('defect_status[]')
    maquinas = request_form.getlist('defect_maquina[]')
    for i in range(len(types)):
        if types[i].strip():
            defects.append(Defect(
                component_type=types[i].strip(),
                specification=models[i].strip() if i < len(models) else '',
                serial_number=serials[i].strip() if i < len(serials) else '',
                description=descs[i].strip() if i < len(descs) else '',
                responsavel=responsaveis[i].strip() if i < len(responsaveis) else '',
                defeito_status=statuses[i].strip() if i < len(statuses) else '',
                maquina=maquinas[i].strip() if i < len(maquinas) else '',
                sort_order=i
            ))
    return defects

def get_incomplete_fields(protocol):
    """Retorna lista de campos faltantes em um protocolo, baseado no tipo."""
    if getattr(protocol, 'incomplete_ignored', False):
        return []
    missing = []
    t = protocol.type

    if not t:
        missing.append('Tipo')
        return missing

    if t == 'ponta_entrega':
        if not protocol.components:
            missing.append('Componentes')
        if not protocol.entry_date:
            missing.append('Data Entrada')

    elif t == 'venda':
        if not protocol.client_name:
            missing.append('Cliente')
        if not protocol.seller:
            missing.append('Vendedor')
        if not protocol.order_number:
            missing.append('Nº Pedido')
        if not protocol.components:
            missing.append('Componentes')

    elif t in ('rma', 'servico'):
        if not protocol.client_name:
            missing.append('Cliente')
        if not protocol.seller:
            missing.append('Vendedor')
        if not protocol.original_order and not protocol.order_number:
            missing.append('Pedido Original')
        if not protocol.rma_extra_equip and not protocol.components and not protocol.rma_equip_itens:
            missing.append('Equipamento')

    elif t == 'nao_comprado':
        if not protocol.client_name:
            missing.append('Cliente')
        if not protocol.seller:
            missing.append('Vendedor')
        if not protocol.order_number:
            missing.append('Nº Pedido')
        if not protocol.components:
            missing.append('Componentes')

    return missing

