from datetime import timedelta
from flask import Blueprint, render_template, request
from flask_login import login_required
from app import db
from app.models import Protocol, Component, Defect, Produto, EstoqueUso, TBMaquina
from app.labels import (
    COMPONENT_LABELS, peca_label,
)

from app.routes.protocols.helpers import parse_date_br
from app.routes.protocols.ocorrencias import (
    _component_ocorrencias_protocolo, _ns_ocorrencias_protocolo, _ns_ocorrencias_maquina,
    _component_ocorrencias_estoque, _ns_ocorrencias_estoque, _modelo_ocorrencias_protocolo,
)

busca_bp = Blueprint('busca', __name__)

@busca_bp.route('/ns/todos')
@login_required
def ns_todos():
    q = request.args.get('q', '').strip().lower()
    linhas = []
    for p in Protocol.query.order_by(Protocol.created_at.desc()).all():
        for oc in _ns_ocorrencias_protocolo(p):
            linhas.append({
                'ns': oc['valor'] or '',
                'local': oc['local'],
                'detalhe': oc['detalhe'],
                'protocolo': p.protocol_number,
                'protocolo_id': p.id,
                'tipo': p.type_label(),
                'venda_pe': p.venda_pe,
                'data': p.entry_date or p.created_at,
                'status': p.status_label()
            })
    if q:
        linhas = [l for l in linhas if q in l['ns'].lower() or q in l['local'].lower()
                  or q in l['protocolo'].lower() or q in l['detalhe'].lower()]
    return render_template('protocols/ns_todos.html', linhas=linhas, total=len(linhas), q=q)

