"""Helpers compartilhados dos protocolos: parsing de formulários e validação."""
import json
import re
from datetime import datetime

from app import db
from app.datas import parse_date_br as parse_date_br  # noqa: F401  (reexportado)
from app.labels import COMPONENT_LABELS, PROTO_TYPE_LABELS
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
        # Na Pronta-Entrega toda máquina é, por definição, pronta-entrega.
        is_prebuilt = (protocol_type == 'ponta_entrega') or (request_form.get(f'pe_switch_{unit}') == 'on')
        # O NS é obrigatório na venda normal e na Pronta-Entrega. Só pode ficar
        # em branco na máquina marcada como PE dentro da venda (NS de referência).
        ns_facultativo = ns_optional or (protocol_type == 'venda' and is_prebuilt)
        for i in range(len(types)):
            ct = types[i].strip()
            serial = serials[i].strip() if i < len(serials) else ''
            if ct:
                if not ns_facultativo and not serial:
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

def _sem_origem_techbuy(itens, tipo):
    """NTB não tem pedido/data de compra — o equipamento não veio da loja."""
    if tipo != 'nao_comprado' or not isinstance(itens, list):
        return itens
    limpos = []
    for item in itens:
        if not isinstance(item, dict):
            limpos.append(item)
            continue
        copia = dict(item)
        copia['pedido'] = ''
        copia['data_compra'] = ''
        limpos.append(copia)
    return limpos


def parse_rma_test_items(request_form):
    """Parse RMA test items from JSON hidden field."""
    raw = request_form.get('rma_test_json', '').strip()
    if not raw:
        return None
    try:
        data = _sem_origem_techbuy(json.loads(raw), request_form.get('type'))
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
    items = _sem_origem_techbuy(items, request_form.get('type'))
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

def _json_tem_itens(valor):
    """True só quando o JSON guardado tem conteúdo (evita '[]' e '{}' contarem)."""
    if not valor:
        return False
    try:
        return bool(json.loads(valor))
    except (json.JSONDecodeError, TypeError):
        return False


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
        # NTB é equipamento não comprado na TechBuy: não tem pedido nem data
        # de compra. O essencial é cliente, vendedor e o equipamento — que
        # pode estar em qualquer uma das seções (equipamento do cliente,
        # teste de mesa, equipamento extra ou componentes).
        if not protocol.client_name:
            missing.append('Cliente')
        if not protocol.seller:
            missing.append('Vendedor')
        if not (protocol.rma_extra_equip or protocol.components
                or _json_tem_itens(protocol.rma_equip_itens)
                or _json_tem_itens(protocol.rma_test_result)):
            missing.append('Equipamento')

    return missing


# ---------------------------------------------------------------------------
# Vínculo Venda PE <-> Pronta-Entrega (máquina por máquina)
# ---------------------------------------------------------------------------

def normalizar_ns(valor):
    """NS comparável: sem espaços, em maiúsculas e sem o prefixo 'R -'."""
    if valor is None:
        return ''
    texto = str(valor).upper().strip()
    texto = re.sub(r'^R\s*-\s*', '', texto)
    texto = re.sub(r'\s+', '', texto)
    return texto


def _somente_digitos(valor):
    return re.sub(r'\D', '', normalizar_ns(valor))


def ns_bate(a, b):
    """Compara dois NS tolerando 'R -', espaços, maiúsculas e zeros à esquerda."""
    a_norm = normalizar_ns(a)
    b_norm = normalizar_ns(b)
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True
    a_dig = _somente_digitos(a_norm)
    b_dig = _somente_digitos(b_norm)
    if len(a_dig) >= 4 and len(b_dig) >= 4:
        if a_dig.lstrip('0') == b_dig.lstrip('0'):
            return True
    return False


def _unidade(valor):
    """Número do bloco sempre com 2 dígitos ('1' -> '01')."""
    texto = str(valor or '').strip()
    return texto.zfill(2) if texto.isdigit() else texto


