"""Ocorrências de componentes/NS/modelos usadas na busca e nos rastreios."""
import json

from app.labels import peca_label

def _component_ocorrencias_protocolo(p, comp):
    """Collect every occurrence of a component type in a protocol."""
    if not comp:
        return []
    ocorrencias = []
    label = peca_label(comp)

    for c in p.components:
        if (c.component_type or '') == comp:
            ocorrencias.append({
                'local': f'Componente {c.type_label()}' + (f' — {c.machine_name}' if c.machine_name else ''),
                'valor': c.specification or c.serial_number or label,
                'detalhe': c.serial_number or ''
            })

    for d in p.defects:
        if (d.component_type or '') == comp:
            ocorrencias.append({
                'local': f'Defeito — {d.type_label()}' + (f' — {d.maquina}' if d.maquina else ''),
                'valor': d.specification or d.serial_number or label,
                'detalhe': d.description or ''
            })

    for campo, rotulo in [('rma_equip_itens', 'Equipamento RMA'),
                          ('rma_trocados', 'Equipamento mudado')]:
        raw = getattr(p, campo)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for _unit, info in data.items():
                for item in info.get('components', []):
                    if (item.get('type') or '') == comp:
                        ocorrencias.append({
                            'local': f'{rotulo} — {info.get("name", "Máquina")}',
                            'valor': item.get('model') or label,
                            'detalhe': item.get('serial') or ''
                        })
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    if p.rma_test_result:
        try:
            for item in json.loads(p.rma_test_result):
                if (item.get('component') or '') == comp:
                    ocorrencias.append({
                        'local': 'Teste de mesa' + (f' — {item.get("machine")}' if item.get('machine') else ''),
                        'valor': item.get('model') or label,
                        'detalhe': (item.get('defeito') or '')
                                + (f' — NS: {item.get("serial")}' if item.get('serial') else '')
                    })
        except (json.JSONDecodeError, TypeError):
            pass

    return ocorrencias


def _ns_ocorrencias_protocolo(p, termo=None):
    """Collect every NS occurrence in a protocol. If termo is None, return all."""
    def casa(valor):
        return termo is None or (valor and termo in valor.lower())

    ocorrencias = []

    for c in p.components:
        if casa(c.serial_number):
            ocorrencias.append({
                'local': f'Componente {c.type_label()}' + (f' — {c.machine_name}' if c.machine_name else ''),
                'valor': c.serial_number,
                'detalhe': c.specification or ''
            })
        if casa(c.machine_ref_ns):
            ocorrencias.append({
                'local': 'Referência da máquina' + (f' — {c.machine_name}' if c.machine_name else ''),
                'valor': c.machine_ref_ns,
                'detalhe': ''
            })

    for d in p.defects:
        if casa(d.serial_number):
            ocorrencias.append({
                'local': f'Defeito — {d.type_label()}',
                'valor': d.serial_number,
                'detalhe': d.description or ''
            })

    if casa(p.ref_ns):
        ocorrencias.append({
            'local': 'Referência NS do protocolo',
            'valor': p.ref_ns,
            'detalhe': ''
        })

    for campo, label in [('rma_equip_itens', 'Equipamento RMA'),
                         ('rma_trocados', 'Equipamento mudado')]:
        raw = getattr(p, campo)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for _unit, info in data.items():
                for comp in info.get('components', []):
                    serial = comp.get('serial')
                    if casa(serial):
                        ocorrencias.append({
                            'local': f'{label} — {info.get("name", "Máquina")}',
                            'valor': serial,
                            'detalhe': comp.get('model') or ''
                        })
        except (json.JSONDecodeError, TypeError):
            pass

    if p.rma_test_result:
        try:
            for item in json.loads(p.rma_test_result):
                serial = item.get('serial')
                if casa(serial):
                    ocorrencias.append({
                        'local': 'Teste de mesa',
                        'valor': serial,
                        'detalhe': peca_label(item.get('component', ''))
                                + (' — ' + item.get('defeito', '') if item.get('defeito') else '')
                                + (f' — Ped.: {item.get("pedido")}' if item.get('pedido') else '')
                                + (f' — Compra: {item.get("data_compra")}' if item.get('data_compra') else '')
                    })
        except (json.JSONDecodeError, TypeError):
            pass

    if p.rma_passagens:
        try:
            for pas in json.loads(p.rma_passagens):
                for chave_serial in ('ns', 'ns_novo'):
                    valor = pas.get(chave_serial)
                    if casa(valor):
                        ocorrencias.append({
                            'local': 'Passagem anterior'
                                        + (f' — protocolo {pas.get("protocolo")}' if pas.get('protocolo') else '')
                                        + (' — novo produto' if chave_serial == 'ns_novo' else ''),
                            'valor': valor,
                            'detalhe': pas.get('pedido') or ''
                        })
        except (json.JSONDecodeError, TypeError):
            pass

    return ocorrencias