@busca_bp.route('/busca')
@login_required
def busca_avancada():
    cliente = request.args.get('cliente', '').strip()
    vendedor = request.args.get('vendedor', '').strip()
    tipo = request.args.get('tipo', '').strip()
    pedido = request.args.get('pedido', '').strip()
    ns = request.args.get('ns', '').strip()
    modelo = request.args.get('modelo', '').strip()
    componente = request.args.get('componente', '').strip()
    data_de_raw = request.args.get('data_de', '').strip()
    data_ate_raw = request.args.get('data_ate', '').strip()
    data_de = parse_date_br(data_de_raw)
    data_ate = parse_date_br(data_ate_raw)

    filtros_ativos = any([cliente, vendedor, tipo, pedido, ns, modelo, componente, data_de, data_ate])
    resultados = []
    total_ocorrencias = 0
    total_comp_ocorrencias = 0

    if filtros_ativos:
        q = Protocol.query
        if cliente:
            q = q.filter(Protocol.client_name.ilike(f'%{cliente}%'))
        if vendedor:
            q = q.filter(Protocol.seller == vendedor)
        if tipo:
            q = q.filter(Protocol.type == tipo)
        if pedido:
            like = f'%{pedido}%'
            q = q.filter(db.or_(Protocol.order_number.ilike(like),
                                Protocol.original_order.ilike(like)))
        if data_de:
            q = q.filter(Protocol.entry_date >= data_de)
        if data_ate:
            q = q.filter(Protocol.entry_date < data_ate + timedelta(days=1))
        if componente:
            q = q.filter(db.or_(
                Protocol.components.any(Component.component_type == componente),
                Protocol.defects.any(Defect.component_type == componente),
                Protocol.rma_test_result.ilike(f'%"component": "{componente}"%'),
                Protocol.rma_equip_itens.ilike(f'%"type": "{componente}"%'),
                Protocol.rma_trocados.ilike(f'%"type": "{componente}"%')
            ))
        if modelo:
            like = f'%{modelo}%'
            q = q.filter(db.or_(
                Protocol.components.any(Component.specification.ilike(like)),
                Protocol.defects.any(Defect.specification.ilike(like)),
                Protocol.rma_test_result.ilike(like),
                Protocol.rma_equip_itens.ilike(like),
                Protocol.rma_trocados.ilike(like)
            ))

        protocols = q.order_by(Protocol.entry_date.desc().nullslast(),
                               Protocol.created_at.desc()).all()

        termo_ns = ns.lower() if ns else None
        for p in protocols:
            ocorrencias = _ns_ocorrencias_protocolo(p, termo_ns) if termo_ns else []
            if termo_ns and not ocorrencias:
                continue
            comp_ocorrencias = _component_ocorrencias_protocolo(p, componente) if componente else []
            if componente and not comp_ocorrencias:
                continue
            resultados.append({'p': p, 'ocorrencias': ocorrencias, 'comp_ocorrencias': comp_ocorrencias})
            total_ocorrencias += len(ocorrencias)
            total_comp_ocorrencias += len(comp_ocorrencias)

    tb_resultados = []
    estoque_resultados = []
    if filtros_ativos and (termo_ns or componente):
        for maq in TBMaquina.query.all():
            if termo_ns:
                ocorrencias, base_local = _ns_ocorrencias_maquina(maq, termo_ns)
            else:
                ocorrencias, base_local = [], ''
                for item in maq.get_ns_itens():
                    if (item.get('comp') or '') == componente:
                        ocorrencias.append({
                            'local': f'peça {peca_label(item.get("comp", ""))}',
                            'valor': item.get('ns') or '',
                            'detalhe': item.get('model') or ''
                        })
                if ocorrencias:
                    dono = maq.registro.nome if maq.registro else ''
                    base_local = f'{dono} — {maq.identificacao or "Máquina"}' if dono else (maq.identificacao or 'Máquina')
            if ocorrencias:
                tb_resultados.append({
                    'maquina': maq,
                    'dono': maq.registro.nome if maq.registro else '',
                    'identificacao': maq.identificacao or 'Máquina',
                    'registro_id': maq.registro_id,
                    'ocorrencias': ocorrencias
                })
        eq = EstoqueUso.query
        if componente:
            eq = eq.filter(db.or_(
                EstoqueUso.tipo_componente == componente,
                EstoqueUso.defeitos.any(Defect.component_type == componente)
            ))
        for eu in eq.all():
            ocorrencias = _ns_ocorrencias_estoque(eu, termo_ns) if termo_ns else _component_ocorrencias_estoque(eu, componente)
            if termo_ns and componente and not _component_ocorrencias_estoque(eu, componente):
                continue
            if ocorrencias:
                estoque_resultados.append({'item': eu, 'ocorrencias': ocorrencias})

    vendedores = [r[0] for r in db.session.query(Protocol.seller).distinct()
                  .filter(Protocol.seller.isnot(None), Protocol.seller != '')
                  .order_by(Protocol.seller).all()]

    tipos_componente = sorted({t[0] for t in db.session.query(Produto.component_type).distinct().all() if t[0]} |
                              {t[0] for t in db.session.query(Component.component_type).distinct().all() if t[0]} |
                              {t[0] for t in db.session.query(Defect.component_type).distinct().all() if t[0]})
    comp_labels = dict(COMPONENT_LABELS)
    for t in tipos_componente:
        comp_labels.setdefault(t, peca_label(t))

    return render_template('protocols/busca.html',
        resultados=resultados, total=len(resultados),
        total_ocorrencias=total_ocorrencias, vendedores=vendedores,
        total_comp_ocorrencias=total_comp_ocorrencias,
        tipos_componente=tipos_componente, comp_labels=comp_labels,
        tb_resultados=tb_resultados, estoque_resultados=estoque_resultados,
        filtros_ativos=filtros_ativos,
        f_cliente=cliente, f_vendedor=vendedor, f_tipo=tipo, f_pedido=pedido,
        f_ns=ns, f_modelo=modelo, f_componente=componente, f_data_de=data_de_raw, f_data_ate=data_ate_raw,
        TYPE_LABELS=Protocol.TYPE_LABELS)

