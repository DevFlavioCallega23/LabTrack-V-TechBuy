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
from app.models import Protocol, Component, Defect, WindowsKey, EstoqueUso

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


def maquinas_pronta_entrega_para_home(incluir_estoque=True):
    """Lista todas as máquinas de Pronta-Entrega para a visão geral da Home.

    Cada item traz a unidade, os componentes, a fonte (NS), as vendas ativas
    ligadas àquela máquina e, opcionalmente, se algum NS dela aparece no Uso
    do Estoque. A disponibilidade segue a mesma regra da tela do protocolo:
    uma máquina está disponível quando não há venda ativa ligada a ela.
    """
    # Vendas ativas por (protocolo da PE, unidade), calculadas de uma vez.
    vendas_por_unidade = {}
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
            unit = _unidade(info.get('unit'))
            vendas_por_unidade.setdefault((pe_id, unit), []).append({
                'id': venda.id,
                'protocol_number': venda.protocol_number,
                'client_name': venda.client_name or '',
                'date': venda.entry_date or venda.created_at,
            })

    # Índice dos NS do Uso do Estoque. Guarda o texto normalizado e os
    # dígitos, para casar do mesmo jeito que o ns_bate().
    estoque_por_texto = {}
    estoque_por_digito = {}
    if incluir_estoque:
        for item in EstoqueUso.query.order_by(EstoqueUso.id).all():
            seriais = [item.ns] + [c.serial_number for c in item.components]
            for serial in seriais:
                chave = normalizar_ns(serial)
                if not chave:
                    continue
                estoque_por_texto.setdefault(chave, item.id)
                digitos = _somente_digitos(chave)
                if len(digitos) >= 4:
                    estoque_por_digito.setdefault(digitos.lstrip('0'), item.id)

    def estoque_da_maquina(comps):
        if not incluir_estoque:
            return None
        for c in comps:
            chave = normalizar_ns(c.serial_number)
            if not chave:
                continue
            if chave in estoque_por_texto:
                return estoque_por_texto[chave]
            digitos = _somente_digitos(chave)
            if len(digitos) >= 4:
                achado = estoque_por_digito.get(digitos.lstrip('0'))
                if achado:
                    return achado
        return None

    resultado = []
    for pe in Protocol.query.filter_by(type='ponta_entrega').order_by(Protocol.id).all():
        unidades = {}
        for c in pe.components:
            unidades.setdefault(_unidade(c.unit), []).append(c)
        for unit in sorted(unidades, key=_ordem_unidade):
            comps = sorted(unidades[unit], key=lambda c: (c.sort_order or 0))
            fonte = next((c.serial_number for c in comps
                          if c.component_type == 'fonte' and c.serial_number), '')
            nome = next((c.machine_name for c in comps if c.machine_name), '')
            vendas = vendas_por_unidade.get((pe.id, unit), [])
            estoque_id = estoque_da_maquina(comps)
            data = pe.entry_date or pe.created_at
            resultado.append({
                'protocol_id': pe.id,
                'protocol_number': pe.protocol_number,
                'unit': unit,
                'machine_name': nome,
                'fonte': fonte,
                'components': [{
                    'type': c.component_type or '',
                    'label': COMPONENT_LABELS.get(c.component_type, c.component_type or ''),
                    'model': c.specification or '',
                    'serial': c.serial_number or '',
                } for c in comps if c.component_type],
                'entry_date': data,
                'disponivel': not vendas,
                'vendas': vendas,
                'estoque_id': estoque_id,
                'estoque_registrado': bool(estoque_id),
            })
    return resultado


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


def _unidade_da_maquina(maquina):
    """Tenta descobrir a unidade pelo nome da máquina ('Computador 01' -> '01')."""
    texto = _texto_limpo(maquina)
    achado = re.search(r'(\d+)\s*$', texto)
    return _unidade(achado.group(1)) if achado else ''


