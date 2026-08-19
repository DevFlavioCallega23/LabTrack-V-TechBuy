from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import TBRegistro, TBMaquina, TBTroca, TBDefeito, TBPassagem
import json

maquinas_bp = Blueprint('maquinas', __name__, url_prefix='/maquinas')


def master_required():
    if not current_user.is_master():
        flash('Acesso restrito ao Master.', 'danger')
        return redirect(url_for('main.dashboard'))
    return None


def get_or_abort_master():
    """Return redirect error if not master, otherwise None."""
    return master_required()


def parse_ns_itens():
    """Parse dynamic component rows (Componente | Configuração | NS) like the venda form."""
    tipos = request.form.getlist('comp_type[]')
    modelos = request.form.getlist('comp_model[]')
    nss = request.form.getlist('comp_ns[]')
    itens = []
    for i, tipo in enumerate(tipos):
        modelo = modelos[i].strip() if i < len(modelos) else ''
        ns = nss[i].strip() if i < len(nss) else ''
        if tipo or modelo or ns:
            itens.append({'comp': tipo, 'model': modelo, 'ns': ns})
    return json.dumps(itens, ensure_ascii=False)


@maquinas_bp.route('/')
@login_required
def index():
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    registros = TBRegistro.query.order_by(TBRegistro.nome.asc()).all()
    return render_template('maquinas/index.html', registros=registros)


@maquinas_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        if not nome:
            flash('Informe o nome da pessoa.', 'warning')
            return render_template('maquinas/registro_form.html', registro=None)
        registro = TBRegistro(nome=nome, data=request.form.get('data', '').strip() or None)
        db.session.add(registro)
        db.session.commit()
        flash(f'Registro de {nome} criado com sucesso!', 'success')
        return redirect(url_for('maquinas.detail', id=registro.id))
    return render_template('maquinas/registro_form.html', registro=None)


@maquinas_bp.route('/<int:id>')
@login_required
def detail(id):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    registro = TBRegistro.query.get_or_404(id)
    return render_template('maquinas/detail.html', registro=registro)


@maquinas_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    registro = TBRegistro.query.get_or_404(id)
    if request.method == 'POST':
        registro.nome = request.form.get('nome', '').strip()
        registro.data = request.form.get('data', '').strip() or None
        db.session.commit()
        flash(f'Registro de {registro.nome} atualizado!', 'success')
        return redirect(url_for('maquinas.detail', id=registro.id))
    return render_template('maquinas/registro_form.html', registro=registro)


@maquinas_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    registro = TBRegistro.query.get_or_404(id)
    nome = registro.nome
    db.session.delete(registro)
    db.session.commit()
    flash(f'Registro de {nome} excluído.', 'success')
    return redirect(url_for('maquinas.index'))


@maquinas_bp.route('/<int:id>/maquina/novo', methods=['GET', 'POST'])
@login_required
def maquina_novo(id):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    registro = TBRegistro.query.get_or_404(id)
    if request.method == 'POST':
        maquina = TBMaquina(
            registro_id=registro.id,
            identificacao=request.form.get('identificacao', '').strip() or None,
            ns_itens=parse_ns_itens() or None,
        )
        db.session.add(maquina)
        db.session.commit()
        flash('Máquina adicionada!', 'success')
        return redirect(url_for('maquinas.detail', id=registro.id))
    return render_template('maquinas/maquina_form.html', registro=registro, maquina=None)


@maquinas_bp.route('/maquina/<int:mid>', methods=['GET', 'POST'])
@login_required
def maquina_editar(mid):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    maquina = TBMaquina.query.get_or_404(mid)
    if request.method == 'POST':
        maquina.identificacao = request.form.get('identificacao', '').strip() or None
        maquina.ns_itens = parse_ns_itens() or None
        db.session.commit()
        flash('Máquina atualizada!', 'success')
        return redirect(url_for('maquinas.detail', id=maquina.registro_id))
    return render_template('maquinas/maquina_form.html', registro=maquina.registro, maquina=maquina)


