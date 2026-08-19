from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import Protocol

etiquetas_bp = Blueprint('etiquetas', __name__, url_prefix='/etiquetas')


@etiquetas_bp.route('/')
@login_required
def index():
    protocolos = Protocol.query.order_by(Protocol.created_at.desc()).limit(300).all()
    return render_template('etiquetas/index.html', protocolos=protocolos)