def _coletar_ns(protocol, por_unidade=None):
    """NS do protocolo com tipo, unidade, máquina, modelo e origem.

    Quando ``por_unidade`` é passado, também preenche
    ``{unidade: {'nome': ..., 'ns': {...}}}`` para a teia por máquina.
    """
    info = {}

    def adicionar(valor, tipo='peca', unidade='', maquina='', fonte='', modelo=''):
        ns = _ns_limpo(valor)
        if not ns:
            return
        unidade_txt = _texto_limpo(unidade)
        maquina_txt = _texto_limpo(maquina)
        modelo_txt = _texto_limpo(modelo)
        unidade_final = (_unidade(unidade_txt) if unidade_txt
                         else _unidade_da_maquina(maquina_txt))
        tipo_final = _tipo_peca(tipo)

        def preencher(item):
            item['tipos'].add(tipo_final)
            if unidade_final:
                item['unidades'].add(unidade_final)
            if maquina_txt:
                item['maquinas'].add(maquina_txt)
            if modelo_txt:
                item['modelos'].add(modelo_txt)
            if fonte:
                item['fontes'].add(fonte)

        item = info.setdefault(ns, {
            'tipos': set(), 'unidades': set(), 'maquinas': set(),
            'modelos': set(), 'fontes': set(),
        })
        preencher(item)

        if por_unidade is not None:
            entrada = por_unidade.setdefault(
                unidade_final, {'nome': '', 'ns': {}})
            if maquina_txt and not entrada['nome']:
                entrada['nome'] = maquina_txt
            item_unidade = entrada['ns'].setdefault(ns, {
                'tipos': set(), 'unidades': set(), 'maquinas': set(),
                'modelos': set(), 'fontes': set(),
            })
            preencher(item_unidade)

    for componente in protocol.components or []:
        adicionar(componente.serial_number, componente.component_type,
                  componente.unit, componente.machine_name, 'componente',
                  componente.specification)
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
                          entrada.get('name'), 'equipamento',
                          componente.get('model'))

    for item in _json_ou(protocol.rma_test_result, []) or []:
        if not isinstance(item, dict):
            continue
        adicionar(item.get('serial'), item.get('component'),
                  item.get('unit'), item.get('machine'), 'teste',
                  item.get('model'))
        for componente in item.get('components') or []:
            if isinstance(componente, dict):
                adicionar(componente.get('serial'),
                          componente.get('type') or componente.get('component'),
                          componente.get('unit'), item.get('machine'), 'teste',
                          componente.get('model') or item.get('model'))

    for unidade, entrada in _equip_entradas(_json_ou(protocol.rma_trocados, {})):
        for componente in entrada.get('components') or []:
            if isinstance(componente, dict):
                adicionar(componente.get('serial'), componente.get('type'),
                          unidade or componente.get('unit'),
                          entrada.get('name'), 'trocado',
                          componente.get('model'))

    for defeito in protocol.defects or []:
        adicionar(defeito.serial_number, defeito.component_type,
                  '', defeito.maquina, 'defeito', defeito.specification)

    adicionar(protocol.ref_ns, 'ref', '', '', 'ref')
    adicionar(protocol.rma_test_serial, 'ref', '', '', 'ref')
    return info


def ns_do_protocolo(protocol):
    """NS do protocolo com o tipo da peça e a unidade onde apareceu."""
    return _coletar_ns(protocol)


def ns_por_unidade(protocol):
    """NS separados por unidade/máquina: {unidade: {'nome': ..., 'ns': {...}}}."""
    por_unidade = {}
    _coletar_ns(protocol, por_unidade)
    return por_unidade


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
    unidades_por_id = {}
    ns_idx = {}
    pedido_idx = {}
    cliente_idx = {}
    for protocolo in todos:
        por_unidade = {}
        info = _coletar_ns(protocolo, por_unidade)
        ns_por_id[protocolo.id] = info
        unidades_por_id[protocolo.id] = por_unidade
        for valor in info:
            ns_idx.setdefault(valor, []).append(protocolo)
        for pedido in _pedidos_do_protocolo(protocolo):
            pedido_idx.setdefault(pedido, []).append(protocolo)
        cliente = _cliente_normalizado(protocolo)
        if cliente:
            cliente_idx.setdefault(cliente, []).append(protocolo)
    return ns_por_id, ns_idx, pedido_idx, cliente_idx, unidades_por_id


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