def parse_sale_refs(request_form, protocol=None):
    """Lê as 'Referências de Venda' digitadas nas máquinas de uma Pronta-Entrega."""
    data = {}
    for key in request_form.keys():
        if not key.startswith('sale_ref_'):
            continue
        unit = key[len('sale_ref_'):]
        if not re.fullmatch(r'\d+', unit):
            continue
        texto = (request_form.get(f'sale_ref_{unit}') or '').strip()
        if not texto:
            continue
        sale_id = (request_form.get(f'sale_ref_id_{unit}') or '').strip()
        sale_number = (request_form.get(f'sale_ref_number_{unit}') or '').strip()
        # Se o texto foi alterado à mão, o vínculo automático deixa de valer.
        if sale_number and sale_number not in texto:
            sale_id, sale_number = '', ''
        data[_unidade(unit)] = {
            'text': texto,
            'sale_id': int(sale_id) if sale_id.isdigit() else None,
            'sale_number': sale_number or None,
        }
    return json.dumps(data, ensure_ascii=False) if data else None


def parse_pe_refs(request_form):
    """Lê os vínculos com Prontas-Entregas enviados pelo formulário de venda."""
    data = {}
    for key in request_form.keys():
        if not key.startswith('pe_ref_json_'):
            continue
        unit = key[len('pe_ref_json_'):]
        if not re.fullmatch(r'\d+', unit):
            continue
        raw = (request_form.get(key) or '').strip()
        if not raw:
            continue
        try:
            info = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(info, dict):
            continue
        try:
            pe_id = int(info.get('protocol_id'))
        except (TypeError, ValueError):
            continue
        pe_unit = info.get('unit')
        if not pe_id or pe_unit in (None, ''):
            continue
        data[_unidade(unit)] = {
            'protocol_id': pe_id,
            'protocol_number': (info.get('protocol_number') or '').strip() or None,
            'unit': _unidade(pe_unit),
            'fonte': (info.get('fonte') or '').strip() or None,
            'machine_name': (info.get('machine_name') or '').strip() or None,
        }
    return json.dumps(data, ensure_ascii=False) if data else None


def texto_referencia_venda(venda):
    """Texto mostrado na Pronta-Entrega: 'PRO-2026-0199 · Cliente · 30/10/2026'."""
    partes = [venda.protocol_number]
    if venda.client_name:
        partes.append(venda.client_name.strip())
    data = venda.entry_date or venda.created_at
    if data:
        partes.append(data.strftime('%d/%m/%Y'))
    return ' · '.join(p for p in partes if p)


def _pe_do_ref(info):
    """Devolve (Protocol da PE, unidade) a partir de um vínculo salvo na venda."""
    if not isinstance(info, dict):
        return None, ''
    try:
        pe_id = int(info.get('protocol_id'))
    except (TypeError, ValueError):
        return None, ''
    pe = Protocol.query.get(pe_id)
    if not pe or pe.type != 'ponta_entrega':
        return None, ''
    return pe, _unidade(info.get('unit'))


def limpar_vinculos_pe(venda, refs_antigos, refs_novos=None):
    """Apaga da Pronta-Entrega as referências desta venda que não valem mais."""
    chaves_novas = set()
    for info in (refs_novos or {}).values():
        pe, unit = _pe_do_ref(info)
        if pe:
            chaves_novas.add((pe.id, unit))
    for info in (refs_antigos or {}).values():
        pe, unit = _pe_do_ref(info)
        if not pe or (pe.id, unit) in chaves_novas:
            continue
        sale_refs = pe.get_sale_refs()
        atual = sale_refs.get(unit)
        if atual is None:
            continue
        if isinstance(atual, dict):
            mesmo = (str(atual.get('sale_id')) == str(venda.id)
                     or atual.get('sale_number') == venda.protocol_number)
        else:
            mesmo = venda.protocol_number in str(atual)
        if mesmo:
            sale_refs.pop(unit, None)
            pe.sale_refs = json.dumps(sale_refs, ensure_ascii=False) if sale_refs else None


def aplicar_vinculos_pe(venda):
    """Grava na Pronta-Entrega a referência desta venda, máquina por máquina."""
    refs = venda.get_pe_refs()
    if not refs:
        return
    texto = texto_referencia_venda(venda)
    for info in refs.values():
        pe, unit = _pe_do_ref(info)
        if not pe:
            continue
        sale_refs = pe.get_sale_refs()
        sale_refs[unit] = {
            'text': texto,
            'sale_id': venda.id,
            'sale_number': venda.protocol_number,
        }
        pe.sale_refs = json.dumps(sale_refs, ensure_ascii=False)


