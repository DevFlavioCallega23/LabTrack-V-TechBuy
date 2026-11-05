"""Helpers compartilhados dos protocolos: parsing de formulários e validação."""
import json
import os
import re
import shutil
import tempfile
from datetime import datetime

from flask import current_app

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
            'pedido': origem.original_order or origem.order_number or '',
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


# --- Teia de protocolos (histórico completo, somente leitura) ------------

_TEIA_CORES_NO = {
    'venda': ('#198754', '#ffffff'),
    'ponta_entrega': ('#ffc107', '#212529'),
    'rma': ('#0d6efd', '#ffffff'),
    'servico': ('#dc3545', '#ffffff'),
    'nao_comprado': ('#6c757d', '#ffffff'),
}

_TEIA_CORES_ARESTA = {
    'retorno': '#0dcaf0',
    'venda_pe': '#20c997',
    'pedido': '#ffc107',
    'equipamento': '#0d6efd',
    'ns': '#0d6efd',
    'cliente': '#adb5bd',
}

_TEIA_LIGACOES = {
    'retorno': 'Retorno',
    'venda_pe': 'Venda ↔ PE',
    'pedido': 'Mesmo pedido',
    'equipamento': 'Mesmo equipamento',
    'ns': 'Mesmo NS',
    'cliente': 'Mesmo cliente',
}


_PLACEHOLDERS = {
    '', 'NIL', 'N/A', 'NA', '-', 'NONE', 'SEM PEDIDO', 'SEM VENDEDOR',
}


def _texto_limpo(valor):
    return str(valor or '').strip()


def _pedido_valido(valor):
    """Pedido de verdade: ignora NIL e códigos curtos que não são números."""
    texto = _texto_limpo(valor)
    if not texto or texto.upper() in _PLACEHOLDERS:
        return False
    if len(texto) < 6 and not texto.isdigit():
        return False
    return True


def _vendedor_valido(valor):
    texto = _texto_limpo(valor)
    return bool(texto) and texto.upper() not in _PLACEHOLDERS


def _cliente_valido(valor):
    texto = _texto_limpo(valor)
    return bool(texto) and texto.upper() not in _PLACEHOLDERS


def _lote_valido(valor):
    texto = _texto_limpo(valor)
    return bool(texto) and texto.upper() not in _PLACEHOLDERS


def _cliente_normalizado(protocol):
    texto = _texto_limpo(protocol.client_name)
    if not _cliente_valido(texto):
        return ''
    return ' '.join(texto.upper().split())


def _pedidos_do_protocolo(protocol):
    pedidos = set()
    for valor in (protocol.order_number, protocol.original_order):
        if _pedido_valido(valor):
            pedidos.add(_texto_limpo(valor).upper())
    return pedidos


def _pedido_principal(protocol):
    for valor in (protocol.original_order, protocol.order_number):
        if _pedido_valido(valor):
            return _texto_limpo(valor)
    return ''


def _data_ordem(protocol):
    return (protocol.rma_entry_date or protocol.entry_date
            or protocol.created_at or datetime.min)


def _tipo_peca(valor):
    texto = _texto_limpo(valor).lower()
    return texto or 'peca'


def _ns_limpo(valor):
    texto = _texto_limpo(valor).upper()
    if len(texto) < 4 or texto in ('NIL', 'NONE', 'N/A', 'NA', '0'):
        return ''
    return texto


def _equip_entradas(dados):
    """Devolve [(unidade, entrada)] para o formato antigo e o novo."""
    if isinstance(dados, dict):
        return [(str(chave), entrada) for chave, entrada in dados.items()
                if isinstance(entrada, dict)]
    if isinstance(dados, list):
        return [('', {'components': dados})]
    return []


