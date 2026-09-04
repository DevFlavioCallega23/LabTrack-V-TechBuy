from datetime import datetime, timedelta
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import Protocol
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

    anos_disponiveis = sorted(set(
        p.created_at.year for p in Protocol.query.all() if p.created_at
    ), reverse=True)

    return render_template('dashboard.html',
        total=total,
        andamento=andamento, concluidos=concluidos,
        recentes=recentes, parados=parados,
        dias_alerta=DIAS_ALERTA,
        anos_disponiveis=anos_disponiveis,
        f_ano=f_ano, f_mes=f_mes)