def _ordem_unidade(unidade):
    """Ordena 01, 02, ..., 10, depois nomes e por último 'sem unidade'."""
    texto = _texto_limpo(unidade)
    if texto.isdigit():
        return (0, int(texto), '')
    if texto:
        return (1, 0, texto)
    return (2, 0, '')


def _label_unidade(unidade, nome=''):
    texto = _texto_limpo(unidade)
    nome = _texto_limpo(nome)
    if nome:
        return nome
    if texto:
        return f'Máquina {texto}'
    return 'Sem unidade'


def _label_da_unidade(protocol, unidade, unidades_por_id):
    entrada = (unidades_por_id.get(protocol.id) or {}).get(unidade) or {}
    return _label_unidade(unidade, entrada.get('nome') or '')


def _info_da_unidade(protocol, unidade, unidades_por_id, ns_por_id):
    """NS que pertencem a uma máquina específica do protocolo."""
    por_unidade = unidades_por_id.get(protocol.id) or {}
    unidade = _texto_limpo(unidade)
    if unidade in por_unidade:
        return por_unidade[unidade]['ns']
    if not unidade:
        entrada = por_unidade.get('')
        if entrada:
            return entrada['ns']
        if not por_unidade:
            return ns_por_id.get(protocol.id, {})
    return {}


def _melhor_unidade(por_unidade, info_atual):
    """Unidade do outro protocolo que mais combina (NS + tipo) com a atual."""
    melhor = None
    melhor_qtd = 0
    for unidade, entrada in (por_unidade or {}).items():
        comuns, _ = _comparar_ns(info_atual, entrada.get('ns') or {})
        qtd = len(comuns)
        if qtd > melhor_qtd:
            melhor = unidade
            melhor_qtd = qtd
        elif qtd and qtd == melhor_qtd and _ordem_unidade(unidade) < _ordem_unidade(melhor):
            melhor = unidade
    return melhor if melhor_qtd else None


def _unidade_do_vinculo(outro, info_atual, unidade_atual, unidades_por_id):
    """Unidade do outro protocolo que representa a mesma máquina."""
    por_unidade = unidades_por_id.get(outro.id) or {}
    melhor = _melhor_unidade(por_unidade, info_atual)
    if melhor is not None:
        return melhor
    if unidade_atual in por_unidade:
        return unidade_atual
    return ''


def _unidade_da_venda_na_pe(venda, pe, pe_unidade):
    """Descobre a unidade da Venda que aponta para a máquina da PE."""
    for venda_unidade, info in (venda.get_pe_refs() or {}).items():
        if not isinstance(info, dict):
            continue
        try:
            pe_id = int(info.get('protocol_id'))
        except (TypeError, ValueError):
            continue
        if pe_id == pe.id and _unidade(info.get('unit')) == _unidade(pe_unidade):
            return _unidade(venda_unidade)
    return ''


def _venda_pe_vizinhos(atual, unidade, por_id):
    """Pares Venda ↔ PE que pertencem à máquina selecionada."""
    if atual.type == 'venda':
        mapa = pe_por_maquina(atual)
        if unidade in mapa:
            pares = [(unidade, [mapa[unidade]])]
        elif not unidade and len(mapa) == 1:
            pares = [(chave, [info]) for chave, info in mapa.items()]
        else:
            pares = []
        for chave, itens in pares:
            for info in itens:
                pe = por_id.get(info.get('id'))
                if pe:
                    yield pe, info.get('unit') or '', (
                        f"Máquina {chave or '?'} · fonte "
                        f"{info.get('fonte') or 'sem NS'}")
    elif atual.type == 'ponta_entrega':
        mapa = vendas_por_maquina_pe(atual)
        if unidade in mapa:
            pares = [(unidade, mapa[unidade])]
        elif not unidade and len(mapa) == 1:
            pares = list(mapa.items())
        else:
            pares = []
        for pe_unidade, itens in pares:
            for info in itens:
                venda = por_id.get(info.get('id'))
                if not venda:
                    continue
                venda_unidade = _unidade_da_venda_na_pe(
                    venda, atual, pe_unidade)
                yield venda, venda_unidade, (
                    f"Máquina {pe_unidade or '?'} · fonte "
                    f"{info.get('fonte') or 'sem NS'}")


