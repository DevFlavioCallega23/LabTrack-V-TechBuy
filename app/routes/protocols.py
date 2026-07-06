from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Protocol, User
from app.forms import ProtocolForm, UserForm

protocols_bp = Blueprint('protocols', __name__, url_prefix='/protocolos')

@protocols_bp.route('/')
@login_required
def list_protocols():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    type_filter = request.args.get('type', '')
    status_filter = request.args.get('status', '')

    query = Protocol.query

    if search:
        query = query.filter(
            db.or_(
                Protocol.protocol_number.ilike(f'%{search}%'),
                Protocol.client_name.ilike(f'%{search}%'),
                Protocol.serial_number.ilike(f'%{search}%'),
                Protocol.order_number.ilike(f'%{search}%'),
                Protocol.observations.ilike(f'%{search}%')
            )
        )
    if type_filter:
        query = query.filter_by(type=type_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)

    protocols = query.order_by(Protocol.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('protocols/list.html',
        protocols=protocols, search=search,
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
            contact=form.contact.data,
            serial_number=form.serial_number.data,
            order_number=form.order_number.data,
            brand=form.brand.data,
            model=form.model.data,
            status=form.status.data,
            entry_date=datetime.combine(entry, datetime.min.time()) if entry else datetime.utcnow(),
            exit_date=datetime.combine(exit, datetime.min.time()) if exit else None,
            observations=form.observations.data,
            created_by=current_user.id
        )
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
        db.session.commit()
        flash(f'Protocolo {protocol.protocol_number} atualizado!', 'success')
        return redirect(url_for('protocols.detail_protocol', id=protocol.id))

    form.entry_date.data = protocol.entry_date.date() if protocol.entry_date else date.today()
    form.exit_date.data = protocol.exit_date.date() if protocol.exit_date else None
    return render_template('protocols/create.html', form=form, editing=True, protocol=protocol)

@protocols_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def delete_protocol(id):
    if not current_user.is_admin():
        flash('Apenas administradores podem excluir protocolos.', 'danger')
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
    if not current_user.is_admin():
        flash('Acesso restrito a administradores.', 'danger')
        return redirect(url_for('main.dashboard'))
    users = User.query.all()
    return render_template('users.html', users=users)

@protocols_bp.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.is_admin():
        flash('Acesso restrito a administradores.', 'danger')
        return redirect(url_for('main.dashboard'))
    form = UserForm()
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
    return render_template('user_form.html', form=form)
