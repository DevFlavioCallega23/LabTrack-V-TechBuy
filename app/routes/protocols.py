from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Protocol, Component, Defect, User
from app.forms import ProtocolForm, UserForm, CreateUserForm, MasterUserForm, MasterCreateUserForm, ChangePasswordForm

protocols_bp = Blueprint('protocols', __name__, url_prefix='/protocolos')

def parse_components(request_form):
    components = []
    types = request_form.getlist('comp_type[]')
    specs = request_form.getlist('comp_spec[]')
    serials = request_form.getlist('comp_serial[]')
    for i in range(len(types)):
        if types[i].strip():
            components.append(Component(
                component_type=types[i].strip(),
                specification=specs[i].strip() if i < len(specs) else '',
                serial_number=serials[i].strip() if i < len(serials) else '',
                sort_order=i
            ))
    return components

def parse_defects(request_form):
    defects = []
    types = request_form.getlist('defect_type[]')
    descs = request_form.getlist('defect_desc[]')
    for i in range(len(types)):
        if types[i].strip():
            defects.append(Defect(
                component_type=types[i].strip(),
                description=descs[i].strip() if i < len(descs) else '',
                sort_order=i
            ))
    return defects

@protocols_bp.route('/')
@login_required
def list_protocols():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    search_mode = request.args.get('search_mode', 'pedido')
    comp_type_filter = request.args.get('comp_type', '')
    type_filter = request.args.get('type', '')
    status_filter = request.args.get('status', '')

    query = Protocol.query

    if search_mode == 'ns' and comp_type_filter and search:
        query = query.join(Protocol.components).filter(
            Component.component_type == comp_type_filter,
            Component.serial_number.ilike(f'%{search}%')
        )
    elif search_mode == 'ns' and search:
        query = query.join(Protocol.components).filter(
            Component.serial_number.ilike(f'%{search}%')
        )
    elif search:
        query = query.filter(
            Protocol.order_number.ilike(f'%{search}%')
        )
    if type_filter:
        query = query.filter_by(type=type_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)

    protocols = query.order_by(Protocol.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('protocols/list.html',
        protocols=protocols, search=search, search_mode=search_mode,
        comp_type_filter=comp_type_filter,
        type_filter=type_filter, status_filter=status_filter)

@protocols_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def create_protocol():
    if not current_user.is_manager():
        flash('Você não tem permissão para criar protocolos.', 'danger')
        return redirect(url_for('protocols.list_protocols'))

    form = ProtocolForm()
    if form.validate_on_submit():
        last = Protocol.query.order_by(Protocol.id.desc()).first()
        next_id = (last.id + 1) if last else 1
        year = datetime.utcnow().year
        protocol_number = f'PRO-{year}-{next_id:04d}'

        entry = form.entry_date.data
        exit = form.exit_date.data

        protocol = Protocol(
            protocol_number=protocol_number,
            type=form.type.data,
            client_name=form.client_name.data,
            lote=form.lote.data,
            order_number=form.order_number.data,
            seller=form.seller.data or None,
            status=form.status.data,
            entry_date=datetime.combine(entry, datetime.min.time()) if entry else datetime.utcnow(),
            exit_date=datetime.combine(exit, datetime.min.time()) if exit else None,
            observations=form.observations.data,
            created_by=current_user.id
        )

        components = parse_components(request.form)
        protocol.components = components
        defects = parse_defects(request.form)
        protocol.defects = defects

        db.session.add(protocol)
        db.session.commit()
        flash(f'Protocolo {protocol_number} criado com sucesso!', 'success')
        return redirect(url_for('protocols.detail_protocol', id=protocol.id))

    return render_template('protocols/create.html', form=form, editing=False)

@protocols_bp.route('/<int:id>')
@login_required
def detail_protocol(id):
    protocol = Protocol.query.get_or_404(id)
    return render_template('protocols/detail.html', protocol=protocol)

@protocols_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def edit_protocol(id):
    if not current_user.is_manager():
        flash('Você não tem permissão para editar protocolos.', 'danger')
        return redirect(url_for('protocols.list_protocols'))

    protocol = Protocol.query.get_or_404(id)
    form = ProtocolForm(obj=protocol)
    if form.validate_on_submit():
        form.populate_obj(protocol)
        entry = form.entry_date.data
        exit = form.exit_date.data
        protocol.entry_date = datetime.combine(entry, datetime.min.time()) if entry else datetime.utcnow()
        protocol.exit_date = datetime.combine(exit, datetime.min.time()) if exit else None
        protocol.updated_at = datetime.utcnow()

        Component.query.filter_by(protocol_id=protocol.id).delete()
        components = parse_components(request.form)
        protocol.components = components
        Defect.query.filter_by(protocol_id=protocol.id).delete()
        defects = parse_defects(request.form)
        protocol.defects = defects

        db.session.commit()
        flash(f'Protocolo {protocol.protocol_number} atualizado!', 'success')
        return redirect(url_for('protocols.detail_protocol', id=protocol.id))

    form.entry_date.data = protocol.entry_date.date() if protocol.entry_date else date.today()
    form.exit_date.data = protocol.exit_date.date() if protocol.exit_date else None
    return render_template('protocols/create.html', form=form, editing=True, protocol=protocol)

@protocols_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def delete_protocol(id):
    if not current_user.is_master():
        flash('Apenas o Master pode excluir protocolos.', 'danger')
        return redirect(url_for('protocols.list_protocols'))

    protocol = Protocol.query.get_or_404(id)
    db.session.delete(protocol)
    db.session.commit()
    flash(f'Protocolo {protocol.protocol_number} excluído.', 'info')
    return redirect(url_for('protocols.list_protocols'))

@protocols_bp.route('/relatorio')
@login_required
def report():
    protocols = Protocol.query.order_by(Protocol.created_at.desc()).all()
    total = len(protocols)
    by_type = {}
    for p in protocols:
        by_type[p.type] = by_type.get(p.type, 0) + 1
    return render_template('protocols/report.html',
        protocols=protocols, total=total, by_type=by_type)

@protocols_bp.route('/usuarios')
@login_required
def list_users():
    if not current_user.is_master():
        flash('Acesso restrito ao Master.', 'danger')
        return redirect(url_for('main.dashboard'))
    users = User.query.all()
    return render_template('users.html', users=users)

@protocols_bp.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.is_master():
        flash('Acesso restrito ao Master.', 'danger')
        return redirect(url_for('main.dashboard'))
    form = MasterCreateUserForm() if current_user.is_master() else CreateUserForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data or f'{form.username.data}@labtrack.local',
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'Usuário {user.username} criado com sucesso!', 'success')
        return redirect(url_for('protocols.list_users'))
    return render_template('user_form.html', form=form, creating=True)