def remover_referencias_da_pe(pe):
    """Remove das vendas os vínculos com uma Pronta-Entrega excluída/trocada."""
    for venda in Protocol.query.filter(Protocol.type == 'venda').all():
        refs = venda.get_pe_refs()
        if not refs:
            continue
        mudou = False
        for unit, info in list(refs.items()):
            if isinstance(info, dict) and str(info.get('protocol_id')) == str(pe.id):
                refs.pop(unit, None)
                mudou = True
        if mudou:
            venda.pe_refs = json.dumps(refs, ensure_ascii=False) if refs else None


def vendas_por_maquina_pe(pe):
    """{unidade: [vendas ativas]} para mostrar dentro da Pronta-Entrega."""
    resultado = {}
    for venda in Protocol.query.filter(Protocol.type == 'venda').order_by(Protocol.id).all():
        if (venda.status or '').lower() == 'cancelado':
            continue
        for info in venda.get_pe_refs().values():
            if not isinstance(info, dict):
                continue
            try:
                pe_id = int(info.get('protocol_id'))
            except (TypeError, ValueError):
                continue
            if pe_id != pe.id:
                continue
            unit = _unidade(info.get('unit'))
            resultado.setdefault(unit, []).append({
                'id': venda.id,
                'protocol_number': venda.protocol_number,
                'client_name': venda.client_name or '',
                'date': venda.entry_date or venda.created_at,
                'fonte': info.get('fonte') or '',
            })
    return resultado


def pe_por_maquina(venda):
    """{unidade: dados da PE} para mostrar dentro da venda."""
    resultado = {}
    for unit, info in venda.get_pe_refs().items():
        pe, pe_unit = _pe_do_ref(info)
        if not pe:
            continue
        resultado[_unidade(unit)] = {
            'id': pe.id,
            'protocol_number': pe.protocol_number,
            'unit': pe_unit,
            'machine_name': info.get('machine_name') or '',
            'fonte': info.get('fonte') or '',
        }
    return resultado


def pe_refs_para_formulario(venda):
    """Completa os vínculos salvos com o número da PE e o nome da máquina."""
    refs = venda.get_pe_refs()
    if not refs:
        return None
    data = {}
    for unit, info in refs.items():
        if not isinstance(info, dict):
            data[unit] = info
            continue
        novo = dict(info)
        pe, pe_unit = _pe_do_ref(info)
        if pe:
            novo['protocol_number'] = pe.protocol_number
            novo['unit'] = pe_unit
            if not novo.get('machine_name'):
                comps = [c for c in pe.components if _unidade(c.unit) == pe_unit]
                novo['machine_name'] = next(
                    (c.machine_name for c in comps if c.machine_name), '')
        data[_unidade(unit)] = novo
    return json.dumps(data, ensure_ascii=False)


def _dados_maquina_pe(pe, unit, venda_ignorada=None):
    """Componentes, fonte e vendas de um bloco específico da Pronta-Entrega."""
    comps = [c for c in pe.components if _unidade(c.unit) == unit]
    comps.sort(key=lambda c: (c.sort_order or 0))
    fonte = next((c.serial_number for c in comps
                  if c.component_type == 'fonte' and c.serial_number), '')
    vendas = []
    for venda in Protocol.query.filter(Protocol.type == 'venda').order_by(Protocol.id).all():
        if venda_ignorada and venda.id == venda_ignorada:
            continue
        if (venda.status or '').lower() == 'cancelado':
            continue
        for info in venda.get_pe_refs().values():
            if not isinstance(info, dict):
                continue
            try:
                pe_id = int(info.get('protocol_id'))
            except (TypeError, ValueError):
                continue
            if pe_id == pe.id and _unidade(info.get('unit')) == unit:
                data = venda.entry_date or venda.created_at
                vendas.append({
                    'id': venda.id,
                    'protocol_number': venda.protocol_number,
                    'client_name': venda.client_name or '',
                    'date': data.strftime('%d/%m/%Y') if data else '',
                })
    return {
        'components': [{
            'type': c.component_type or '',
            'label': COMPONENT_LABELS.get(c.component_type, c.component_type or ''),
            'model': c.specification or '',
            'serial': c.serial_number or '',
        } for c in comps if c.component_type],
        'fonte': fonte or '',
        'vendida': vendas,
        'disponivel': not vendas,
    }