@busca_bp.route('/ns')
@login_required
def rastreio_ns():
    busca = request.args.get('busca', '').strip()
    tipo = request.args.get('tipo', '').strip()
    resultados = []
    tb_resultados = []
    estoque_resultados = []
    if busca:
        termo = busca.lower()
        if tipo != 'estoque':
            pq = Protocol.query
            if tipo:
                pq = pq.filter(Protocol.type == tipo)
            for p in pq.order_by(Protocol.created_at.desc()).all():
                ocorrencias = _ns_ocorrencias_protocolo(p, termo)
                if ocorrencias:
                    resultados.append({
                        'protocolo': p,
                        'ocorrencias': ocorrencias
                    })

        # Máquinas TechBuy (módulo do Master)
        for maq in (TBMaquina.query.all() if tipo != 'estoque' else []):
            ocorrencias = []
            dono = maq.registro.nome if maq.registro else ''
            ident = maq.identificacao or 'Máquina'
            base_local = f'Máquinas TechBuy — {dono} — {ident}'
            for item in maq.get_ns_itens():
                if item.get('ns') and termo in item['ns'].lower():
                    ocorrencias.append({
                        'local': f'{base_local} — peça {peca_label(item.get("comp", ""))}',
                        'valor': item['ns'],
                        'detalhe': item.get('model') or ''
                    })
            for t in maq.trocas:
                if t.ns and termo in t.ns.lower():
                    ocorrencias.append({
                        'local': f'{base_local} — troca de {t.produto or "produto"}',
                        'valor': t.ns,
                        'detalhe': f'Data: {t.data or "-"}'
                    })
            for d in maq.defeitos:
                if d.ns and termo in d.ns.lower():
                    ocorrencias.append({
                        'local': f'{base_local} — defeito em {d.produto or "produto"}',
                        'valor': d.ns,
                        'detalhe': d.defeito or ''
                    })
            for pas in maq.passagens:
                if pas.ns and termo in pas.ns.lower():
                    ocorrencias.append({
                        'local': f'{base_local} — passagem de {pas.produto or "produto"}',
                        'valor': pas.ns,
                        'detalhe': pas.defeito or ''
                    })
            if ocorrencias:
                tb_resultados.append({
                    'maquina': maq,
                    'dono': dono,
                    'identificacao': maq.identificacao or 'Máquina',
                    'ocorrencias': ocorrencias
                })

        for eu in EstoqueUso.query.all():
            ocorrencias = _ns_ocorrencias_estoque(eu, termo)
            if ocorrencias:
                estoque_resultados.append({'item': eu, 'ocorrencias': ocorrencias})

    return render_template('protocols/ns.html', busca=busca, resultados=resultados,
        total_resultados=len(resultados), tb_resultados=tb_resultados,
        estoque_resultados=estoque_resultados,
        f_tipo=tipo, TYPE_LABELS=Protocol.TYPE_LABELS)



@busca_bp.route('/rastreio-pedido')
@login_required
def rastreio_pedido():
    busca = request.args.get('busca', '').strip()
    resultados = []
    if busca:
        like = f'%{busca}%'
        for p in Protocol.query.filter(
            db.or_(Protocol.order_number.ilike(like),
                   Protocol.original_order.ilike(like))
        ).order_by(Protocol.created_at.desc()).all():
            resultados.append({'protocolo': p})
    return render_template('protocols/rastreio_pedido.html', busca=busca,
        resultados=resultados, total_resultados=len(resultados))