@protocols_bp.route('/minha-conta', methods=['GET', 'POST'])
@login_required
def minha_conta():
    form = UserForm(obj=current_user)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data or f'{form.username.data}@labtrack.local'
        db.session.commit()
        flash('Dados atualizados com sucesso!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('user_form.html', form=form, editing=True, current_user_page=True)

@protocols_bp.route('/minha-conta/alterar-senha', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Senha atual incorreta.', 'danger')
            return render_template('change_password.html', form=form)
        if form.new_password.data != form.confirm_password.data:
            flash('As novas senhas não conferem.', 'danger')
            return render_template('change_password.html', form=form)
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Senha alterada com sucesso!', 'success')
        return redirect(url_for('protocols.minha_conta'))
    return render_template('change_password.html', form=form)

@protocols_bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if not current_user.is_master():
        flash('Acesso restrito ao Master.', 'danger')
        return redirect(url_for('main.dashboard'))
    user = User.query.get_or_404(id)
    form = MasterUserForm(obj=user) if current_user.is_master() else UserForm(obj=user)
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data or f'{form.username.data}@labtrack.local'
        user.role = form.role.data
        db.session.commit()
        flash(f'Usuário {user.username} atualizado com sucesso!', 'success')
        return redirect(url_for('protocols.list_users'))
    return render_template('user_form.html', form=form, editing=True, user=user)
