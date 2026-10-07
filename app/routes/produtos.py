from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.decorators import master_required
from app.labels import COMPONENT_KEYS_OFICIAIS, COMPONENT_LABELS, COMPONENT_ORDER, carregar_tipos_custom, aplicar_ordem_custom
from app.models import Produto, ComponenteTipo, TipoOrdem

produtos_bp = Blueprint('produtos', __name__, url_prefix='/produtos')


def sync_tipo_custom(component_type, label_novo):
    """Prepara o tipo digitado no botão + para salvar junto do produto.

    Retorna o objeto ComponenteTipo a persistir (novo ou com label
    atualizado), ou None quando não há nada a fazer.
    """
    if not component_type or not label_novo:
        return None
    if component_type in COMPONENT_KEYS_OFICIAIS:
        return None
    row = ComponenteTipo.query.get(component_type)
    if row:
        if row.label != label_novo:
            row.label = label_novo
            return row
        return None
    return ComponenteTipo(key=component_type, label=label_novo)


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
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    
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
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    
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

        novo_tipo = sync_tipo_custom(
            component_type, request.form.get('component_type_label', '').strip())
        if novo_tipo:
            db.session.add(novo_tipo)

        p = Produto(component_type=component_type, model_name=model_name)
        db.session.add(p)
        db.session.commit()
        if novo_tipo:
            carregar_tipos_custom([(component_type, novo_tipo.label)])
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('produtos.index'))
    
    return render_template('produtos/form.html', produto=None, tipos=get_tipos_choices())

@produtos_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    
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

        novo_tipo = sync_tipo_custom(
            component_type, request.form.get('component_type_label', '').strip())
        if novo_tipo:
            db.session.add(novo_tipo)

        p.component_type = component_type
        p.model_name = model_name
        db.session.commit()
        if novo_tipo:
            carregar_tipos_custom([(component_type, novo_tipo.label)])
        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('produtos.index'))
    
    return render_template('produtos/form.html', produto=p, tipos=get_tipos_choices())

@produtos_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    
    p = Produto.query.get_or_404(id)
    
    if p.components:
        flash(f'Não é possível excluir: produto vinculado a {len(p.components)} componente(s) em protocolos.', 'danger')
        return redirect(url_for('produtos.index'))
    
    db.session.delete(p)
    db.session.commit()
    flash('Produto excluído com sucesso!', 'success')
    return redirect(url_for('produtos.index'))

@produtos_bp.route('/api/criar', methods=['POST'])
@login_required
def api_criar():
    bloqueio = master_required()
    if bloqueio:
        return bloqueio, 403
    data = request.get_json(silent=True) or {}
    component_type = str(data.get('component_type') or '').strip()
    model_name = str(data.get('model_name') or '').strip()
    if not component_type or not model_name:
        return {'erro': 'Informe o tipo e o modelo do componente.'}, 400
    existe = Produto.query.filter(
        Produto.component_type == component_type,
        db.func.lower(Produto.model_name) == model_name.lower(),
    ).first()
    if existe:
        return {'id': existe.id, 'component_type': existe.component_type,
                'model_name': existe.model_name, 'ja_existia': True}
    p = Produto(component_type=component_type, model_name=model_name)
    db.session.add(p)
    db.session.commit()
    return {'id': p.id, 'component_type': p.component_type,
            'model_name': p.model_name, 'ja_existia': False}


@produtos_bp.route('/api/listar')
@login_required
def api_listar():
    tipo = request.args.get('tipo', '').strip()
    q = Produto.query
    if tipo:
        q = q.filter_by(component_type=tipo)
    produtos = q.order_by(Produto.model_name).all()
    return [{'id': p.id, 'component_type': p.component_type, 'model_name': p.model_name, 'type_label': p.type_label()} for p in produtos]


def ordem_atual():
    """(chave, rótulo) dos componentes com produto no catálogo, na ordem vigente."""
    com_produto = {
        t for (t,) in db.session.query(Produto.component_type).distinct() if t
    }
    chaves = [k for k in COMPONENT_ORDER if k in com_produto]
    chaves += sorted(t for t in com_produto if t not in chaves)
    return [(k, COMPONENT_LABELS.get(k, k)) for k in chaves]


@produtos_bp.route('/ordem', methods=['GET', 'POST'])
@login_required
def ordem():
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    if request.method == 'POST':
        chaves = [k.strip() for k in request.form.getlist('ordem[]') if k.strip()]
        TipoOrdem.query.delete()
        for i, k in enumerate(chaves):
            db.session.add(TipoOrdem(key=k, posicao=i))
        db.session.commit()
        aplicar_ordem_custom([(k, i) for i, k in enumerate(chaves)])
        flash('Ordem dos componentes salva!', 'success')
        return redirect(url_for('produtos.index'))
    return render_template('produtos/ordem.html', itens=ordem_atual())
