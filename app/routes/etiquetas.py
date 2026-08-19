from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Protocol, EtiquetaSalva

etiquetas_bp = Blueprint('etiquetas', __name__, url_prefix='/etiquetas')


@etiquetas_bp.route('/')
@login_required
def index():
    protocolos = Protocol.query.order_by(Protocol.created_at.desc()).limit(300).all()
    salvas = EtiquetaSalva.query.order_by(EtiquetaSalva.created_at.desc()).limit(50).all()
    return render_template('etiquetas/index.html', protocolos=protocolos, salvas=salvas)


@etiquetas_bp.route('/salvar', methods=['POST'])
@login_required
def salvar():
    dados = {
        'protocolo_id': request.form.get('protocolo_id', '') or None,
        'ref': request.form.get('ref', '').strip(),
        'cliente': request.form.get('cliente', '').strip(),
        'vendedor': request.form.get('vendedor', '').strip(),
        'entrada': request.form.get('entrada', '').strip(),
        'pedido': request.form.get('pedido', '').strip(),
        'garantia': request.form.get('garantia', '').strip(),
        'cenario': request.form.get('cenario', '').strip() or 'case',
        'tamanho': request.form.get('tamanho', '').strip() or 'media',
        'produto': request.form.get('produto', '').strip(),
        'ns': request.form.get('ns', '').strip(),
        'obs': request.form.get('obs', '').strip(),
    }
    try:
        copias = max(1, min(99, int(request.form.get('copias', '1'))))
    except (TypeError, ValueError):
        copias = 1
    if not dados['ref'] and not dados['produto']:
        flash('Preencha ao menos a referência ou o produto da etiqueta.', 'warning')
        return redirect(url_for('etiquetas.index'))
    etiqueta = EtiquetaSalva(**dados, copias=copias, created_by=current_user.username)
    db.session.add(etiqueta)
    db.session.commit()
    flash('Etiqueta salva! Envie o link para alguém imprimir.', 'success')
    return redirect(url_for('etiquetas.salva', id=etiqueta.id))


@etiquetas_bp.route('/salva/<int:id>')
@login_required
def salva(id):
    etiqueta = EtiquetaSalva.query.get_or_404(id)
    return render_template('etiquetas/salva.html', e=etiqueta)


@etiquetas_bp.route('/salva/<int:id>/excluir', methods=['POST'])
@login_required
def salva_excluir(id):
    etiqueta = EtiquetaSalva.query.get_or_404(id)
    db.session.delete(etiqueta)
    db.session.commit()
    flash('Etiqueta excluída.', 'success')
    return redirect(url_for('etiquetas.index'))