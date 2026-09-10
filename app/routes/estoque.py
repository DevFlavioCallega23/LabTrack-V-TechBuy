import json
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import EstoqueUso, Defect, Produto

estoque_bp = Blueprint('estoque', __name__, url_prefix='/estoque')


def build_component_types():
    tipos_db = db.session.query(Produto.component_type).distinct().all()
    tipos_existentes = {t[0] for t in tipos_db}
    default_order = ['processador', 'placa_mae', 'ram', 'ssd', 'fonte', 'placa_de_video', 'gpu', 'gabinete', 'monitor']
    order = [t for t in default_order if t in tipos_existentes]
    for t in tipos_existentes:
        if t not in order:
            order.append(t)
    if not order:
        order = ['processador', 'placa_mae', 'ram', 'ssd', 'fonte', 'monitor']
    labels = Produto.TYPE_LABELS
    return json.dumps([{'key': t, 'label': labels.get(t, t)} for t in order])


def get_catalog_context():
    return dict(
        produtos_catalogo=json.dumps([{'id': p.id, 'component_type': p.component_type, 'model_name': p.model_name} for p in Produto.query.order_by(Produto.component_type, Produto.model_name).all()]),
        component_types=build_component_types(),
    )


def master_required():
    if not current_user.is_master():
        flash('Acesso restrito ao Master.', 'danger')
        return redirect(url_for('main.dashboard'))
    return None


def normalize_date_br(text):
    """Normaliza DD/MM/AA -> DD/MM/AAAA igual aos protocolos."""
    if not text or not text.strip():
        return None
    text = text.strip()
    parts = text.replace('-', '/').split('/')
    if len(parts) == 3 and len(parts[2]) == 2 and parts[2].isdigit():
        parts[2] = '20' + parts[2]
        return '/'.join(parts)
    return text


def parse_estoque_defects(request_form):
    defects = []
    types = request_form.getlist('defect_type[]')
    models = request_form.getlist('defect_model[]')
    serials = request_form.getlist('defect_serial[]')
    descs = request_form.getlist('defect_desc[]')
    maquinas = request_form.getlist('defect_maquina[]')
    vindo_estoque_vals = request_form.getlist('defect_vindo_estoque[]')
    for i in range(len(types)):
        if types[i].strip():
            defects.append(Defect(
                component_type=types[i].strip(),
                specification=models[i].strip() if i < len(models) else '',
                serial_number=serials[i].strip() if i < len(serials) else '',
                description=descs[i].strip() if i < len(descs) else '',
                maquina=maquinas[i].strip() if i < len(maquinas) else '',
                vindo_estoque='1' in vindo_estoque_vals if i < len(vindo_estoque_vals) else False,
                sort_order=i
            ))
    return defects


def parse_estoque_passagens(request_form):
    entradas = request_form.getlist('pass_entrada[]')
    saidas = request_form.getlist('pass_saida[]')
    usos = request_form.getlist('pass_uso[]')
    itens = []
    for i in range(max(len(entradas), len(saidas), len(usos))):
        ent = normalize_date_br(entradas[i]) if i < len(entradas) else None
        sai = normalize_date_br(saidas[i]) if i < len(saidas) else None
        uso = usos[i].strip() if i < len(usos) else ''
        if ent or sai or uso:
            itens.append({'data_entrada': ent or '', 'data_saida': sai or '', 'uso': uso})
    return json.dumps(itens) if itens else None


@estoque_bp.route('/')
@login_required
def index():
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    itens = EstoqueUso.query.order_by(EstoqueUso.id.desc()).all()
    return render_template('estoque/index.html', itens=itens)


@estoque_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    if request.method == 'POST':
        equipamento = request.form.get('equipamento', '').strip()
        if not equipamento:
            flash('Informe o equipamento.', 'warning')
            return render_template('estoque/form.html', item=None, **get_catalog_context())
        passagens_json = parse_estoque_passagens(request.form)
        primeira = json.loads(passagens_json)[0] if passagens_json else {}
        item = EstoqueUso(
            data_entrada=primeira.get('data_entrada') or None,
            tipo_componente=request.form.get('tipo_componente', '').strip() or None,
            equipamento=equipamento,
            ns=request.form.get('ns', '').strip() or None,
            uso=primeira.get('uso') or None,
            data_saida=primeira.get('data_saida') or None,
            laudo=request.form.get('laudo', '').strip() or None,
            obs=request.form.get('obs', '').strip() or None,
            passagens=passagens_json,
        )
        db.session.add(item)
        db.session.flush()

        defects = parse_estoque_defects(request.form)
        for d in defects:
            d.estoque_uso_id = item.id
        db.session.add_all(defects)
        db.session.commit()
        flash(f'Registro de uso criado!', 'success')
        return redirect(url_for('estoque.detail', id=item.id))
    return render_template('estoque/form.html', item=None, **get_catalog_context())


@estoque_bp.route('/<int:id>')
@login_required
def detail(id):
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    item = EstoqueUso.query.get_or_404(id)
    return render_template('estoque/detail.html', item=item)


@estoque_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    item = EstoqueUso.query.get_or_404(id)
    if request.method == 'POST':
        item.equipamento = request.form.get('equipamento', '').strip() or item.equipamento
        item.tipo_componente = request.form.get('tipo_componente', '').strip() or None
        item.ns = request.form.get('ns', '').strip() or None
        item.laudo = request.form.get('laudo', '').strip() or None
        item.obs = request.form.get('obs', '').strip() or None
        item.passagens = parse_estoque_passagens(request.form)
        if item.passagens:
            primeira = json.loads(item.passagens)[0]
            item.data_entrada = primeira.get('data_entrada') or None
            item.data_saida = primeira.get('data_saida') or None
            item.uso = primeira.get('uso') or None

        Defect.query.filter_by(estoque_uso_id=item.id).delete()
        defects = parse_estoque_defects(request.form)
        for d in defects:
            d.estoque_uso_id = item.id
        db.session.add_all(defects)
        db.session.commit()
        flash('Registro atualizado!', 'success')
        return redirect(url_for('estoque.detail', id=item.id))
    return render_template('estoque/form.html', item=item, **get_catalog_context())


@estoque_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    item = EstoqueUso.query.get_or_404(id)
    Defect.query.filter_by(estoque_uso_id=item.id).delete()
    db.session.delete(item)
    db.session.commit()
    flash('Registro excluído.', 'success')
    return redirect(url_for('estoque.index'))