def _vizinhos_da_maquina(atual, unidade, ns_por_id, ns_idx,
                        unidades_por_id, por_id):
    """Vizinhos da máquina: retorno, mesmo NS + tipo e Venda ↔ PE."""
    achados = {}

    def adicionar(outro, unidade_outro, tipo, evidencia):
        if not outro or outro.id == atual.id:
            return
        chave = (outro.id, unidade_outro or '')
        existente = achados.get(chave)
        if existente is None:
            achados[chave] = {
                'protocol': outro,
                'unidade': unidade_outro or '',
                'tipo': tipo,
                'evidencias': [evidencia] if evidencia else [],
            }
        elif evidencia and evidencia not in existente['evidencias']:
            existente['evidencias'].append(evidencia)

    info_atual = _info_da_unidade(atual, unidade, unidades_por_id, ns_por_id)

    origem = atual.get_origin()
    if origem:
        adicionar(
            origem,
            _unidade_do_vinculo(origem, info_atual, unidade, unidades_por_id),
            'retorno', f'Retorno de {atual.protocol_number}')
    for retorno in atual.get_returns():
        adicionar(
            retorno,
            _unidade_do_vinculo(retorno, info_atual, unidade, unidades_por_id),
            'retorno', f'Gerou {retorno.protocol_number}')

    for ns, item in info_atual.items():
        for outro in ns_idx.get(ns, []):
            if outro.id == atual.id:
                continue
            unidade_outro = _melhor_unidade(
                unidades_por_id.get(outro.id) or {}, {ns: item})
            if unidade_outro is None:
                continue
            if not _mesmo_contexto(atual, outro):
                continue
            tipo_peca = sorted(item['tipos'])[0]
            adicionar(outro, unidade_outro, 'equipamento',
                      f'NS {ns} · {_tipo_peca_label(tipo_peca)}')

    for outro, unidade_outro, evidencia in _venda_pe_vizinhos(
            atual, unidade, por_id):
        adicionar(outro, unidade_outro, 'venda_pe', evidencia)

    return achados


def _ns_detalhe(info_ns):
    detalhe = []
    for ns in sorted(info_ns):
        item = info_ns[ns]
        tipos = sorted(item['tipos'])
        modelos = sorted(item.get('modelos') or [])
        detalhe.append({
            'ns': ns,
            'tipos': tipos,
            'tipos_label': ', '.join(_tipo_peca_label(t) for t in tipos),
            'unidades': sorted(item['unidades'], key=_ordem_unidade),
            'maquinas': sorted(item['maquinas']),
            'modelos': modelos,
            'modelos_label': ', '.join(modelos),
        })
    return detalhe


def _montar_no(protocol, info_ns, flags=None, papel='', unidade='',
               unidade_label=''):
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
        'unidade': unidade or '',
        'unidade_label': unidade_label or _label_unidade(unidade),
        'ns': sorted(info_ns),
        'ns_detalhe': _ns_detalhe(info_ns),
        'info_ns': info_ns,
        'pedidos': pedidos,
        'pedido': pedidos[0] if pedidos else '',
        'cliente': _texto_limpo(protocol.client_name),
        'retorno_label': protocol.return_label() or '',
        'flags': flags or {},
        'papel': papel,
    }