def buscar_pronta_entrega(ns='', pe_numero='', unit='', ignorar_venda_id=None, limite=12):
    """Procura máquinas de Pronta-Entrega pelo NS da fonte ou pelo protocolo + bloco."""
    ns = (ns or '').strip()
    pe_numero = (pe_numero or '').strip().upper()
    unit = _unidade(unit) if unit else ''
    if not ns and not pe_numero:
        return []
    candidatas = Protocol.query.filter_by(type='ponta_entrega').order_by(Protocol.id).all()
    resultados = []
    for pe in candidatas:
        if pe_numero:
            numero = pe.protocol_number.upper()
            if not (numero == pe_numero or numero.endswith(pe_numero) or pe_numero in numero):
                continue
        unidades = {}
        for c in pe.components:
            u = _unidade(c.unit)
            if unit and u != unit:
                continue
            unidades.setdefault(u, []).append(c)
        for u, comps in unidades.items():
            fontes = [c.serial_number for c in comps
                      if c.component_type == 'fonte' and c.serial_number]
            if ns and not any(ns_bate(f, ns) for f in fontes):
                continue
            info = _dados_maquina_pe(pe, u, ignorar_venda_id)
            nome = next((c.machine_name for c in comps if c.machine_name), '')
            resultados.append({
                'protocol_id': pe.id,
                'protocol_number': pe.protocol_number,
                'unit': u,
                'machine_name': nome,
                'fonte': info['fonte'],
                'components': info['components'],
                'vendida': info['vendida'],
                'disponivel': info['disponivel'],
            })
            if len(resultados) >= limite:
                return resultados
    return resultados


def avisos_pe_ja_vendida(venda):
    """Avisos (sem bloquear) quando a máquina de PE já saiu em outra venda ativa."""
    avisos = []
    for info in venda.get_pe_refs().values():
        pe, unit = _pe_do_ref(info)
        if not pe:
            continue
        for outra in Protocol.query.filter(Protocol.type == 'venda').order_by(Protocol.id).all():
            if outra.id == venda.id or (outra.status or '').lower() == 'cancelado':
                continue
            for oi in outra.get_pe_refs().values():
                if not isinstance(oi, dict):
                    continue
                try:
                    opid = int(oi.get('protocol_id'))
                except (TypeError, ValueError):
                    continue
                if opid == pe.id and _unidade(oi.get('unit')) == unit:
                    avisos.append(
                        f'A máquina Nº {unit} da {pe.protocol_number} já saiu na venda '
                        f'{outra.protocol_number} ({outra.client_name or "sem cliente"}). '
                        f'Confirme se é troca/devolução.'
                    )
    return avisos


# --- Retornos (a mesma máquina volta ao laboratório) --------------------

def _json_ou(texto, padrao):
    try:
        return json.loads(texto) if texto else padrao
    except (json.JSONDecodeError, TypeError):
        return padrao


def _data_br(valor):
    return valor.strftime('%d/%m/%Y') if valor else ''


def _equip_itens_para_retorno(origem):
    """Equipamentos do protocolo anterior no formato 'Equipamento que chegou'."""
    itens = _json_ou(origem.rma_equip_itens, None)
    if isinstance(itens, dict) and itens:
        return itens
    if not origem.components:
        return None
    agrupado = {}
    for c in sorted(origem.components, key=lambda x: (x.sort_order or 0)):
        unit = _unidade(c.unit)
        entrada = agrupado.setdefault(unit, {
            'name': c.machine_name or f'Computador {unit}',
            'components': [],
        })
        if c.machine_name:
            entrada['name'] = c.machine_name
        entrada['components'].append({
            'type': c.component_type,
            'model': c.specification or '',
            'serial': c.serial_number or '',
        })
    return agrupado or None


def _primeiro_serial(texto_json):
    itens = _json_ou(texto_json, [])
    if isinstance(itens, dict):
        itens = list(itens.values())
    for item in itens or []:
        if not isinstance(item, dict):
            continue
        if item.get('serial'):
            return item['serial']
        for comp in item.get('components') or []:
            if isinstance(comp, dict) and comp.get('serial'):
                return comp['serial']
    return ''


