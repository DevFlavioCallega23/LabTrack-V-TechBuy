from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Protocol

main_bp = Blueprint('main', __name__)

DIAS_ALERTA = 7

@main_bp.route('/')
@login_required
def dashboard():
    total = Protocol.query.count()
    andamento = Protocol.query.filter_by(status='andamento').count()
    concluidos = Protocol.query.filter_by(status='concluido').count()
    recentes = Protocol.query.order_by(Protocol.created_at.desc()).limit(10).all()

    # Protocolos parados: não concluídos/cancelados, sem data de saída,
    # sem atividade nos últimos DIAS_ALERTA dias
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

    return render_template('dashboard.html',
        total=total,
        andamento=andamento, concluidos=concluidos,
        recentes=recentes, parados=parados,
        dias_alerta=DIAS_ALERTA)
