import json
import re
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Protocol, Component, Defect, User, WindowsKey
from app.models import TBRegistro, TBMaquina, TBTroca, TBDefeito, TBPassagem
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
        is_prebuilt = request_form.get(f'pe_switch_{unit}') == 'on'
        for i in range(len(types)):
            ct = types[i].strip()
            serial = serials[i].strip() if i < len(serials) else ''
            if ct:
                if not is_prebuilt:
                    if not serial:
                        continue
                    if len(serial) < 6:
                        flash(f'Nº de série deve ter no mínimo 6 caracteres.', 'danger')
                        return None
                model = models[i].strip() if i < len(models) else ''
                components.append(Component(
                    component_type=ct,
                    specification=model,
                    serial_number=serial or None,
                    unit=unit,
                    machine_name=machine_name,
                    sort_order=int(unit) * 100 + i,
                    is_prebuilt=is_prebuilt
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
    defeitos = request_form.getlist('rma_test_defeito[]')
    pedidos = request_form.getlist('rma_test_pedido[]')
    datas_compra = request_form.getlist('rma_test_data_compra[]')
    statuses = request_form.getlist('rma_test_status[]')
    items = []
    for i in range(len(comps)):
        if comps[i].strip():
            items.append({
                'component': comps[i].strip(),
                'model': models[i].strip() if i < len(models) else '',
                'serial': serials[i].strip() if i < len(serials) else '',
                'defeito': defeitos[i].strip() if i < len(defeitos) else '',
                'pedido': pedidos[i].strip() if i < len(pedidos) else '',
                'data_compra': datas_compra[i].strip() if i < len(datas_compra) else '',
                'status': statuses[i].strip() if i < len(statuses) else ''
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
    responsaveis = request_form.getlist('defect_resp[]')
    statuses = request_form.getlist('defect_status[]')
    maquinas = request_form.getlist('defect_maquina[]')
    for i in range(len(types)):
        if types[i].strip():
            defects.append(Defect(
                component_type=types[i].strip(),
                specification=models[i].strip() if i < len(models) else '',
                serial_number=serials[i].strip() if i < len(serials) else '',
                description=descs[i].strip() if i < len(descs) else '',
                responsavel=responsaveis[i].strip() if i < len(responsaveis) else '',
                defeito_status=statuses[i].strip() if i < len(statuses) else '',
                maquina=maquinas[i].strip() if i < len(maquinas) else '',
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
    mes_filter = request.args.get('mes', '')

    query = Protocol.query

    if search_mode == 'ns' and comp_type_filter and search:
        query = query.filter(
            Protocol.components.any(
                Component.component_type == comp_type_filter,
                Component.serial_number.ilike(f'%{search}%')
            )
        )
    elif search_mode == 'ns' and search:
        query = query.filter(
            db.or_(
                Protocol.components.any(Component.serial_number.ilike(f'%{search}%')),
                Protocol.components.any(Component.machine_ref_ns.ilike(f'%{search}%')),
                Protocol.defects.any(Defect.serial_number.ilike(f'%{search}%')),
                Protocol.rma_test_result.ilike(f'%{search}%'),
                Protocol.rma_equip_itens.ilike(f'%{search}%'),
                Protocol.rma_trocados.ilike(f'%{search}%'),
                Protocol.rma_passagens.ilike(f'%{search}%'),
                Protocol.power_cable_fonte_serial.ilike(f'%{search}%'),
                Protocol.ref_ns.ilike(f'%{search}%')
            )
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
    if mes_filter and re.fullmatch(r'\d{4}-\d{2}', mes_filter):
        try:
            ano = int(mes_filter[:4])
            mes = int(mes_filter[5:7])
            if 1 <= mes <= 12:
                inicio = datetime(ano, mes, 1)
                fim = datetime(ano + 1, 1, 1) if mes == 12 else datetime(ano, mes + 1, 1)
                query = query.filter(Protocol.entry_date >= inicio,
                                     Protocol.entry_date < fim)
        except ValueError:
            pass

    protocols = query.order_by(Protocol.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('protocols/list.html',
        protocols=protocols, search=search, search_mode=search_mode,
        comp_type_filter=comp_type_filter,
        type_filter=type_filter, status_filter=status_filter, mes_filter=mes_filter)

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
                defect_data=defect_data, win_keys_data=win_keys_data, machines=build_machine_names(comp_data))

        last = Protocol.query.order_by(Protocol.id.desc()).first()
        next_id = (last.id + 1) if last else 1
        year = datetime.utcnow().year
        protocol_number = f'PRO-{year}-{next_id:04d}'

        entry = form.entry_date.data
        exit = form.exit_date.data

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
            rma_equip_itens=rma_equip_itens,
            rma_test_result=rma_test_result,
            rma_trocados=parse_rma_trocados(request.form),
            rma_entry_date=form.rma_entry_date.data or None,
            rma_in_warranty=form.type.data == 'rma',
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
        comp_data = '{}'
        rma_comp_data = '{}'
        rma_test_data = '[]'
        rma_trocados_data = '[]'
        defect_data = None
        win_keys_data = '[]'

    return render_template('protocols/create.html', form=form, editing=False,
        comp_data=comp_data, rma_comp_data=rma_comp_data, rma_test_data=rma_test_data,
        rma_trocados_data=rma_trocados_data, defect_data=defect_data, win_keys_data=win_keys_data,
        machines=build_machine_names(comp_data))

@protocols_bp.route('/<int:id>')
@login_required
def detail_protocol(id):
    protocol = Protocol.query.get_or_404(id)
    return render_template('protocols/detail.html', protocol=protocol)

def build_component_data(protocol):
    """Build {unit: {name: str, components: [{type, serial, model}], is_prebuilt}} dict for editing."""
    data = {}
    for c in protocol.components:
        u = c.unit or '01'
        if u not in data:
            data[u] = {
                'name': c.machine_name or f'Máquina {u}',
                'components': [],
                'is_prebuilt': c.is_prebuilt or False
            }
        data[u]['components'].append({
            'type': c.component_type,
            'serial': c.serial_number or '',
            'model': c.specification or ''
        })
    return json.dumps(data)

def build_comp_data_from_form(request_form):
    """Build {unit: {name, components, is_prebuilt}} JSON from submitted form data (for preserving input on validation error)."""
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
            is_prebuilt = request_form.get(f'pe_switch_{unit}') == 'on'
            comps = []
            for i in range(len(types)):
                if types[i].strip():
                    comps.append({
                        'type': types[i].strip(),
                        'model': models[i].strip() if i < len(models) else '',
                        'serial': serials[i].strip() if i < len(serials) else ''
                    })
            data[unit] = {'name': machine_name, 'components': comps, 'is_prebuilt': is_prebuilt}
    return json.dumps(data)

def build_defect_data_from_form(request_form):
    """Build list of {type, serial, model, desc, resp, status, maquina} from submitted form data for preserving on validation error."""
    types = request_form.getlist('defect_type[]')
    serials = request_form.getlist('defect_serial[]')
    descs = request_form.getlist('defect_desc[]')
    models = request_form.getlist('defect_model[]')
    responsaveis = request_form.getlist('defect_resp[]')
    statuses = request_form.getlist('defect_status[]')
    maquinas = request_form.getlist('defect_maquina[]')
    defects = []
    for i in range(len(types)):
        if types[i].strip():
            defects.append({
                'type': types[i].strip(),
                'serial': serials[i].strip() if i < len(serials) else '',
                'model': models[i].strip() if i < len(models) else '',
                'desc': descs[i].strip() if i < len(descs) else '',
                'resp': responsaveis[i].strip() if i < len(responsaveis) else '',
                'status': statuses[i].strip() if i < len(statuses) else '',
                'maquina': maquinas[i].strip() if i < len(maquinas) else ''
            })
    return defects

def build_machine_names(comp_data):
    """Return a label for each machine in the lot, disambiguating duplicated names by unit."""
    if not comp_data:
        return []
    try:
        data = json.loads(comp_data) if isinstance(comp_data, str) else comp_data
    except (json.JSONDecodeError, TypeError):
        return []
    units = sorted(data.keys(), key=lambda x: (len(str(x)), str(x)))
    base = [(unit, (data[unit].get('name') or f'Máquina {unit}').strip()) for unit in units]
    counts = {}
    for _, name in base:
        counts[name] = counts.get(name, 0) + 1
    labels = []
    for unit, name in base:
        labels.append(f'{name} (unid. {unit})' if counts[name] > 1 else name)
    return labels

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
                rma_trocados_data=rma_trocados_data, defect_data=defect_data, win_keys_data=win_keys_data,
                machines=build_machine_names(comp_data))

        form.populate_obj(protocol)
        protocol.entry_date = parse_date_br(form.entry_date.data) if form.entry_date.data else datetime.utcnow()
        protocol.exit_date = parse_date_br(form.exit_date.data) if form.exit_date.data else None
        protocol.updated_at = datetime.utcnow()

        protocol.power_cable = request.form.get('power_cable', '').strip() or None
        protocol.power_cable_fonte_serial = request.form.get('power_cable_fonte_serial', '').strip() or None
        protocol.rma_in_warranty = form.type.data == 'rma'
        protocol.rma_passagens = request.form.get('rma_passagens_json', '').strip() or None
        protocol.original_order = form.original_order.data or None
        protocol.rma_extra_equip = form.rma_extra_equip.data or None
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
        rma_trocados_data=rma_trocados_data, defect_data=defect_data, win_keys_data=win_keys_data,
        machines=build_machine_names(comp_data))

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

    defect_totals = {}
    for d in Defect.query.all():
        defect_totals[d.component_type] = defect_totals.get(d.component_type, 0) + 1
    for p in protocols:
        if p.type in ('rma', 'servico') and p.rma_test_result:
            try:
                items = json.loads(p.rma_test_result)
                for item in items:
                    comp = item.get('component', '').strip()
                    if comp:
                        defect_totals[comp] = defect_totals.get(comp, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

    MESES_ABREV = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun',
                   7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}
    por_mes = {}
    for p in protocols:
        d = p.entry_date or p.created_at
        if d:
            por_mes[(d.year, d.month)] = por_mes.get((d.year, d.month), 0) + 1
    entradas_por_mes = [{
        'chave': f'{ano:04d}-{mes:02d}',
        'rotulo': f'{MESES_ABREV[mes]}/{ano}',
        'count': count
    } for (ano, mes), count in sorted(por_mes.items())]

    return render_template('protocols/report.html',
        protocols=protocols, total=total, by_type=by_type,
        defect_totals=defect_totals, entradas_por_mes=entradas_por_mes)

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

@protocols_bp.route('/<int:id>/status', methods=['POST'])
@login_required
def update_status(id):
    if not current_user.is_manager():
        return {'error': 'Sem permissão'}, 403
    protocol = Protocol.query.get_or_404(id)
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ('pendente', 'andamento', 'concluido', 'cancelado'):
        return {'error': 'Status inválido'}, 400
    protocol.status = new_status
    db.session.commit()
    return {'ok': True, 'status': new_status}

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

RESP_LABELS = {
    'loja': 'Loja',
    'cliente': 'Cliente',
    'terceiro': 'Terceiro'
}

COMP_LABELS = {
    'processador': 'Processador',
    'placa_mae': 'Placa-Mãe',
    'ram': 'RAM',
    'ssd': 'SSD',
    'hdd': 'HD (mecânico)',
    'fonte': 'Fonte',
    'monitor': 'Monitor',
    'outro': 'Outro'
}

DEFEITO_STATUS_LABELS = {
    'aguardando_peca': 'Aguardando peça',
    'em_teste': 'Em teste',
    'trocado': 'Trocado',
    'devolvido': 'Devolvido ao cliente',
    'concluido': 'Concluído'
}

def situacao_protocolo(p):
    """Classify a protocol into one of the defect situations."""
    if p.type in ('rma', 'servico'):
        return 'rma_garantia' if p.rma_in_warranty else 'rma_fora'
    if p.type == 'nao_comprado':
        return 'ntb'
    return 'venda'

def build_defeitos_agrupados():
    """Aggregate all defects grouped by situation."""
    grupos = {'rma_garantia': [], 'rma_fora': [], 'ntb': [], 'venda': []}
    protocols = Protocol.query.order_by(Protocol.created_at.desc()).all()
    for p in protocols:
        situacao = situacao_protocolo(p)
        # Defects from Defect table (Venda/PE/NTB and RMA if registered there)
        for d in p.defects:
            grupos[situacao].append({
                'fonte': 'defect',
                'defect_id': d.id,
                'component': d.component_type,
                'model': d.specification or '',
                'serial': d.serial_number or '',
                'desc': d.description or '',
                'responsavel': d.responsavel or '',
                'status': d.defeito_status or '',
                'maquina': d.maquina or '',
                'protocolo': p.protocol_number,
                'protocolo_id': p.id,
                'protocolo_status': p.status,
                'cliente': p.client_name or '',
                'data': p.entry_date,
                'tipo': p.type,
                'garantia': p.rma_in_warranty if p.type in ('rma', 'servico') else None
            })
        # Teste de Mesa items (RMA/NTB) NÃO aparecem em "Defeitos" — só no Rastreio de NS
        # if p.rma_test_result and p.type in ('rma', 'nao_comprado'):
        #     try:
        #         itens = json.loads(p.rma_test_result)
        #         for idx, item in enumerate(itens):
        #             if not item.get('component'):
        #                 continue
        #             grupos[situacao].append({
        #                 'fonte': 'teste',
        #                 'defect_id': None,
        #                 'teste_idx': idx,
        #                 'protocolo_id': p.id,
        #                 'protocolo_status': p.status,
        #                 'component': item.get('component', ''),
        #                 'model': item.get('model', ''),
        #                 'serial': item.get('serial', ''),
        #                 'desc': item.get('defeito', ''),
        #                 'responsavel': 'loja' if situacao == 'rma_garantia' else ('cliente' if situacao == 'rma_fora' else ''),
        #                 'status': item.get('status', ''),
        #                 'maquina': '',
        #                 'protocolo': p.protocol_number,
        #                 'cliente': p.client_name or '',
        #                 'data': p.entry_date,
        #                 'tipo': p.type,
        #                 'garantia': p.rma_in_warranty if p.type == 'rma' else None
        #             })
        #     except (json.JSONDecodeError, TypeError):
        #         pass
    return grupos

@protocols_bp.route('/defeitos')
@login_required
def defeitos():
    q = request.args.get('q', '').strip().lower()
    f_status = request.args.get('status', '')
    f_resp = request.args.get('resp', '')
    grupos = build_defeitos_agrupados()
    if q or f_status or f_resp:
        def filtro(item):
            if q:
                alvo = ' '.join(str(item.get(k, '') or '') for k in (
                    'component', 'model', 'serial', 'desc', 'protocolo', 'cliente', 'maquina')).lower()
                if q not in alvo:
                    return False
            if f_status and item.get('status', '') != f_status:
                return False
            if f_resp and item.get('responsavel', '') != f_resp:
                return False
            return True
        for chave in grupos:
            grupos[chave] = [it for it in grupos[chave] if filtro(it)]
    return render_template('defeitos.html', grupos=grupos,
        resp_labels=RESP_LABELS, status_labels=DEFEITO_STATUS_LABELS,
        q_filter=q, status_filtro=f_status, resp_filtro=f_resp)

@protocols_bp.route('/ns')
@login_required
def rastreio_ns():
    busca = request.args.get('busca', '').strip()
    resultados = []
    tb_resultados = []
    if busca:
        termo = busca.lower()
        for p in Protocol.query.order_by(Protocol.created_at.desc()).all():
            ocorrencias = []

            for c in p.components:
                if c.serial_number and termo in c.serial_number.lower():
                    ocorrencias.append({
                        'local': f'Componente {c.type_label()}' + (f' — {c.machine_name}' if c.machine_name else ''),
                        'valor': c.serial_number,
                        'detalhe': c.specification or ''
                    })
                if c.machine_ref_ns and termo in c.machine_ref_ns.lower():
                    ocorrencias.append({
                        'local': 'Referência da máquina' + (f' — {c.machine_name}' if c.machine_name else ''),
                        'valor': c.machine_ref_ns,
                        'detalhe': ''
                    })

            for d in p.defects:
                if d.serial_number and termo in d.serial_number.lower():
                    ocorrencias.append({
                        'local': f'Defeito — {d.type_label()}',
                        'valor': d.serial_number,
                        'detalhe': d.description or ''
                    })

            if p.power_cable_fonte_serial and termo in p.power_cable_fonte_serial.lower():
                ocorrencias.append({
                    'local': 'Fonte (serial do cabo de força)',
                    'valor': p.power_cable_fonte_serial,
                    'detalhe': ''
                })

            if p.ref_ns and termo in p.ref_ns.lower():
                ocorrencias.append({
                    'local': 'Referência NS do protocolo',
                    'valor': p.ref_ns,
                    'detalhe': ''
                })

            for campo, label in [('rma_equip_itens', 'Equipamento RMA'),
                                 ('rma_trocados', 'Equipamento mudado')]:
                raw = getattr(p, campo)
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                    for unit, info in data.items():
                        for comp in info.get('components', []):
                            if comp.get('serial') and termo in comp['serial'].lower():
                                ocorrencias.append({
                                    'local': f'{label} — {info.get("name", "Máquina")}',
                                    'valor': comp['serial'],
                                    'detalhe': comp.get('model') or ''
                                })
                except (json.JSONDecodeError, TypeError):
                    pass

            if p.rma_test_result:
                try:
                    for item in json.loads(p.rma_test_result):
                        if item.get('serial') and termo in item['serial'].lower():
                            ocorrencias.append({
                                'local': 'Teste de mesa',
                                'valor': item['serial'],
                                'detalhe': (COMP_LABELS.get(item.get('component', ''), item.get('component', '')))
                                        + (' — ' + item.get('defeito', '') if item.get('defeito') else '')
                                        + (f' — Ped.: {item.get("pedido")}' if item.get('pedido') else '')
                                        + (f' — Compra: {item.get("data_compra")}' if item.get('data_compra') else '')
                            })
                except (json.JSONDecodeError, TypeError):
                    pass

            if p.rma_passagens:
                try:
                    for pas in json.loads(p.rma_passagens):
                        if pas.get('ns') and termo in pas['ns'].lower():
                            ocorrencias.append({
                                'local': 'Passagem anterior'
                                            + (f' — protocolo {pas.get("protocolo")}' if pas.get('protocolo') else ''),
                                'valor': pas['ns'],
                                'detalhe': pas.get('pedido') or ''
                            })
                except (json.JSONDecodeError, TypeError):
                    pass

            if ocorrencias:
                resultados.append({
                    'protocolo': p,
                    'ocorrencias': ocorrencias
                })

        # Máquinas TechBuy (módulo do Master)
        for maq in TBMaquina.query.all():
            ocorrencias = []
            dono = maq.registro.nome if maq.registro else ''
            ident = maq.identificacao or 'Máquina'
            base_local = f'Máquinas TechBuy — {dono} — {ident}'
            for item in maq.get_ns_itens():
                if item.get('ns') and termo in item['ns'].lower():
                    ocorrencias.append({
                        'local': f'{base_local} — peça {COMP_LABELS.get(item.get("comp", ""), item.get("comp", ""))}',
                        'valor': item['ns'],
                        'detalhe': item.get('model') or ''
                    })
            for t in maq.trocas:
                if t.ns and termo in t.ns.lower():
                    ocorrencias.append({
                        'local': f'{base_local} — troca de {t.produto or "produto"}',
                        'valor': t.ns,
                        'detalhe': f'Data: {t.data or "-"}'
                    })
            for d in maq.defeitos:
                if d.ns and termo in d.ns.lower():
                    ocorrencias.append({
                        'local': f'{base_local} — defeito em {d.produto or "produto"}',
                        'valor': d.ns,
                        'detalhe': d.defeito or ''
                    })
            for pas in maq.passagens:
                if pas.ns and termo in pas.ns.lower():
                    ocorrencias.append({
                        'local': f'{base_local} — passagem de {pas.produto or "produto"}',
                        'valor': pas.ns,
                        'detalhe': pas.defeito or ''
                    })
            if ocorrencias:
                tb_resultados.append({
                    'maquina': maq,
                    'dono': dono,
                    'identificacao': maq.identificacao or 'Máquina',
                    'ocorrencias': ocorrencias
                })

    return render_template('protocols/ns.html', busca=busca, resultados=resultados,
        total_resultados=len(resultados), tb_resultados=tb_resultados)

@protocols_bp.route('/defeitos/<int:id>/status', methods=['POST'])
@login_required
def update_defeito_status(id):
    if not current_user.is_manager():
        return {'error': 'Sem permissão'}, 403
    defect = Defect.query.get_or_404(id)
    data = request.get_json()
    novo_status = data.get('status', '')
    if novo_status not in DEFEITO_STATUS_LABELS and novo_status not in ('', None):
        return {'error': 'Status inválido'}, 400
    defect.defeito_status = novo_status or None
    db.session.commit()
    return {'ok': True, 'status': defect.defeito_status}

@protocols_bp.route('/defeitos/teste/<int:id>/<int:idx>/status', methods=['POST'])
@login_required
def update_teste_status(id, idx):
    if not current_user.is_manager():
        return {'error': 'Sem permissão'}, 403
    protocol = Protocol.query.get_or_404(id)
    data = request.get_json()
    novo_status = data.get('status', '')
    if novo_status not in DEFEITO_STATUS_LABELS and novo_status not in ('', None):
        return {'error': 'Status inválido'}, 400
    try:
        itens = json.loads(protocol.rma_test_result) if protocol.rma_test_result else []
        if idx >= len(itens):
            return {'error': 'Item não encontrado'}, 404
        itens[idx]['status'] = novo_status or ''
        protocol.rma_test_result = json.dumps(itens)
        db.session.commit()
        return {'ok': True, 'status': novo_status}
    except (json.JSONDecodeError, TypeError):
        return {'error': 'Dados inválidos'}, 400