@busca_bp.route('/rastreio-equipamento')
@login_required
def rastreio_equipamento():
    busca = request.args.get('busca', '').strip()
    componente = request.args.get('componente', '').strip()
    tipo = request.args.get('tipo', '').strip()
    resultados = []
    estoque_resultados = []
    if busca or componente:
        termo = busca.lower() if busca else None
        like = f'%{busca}%' if busca else None
        q = Protocol.query
        if tipo and tipo != 'estoque':
            q = q.filter(Protocol.type == tipo)
        if like:
            q = q.filter(db.or_(
                Protocol.components.any(Component.specification.ilike(like)),
                Protocol.defects.any(Defect.specification.ilike(like)),
                Protocol.rma_test_result.ilike(like),
                Protocol.rma_equip_itens.ilike(like),
                Protocol.rma_trocados.ilike(like)
            ))
        if componente:
            q = q.filter(db.or_(
                Protocol.components.any(Component.component_type == componente),
                Protocol.defects.any(Defect.component_type == componente),
                Protocol.rma_test_result.ilike(f'%"component": "{componente}"%'),
                Protocol.rma_equip_itens.ilike(f'%"type": "{componente}"%'),
                Protocol.rma_trocados.ilike(f'%"type": "{componente}"%')
            ))
        if tipo != 'estoque':
            for p in q.order_by(Protocol.created_at.desc()).all():
                ocorrencias = _modelo_ocorrencias_protocolo(p, termo) if termo else _component_ocorrencias_protocolo(p, componente)
                if termo and componente and not _component_ocorrencias_protocolo(p, componente):
                    continue
                resultados.append({'protocolo': p, 'ocorrencias': ocorrencias})
        eq = EstoqueUso.query
        if componente:
            eq = eq.filter(db.or_(
                EstoqueUso.tipo_componente == componente,
                EstoqueUso.defeitos.any(Defect.component_type == componente)
            ))
        if like:
            eq = eq.filter(db.or_(
                EstoqueUso.equipamento.ilike(like),
                EstoqueUso.defeitos.any(Defect.specification.ilike(like))
            ))
        for eu in eq.all():
            ocorrencias = []
            if termo and eu.equipamento and termo in eu.equipamento.lower():
                ocorrencias.append({'local': 'Equipamento', 'valor': eu.equipamento, 'detalhe': eu.ns or ''})
            for d in eu.defeitos:
                if termo and d.specification and termo in d.specification.lower():
                    ocorrencias.append({'local': f'Defeito — {d.type_label()}', 'valor': d.specification, 'detalhe': d.serial_number or ''})
                elif componente and (d.component_type or '') == componente and not termo:
                    ocorrencias.append({'local': f'Defeito — {d.type_label()}', 'valor': d.specification or '', 'detalhe': d.serial_number or ''})
            if componente and (eu.tipo_componente or '') == componente and not any(o['local'] == 'Equipamento' for o in ocorrencias):
                ocorrencias.append({'local': 'Equipamento', 'valor': eu.equipamento or '', 'detalhe': eu.ns or ''})
            if ocorrencias:
                estoque_resultados.append({'item': eu, 'ocorrencias': ocorrencias})

    tipos_componente = sorted({t[0] for t in db.session.query(Produto.component_type).distinct().all() if t[0]} |
                              {t[0] for t in db.session.query(Component.component_type).distinct().all() if t[0]} |
                              {t[0] for t in db.session.query(Defect.component_type).distinct().all() if t[0]})
    comp_labels = dict(COMPONENT_LABELS)
    for t in tipos_componente:
        comp_labels.setdefault(t, peca_label(t))

    return render_template('protocols/rastreio_equipamento.html', busca=busca,
        resultados=resultados, total_resultados=len(resultados),
        estoque_resultados=estoque_resultados,
        tipos_componente=tipos_componente, comp_labels=comp_labels,
        f_componente=componente, f_tipo=tipo, TYPE_LABELS=Protocol.TYPE_LABELS)


@busca_bp.route('/rastreio-cliente')
@login_required
def rastreio_cliente():
    busca = request.args.get('busca', '').strip()
    tipo = request.args.get('tipo', '').strip()
    resultados = []
    if busca:
        q = Protocol.query.filter(Protocol.client_name.ilike(f'%{busca}%'))
        if tipo:
            q = q.filter(Protocol.type == tipo)
        for p in q.order_by(Protocol.created_at.desc()).all():
            resultados.append({'protocolo': p})
    return render_template('protocols/rastreio_cliente.html', busca=busca,
        resultados=resultados, total_resultados=len(resultados),
        f_tipo=tipo, TYPE_LABELS=Protocol.TYPE_LABELS)

