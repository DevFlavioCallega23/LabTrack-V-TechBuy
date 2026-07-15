import json
import re
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Protocol, Component, Defect, User, WindowsKey
from app.forms import ProtocolForm, UserForm, CreateUserForm, MasterUserForm, MasterCreateUserForm, ChangePasswordForm
from sqlalchemy import func

protocols_bp = Blueprint('protocols', __name__, url_prefix='/protocolos')

def parse_date_br(text):
    if not text or not text.strip():
        return None
    text = text.strip().replace('/', '-')
    for fmt in ['%d-%m-%Y', '%d-%m-%y', '%Y-%m-%d']:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None

def parse_int_or_none(val):
    if not val or not str(val).strip():
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

def parse_components(request_form):
    components = []
    seen_units = set()
    for key in request_form.keys():
        if key.startswith('comp_type_') and key.endswith('[]'):
            unit = key[len('comp_type_'):-2]
            seen_units.add(unit)
    for unit in sorted(seen_units):
        types = request_form.getlist(f'comp_type_{unit}[]')
        models = request_form.getlist(f'comp_model_{unit}[]')
        serials = request_form.getlist(f'comp_serial_{unit}[]')
        machine_name = request_form.get(f'machine_name_{unit}', '').strip() or f'Máquina {unit}'
        for i in range(len(types)):
            ct = types[i].strip()
            serial = serials[i].strip() if i < len(serials) else ''
            if ct and serial:
                if len(serial) < 6:
                    flash(f'Nº de série deve ter no mínimo 6 caracteres.', 'danger')
                    return None
                model = models[i].strip() if i < len(models) else ''
                components.append(Component(
                    component_type=ct,
                    specification=model,
                    serial_number=serial,
                    unit=unit,
                    machine_name=machine_name,
                    sort_order=int(unit) * 100 + i
                ))
    return components