def _aplicar_trocados_no_equipamento(equipamentos, trocados, test_itens):
    """Troca, no equipamento copiado, as peças antigas pelas novas.

    O cliente devolve a máquina como ela está agora: se a RAM defeituosa foi
    substituída, o novo protocolo já deve mostrar a RAM nova (modelo e NS).
    """
    if not isinstance(equipamentos, dict) or not isinstance(trocados, dict):
        return equipamentos

    por_nome = {}
    for unit, entrada in equipamentos.items():
        if isinstance(entrada, dict):
            por_nome[(entrada.get('name') or '').strip().lower()] = unit

    for unit, troca in trocados.items():
        if not isinstance(troca, dict):
            continue
        alvo = equipamentos.get(unit) or equipamentos.get(_unidade(unit))
        if not isinstance(alvo, dict):
            alvo = equipamentos.get(
                por_nome.get((troca.get('name') or '').strip().lower(), ''), None)
        if not isinstance(alvo, dict):
            continue

        comps = alvo.setdefault('components', [])
        nome = (alvo.get('name') or '').strip().lower()
        usados = set()
        for novo in troca.get('components') or []:
            if not isinstance(novo, dict) or not novo.get('type'):
                continue
            tipo = novo['type']

            # Descobre qual peça antiga foi marcada como trocada no teste de mesa,
            # para acertar o item certo quando a máquina tem duas peças iguais.
            serial_defeito = ''
            for item in test_itens or []:
                if not isinstance(item, dict):
                    continue
                mesma_maquina = (item.get('machine') or '').strip().lower() == nome
                if (mesma_maquina and item.get('component') == tipo
                        and (item.get('status') or '').lower() == 'trocado'):
                    serial_defeito = item.get('serial') or ''
                    break

            indice = None
            if serial_defeito:
                indice = next(
                    (i for i, c in enumerate(comps)
                     if i not in usados and c.get('type') == tipo
                     and (c.get('serial') or '') == serial_defeito), None)
            if indice is None:
                indice = next(
                    (i for i, c in enumerate(comps)
                     if i not in usados and c.get('type') == tipo), None)

            entrada = {
                'type': tipo,
                'model': novo.get('model') or '',
                'serial': novo.get('serial') or '',
            }
            if indice is None:
                comps.append(entrada)
            else:
                usados.add(indice)
                comps[indice] = entrada

    return equipamentos


def criar_protocolo_retorno(origem, novo_tipo, user_id):
    """Monta (sem gravar) o protocolo do novo retorno, ligado ao anterior."""
    if novo_tipo not in PROTO_TYPE_LABELS:
        return None
    hoje = datetime.utcnow()
    # Na venda/PE/NTB a entrada é hoje; no RMA/serviço a "data da compra"
    # continua sendo a do protocolo anterior.
    if novo_tipo in ('rma', 'servico'):
        entrada = origem.entry_date or hoje
        rma_entrada = hoje
    else:
        entrada = hoje
        rma_entrada = None

    if novo_tipo == 'rma':
        garantia = True
    elif novo_tipo == 'servico':
        garantia = False
    else:
        garantia = origem.rma_in_warranty

    novo = Protocol(
        protocol_number=gerar_numero_protocolo(),
        type=novo_tipo,
        origin_id=origem.id,
        client_name=origem.client_name,
        seller=origem.seller,
        lote=origem.lote,
        status='pendente',
        entry_date=entrada,
        rma_entry_date=rma_entrada,
        rma_in_warranty=garantia,
        order_number=origem.order_number,
        original_order=origem.original_order,
        ref_ns=origem.ref_ns,
        rma_extra_equip=origem.rma_extra_equip,
        created_by=user_id,
    )

    equipamentos = _equip_itens_para_retorno(origem)
    equipamentos = _aplicar_trocados_no_equipamento(
        equipamentos,
        _json_ou(origem.rma_trocados, {}),
        _json_ou(origem.rma_test_result, []))
    if equipamentos and novo_tipo in ('rma', 'servico', 'nao_comprado'):
        novo.rma_equip_itens = json.dumps(equipamentos, ensure_ascii=False)

    if novo_tipo in ('venda', 'ponta_entrega'):
        for c in sorted(origem.components, key=lambda x: (x.sort_order or 0)):
            novo.components.append(Component(
                component_type=c.component_type,
                specification=c.specification,
                serial_number=c.serial_number,
                unit=c.unit,
                machine_name=c.machine_name,
                sort_order=c.sort_order,
                is_prebuilt=c.is_prebuilt,
                machine_ref_ns=c.machine_ref_ns,
                material_comum=c.material_comum,
                product_id=c.product_id,
            ))
        novo.power_cables = origem.power_cables

    if novo_tipo in ('rma', 'servico'):
        passagens = _json_ou(origem.rma_passagens, [])
        if not isinstance(passagens, list):
            passagens = []
        passagens.append({
            'protocolo': origem.protocol_number,
            'ns': _primeiro_serial(origem.rma_test_result),
            'ns_novo': _primeiro_serial(origem.rma_trocados),
            'pedido': '',
            'data_entrada': _data_br(origem.rma_entry_date or origem.entry_date),
            'data_saida': _data_br(origem.exit_date),
        })
        novo.rma_passagens = json.dumps(passagens, ensure_ascii=False)

    return novo


