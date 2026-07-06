from datetime import datetime
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Protocol

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    total = Protocol.query.count()
    pendentes = Protocol.query.filter_by(status='pendente').count()
    andamento = Protocol.query.filter_by(status='andamento').count()
    concluidos = Protocol.query.filter_by(status='concluido').count()
    recentes = Protocol.query.order_by(Protocol.created_at.desc()).limit(10).all()
    return render_template('dashboard.html',
        total=total, pendentes=pendentes,
        andamento=andamento, concluidos=concluidos,
        recentes=recentes)
