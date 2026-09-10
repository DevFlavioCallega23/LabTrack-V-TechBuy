from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Produto

produtos_bp = Blueprint('produtos', __name__, url_prefix='/produtos')


def get_tipos_choices():
    from app.models import Component, Defect
    conhecidos = set(Produto.TYPE_LABELS.keys()) | set(Produto.TYPE_ORDER)
    for (t,) in db.session.query(Produto.component_type).distinct().all():
        if t:
            conhecidos.add(t)
    for (t,) in db.session.query(Component.component_type).distinct().all():
        if t:
            conhecidos.add(t)
    for (t,) in db.session.query(Defect.component_type).distinct().all():
        if t:
            conhecidos.add(t)
    conhecidos.discard('outro')
    ordenados = [t for t in Produto.TYPE_ORDER if t in conhecidos]
    for t in sorted(conhecidos):
        if t not in ordenados:
            ordenados.append(t)
    return [(t, Produto.TYPE_LABELS.get(t, t)) for t in ordenados]

@produtos_bp.route('/')
@login_required
def index():
    if not current_user.is_master():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    f_tipo = request.args.get('tipo', '').strip()
    q = Produto.query
    if f_tipo:
        q = q.filter_by(component_type=f_tipo)
    produtos = q.all()
    ordem = {t: i for i, t in enumerate(Produto.TYPE_ORDER)}
    produtos.sort(key=lambda p: (ordem.get(p.component_type, 999), p.model_name))
    
    tipos = [t[0] for t in db.session.query(Produto.component_type).distinct().all()]
    tipos.sort(key=lambda t: ordem.get(t, 999))
    
    return render_template('produtos/index.html', 
                           produtos=produtos, 
                           tipos=tipos,
                           f_tipo=f_tipo)

@produtos_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if not current_user.is_master():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        component_type = request.form.get('component_type', '').strip()
        model_name = request.form.get('model_name', '').strip()
        
        if not component_type or not model_name:
            flash('Preencha todos os campos.', 'danger')
            return render_template('produtos/form.html', produto=None, tipos=get_tipos_choices())
        
        existe = Produto.query.filter_by(component_type=component_type, model_name=model_name).first()
        if existe:
            flash('Este produto já está cadastrado.', 'warning')
            return render_template('produtos/form.html', produto=None, tipos=get_tipos_choices())
        
        p = Produto(component_type=component_type, model_name=model_name)
        db.session.add(p)
        db.session.commit()
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('produtos.index'))
    
    return render_template('produtos/form.html', produto=None, tipos=get_tipos_choices())

@produtos_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    if not current_user.is_master():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    p = Produto.query.get_or_404(id)
    
    if request.method == 'POST':
        component_type = request.form.get('component_type', '').strip()
        model_name = request.form.get('model_name', '').strip()
        
        if not component_type or not model_name:
            flash('Preencha todos os campos.', 'danger')
            return render_template('produtos/form.html', produto=p, tipos=get_tipos_choices())
        
        existe = Produto.query.filter(
            Produto.component_type == component_type,
            Produto.model_name == model_name,
            Produto.id != id
        ).first()
        if existe:
            flash('Este produto já está cadastrado.', 'warning')
            return render_template('produtos/form.html', produto=p, tipos=get_tipos_choices())
        
        p.component_type = component_type
        p.model_name = model_name
        db.session.commit()
        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('produtos.index'))
    
    return render_template('produtos/form.html', produto=p, tipos=get_tipos_choices())

@produtos_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    if not current_user.is_master():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    p = Produto.query.get_or_404(id)
    
    if p.components:
        flash(f'Não é possível excluir: produto vinculado a {len(p.components)} componente(s) em protocolos.', 'danger')
        return redirect(url_for('produtos.index'))
    
    db.session.delete(p)
    db.session.commit()
    flash('Produto excluído com sucesso!', 'success')
    return redirect(url_for('produtos.index'))

@produtos_bp.route('/api/listar')
@login_required
def api_listar():
    tipo = request.args.get('tipo', '').strip()
    q = Produto.query
    if tipo:
        q = q.filter_by(component_type=tipo)
    produtos = q.order_by(Produto.model_name).all()
    return [{'id': p.id, 'component_type': p.component_type, 'model_name': p.model_name, 'type_label': p.type_label()} for p in produtos]