def historico_do_protocolo(protocol):
    """Resumo somente leitura usado na tela de edição do retorno."""
    if not protocol:
        return None
    trocados_raw = _json_ou(protocol.rma_trocados, None)
    if isinstance(trocados_raw, dict):
        trocados = trocados_raw
    elif isinstance(trocados_raw, list) and trocados_raw:
        trocados = {'01': {'name': 'Computador 01', 'components': trocados_raw}}
    else:
        trocados = {}
    return {
        'protocol': protocol,
        'test_itens': _json_ou(protocol.rma_test_result, []) or [],
        'trocados': trocados,
        'equip_itens': _equip_itens_para_retorno(protocol) or {},
        'passagens': _json_ou(protocol.rma_passagens, []) or [],
    }


def _pedido_normalizado(valor):
    pedido = (valor or '').strip().upper()
    # Evita agrupar protocolos sem pedido de verdade (o laboratório usa NIL).
    if pedido in ('', 'NIL', 'N/A', 'NA', '-', 'NONE', 'SEM PEDIDO'):
        return ''
    return pedido


def historico_por_pedido(pedido, ignorar_id=None):
    """Histórico completo (defeitos/trocados) dos protocolos do mesmo pedido."""
    return [historico_do_protocolo(p)
            for p in protocolos_por_pedido(pedido, ignorar_id=ignorar_id)]


def protocolos_por_pedido(pedido, ignorar_id=None):
    """Todos os protocolos do mesmo pedido (e a corrente deles), em ordem.

    Serve para puxar o histórico mesmo quando o retorno foi cadastrado à mão,
    só repetindo o número do pedido.
    """
    alvo = _pedido_normalizado(pedido)
    if not alvo:
        return []
    candidatos = Protocol.query.filter(db.or_(
        db.func.upper(db.func.trim(db.func.coalesce(Protocol.order_number, ''))) == alvo,
        db.func.upper(db.func.trim(db.func.coalesce(Protocol.original_order, ''))) == alvo,
    )).order_by(Protocol.entry_date, Protocol.id).all()

    encontrados = {}
    for candidato in candidatos:
        for item in candidato.get_return_chain():
            encontrados[item.id] = item
    if ignorar_id:
        encontrados.pop(ignorar_id, None)

    return sorted(
        encontrados.values(),
        key=lambda p: (p.entry_date or p.created_at or datetime.min, p.id))


def protocolos_por_referencia(termo, ignorar_id=None):
    """Procura por número do pedido OU por número do protocolo (parcial)."""
    termo = (termo or '').strip()
    if not termo:
        return []
    alvo = termo.upper().replace('%', '').replace('_', '')
    if not alvo:
        return []
    pedido = _pedido_normalizado(termo)

    condicoes = [db.func.upper(Protocol.protocol_number).like(f'%{alvo}%')]
    if pedido:
        condicoes += [
            db.func.upper(db.func.trim(db.func.coalesce(Protocol.order_number, ''))) == pedido,
            db.func.upper(db.func.trim(db.func.coalesce(Protocol.original_order, ''))) == pedido,
        ]
    candidatos = Protocol.query.filter(db.or_(*condicoes)) \
        .order_by(Protocol.entry_date, Protocol.id).all()

    encontrados = {}
    for candidato in candidatos:
        for item in candidato.get_return_chain():
            encontrados[item.id] = item
    if ignorar_id:
        encontrados.pop(ignorar_id, None)

    return sorted(
        encontrados.values(),
        key=lambda p: (p.entry_date or p.created_at or datetime.min, p.id))


def historico_por_referencia(termo, ignorar_id=None):
    return [historico_do_protocolo(p)
            for p in protocolos_por_referencia(termo, ignorar_id=ignorar_id)]