def parse_rma_equip(request_form):
    """Parse RMA equipment JSON from form."""
    raw = request_form.get('rma_equip_json', '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        # Remove empty entries (no components)
        cleaned = {k: v for k, v in data.items() if v.get('components')}
        return json.dumps(cleaned) if cleaned else None
    except (json.JSONDecodeError, TypeError):
        return None

def build_rma_equip_data(protocol):
    """Build RMA equipment JSON from protocol for editing."""
    if not protocol.rma_equip_itens:
        return '{}'
    try:
        data = json.loads(protocol.rma_equip_itens)
        return json.dumps(data)
    except (json.JSONDecodeError, TypeError):
        return '{}'

def build_rma_equip_data_from_form(request_form):
    """Build RMA equipment JSON from submitted form data for preserving on validation error."""
    data = {}
    for key in request_form.keys():
        if key.startswith('rma_comp_type_') and key.endswith('[]'):
            unit = key[len('rma_comp_type_'):-2]
            if unit in data:
                continue
            types = request_form.getlist(f'rma_comp_type_{unit}[]')
            models = request_form.getlist(f'rma_comp_model_{unit}[]')
            serials = request_form.getlist(f'rma_comp_serial_{unit}[]')
            machine_name = request_form.get(f'rma_machine_name_{unit}', '').strip() or f'Computador {unit}'
            comps = []
            for i in range(len(types)):
                if types[i].strip():
                    comps.append({
                        'type': types[i].strip(),
                        'model': models[i].strip() if i < len(models) else '',
                        'serial': serials[i].strip() if i < len(serials) else ''
                    })
            data[unit] = {'name': machine_name, 'components': comps}
    return json.dumps(data)

def parse_rma_test_items(request_form):
    """Parse RMA test items from JSON hidden field."""
    raw = request_form.get('rma_test_json', '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return json.dumps(data)
    except (json.JSONDecodeError, TypeError):
        return None

def build_rma_test_data_from_form(request_form):
    """Build RMA test items from submitted form data for preserving on validation error."""
    comps = request_form.getlist('rma_test_comp[]')
    models = request_form.getlist('rma_test_model[]')
    serials = request_form.getlist('rma_test_serial[]')
    pedidos = request_form.getlist('rma_test_pedido[]')
    garantias = request_form.getlist('rma_test_garantia[]')
    defeitos = request_form.getlist('rma_test_defeito[]')
    items = []
    for i in range(len(comps)):
        if comps[i].strip():
            items.append({
                'component': comps[i].strip(),
                'model': models[i].strip() if i < len(models) else '',
                'serial': serials[i].strip() if i < len(serials) else '',
                'pedido': pedidos[i].strip() if i < len(pedidos) else '',
                'garantia': garantias[i] == '1' if i < len(garantias) else False,
                'defeito': defeitos[i].strip() if i < len(defeitos) else ''
            })
    return json.dumps(items) if items else None

def parse_rma_trocados(request_form):
    """Parse Equipamentos Mudados from JSON hidden field (card-based structure)."""
    raw = request_form.get('rma_trocados_json', '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        cleaned = {k: v for k, v in data.items() if v.get('components')}
        return json.dumps(cleaned) if cleaned else None
    except (json.JSONDecodeError, TypeError):
        return None

def build_rma_trocados_data_from_form(request_form):
    """Build Equipamentos Mudados from submitted form data for preserving on validation error."""
    data = {}
    for key in request_form.keys():
        if key.startswith('trocado_comp_type_') and key.endswith('[]'):
            unit = key[len('trocado_comp_type_'):-2]
            if unit in data:
                continue
            types = request_form.getlist(f'trocado_comp_type_{unit}[]')
            models = request_form.getlist(f'trocado_comp_model_{unit}[]')
            serials = request_form.getlist(f'trocado_comp_serial_{unit}[]')
            machine_name = request_form.get(f'trocado_machine_name_{unit}', '').strip() or f'Computador {unit}'
            comps = []
            for i in range(len(types)):
                if types[i].strip():
                    comps.append({
                        'type': types[i].strip(),
                        'model': models[i].strip() if i < len(models) else '',
                        'serial': serials[i].strip() if i < len(serials) else ''
                    })
            data[unit] = {'name': machine_name, 'components': comps}
    return json.dumps(data)

def parse_windows_keys(request_form):
    raw = request_form.get('windows_keys_json', '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return [WindowsKey(
            chave=item.get('chave', ''),
            fonte=item.get('fonte', ''),
            ativo=item.get('ativo', False),
            sort_order=i
        ) for i, item in enumerate(data)]
    except (json.JSONDecodeError, TypeError):
        return None

def build_windows_key_data_from_form(request_form):
    raw = request_form.get('windows_keys_json', '').strip()
    if raw:
        return raw
    return '[]'

def build_windows_key_data(protocol):
    if protocol.windows_keys:
        return json.dumps([{
            'chave': k.chave or '',
            'fonte': k.fonte or '',
            'ativo': k.ativo
        } for k in protocol.windows_keys])
    return '[]'

def parse_defects(request_form):
    defects = []
    types = request_form.getlist('defect_type[]')
    descs = request_form.getlist('defect_desc[]')
    serials = request_form.getlist('defect_serial[]')
    models = request_form.getlist('defect_model[]')
    for i in range(len(types)):
        if types[i].strip():
            defects.append(Defect(
                component_type=types[i].strip(),
                specification=models[i].strip() if i < len(models) else '',
                serial_number=serials[i].strip() if i < len(serials) else '',
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
    elif search_mode == 'cliente' and search:
        query = query.filter(
            Protocol.client_name.ilike(f'%{search}%')
        )
    elif search:
        query = query.filter(
            db.or_(
                Protocol.order_number.ilike(f'%{search}%'),
                Protocol.original_order.ilike(f'%{search}%')
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
        components = parse_components(request.form)
        if components is None:
            comp_data = build_comp_data_from_form(request.form)
            rma_comp_data = build_rma_equip_data_from_form(request.form)
            rma_test_data = build_rma_test_data_from_form(request.form)
            rma_trocados_data = build_rma_trocados_data_from_form(request.form)
            form.entry_date.data = request.form.get('entry_date', '')
            form.exit_date.data = request.form.get('exit_date', '')
            defect_data = build_defect_data_from_form(request.form)
            win_keys_data = build_windows_key_data_from_form(request.form)
            return render_template('protocols/create.html', form=form, editing=False, comp_data=comp_data,
                rma_comp_data=rma_comp_data, rma_test_data=rma_test_data, rma_trocados_data=rma_trocados_data,
                defect_data=defect_data, win_keys_data=win_keys_data)

        last = Protocol.query.order_by(Protocol.id.desc()).first()
        next_id = (last.id + 1) if last else 1
        year = datetime.utcnow().year
        protocol_number = f'PRO-{year}-{next_id:04d}'

        entry = form.entry_date.data
        exit = form.exit_date.data

        os_number = None
        if form.type.data in ('rma',):
            last_os = Protocol.query.filter(
                Protocol.os_number.isnot(None),
                Protocol.os_number.like('OS-%')
            ).order_by(Protocol.id.desc()).first()
            next_os = int(last_os.os_number.split('-')[-1]) + 1 if last_os and last_os.os_number else 1
            os_number = f'OS-{year}-{next_os:04d}'

        power_cable = request.form.get('power_cable', '').strip() or None
        power_cable_fonte = request.form.get('power_cable_fonte_serial', '').strip() or None
        rma_passagens = request.form.get('rma_passagens_json', '').strip() or None
        rma_equip_itens = parse_rma_equip(request.form)
        rma_test_result = parse_rma_test_items(request.form)

        protocol = Protocol(
            protocol_number=protocol_number,
            type=form.type.data,
            client_name=form.client_name.data,
            lote=form.lote.data,
            order_number=form.order_number.data,
            os_number=os_number,
            seller=form.seller.data or None,
            status=form.status.data,
            entry_date=parse_date_br(form.entry_date.data) if form.entry_date.data else datetime.utcnow(),
            exit_date=parse_date_br(form.exit_date.data) if form.exit_date.data else None,
            observations=form.observations.data,
            power_cable=power_cable,
            power_cable_fonte_serial=power_cable_fonte,
            ref_ns=form.ref_ns.data or None,
            base_defect=form.base_defect.data or None,
            original_order=form.original_order.data or None,
            rma_extra_equip=form.rma_extra_equip.data or None,
            rma_extra_qtd=parse_int_or_none(request.form.get('rma_extra_qtd')),
            rma_equip_itens=rma_equip_itens,
            rma_test_result=rma_test_result,
            rma_trocados=parse_rma_trocados(request.form),
            rma_entry_date=form.rma_entry_date.data or None,
            rma_in_warranty=request.form.get('rma_in_warranty') == '1',
            rma_passagens=rma_passagens,
            created_by=current_user.id
        )

        protocol.components = components
        defects = parse_defects(request.form)
        protocol.defects = defects
        windows_keys = parse_windows_keys(request.form)
        if windows_keys:
            protocol.windows_keys = windows_keys

        db.session.add(protocol)
        db.session.commit()
        flash(f'Protocolo {protocol_number} criado com sucesso!', 'success')
        return redirect(url_for('protocols.detail_protocol', id=protocol.id))

    return render_template('protocols/create.html', form=form, editing=False, comp_data='{}', rma_comp_data='{}', rma_test_data='[]', rma_trocados_data='[]', win_keys_data='[]')

@protocols_bp.route('/<int:id>')
@login_required
def detail_protocol(id):
    protocol = Protocol.query.get_or_404(id)
    return render_template('protocols/detail.html', protocol=protocol)

def build_component_data(protocol):
    """Build {unit: {name: str, components: [{type, serial, model}]}} dict for editing."""
    data = {}
    for c in protocol.components:
        u = c.unit or '01'
        if u not in data:
            data[u] = {'name': c.machine_name or f'Máquina {u}', 'components': []}
        data[u]['components'].append({
            'type': c.component_type,
            'serial': c.serial_number or '',
            'model': c.specification or ''
        })
    return json.dumps(data)

def build_comp_data_from_form(request_form):
    """Build {unit: {name, components}} JSON from submitted form data (for preserving input on validation error)."""
    data = {}
    for key in request_form.keys():
        if key.startswith('comp_type_') and key.endswith('[]'):
            unit = key[len('comp_type_'):-2]
            if unit in data:
                continue
            types = request_form.getlist(f'comp_type_{unit}[]')
            models = request_form.getlist(f'comp_model_{unit}[]')
            serials = request_form.getlist(f'comp_serial_{unit}[]')
            machine_name = request_form.get(f'machine_name_{unit}', '').strip() or f'Máquina {unit}'
            comps = []
            for i in range(len(types)):
                if types[i].strip():
                    comps.append({
                        'type': types[i].strip(),
                        'model': models[i].strip() if i < len(models) else '',
                        'serial': serials[i].strip() if i < len(serials) else ''
                    })
            data[unit] = {'name': machine_name, 'components': comps}
    return json.dumps(data)

def build_defect_data_from_form(request_form):
    """Build list of {type, serial, model, desc} from submitted form data for preserving on validation error."""
    types = request_form.getlist('defect_type[]')
    serials = request_form.getlist('defect_serial[]')
    descs = request_form.getlist('defect_desc[]')
    models = request_form.getlist('defect_model[]')
    defects = []
    for i in range(len(types)):
        if types[i].strip():
            defects.append({
                'type': types[i].strip(),
                'serial': serials[i].strip() if i < len(serials) else '',
                'model': models[i].strip() if i < len(models) else '',
                'desc': descs[i].strip() if i < len(descs) else ''
            })
    return defects

@protocols_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def edit_protocol(id):
    if not current_user.is_manager():
        flash('Você não tem permissão para editar protocolos.', 'danger')
        return redirect(url_for('protocols.list_protocols'))

    protocol = Protocol.query.get_or_404(id)
    form = ProtocolForm(obj=protocol)
    if form.validate_on_submit():
        components = parse_components(request.form)
        if components is None:
            comp_data = build_comp_data_from_form(request.form)
            rma_comp_data = build_rma_equip_data_from_form(request.form)
            rma_test_data = build_rma_test_data_from_form(request.form)
            rma_trocados_data = build_rma_trocados_data_from_form(request.form)
            form.entry_date.data = request.form.get('entry_date', '')
            form.exit_date.data = request.form.get('exit_date', '')
            defect_data = build_defect_data_from_form(request.form)
            win_keys_data = build_windows_key_data_from_form(request.form)
            return render_template('protocols/create.html', form=form, editing=True, protocol=protocol,
                comp_data=comp_data, rma_comp_data=rma_comp_data, rma_test_data=rma_test_data,
                rma_trocados_data=rma_trocados_data, defect_data=defect_data, win_keys_data=win_keys_data)

        form.populate_obj(protocol)
        protocol.entry_date = parse_date_br(form.entry_date.data) if form.entry_date.data else datetime.utcnow()
        protocol.exit_date = parse_date_br(form.exit_date.data) if form.exit_date.data else None
        protocol.updated_at = datetime.utcnow()

        protocol.power_cable = request.form.get('power_cable', '').strip() or None
        protocol.power_cable_fonte_serial = request.form.get('power_cable_fonte_serial', '').strip() or None
        protocol.rma_in_warranty = request.form.get('rma_in_warranty') == '1'
        protocol.rma_passagens = request.form.get('rma_passagens_json', '').strip() or None
        protocol.original_order = form.original_order.data or None
        protocol.rma_extra_equip = form.rma_extra_equip.data or None
        protocol.rma_extra_qtd = parse_int_or_none(request.form.get('rma_extra_qtd'))
        protocol.rma_equip_itens = parse_rma_equip(request.form)
        protocol.rma_test_result = parse_rma_test_items(request.form)
        protocol.rma_trocados = parse_rma_trocados(request.form)
        protocol.rma_entry_date = form.rma_entry_date.data or None

        Component.query.filter_by(protocol_id=protocol.id).delete()
        protocol.components = components
        Defect.query.filter_by(protocol_id=protocol.id).delete()
        defects = parse_defects(request.form)
        protocol.defects = defects
        WindowsKey.query.filter_by(protocol_id=protocol.id).delete()
        windows_keys = parse_windows_keys(request.form)
        if windows_keys:
            protocol.windows_keys = windows_keys

        db.session.commit()
        flash(f'Protocolo {protocol.protocol_number} atualizado!', 'success')
        return redirect(url_for('protocols.detail_protocol', id=protocol.id))

    if request.method == 'POST':
        flash(f'Não foi possível salvar. Verifique os campos obrigatórios.', 'warning')
        comp_data = build_comp_data_from_form(request.form)
        rma_comp_data = build_rma_equip_data_from_form(request.form)
        rma_test_data = build_rma_test_data_from_form(request.form)
        rma_trocados_data = build_rma_trocados_data_from_form(request.form)
        defect_data = build_defect_data_from_form(request.form)
        win_keys_data = build_windows_key_data_from_form(request.form)
        form.entry_date.data = request.form.get('entry_date', '')
        form.exit_date.data = request.form.get('exit_date', '')
        form.rma_entry_date.data = request.form.get('rma_entry_date', '')
    else:
        comp_data = build_component_data(protocol)
        rma_comp_data = build_rma_equip_data(protocol)
        rma_test_data = protocol.rma_test_result or '[]'
        rma_trocados_data = protocol.rma_trocados or '[]'
        defect_data = None
        win_keys_data = build_windows_key_data(protocol)
        form.entry_date.data = protocol.entry_date.strftime('%d/%m/%Y') if protocol.entry_date else ''
        form.exit_date.data = protocol.exit_date.strftime('%d/%m/%Y') if protocol.exit_date else ''
        form.rma_entry_date.data = protocol.rma_entry_date or ''
    return render_template('protocols/create.html', form=form, editing=True, protocol=protocol,
        comp_data=comp_data, rma_comp_data=rma_comp_data, rma_test_data=rma_test_data,
        rma_trocados_data=rma_trocados_data, defect_data=defect_data, win_keys_data=win_keys_data)

@protocols_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def delete_protocol(id):
    if not current_user.is_master():
        flash('Acesso restrito ao Master.', 'danger')
        return redirect(url_for('protocols.list_protocols'))
    protocol = Protocol.query.get_or_404(id)
    protocol_number = protocol.protocol_number
    Component.query.filter_by(protocol_id=protocol.id).delete()
    Defect.query.filter_by(protocol_id=protocol.id).delete()
    db.session.delete(protocol)
    db.session.commit()
    flash(f'Protocolo {protocol_number} excluído com sucesso!', 'success')
    return redirect(url_for('protocols.list_protocols'))

@protocols_bp.route('/relatorio')
@login_required
def report():
    protocols = Protocol.query.order_by(Protocol.created_at.desc()).all()
    total = len(protocols)
    by_type = {}
    for p in protocols:
        by_type[p.type] = by_type.get(p.type, 0) + 1

    defect_stats = db.session.query(
        Defect.component_type,
        Defect.serial_number,
        Defect.description,
        Protocol.client_name,
        Protocol.entry_date
    ).join(Protocol).order_by(Protocol.entry_date.desc()).all()

    defect_totals = {}
    for d in defect_stats:
        defect_totals[d.component_type] = defect_totals.get(d.component_type, 0) + 1

    return render_template('protocols/report.html',
        protocols=protocols, total=total, by_type=by_type,
        defect_stats=defect_stats, defect_totals=defect_totals)

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
