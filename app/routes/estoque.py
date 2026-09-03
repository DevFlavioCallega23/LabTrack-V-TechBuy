from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import EstoqueUso, Defect

estoque_bp = Blueprint('estoque', __name__, url_prefix='/estoque')


def master_required():
    if not current_user.is_master():
        flash('Acesso restrito ao Master.', 'danger')
        return redirect(url_for('main.dashboard'))
    return None


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
            return render_template('estoque/form.html', item=None)
        item = EstoqueUso(
            data_entrada=request.form.get('data_entrada', '').strip() or None,
            equipamento=equipamento,
            ns=request.form.get('ns', '').strip() or None,
            uso=request.form.get('uso', '').strip() or None,
            data_saida=request.form.get('data_saida', '').strip() or None,
            laudo=request.form.get('laudo', '').strip() or None,
            obs=request.form.get('obs', '').strip() or None,
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
    return render_template('estoque/form.html', item=None)


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
        item.data_entrada = request.form.get('data_entrada', '').strip() or None
        item.ns = request.form.get('ns', '').strip() or None
        item.uso = request.form.get('uso', '').strip() or None
        item.data_saida = request.form.get('data_saida', '').strip() or None
        item.laudo = request.form.get('laudo', '').strip() or None
        item.obs = request.form.get('obs', '').strip() or None

        Defect.query.filter_by(estoque_uso_id=item.id).delete()
        defects = parse_estoque_defects(request.form)
        for d in defects:
            d.estoque_uso_id = item.id
        db.session.add_all(defects)
        db.session.commit()
        flash('Registro atualizado!', 'success')
        return redirect(url_for('estoque.detail', id=item.id))
    return render_template('estoque/form.html', item=item)


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