def ns_do_protocolo(protocol):
    """NS do protocolo com o tipo da peça e a unidade onde apareceu."""
    info = {}

    def adicionar(valor, tipo='peca', unidade='', maquina='', fonte=''):
        ns = _ns_limpo(valor)
        if not ns:
            return
        item = info.setdefault(ns, {
            'tipos': set(), 'unidades': set(),
            'maquinas': set(), 'fontes': set(),
        })
        item['tipos'].add(_tipo_peca(tipo))
        if _texto_limpo(unidade):
            item['unidades'].add(_texto_limpo(unidade))
        if _texto_limpo(maquina):
            item['maquinas'].add(_texto_limpo(maquina))
        if fonte:
            item['fontes'].add(fonte)

    for componente in protocol.components or []:
        adicionar(componente.serial_number, componente.component_type,
                  componente.unit, componente.machine_name, 'componente')
        adicionar(componente.machine_ref_ns, 'maquina',
                  componente.unit, componente.machine_name, 'maquina')

    for info_pe in protocol.get_pe_refs().values():
        if isinstance(info_pe, dict):
            adicionar(info_pe.get('fonte'), 'fonte_pe',
                      info_pe.get('unit'), info_pe.get('machine_name'), 'pe')

    for unidade, entrada in _equip_entradas(_json_ou(protocol.rma_equip_itens, {})):
        for componente in entrada.get('components') or []:
            if isinstance(componente, dict):
                adicionar(componente.get('serial'), componente.get('type'),
                          unidade or componente.get('unit'),
                          entrada.get('name'), 'equipamento')

    for item in _json_ou(protocol.rma_test_result, []) or []:
        if not isinstance(item, dict):
            continue
        adicionar(item.get('serial'), item.get('component'),
                  item.get('unit'), item.get('machine'), 'teste')
        for componente in item.get('components') or []:
            if isinstance(componente, dict):
                adicionar(componente.get('serial'),
                          componente.get('type') or componente.get('component'),
                          componente.get('unit'), item.get('machine'), 'teste')

    for unidade, entrada in _equip_entradas(_json_ou(protocol.rma_trocados, {})):
        for componente in entrada.get('components') or []:
            if isinstance(componente, dict):
                adicionar(componente.get('serial'), componente.get('type'),
                          unidade or componente.get('unit'),
                          entrada.get('name'), 'trocado')

    for defeito in protocol.defects or []:
        adicionar(defeito.serial_number, defeito.component_type,
                  '', defeito.maquina, 'defeito')

    adicionar(protocol.ref_ns, 'ref', '', '', 'ref')
    adicionar(protocol.rma_test_serial, 'ref', '', '', 'ref')
    return info


def _comparar_ns(info_a, info_b):
    """NS iguais com o mesmo tipo e NS iguais com tipo diferente (conferir)."""
    comuns = []
    conflitos = []
    for ns in set(info_a) & set(info_b):
        tipos_a = info_a[ns]['tipos']
        tipos_b = info_b[ns]['tipos']
        tipos = tipos_a & tipos_b
        if tipos:
            comuns.append((ns, sorted(tipos)[0], info_a[ns], info_b[ns]))
        else:
            conflitos.append((ns, sorted(tipos_a), sorted(tipos_b),
                              info_a[ns], info_b[ns]))
    return comuns, conflitos


def _indice_teia(todos):
    """Índices para achar vizinhos sem varrer o banco a cada nó."""
    ns_por_id = {}
    ns_idx = {}
    pedido_idx = {}
    cliente_idx = {}
    for protocolo in todos:
        info = ns_do_protocolo(protocolo)
        ns_por_id[protocolo.id] = info
        for valor in info:
            ns_idx.setdefault(valor, []).append(protocolo)
        for pedido in _pedidos_do_protocolo(protocolo):
            pedido_idx.setdefault(pedido, []).append(protocolo)
        cliente = _cliente_normalizado(protocolo)
        if cliente:
            cliente_idx.setdefault(cliente, []).append(protocolo)
    return ns_por_id, ns_idx, pedido_idx, cliente_idx



def _tipo_peca_label(tipo):
    return COMPONENT_LABELS.get(tipo, (tipo or '').replace('_', ' ').title())


def _unidades(info_ns):
    unidades = set()
    for item in info_ns.values():
        unidades.update(item['unidades'])
    return unidades


def _mesmo_contexto(a, b):
    """Mesmo cliente ou mesmo pedido válido — confirma que é a mesma máquina."""
    cliente_a = _cliente_normalizado(a)
    cliente_b = _cliente_normalizado(b)
    if cliente_a and cliente_a == cliente_b:
        return True
    return bool(_pedidos_do_protocolo(a) & _pedidos_do_protocolo(b))