@maquinas_bp.route('/maquina/<int:mid>/excluir', methods=['POST'])
@login_required
def maquina_excluir(mid):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    maquina = TBMaquina.query.get_or_404(mid)
    registro_id = maquina.registro_id
    db.session.delete(maquina)
    db.session.commit()
    flash('Máquina excluída.', 'success')
    return redirect(url_for('maquinas.detail', id=registro_id))


@maquinas_bp.route('/maquina/<int:mid>/troca', methods=['POST'])
@login_required
def troca_novo(mid):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    maquina = TBMaquina.query.get_or_404(mid)
    produto = request.form.get('produto', '').strip()
    ns = request.form.get('ns', '').strip()
    if produto or ns:
        db.session.add(TBTroca(
            maquina_id=maquina.id,
            data=request.form.get('data', '').strip() or None,
            produto=produto or None,
            ns=ns or None,
        ))
        db.session.commit()
        flash('Troca registrada!', 'success')
    else:
        flash('Informe produto ou NS da troca.', 'warning')
    return redirect(url_for('maquinas.detail', id=maquina.registro_id))


@maquinas_bp.route('/troca/<int:tid>/excluir', methods=['POST'])
@login_required
def troca_excluir(tid):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    troca = TBTroca.query.get_or_404(tid)
    registro_id = troca.maquina.registro_id
    db.session.delete(troca)
    db.session.commit()
    flash('Troca excluída.', 'success')
    return redirect(url_for('maquinas.detail', id=registro_id))


@maquinas_bp.route('/maquina/<int:mid>/defeito', methods=['POST'])
@login_required
def defeito_novo(mid):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    maquina = TBMaquina.query.get_or_404(mid)
    produto = request.form.get('produto', '').strip()
    ns = request.form.get('ns', '').strip()
    defeito = request.form.get('defeito', '').strip()
    if produto or ns or defeito:
        db.session.add(TBDefeito(
            maquina_id=maquina.id,
            data=request.form.get('data', '').strip() or None,
            produto=produto or None,
            ns=ns or None,
            defeito=defeito,
        ))
        db.session.commit()
        flash('Defeito registrado!', 'success')
    else:
        flash('Preencha os dados do defeito.', 'warning')
    return redirect(url_for('maquinas.detail', id=maquina.registro_id))


@maquinas_bp.route('/defeito/<int:did>/excluir', methods=['POST'])
@login_required
def defeito_excluir(did):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    defeito = TBDefeito.query.get_or_404(did)
    registro_id = defeito.maquina.registro_id
    db.session.delete(defeito)
    db.session.commit()
    flash('Defeito excluído.', 'success')
    return redirect(url_for('maquinas.detail', id=registro_id))


@maquinas_bp.route('/maquina/<int:mid>/passagem', methods=['POST'])
@login_required
def passagem_novo(mid):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    maquina = TBMaquina.query.get_or_404(mid)
    produto = request.form.get('produto', '').strip()
    ns = request.form.get('ns', '').strip()
    defeito = request.form.get('defeito', '').strip()
    if produto or ns or defeito:
        db.session.add(TBPassagem(
            maquina_id=maquina.id,
            data=request.form.get('data', '').strip() or None,
            produto=produto or None,
            ns=ns or None,
            defeito=defeito,
        ))
        db.session.commit()
        flash('Passagem registrada!', 'success')
    else:
        flash('Preencha os dados da passagem.', 'warning')
    return redirect(url_for('maquinas.detail', id=maquina.registro_id))


@maquinas_bp.route('/passagem/<int:pid>/excluir', methods=['POST'])
@login_required
def passagem_excluir(pid):
    bloqueio = get_or_abort_master()
    if bloqueio:
        return bloqueio
    passagem = TBPassagem.query.get_or_404(pid)
    registro_id = passagem.maquina.registro_id
    db.session.delete(passagem)
    db.session.commit()
    flash('Passagem excluída.', 'success')
    return redirect(url_for('maquinas.detail', id=registro_id))