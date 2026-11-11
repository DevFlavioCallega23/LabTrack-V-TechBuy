from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.forms import QuickProtocolForm
from app.models import Protocol
from app.routes.protocols.helpers import (
    gerar_numero_protocolo, parse_date_br, maquinas_pronta_entrega_para_home,
)
from sqlalchemy import extract

main_bp = Blueprint('main', __name__)

DIAS_ALERTA = 7

@main_bp.route('/')
@login_required
def dashboard():
    f_ano = request.args.get('ano', '', type=str)
    f_mes = request.args.get('mes', '', type=str)

    q = Protocol.query

    if f_ano and f_ano.isdigit():
        q = q.filter(extract('year', Protocol.created_at) == int(f_ano))
    if f_mes and f_mes.isdigit():
        q = q.filter(extract('month', Protocol.created_at) == int(f_mes))

    total = q.count()
    andamento = q.filter_by(status='andamento').count()
    concluidos = q.filter_by(status='concluido').count()

    recentes_q = Protocol.query
    if f_ano and f_ano.isdigit():
        recentes_q = recentes_q.filter(extract('year', Protocol.created_at) == int(f_ano))
    if f_mes and f_mes.isdigit():
        recentes_q = recentes_q.filter(extract('month', Protocol.created_at) == int(f_mes))
    recentes = recentes_q.order_by(Protocol.created_at.desc()).limit(10).all()

    limite = datetime.utcnow() - timedelta(days=DIAS_ALERTA)
    parados = []
    for p in Protocol.query.filter(Protocol.status.notin_(['concluido', 'cancelado'])).order_by(Protocol.created_at.desc()).all():
        if p.exit_date:
            continue
        ref = p.updated_at or p.created_at or p.entry_date
        if ref and ref < limite:
            p.dias_parado = (datetime.utcnow() - ref).days
            parados.append(p)
    parados.sort(key=lambda x: x.dias_parado, reverse=True)
    parados_ids = {p.id for p in parados}

    anos_disponiveis = sorted(set(
        p.created_at.year for p in Protocol.query.all() if p.created_at
    ), reverse=True)

    pode_ver_estoque = current_user.is_master()
    pe_maquinas = maquinas_pronta_entrega_para_home(
        incluir_estoque=pode_ver_estoque)
    pe_disponiveis = sum(1 for m in pe_maquinas if m['disponivel'])
    pe_vendidas = len(pe_maquinas) - pe_disponiveis
    pe_sem_estoque = sum(
        1 for m in pe_maquinas
        if m['disponivel'] and not m['estoque_registrado'])

    return render_template('dashboard.html',
        total=total,
        andamento=andamento, concluidos=concluidos,
        recentes=recentes, parados=parados, parados_ids=parados_ids,
        dias_alerta=DIAS_ALERTA,
        anos_disponiveis=anos_disponiveis,
        f_ano=f_ano, f_mes=f_mes,
        pe_maquinas=pe_maquinas, pe_disponiveis=pe_disponiveis,
        pe_vendidas=pe_vendidas, pe_sem_estoque=pe_sem_estoque,
        pode_ver_estoque=pode_ver_estoque,
        quick_form=QuickProtocolForm())


@main_bp.route('/registro-rapido', methods=['POST'])
@login_required
def registro_rapido():
    """Cria um protocolo a partir do bloco 'Registro rápido' da Home.

    Os campos mostrados na Home mudam conforme o tipo, seguindo o que é
    essencial em cada um. Aqui o servidor grava só o que faz sentido para o
    tipo escolhido e já abre a edição, para completar equipamento, teste de
    mesa etc.
    """
    if not current_user.is_manager():
        flash('Você não tem permissão para criar protocolos.', 'danger')
        return redirect(url_for('main.dashboard'))

    form = QuickProtocolForm()
    if not form.validate_on_submit():
        flash('Confira o registro rápido: informe o tipo de protocolo.', 'warning')
        return redirect(url_for('main.dashboard'))

    tipo = form.type.data
    if tipo not in ('venda', 'ponta_entrega', 'rma', 'servico', 'nao_comprado'):
        flash('Escolha o tipo de protocolo.', 'warning')
        return redirect(url_for('main.dashboard'))

    # Tipos com cliente no formulário completo (a Pronta-Entrega não tem).
    if tipo in ('venda', 'rma', 'servico', 'nao_comprado'):
        if not (form.client_name.data or '').strip():
            flash('Informe o cliente para este tipo de protocolo.', 'warning')
            return redirect(url_for('main.dashboard'))

    cliente = (form.client_name.data or '').strip()
    vendedor = (form.seller.data or '').strip() or None
    pedido = (form.pedido.data or '').strip() or None
    lote = (form.lote.data or '').strip() or None
    data_informada = parse_date_br((form.entry_date.data or '').strip()) \
        if (form.entry_date.data or '').strip() else None
    relato = (form.base_defect.data or '').strip()

    protocol = Protocol(
        protocol_number=gerar_numero_protocolo(),
        type=tipo,
        client_name=cliente or None,
        seller=vendedor,
        status='andamento',
        rma_in_warranty=(tipo == 'rma'),
        created_by=current_user.id,
    )

    # Venda: pedido e quantidade ficam nos campos de venda.
    if tipo == 'venda':
        protocol.order_number = pedido
        protocol.lote = lote
        protocol.entry_date = data_informada

    # RMA / Serviço: o pedido é o da compra original; a data de entrada no
    # laboratório é hoje e "Data da Compra" só é preenchida se informada.
    elif tipo in ('rma', 'servico'):
        protocol.original_order = pedido
        protocol.lote = lote
        protocol.entry_date = data_informada
        protocol.rma_entry_date = datetime.utcnow()

    # Pronta-Entrega: sem cliente/pedido; a entrada é hoje se não informada.
    elif tipo == 'ponta_entrega':
        protocol.lote = lote
        protocol.entry_date = data_informada or datetime.utcnow()

    # RMA/Serviço/NTB têm o campo "Defeito informado pelo cliente"; em Venda e
    # Pronta-Entrega esse campo não aparece no formulário, então o relato vai
    # para as Observações (onde continua visível e editável).
    if relato:
        if tipo in ('rma', 'servico', 'nao_comprado'):
            protocol.base_defect = relato
        else:
            protocol.observations = relato

    db.session.add(protocol)
    db.session.commit()
    flash(f'Protocolo {protocol.protocol_number} criado. Complete as informações abaixo.',
          'success')
    return redirect(url_for('protocols.edit_protocol', id=protocol.id))