def teia_do_protocolo(protocol, limite=60, unidade=None):
    """Linha do tempo de uma máquina por vez, com ramos laterais e contexto.

    A máquina é escolhida pelo parâmetro ``unidade``. Quando ele não é
    informado, abre na máquina com mais ligações com outros protocolos.
    """
    if not protocol:
        return None

    todos = Protocol.query.order_by(Protocol.entry_date, Protocol.id).all()
    por_id = {p.id: p for p in todos}
    ns_por_id, ns_idx, pedido_idx, cliente_idx, unidades_por_id = _indice_teia(todos)

    unidades_raiz = unidades_por_id.get(protocol.id) or {}
    if not unidades_raiz:
        unidades_raiz = {'': {'nome': '', 'ns': {}}}

    # --- Escolha da máquina: a que tem mais ligações com outros protocolos --
    # Mesmo pedido pesa mais que só o mesmo cliente, e RMA/Serviço pesa mais
    # que outra Venda, para abrir direto na máquina do caso em andamento.
    ligacoes_por_unidade = {}
    peso_por_unidade = {}
    for chave_unidade in unidades_raiz:
        info_u = _info_da_unidade(
            protocol, chave_unidade, unidades_por_id, ns_por_id)
        outros = {}
        for ns, item in info_u.items():
            for outro in ns_idx.get(ns, []):
                if outro.id == protocol.id:
                    continue
                comuns, _ = _comparar_ns(
                    {ns: item}, ns_por_id.get(outro.id, {}))
                if not comuns:
                    continue
                pontos = 1
                if (_pedidos_do_protocolo(protocol)
                        & _pedidos_do_protocolo(outro)):
                    pontos += 2
                if outro.type in ('rma', 'servico'):
                    pontos += 1
                outros[outro.id] = max(outros.get(outro.id, 0), pontos)
        ligacoes_por_unidade[chave_unidade] = len(outros)
        peso_por_unidade[chave_unidade] = sum(outros.values())

    ordem = sorted(
        unidades_raiz,
        key=lambda u: (-peso_por_unidade.get(u, 0),
                       -ligacoes_por_unidade.get(u, 0),
                       -len((unidades_raiz[u] or {}).get('ns') or {}),
                       _ordem_unidade(u)))
    if unidade is None:
        unidade_selecionada = ordem[0] if ordem else ''
    else:
        unidade_selecionada = _texto_limpo(unidade)
        if unidade_selecionada not in unidades_raiz:
            unidade_selecionada = ordem[0] if ordem else ''

    unidades = []
    for chave_unidade in sorted(unidades_raiz, key=_ordem_unidade):
        entrada = unidades_raiz[chave_unidade] or {}
        info_u = entrada.get('ns') or {}
        unidades.append({
            'unidade': chave_unidade,
            'valor': chave_unidade or 'sem',
            'label': _label_unidade(chave_unidade, entrada.get('nome') or ''),
            'ns': len(info_u),
            'ligacoes': ligacoes_por_unidade.get(chave_unidade, 0),
            'selecionada': chave_unidade == unidade_selecionada,
        })
    unidade_label = _label_da_unidade(
        protocol, unidade_selecionada, unidades_por_id)

    # --- Coluna principal: a máquina selecionada e seus vizinhos -----------
    selecionados = {(protocol.id, unidade_selecionada or ''): protocol}
    fila = [(protocol, unidade_selecionada or '')]
    arestas = {}
    truncada = False

    while fila:
        atual, unidade_atual = fila.pop(0)
        vizinhos = _vizinhos_da_maquina(
            atual, unidade_atual, ns_por_id, ns_idx,
            unidades_por_id, por_id)
        for (outro_id, unidade_outro), vizinho in vizinhos.items():
            outro = vizinho['protocol']
            chave_no = (outro.id, unidade_outro or '')
            if chave_no not in selecionados:
                if len(selecionados) >= limite:
                    truncada = True
                    continue
                selecionados[chave_no] = outro
                fila.append((outro, unidade_outro or ''))
            de = (atual.id, unidade_atual or '')
            para = (outro.id, unidade_outro or '')
            chave_aresta = (min(de, para), max(de, para), vizinho['tipo'])
            existente = arestas.get(chave_aresta)
            if existente is None:
                arestas[chave_aresta] = {
                    'de': de,
                    'para': para,
                    'tipo': vizinho['tipo'],
                    'rotulo': _TEIA_LIGACOES.get(
                        vizinho['tipo'], vizinho['tipo']),
                    'evidencias': list(vizinho['evidencias']),
                }
            else:
                for evidencia in vizinho['evidencias']:
                    if evidencia and evidencia not in existente['evidencias']:
                        existente['evidencias'].append(evidencia)

    principal_itens = list(selecionados.items())
    principal_itens.sort(
        key=lambda item: (_data_ordem(item[1]), item[1].id,
                          _ordem_unidade(item[0][1])))
    chaves_principal = set(selecionados)

    # --- Ramos laterais: mesmo NS + tipo, mas outra máquina ----------------
    ramos_por_ancora = {}
    ramo_ids = set()
    for outro in sorted(todos, key=lambda p: (_data_ordem(p), p.id)):
        if any(pid == outro.id for pid, _ in selecionados):
            continue
        por_unidade_outro = unidades_por_id.get(outro.id) or {}
        ancoras = []
        for (pid, unidade_atual), atual in selecionados.items():
            info_atual = _info_da_unidade(
                atual, unidade_atual, unidades_por_id, ns_por_id)
            for ns, item in info_atual.items():
                unidade_outro = _melhor_unidade(
                    por_unidade_outro, {ns: item})
                if unidade_outro is None:
                    continue
                ancoras.append((atual, unidade_atual, unidade_outro, ns,
                                sorted(item['tipos'])[0]))
        if not ancoras:
            continue
        ancora, unidade_atual, unidade_outro, ns, tipo_peca = max(
            ancoras, key=lambda t: (_data_ordem(t[0]), t[0].id))
        chave_ancora = (ancora.id, unidade_atual or '')
        ramos_por_ancora.setdefault(chave_ancora, []).append({
            'protocol': outro,
            'unidade': unidade_outro or '',
            'ns': ns,
            'tipo_peca': tipo_peca,
            'motivo': ('mesmo NS' if not _mesmo_contexto(ancora, outro)
                       else 'mesmo equipamento'),
        })
        ramo_ids.add(outro.id)

    # --- Contexto: mesmo cliente/pedido, sem vínculo com a máquina ---------
    cliente_raiz = _cliente_normalizado(protocol)
    pedidos_raiz = _pedidos_do_protocolo(protocol)
    ids_incluidos = {pid for pid, _ in selecionados} | ramo_ids
    contexto = []
    for outro in sorted(todos, key=lambda p: (_data_ordem(p), p.id)):
        if outro.id in ids_incluidos:
            continue
        mesmo_cliente = bool(
            cliente_raiz and _cliente_normalizado(outro) == cliente_raiz)
        mesmo_pedido = bool(
            pedidos_raiz & _pedidos_do_protocolo(outro))
        if mesmo_cliente or mesmo_pedido:
            contexto.append(outro)

    # --- Flags usadas pelos filtros e pelos cartões ------------------------
    info_raiz = _info_da_unidade(
        protocol, unidade_selecionada, unidades_por_id, ns_por_id)
    unidades_raiz_info = _unidades(info_raiz)
    cadeia_ids = {p.id for p in protocol.get_return_chain()}
    ids_venda_pe = set()
    for aresta in arestas.values():
        if aresta['tipo'] == 'venda_pe':
            ids_venda_pe.add(aresta['de'][0])
            ids_venda_pe.add(aresta['para'][0])

    def flags_de(outro, papel, info_no, unidade_no=''):
        mesmo_cliente = bool(
            cliente_raiz and _cliente_normalizado(outro) == cliente_raiz)
        mesmo_pedido = bool(
            pedidos_raiz & _pedidos_do_protocolo(outro))
        mesmo_equipamento = False
        for ns, item in (info_no or {}).items():
            if _comparar_ns({ns: item}, info_raiz)[0]:
                mesmo_equipamento = True
                break
        mesma_unidade = bool(
            _unidades(info_no or {}) & unidades_raiz_info
            and (mesmo_cliente or mesmo_pedido))
        return {
            'mesmo_pedido': mesmo_pedido,
            'mesmo_cliente': mesmo_cliente,
            'mesmo_cliente_pedido': bool(mesmo_cliente and mesmo_pedido),
            'mesmo_equipamento': mesmo_equipamento,
            'mesma_unidade': mesma_unidade,
            'retorno': outro.id in cadeia_ids,
            'venda_pe': outro.id in ids_venda_pe,
            'principal': papel == 'principal',
            'ramo': papel == 'ramo',
            'contexto': papel == 'contexto',
        }

    principal_nos = []
    for (pid, unidade_no), p in principal_itens:
        info_no = _info_da_unidade(
            p, unidade_no, unidades_por_id, ns_por_id)
        principal_nos.append(_montar_no(
            p, info_no, flags_de(p, 'principal', info_no, unidade_no),
            'principal', unidade_no,
            _label_da_unidade(p, unidade_no, unidades_por_id)))

    ramos = []
    for ancora in principal_nos:
        itens = ramos_por_ancora.get((ancora['id'], ancora['unidade']))
        if not itens:
            continue
        nos = []
        for item in itens:
            outro = item['protocol']
            unidade_outro = item['unidade']
            info_outro = _info_da_unidade(
                outro, unidade_outro, unidades_por_id, ns_por_id)
            no = _montar_no(
                outro, info_outro,
                flags_de(outro, 'ramo', info_outro, unidade_outro),
                'ramo', unidade_outro,
                _label_da_unidade(outro, unidade_outro, unidades_por_id))
            no['ramo_ns'] = item['ns']
            no['ramo_tipo'] = _tipo_peca_label(item['tipo_peca'])
            no['ramo_motivo'] = item['motivo']
            nos.append(no)
        nos.sort(key=lambda no: (no['data_ordem'], no['id'],
                                 _ordem_unidade(no['unidade'])))
        ramos.append({
            'ancora_id': ancora['id'],
            'ancora_unidade': ancora['unidade'],
            'ancora_numero': ancora['numero'],
            'ancora': ancora['protocol'],
            'nos': nos,
        })

    contexto_nos = []
    for p in contexto:
        info_p = ns_por_id.get(p.id, {})
        contexto_nos.append(_montar_no(
            p, info_p, flags_de(p, 'contexto', info_p), 'contexto'))

    grupos_contexto = {}
    for no in contexto_nos:
        grupos_contexto.setdefault(no['tipo'], []).append(no)
    context_tipos = []
    for tipo in sorted(
            grupos_contexto,
            key=lambda t: (PROTO_TYPE_LABELS.get(t, t), t)):
        itens = grupos_contexto[tipo]
        itens.sort(key=lambda no: (no['data_ordem'], no['id']))
        context_tipos.append({
            'tipo': tipo,
            'label': PROTO_TYPE_LABELS.get(tipo, tipo),
            'badge': itens[0]['protocol'].type_badge() or 'bg-secondary',
            'protocolos': itens,
        })

    # --- Arestas só da coluna principal ------------------------------------
    arestas_info = []
    for aresta in arestas.values():
        if (aresta['de'] not in chaves_principal
                or aresta['para'] not in chaves_principal):
            continue
        de_protocol = por_id[aresta['de'][0]]
        para_protocol = por_id[aresta['para'][0]]
        arestas_info.append({
            'de': aresta['de'][0],
            'para': aresta['para'][0],
            'de_unidade': aresta['de'][1],
            'para_unidade': aresta['para'][1],
            'de_label': _label_da_unidade(
                de_protocol, aresta['de'][1], unidades_por_id),
            'para_label': _label_da_unidade(
                para_protocol, aresta['para'][1], unidades_por_id),
            'tipo': aresta['tipo'],
            'rotulo': aresta['rotulo'],
            'de_numero': de_protocol.protocol_number,
            'para_numero': para_protocol.protocol_number,
            'evidencia': ' · '.join(aresta['evidencias']),
            'cor': _TEIA_CORES_ARESTA.get(aresta['tipo'], '#adb5bd'),
        })
    arestas_info.sort(
        key=lambda a: (a['tipo'], a['de'], a['para'],
                       _ordem_unidade(a['de_unidade']),
                       _ordem_unidade(a['para_unidade'])))

    contagem = {}
    for aresta in arestas_info:
        contagem[aresta['tipo']] = contagem.get(aresta['tipo'], 0) + 1

    # --- Conferência: mesmo NS com peça diferente --------------------------
    info_maquina = {}
    for (pid, unidade_no), p in principal_itens:
        info_maquina[(pid, unidade_no or '')] = _info_da_unidade(
            p, unidade_no, unidades_por_id, ns_por_id)
    for ramo in ramos:
        for no in ramo['nos']:
            info_maquina[(no['id'], no['unidade'] or '')] = no['info_ns']

    ids_conflito = {pid for pid, _ in info_maquina}
    for info_no in info_maquina.values():
        for ns in info_no:
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
                    'unidades_a': sorted(
                        info_a['unidades'], key=_ordem_unidade),
                    'unidades_b': sorted(
                        info_b['unidades'], key=_ordem_unidade),
                })
    conflitos.sort(key=lambda c: (c['ns'], c['protocolo_a']))

    # --- NS iguais com o mesmo tipo (ligações reais) -----------------------
    ns_comuns_mapa = {}
    for (pid, unidade_no), p in principal_itens:
        info_no = info_maquina.get((pid, unidade_no or ''), {})
        for ns, dados in info_no.items():
            for tipo in dados['tipos']:
                chave = (ns, tipo)
                entrada = ns_comuns_mapa.setdefault(chave, {
                    'ns': ns,
                    'tipo': _tipo_peca_label(tipo),
                    'protocolos': {},
                })
                entrada['protocolos'][p.id] = {
                    'numero': p.protocol_number,
                    'unidade': unidade_no or '',
                    'unidade_label': _label_da_unidade(
                        p, unidade_no, unidades_por_id),
                }
    ns_comuns = []
    for chave in sorted(ns_comuns_mapa):
        entrada = ns_comuns_mapa[chave]
        if len(entrada['protocolos']) < 2:
            continue
        ns_comuns.append({
            'ns': entrada['ns'],
            'tipo': entrada['tipo'],
            'protocolos': [
                entrada['protocolos'][pid]
                for pid in sorted(entrada['protocolos'])],
            'ids': sorted(entrada['protocolos']),
        })

    # --- Pedidos da coluna principal ---------------------------------------
    protocolos_principais = {}
    for (pid, unidade_no), p in principal_itens:
        protocolos_principais[pid] = p
    pedidos_principais = {}
    for p in protocolos_principais.values():
        for pedido in _pedidos_do_protocolo(p):
            pedidos_principais.setdefault(pedido, []).append(p)
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

    nodes_info = list(principal_nos)
    for ramo in ramos:
        nodes_info.extend(ramo['nos'])

    return {
        'raiz': protocol,
        'main': principal_nos,
        'branches': ramos,
        'context': contexto_nos,
        'context_tipos': context_tipos,
        'nodes': nodes_info,
        'edges': arestas_info,
        'ligacoes': _TEIA_LIGACOES,
        'cores': _TEIA_CORES_ARESTA,
        'contagem': contagem,
        'truncada': truncada,
        'total': len(nodes_info),
        'total_principal': len(principal_nos),
        'total_ramos': len(ramo_ids),
        'ns_raiz': sorted(info_raiz),
        'ns_comuns': ns_comuns,
        'conflicts': conflitos,
        'por_pedido': por_pedido,
        'pedido_conflito': pedido_conflito,
        'pedidos_principais': pedidos_principais_lista,
        'ramo_ids': sorted(ramo_ids),
        'unidades': unidades,
        'unidade_selecionada': unidade_selecionada,
        'unidade_label': unidade_label,
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

    principais = []
    info_por_no = {}
    vistos = set()
    for no in teia['main']:
        p = no['protocol']
        info_por_no[p.id] = no.get('info_ns') or ns_do_protocolo(p)
        if p.id in vistos:
            continue
        vistos.add(p.id)
        principais.append(p)
    if protocol.id not in vistos:
        principais.append(protocol)
        info_por_no[protocol.id] = ns_do_protocolo(protocol)
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
    info_por_id = {
        p.id: info_por_no.get(p.id) or ns_do_protocolo(p)
        for p in principais
    }

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


def aplicar_preenchimento(protocol, indices, unidade=None):
    """Aplica somente as sugestões escolhidas. Sempre faz backup antes."""
    teia = teia_do_protocolo(protocol, unidade=unidade)
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