def _vizinhos_principais(atual, ns_por_id, ns_idx, por_id):
    """Vizinhos que entram na coluna principal da máquina."""
    achados = {}

    def adicionar(outro, tipo, evidencia):
        if not outro or outro.id == atual.id:
            return
        existente = achados.get(outro.id)
        if existente is None:
            achados[outro.id] = {
                'protocol': outro,
                'tipo': tipo,
                'evidencias': [evidencia] if evidencia else [],
            }
        elif evidencia and evidencia not in existente['evidencias']:
            existente['evidencias'].append(evidencia)

    origem = atual.get_origin()
    if origem:
        adicionar(origem, 'retorno', f'Retorno de {atual.protocol_number}')
    for retorno in atual.get_returns():
        adicionar(retorno, 'retorno', f'Gerou {retorno.protocol_number}')

    info_atual = ns_por_id.get(atual.id, {})
    for ns, item in info_atual.items():
        for outro in ns_idx.get(ns, []):
            if outro.id == atual.id:
                continue
            comuns, _ = _comparar_ns({ns: item}, ns_por_id.get(outro.id, {}))
            if not comuns:
                continue
            if _mesmo_contexto(atual, outro):
                tipo_peca = comuns[0][1]
                adicionar(outro, 'equipamento',
                         f'NS {ns} · {_tipo_peca_label(tipo_peca)}')

    if atual.type == 'venda':
        for info in pe_por_maquina(atual).values():
            outro = por_id.get(info.get('id'))
            if outro:
                adicionar(
                    outro, 'venda_pe',
                    f"Máquina {info.get('unit') or '?'} · fonte "
                    f"{info.get('fonte') or 'sem NS'}")
    elif atual.type == 'ponta_entrega':
        for unidade, vendas in vendas_por_maquina_pe(atual).items():
            for venda in vendas:
                outro = por_id.get(venda.get('id'))
                if outro:
                    adicionar(
                        outro, 'venda_pe',
                        f"Máquina {unidade} · fonte "
                        f"{venda.get('fonte') or 'sem NS'}")

    return achados


def _ns_detalhe(info_ns):
    detalhe = []
    for ns in sorted(info_ns):
        item = info_ns[ns]
        tipos = sorted(item['tipos'])
        detalhe.append({
            'ns': ns,
            'tipos': tipos,
            'tipos_label': ', '.join(_tipo_peca_label(t) for t in tipos),
            'unidades': sorted(item['unidades']),
            'maquinas': sorted(item['maquinas']),
        })
    return detalhe


def _montar_no(protocol, info_ns, flags=None, papel=''):
    data_ref = _data_ordem(protocol)
    cor, cor_texto = _TEIA_CORES_NO.get(protocol.type, ('#0d6efd', '#ffffff'))
    pedidos = sorted(_pedidos_do_protocolo(protocol))
    return {
        'id': protocol.id,
        'protocol': protocol,
        'numero': protocol.protocol_number,
        'tipo': protocol.type,
        'tipo_label': protocol.type_label() or '',
        'status_label': protocol.status_label() or '',
        'status_badge': protocol.status_badge() or 'bg-secondary',
        'data': data_ref.strftime('%d/%m/%Y') if data_ref else '',
        'data_ordem': data_ref,
        'cor': cor,
        'cor_texto': cor_texto,
        'ns': sorted(info_ns),
        'ns_detalhe': _ns_detalhe(info_ns),
        'pedidos': pedidos,
        'pedido': pedidos[0] if pedidos else '',
        'cliente': _texto_limpo(protocol.client_name),
        'retorno_label': protocol.return_label() or '',
        'flags': flags or {},
        'papel': papel,
    }