def _ns_ocorrencias_maquina(maq, termo):
    """Collect NS occurrences in a TechBuy machine record."""
    ocorrencias = []
    dono = maq.registro.nome if maq.registro else ''
    ident = maq.identificacao or 'Máquina'
    base_local = f'{dono} — {ident}' if dono else ident
    for item in maq.get_ns_itens():
        if item.get('ns') and termo in item['ns'].lower():
            ocorrencias.append({
                'local': f'peça {peca_label(item.get("comp", ""))}',
                'valor': item['ns'],
                'detalhe': item.get('model') or ''
            })
    for t in maq.trocas:
        if t.ns and termo in t.ns.lower():
            ocorrencias.append({
                'local': f'troca de {t.produto or "produto"}',
                'valor': t.ns,
                'detalhe': f'Data: {t.data or "-"}'
            })
    for d in maq.defeitos:
        if d.ns and termo in d.ns.lower():
            ocorrencias.append({
                'local': f'defeito em {d.produto or "produto"}',
                'valor': d.ns,
                'detalhe': d.defeito or ''
            })
    for pas in maq.passagens:
        if pas.ns and termo in pas.ns.lower():
            ocorrencias.append({
                'local': 'passagem',
                'valor': pas.ns,
                'detalhe': pas.defeito or ''
            })
    return ocorrencias, base_local


def _component_ocorrencias_estoque(eu, comp):
    """Check if a component type exists in an EstoqueUso record."""
    if not comp:
        return []
    ocorrencias = []
    if (eu.tipo_componente or '') == comp:
        ocorrencias.append({'local': 'Equipamento', 'valor': eu.equipamento or '', 'detalhe': eu.ns or ''})
    for d in eu.defeitos:
        if (d.component_type or '') == comp:
            ocorrencias.append({'local': f'Defeito — {d.type_label()}', 'valor': d.specification or '', 'detalhe': d.serial_number or ''})
    return ocorrencias


def _ns_ocorrencias_estoque(eu, termo):
    """Collect NS occurrences in an EstoqueUso record."""
    ocorrencias = []
    if eu.ns and termo in eu.ns.lower():
        ocorrencias.append({
            'local': f'{eu.equipamento or "Equipamento"}',
            'valor': eu.ns,
            'detalhe': eu.uso or ''
        })
    for d in eu.defeitos:
        if d.serial_number and termo in d.serial_number.lower():
            ocorrencias.append({
                'local': f'Defeito — {d.type_label()}',
                'valor': d.serial_number,
                'detalhe': d.description or ''
            })
    return ocorrencias


def _modelo_ocorrencias_protocolo(p, termo):
    """Collect model/equipment matches in a protocol."""
    ocorrencias = []
    for c in p.components:
        if c.specification and termo in c.specification.lower():
            ocorrencias.append({
                'local': f'Componente {c.type_label()}' + (f' — {c.machine_name}' if c.machine_name else ''),
                'valor': c.specification,
                'detalhe': c.serial_number or ''
            })
    for d in p.defects:
        if d.specification and termo in d.specification.lower():
            ocorrencias.append({
                'local': f'Defeito — {d.type_label()}' + (f' — {d.maquina}' if d.maquina else ''),
                'valor': d.specification,
                'detalhe': d.serial_number or ''
            })
    for campo, rotulo in [('rma_equip_itens', 'Equipamento RMA'),
                          ('rma_trocados', 'Equipamento mudado')]:
        raw = getattr(p, campo)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for _unit, info in data.items():
                for comp in info.get('components', []):
                    if comp.get('model') and termo in comp['model'].lower():
                        ocorrencias.append({
                            'local': f'{rotulo} — {info.get("name", "Máquina")}',
                            'valor': comp['model'],
                            'detalhe': comp.get('serial') or ''
                        })
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
    if p.rma_test_result:
        try:
            for item in json.loads(p.rma_test_result):
                if item.get('model') and termo in item['model'].lower():
                    ocorrencias.append({
                        'local': 'Teste de mesa' + (f' — {item.get("machine")}' if item.get('machine') else ''),
                        'valor': item['model'],
                        'detalhe': item.get('serial') or ''
                    })
        except (json.JSONDecodeError, TypeError):
            pass
    return ocorrencias