def teia_do_protocolo(protocol, limite=60):
    """Linha do tempo vertical da máquina + ramos laterais de peças.

    Coluna principal: retorno, mesmo equipamento (cliente/pedido + NS + tipo)
    e venda ↔ PE. O que só compartilha NS sem ser a mesma máquina vira ramo
    lateral. Protocolos do mesmo cliente/pedido aparecem como contexto.
    """
    if not protocol:
        return None

    todos = Protocol.query.order_by(Protocol.entry_date, Protocol.id).all()
    por_id = {p.id: p for p in todos}
    ns_por_id, ns_idx, pedido_idx, cliente_idx = _indice_teia(todos)

    principal = {protocol.id: protocol}
    fila = [protocol]
    arestas = {}
    truncada = False

    while fila:
        atual = fila.pop(0)
        vizinhos = _vizinhos_principais(atual, ns_por_id, ns_idx, por_id)
        for vizinho in vizinhos.values():
            outro = vizinho['protocol']
            if outro.id not in principal:
                if len(principal) >= limite:
                    truncada = True
                    continue
                principal[outro.id] = outro
                fila.append(outro)
            chave = (min(atual.id, outro.id), max(atual.id, outro.id),
                     vizinho['tipo'])
            existente = arestas.get(chave)
            if existente is None:
                arestas[chave] = {
                    'de': atual.id,
                    'para': outro.id,
                    'tipo': vizinho['tipo'],
                    'rotulo': _TEIA_LIGACOES.get(vizinho['tipo'], vizinho['tipo']),
                    'evidencias': list(vizinho['evidencias']),
                }
            else:
                for evidencia in vizinho['evidencias']:
                    if evidencia and evidencia not in existente['evidencias']:
                        existente['evidencias'].append(evidencia)

    principal_lista = sorted(
        principal.values(), key=lambda p: (_data_ordem(p), p.id))
    principal_ids = {p.id for p in principal_lista}

    # --- Ramos laterais: mesmo NS + mesmo tipo, mas outra máquina ----------
    incluidos = dict(principal)
    ramos_por_ancora = {}
    for outro in sorted(todos, key=lambda p: (_data_ordem(p), p.id)):
        if outro.id in incluidos:
            continue
        info_outro = ns_por_id.get(outro.id, {})
        ancoras = []
        for ns, item in info_outro.items():
            for candidato in principal_lista:
                comuns, _ = _comparar_ns(
                    {ns: item}, ns_por_id.get(candidato.id, {}))
                if comuns:
                    ancoras.append((candidato, ns, comuns[0][1]))
        if not ancoras:
            continue
        ancora, ns, tipo_peca = max(
            ancoras, key=lambda t: (_data_ordem(t[0]), t[0].id))
        ramos_por_ancora.setdefault(ancora.id, []).append({
            'protocol': outro,
            'ns': ns,
            'tipo_peca': tipo_peca,
            'motivo': ('mesmo NS' if not _mesmo_contexto(ancora, outro)
                       else 'mesmo equipamento'),
        })
        incluidos[outro.id] = outro

    # --- Contexto: mesmo cliente/pedido, útil para os filtros --------------
    cliente_raiz = _cliente_normalizado(protocol)
    pedidos_raiz = _pedidos_do_protocolo(protocol)
    contexto = []
    for outro in sorted(todos, key=lambda p: (_data_ordem(p), p.id)):
        if outro.id in incluidos:
            continue
        mesmo_cliente = bool(cliente_raiz
                             and _cliente_normalizado(outro) == cliente_raiz)
        mesmo_pedido = bool(pedidos_raiz
                            & _pedidos_do_protocolo(outro))
        if mesmo_cliente or mesmo_pedido:
            contexto.append(outro)
            incluidos[outro.id] = outro

    # --- Flags usadas pelos filtros da tela --------------------------------
    info_raiz = ns_por_id.get(protocol.id, {})
    unidades_raiz = _unidades(info_raiz)
    cadeia_ids = {p.id for p in protocol.get_return_chain()}
    ids_venda_pe = set()
    if protocol.type == 'venda':
        for info in pe_por_maquina(protocol).values():
            if info.get('id'):
                ids_venda_pe.add(info['id'])
    elif protocol.type == 'ponta_entrega':
        for vendas in vendas_por_maquina_pe(protocol).values():
            for venda in vendas:
                if venda.get('id'):
                    ids_venda_pe.add(venda['id'])

    def flags_de(outro, papel):
        info_outro = ns_por_id.get(outro.id, {})
        mesmo_cliente = bool(cliente_raiz
                             and _cliente_normalizado(outro) == cliente_raiz)
        mesmo_pedido = bool(pedidos_raiz
                            & _pedidos_do_protocolo(outro))
        mesmo_equipamento = False
        for ns, item in info_outro.items():
            if _comparar_ns({ns: item}, info_raiz)[0]:
                mesmo_equipamento = True
                break
        mesma_unidade = bool(_unidades(info_outro) & unidades_raiz) and (
            mesmo_cliente or mesmo_pedido)
        return {
            'mesmo_pedido': mesmo_pedido,
            'mesmo_cliente': mesmo_cliente,
            'mesmo_equipamento': mesmo_equipamento,
            'mesma_unidade': mesma_unidade,
            'retorno': outro.id in cadeia_ids,
            'venda_pe': outro.id in ids_venda_pe,
            'principal': outro.id in principal_ids,
            'ramo': papel == 'ramo',
            'contexto': papel == 'contexto',
        }

    principal_nos = [
        _montar_no(p, ns_por_id.get(p.id, {}),
                   flags_de(p, 'principal'), 'principal')
        for p in principal_lista
    ]

    ramos = []
    ramo_ids = set()
    for ancora in principal_lista:
        itens = ramos_por_ancora.get(ancora.id)
        if not itens:
            continue
        nos = []
        for item in itens:
            outro = item['protocol']
            ramo_ids.add(outro.id)
            no = _montar_no(outro, ns_por_id.get(outro.id, {}),
                            flags_de(outro, 'ramo'), 'ramo')
            no['ramo_ns'] = item['ns']
            no['ramo_tipo'] = _tipo_peca_label(item['tipo_peca'])
            no['ramo_motivo'] = item['motivo']
            nos.append(no)
        nos.sort(key=lambda no: (no['data_ordem'], no['id']))
        ramos.append({
            'ancora_id': ancora.id,
            'ancora_numero': ancora.protocol_number,
            'ancora': ancora,
            'nos': nos,
        })

    contexto_nos = [
        _montar_no(p, ns_por_id.get(p.id, {}),
                   flags_de(p, 'contexto'), 'contexto')
        for p in contexto
    ]

    # --- Arestas só da coluna principal ------------------------------------
    arestas_info = []
    for aresta in arestas.values():
        if aresta['de'] not in principal_ids or aresta['para'] not in principal_ids:
            continue
        arestas_info.append({
            'de': aresta['de'],
            'para': aresta['para'],
            'tipo': aresta['tipo'],
            'rotulo': aresta['rotulo'],
            'de_numero': por_id[aresta['de']].protocol_number,
            'para_numero': por_id[aresta['para']].protocol_number,
            'evidencia': ' · '.join(aresta['evidencias']),
            'cor': _TEIA_CORES_ARESTA.get(aresta['tipo'], '#adb5bd'),
        })
    arestas_info.sort(key=lambda a: (a['tipo'], a['de'], a['para']))

    contagem = {}
    for aresta in arestas_info:
        contagem[aresta['tipo']] = contagem.get(aresta['tipo'], 0) + 1

    # --- Conferência: mesmo NS com peça diferente --------------------------
    # A conferência olha só a máquina (coluna principal + ramos), não o
    # contexto do cliente, para não encher a tela com casos de outra máquina.
    lista_maquina = [protocol] + principal_lista
    for ramo in ramos:
        lista_maquina.extend(no['protocol'] for no in ramo['nos'])
    vistos_ids = set()
    lista_maquina_unica = []
    for item in lista_maquina:
        if item.id in vistos_ids:
            continue
        vistos_ids.add(item.id)
        lista_maquina_unica.append(item)

    # Para conferir, traga também quem repete o NS com outro tipo de peça,
    # mesmo sendo de outro cliente/pedido (ex.: FONTE em um, RAM em outro).
    ids_conflito = set(vistos_ids)
    for item in lista_maquina_unica:
        for ns in ns_por_id.get(item.id, {}):
            for outro in ns_idx.get(ns, []):
                ids_conflito.add(outro.id)
    lista_conflito = [por_id[i] for i in sorted(ids_conflito)][:200]

    conflitos = []
    vistos_conflitos = set()
    for indice, a in enumerate(lista_conflito):
        for b in lista_conflito[indice + 1:]:
            _, conf = _comparar_ns(
                ns_por_id.get(a.id, {}), ns_por_id.get(b.id, {}))
            for ns, tipos_a, tipos_b, info_a, info_b in conf:
                chave = (ns, min(a.id, b.id), max(a.id, b.id))
                if chave in vistos_conflitos:
                    continue
                vistos_conflitos.add(chave)
                conflitos.append({
                    'ns': ns,
                    'protocolo_a': a.protocol_number,
                    'protocolo_b': b.protocol_number,
                    'id_a': a.id,
                    'id_b': b.id,
                    'tipos_a': [_tipo_peca_label(t) for t in tipos_a],
                    'tipos_b': [_tipo_peca_label(t) for t in tipos_b],
                    'unidades_a': sorted(info_a['unidades']),
                    'unidades_b': sorted(info_b['unidades']),
                })
    conflitos.sort(key=lambda c: (c['ns'], c['protocolo_a']))

    # --- NS iguais com o mesmo tipo (ligações reais) -----------------------
    ns_comuns_mapa = {}
    for item in lista_maquina_unica:
        info = ns_por_id.get(item.id, {})
        for ns, dados in info.items():
            for tipo in dados['tipos']:
                chave = (ns, tipo)
                entrada = ns_comuns_mapa.setdefault(chave, {
                    'ns': ns,
                    'tipo': _tipo_peca_label(tipo),
                    'protocolos': set(),
                    'ids': set(),
                })
                entrada['protocolos'].add(item.protocol_number)
                entrada['ids'].add(item.id)
    ns_comuns = []
    for chave in sorted(ns_comuns_mapa):
        entrada = ns_comuns_mapa[chave]
        if len(entrada['protocolos']) < 2:
            continue
        ns_comuns.append({
            'ns': entrada['ns'],
            'tipo': entrada['tipo'],
            'protocolos': sorted(entrada['protocolos']),
            'ids': sorted(entrada['ids']),
        })

    # --- Pedidos da coluna principal ---------------------------------------
    pedidos_principais = {}
    for item in principal_lista:
        for pedido in _pedidos_do_protocolo(item):
            pedidos_principais.setdefault(pedido, []).append(item)
    por_pedido = []
    for pedido, itens in sorted(pedidos_principais.items()):
        if len(itens) < 2:
            continue
        por_pedido.append({
            'pedido': pedido,
            'protocolos': [p.protocol_number for p in itens],
            'ids': [p.id for p in itens],
        })
    pedido_conflito = len(pedidos_principais) > 1
    pedidos_principais_lista = sorted(pedidos_principais)

    nodes_info = principal_nos + contexto_nos
    for ramo in ramos:
        nodes_info.extend(ramo['nos'])

    return {
        'raiz': protocol,
        'main': principal_nos,
        'branches': ramos,
        'context': contexto_nos,
        'nodes': nodes_info,
        'edges': arestas_info,
        'ligacoes': _TEIA_LIGACOES,
        'cores': _TEIA_CORES_ARESTA,
        'contagem': contagem,
        'truncada': truncada,
        'total': len(nodes_info),
        'total_principal': len(principal_nos),
        'ns_raiz': sorted(info_raiz),
        'ns_comuns': ns_comuns,
        'conflicts': conflitos,
        'por_pedido': por_pedido,
        'pedido_conflito': pedido_conflito,
        'pedidos_principais': pedidos_principais_lista,
        'ramo_ids': sorted(ramo_ids),
    }


# --- Preenchimento automático da teia -------------------------------------

_CAMPOS_PREENCHIVEIS = [
    ('client_name', 'Cliente', _cliente_valido),
    ('order_number', 'Pedido', _pedido_valido),
    ('original_order', 'Pedido original', _pedido_valido),
    ('seller', 'Vendedor', _vendedor_valido),
    ('lote', 'Quantidade', _lote_valido),
]


def _serial_principal(protocol):
    serial = _primeiro_serial(protocol.rma_test_result)
    if serial:
        return serial
    serial = _primeiro_serial(protocol.rma_trocados)
    if serial:
        return serial
    for componente in protocol.components or []:
        if _ns_limpo(componente.serial_number):
            return componente.serial_number
    return ''


def sugestoes_preenchimento(protocol, teia=None):
    """Sugere completar campos vazios/NIL, passagens e vínculo de retorno."""
    if teia is None:
        teia = teia_do_protocolo(protocol)
    if not teia:
        return {'itens': [], 'conflitos': [], 'principal': []}

    principais = [no['protocol'] for no in teia['main']]
    if protocol.id not in {p.id for p in principais}:
        principais.append(protocol)
    principais.sort(key=lambda p: (_data_ordem(p), p.id))

    itens = []
    conflitos = []

    for alvo in principais:
        for campo, rotulo, valido in _CAMPOS_PREENCHIVEIS:
            # Pedido conflitante não é preenchido no automático: abre o ajuste.
            if (campo in ('order_number', 'original_order')
                    and teia.get('pedido_conflito')):
                continue
            atual = getattr(alvo, campo, None)
            if valido(atual):
                continue
            candidatos = []
            for fonte in principais:
                if fonte.id == alvo.id:
                    continue
                valor = getattr(fonte, campo, None)
                if valido(valor):
                    candidatos.append((fonte, _texto_limpo(valor)))
            if not candidatos:
                continue
            distintos = {}
            for fonte, valor in candidatos:
                distintos.setdefault(valor.upper(), []).append((fonte, valor))
            if len(distintos) > 1:
                conflitos.append({
                    'protocolo_id': alvo.id,
                    'protocolo_numero': alvo.protocol_number,
                    'campo': campo,
                    'campo_label': rotulo,
                    'opcoes': [
                        {'valor': lista[0][1],
                         'protocolo': lista[0][0].protocol_number}
                        for lista in distintos.values()
                    ],
                })
                if campo == 'original_order':
                    # Pedido original precisa ser único na corrente.
                    continue
            fonte, valor = max(
                candidatos, key=lambda par: (_data_ordem(par[0]), par[0].id))
            itens.append({
                'protocolo_id': alvo.id,
                'protocolo_numero': alvo.protocol_number,
                'campo': campo,
                'campo_label': rotulo,
                'valor_atual': _texto_limpo(atual),
                'valor_novo': valor,
                'origem_numero': fonte.protocol_number,
                'tipo': 'campo',
                'descricao': (
                    f"{alvo.protocol_number}: {rotulo} "
                    f"{_texto_limpo(atual) or '(vazio)'} → {valor} "
                    f"(de {fonte.protocol_number})"),
            })

    # --- Passagens nos protocolos de retorno ------------------------------
    alvo_passagem = max(principais, key=lambda p: (_data_ordem(p), p.id))
    info_por_id = {p.id: ns_do_protocolo(p) for p in principais}

    def _origem_provavel(alvo):
        if alvo.type not in ('rma', 'servico'):
            return None
        anteriores = [
            p for p in principais
            if p.id != alvo.id
            and p.type in ('rma', 'servico')
            and (_data_ordem(p), p.id) < (_data_ordem(alvo), alvo.id)
        ]
        candidatos = []
        for fonte in anteriores:
            comuns, _ = _comparar_ns(
                info_por_id.get(alvo.id, {}), info_por_id.get(fonte.id, {}))
            if comuns and _mesmo_contexto(alvo, fonte):
                candidatos.append(fonte)
        if not candidatos:
            return None
        return max(candidatos, key=lambda p: (_data_ordem(p), p.id))

    for alvo in principais:
        if alvo.type not in ('rma', 'servico'):
            continue
        anteriores = [
            p for p in principais
            if (_data_ordem(p), p.id) < (_data_ordem(alvo), alvo.id)
        ]
        if not anteriores:
            continue
        provavel = _origem_provavel(alvo)
        eh_mais_novo = alvo.id == alvo_passagem.id
        # O mais novo recebe todo o histórico; os retornos do meio recebem
        # apenas a passagem do seu provável protocolo de origem.
        fontes = anteriores if eh_mais_novo else (
            [provavel] if provavel else [])
        passagens_atuais = _json_ou(alvo.rma_passagens, [])
        if not isinstance(passagens_atuais, list):
            passagens_atuais = []
        existentes = {
            str(pas.get('protocolo'))
            for pas in passagens_atuais if isinstance(pas, dict)
        }
        for fonte in fontes:
            if fonte is None or fonte.id == alvo.id:
                continue
            if fonte.protocol_number in existentes:
                continue
            tem_historico = bool(
                fonte.rma_test_result or fonte.rma_trocados
                or fonte.type in ('rma', 'servico', 'nao_comprado'))
            if not tem_historico:
                continue
            direta = bool(alvo.origin_id and fonte.id == alvo.origin_id)
            if not alvo.origin_id and provavel is not None:
                direta = fonte.id == provavel.id
            passagem = {
                'protocolo': fonte.protocol_number,
                'ns': _primeiro_serial(fonte.rma_test_result),
                'ns_novo': _primeiro_serial(fonte.rma_trocados),
                'pedido': fonte.original_order or fonte.order_number or '',
                'data_entrada': _data_br(fonte.rma_entry_date or fonte.entry_date),
                'data_saida': _data_br(fonte.exit_date),
                'outra': not direta,
            }
            itens.append({
                'protocolo_id': alvo.id,
                'protocolo_numero': alvo.protocol_number,
                'campo': 'passagem',
                'campo_label': 'Passagem',
                'valor_atual': '',
                'valor_novo': fonte.protocol_number,
                'origem_numero': fonte.protocol_number,
                'tipo': 'passagem',
                'passagem': passagem,
                'descricao': (
                    f"{alvo.protocol_number}: registrar passagem de "
                    f"{fonte.protocol_number}"
                    + ('' if direta else ' como outra passagem')),
            })

    # --- Vínculo de retorno (RMA que voltou de outro RMA) -----------------
    for alvo in principais:
        if alvo.type not in ('rma', 'servico') or alvo.origin_id:
            continue
        anteriores = [
            p for p in principais
            if p.id != alvo.id
            and p.type in ('rma', 'servico')
            and (_data_ordem(p), p.id) < (_data_ordem(alvo), alvo.id)
        ]
        candidatos = []
        for fonte in anteriores:
            comuns, _ = _comparar_ns(
                info_por_id.get(alvo.id, {}), info_por_id.get(fonte.id, {}))
            if not comuns:
                continue
            if not _mesmo_contexto(alvo, fonte):
                continue
            candidatos.append(fonte)
        if not candidatos:
            continue
        fonte = max(candidatos, key=lambda p: (_data_ordem(p), p.id))
        itens.append({
            'protocolo_id': alvo.id,
            'protocolo_numero': alvo.protocol_number,
            'campo': 'origin_id',
            'campo_label': 'Vínculo de retorno',
            'valor_atual': '',
            'valor_novo': fonte.id,
            'origem_numero': fonte.protocol_number,
            'tipo': 'origem',
            'descricao': (
                f"{alvo.protocol_number}: marcar como retorno de "
                f"{fonte.protocol_number}"),
        })

    return {
        'itens': itens,
        'conflitos': conflitos,
        'principal': principais,
        'alvo_passagem': alvo_passagem,
    }


def _pasta_backup():
    if current_app.config.get('TESTING'):
        pasta = os.path.join(tempfile.gettempdir(), 'labtrack-test-backups')
    else:
        pasta = os.path.abspath(os.path.join(
            current_app.root_path, '..', '_dev', 'backups'))
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _backup_antes_preenchimento():
    caminho = db.engine.url.database
    if not caminho or caminho == ':memory:':
        return None
    if not os.path.exists(caminho):
        return None
    pasta = _pasta_backup()
    agora = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    destino = os.path.join(
        pasta, f'labtrack-{agora}-antes-preenchimento-teia.db')
    shutil.copy2(caminho, destino)
    return destino


def aplicar_preenchimento(protocol, indices):
    """Aplica somente as sugestões escolhidas. Sempre faz backup antes."""
    teia = teia_do_protocolo(protocol)
    pacote = sugestoes_preenchimento(protocol, teia)
    itens = pacote['itens']

    selecionados = []
    for indice in indices:
        try:
            selecionados.append(itens[int(indice)])
        except (TypeError, ValueError, IndexError):
            continue
    if not selecionados:
        return {'alterados': [], 'backup': None, 'log': None}

    backup = _backup_antes_preenchimento()
    alterados = []

    for item in selecionados:
        alvo = db.session.get(Protocol, item['protocolo_id'])
        if not alvo:
            continue
        campo = item['campo']

        if campo == 'passagem':
            passagens = _json_ou(alvo.rma_passagens, [])
            if not isinstance(passagens, list):
                passagens = []
            nova = item.get('passagem') or {}
            numero = str(nova.get('protocolo') or '')
            if not numero:
                continue
            if any(str(pas.get('protocolo')) == numero
                   for pas in passagens if isinstance(pas, dict)):
                continue
            passagens.append(nova)
            alvo.rma_passagens = json.dumps(passagens, ensure_ascii=False)
            alterados.append({
                'protocolo': alvo.protocol_number,
                'campo': 'passagem',
                'valor_novo': numero,
            })
            continue

        if campo == 'origin_id':
            if alvo.origin_id:
                continue
            try:
                alvo.origin_id = int(item['valor_novo'])
            except (TypeError, ValueError):
                continue
            alterados.append({
                'protocolo': alvo.protocol_number,
                'campo': 'origin_id',
                'valor_novo': alvo.origin_id,
            })
            continue

        validador = next(
            (valido for nome, _, valido in _CAMPOS_PREENCHIVEIS
             if nome == campo), None)
        if validador is None:
            continue
        if validador(getattr(alvo, campo, None)):
            continue
        valor = _texto_limpo(item.get('valor_novo'))
        if not valor:
            continue
        anterior = _texto_limpo(getattr(alvo, campo, None))
        setattr(alvo, campo, valor)
        alterados.append({
            'protocolo': alvo.protocol_number,
            'campo': campo,
            'valor_atual': anterior,
            'valor_novo': valor,
        })

    if not alterados:
        db.session.rollback()
        return {'alterados': [], 'backup': backup, 'log': None}

    db.session.commit()

    log = None
    if backup:
        log = os.path.splitext(backup)[0] + '.json'
        try:
            with open(log, 'w', encoding='utf-8') as arquivo:
                json.dump({
                    'data': datetime.utcnow().isoformat(),
                    'protocolo': protocol.protocol_number,
                    'backup': backup,
                    'alteracoes': alterados,
                }, arquivo, ensure_ascii=False, indent=2)
        except OSError:
            log = None

    return {'alterados': alterados, 'backup': backup, 'log': log}
