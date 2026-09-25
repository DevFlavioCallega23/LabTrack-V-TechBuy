import json
import re
import io
import os
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, send_file, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.decorators import master_required
from app.models import Protocol, Component, Defect, WindowsKey, Produto
from app.forms import ProtocolForm
from app.labels import (
    TEMPO_LABELS,
)

from app.routes.protocols import protocols_bp
from app.routes.protocols.helpers import (
    gerar_numero_protocolo, parse_date_br, build_validation_messages, parse_components,
    parse_power_cables, parse_rma_equip, build_rma_equip_data, build_rma_equip_data_from_form,
    parse_rma_test_items, build_rma_test_data_from_form, parse_rma_trocados,
    build_rma_trocados_data_from_form, parse_windows_keys, build_windows_key_data_from_form,
    build_windows_key_data, parse_defects, get_incomplete_fields,
)

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
    incompletos_filter = request.args.get('incompletos', '')

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

    all_protocols = Protocol.query.all()
    incomplete_ids = [p.id for p in all_protocols if get_incomplete_fields(p)]
    incomplete_count = len(incomplete_ids)

    if incompletos_filter:
        if incomplete_ids:
            query = query.filter(Protocol.id.in_(incomplete_ids))
        else:
            query = query.filter(db.false())

    protocols = query.order_by(Protocol.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    incomplete_map = {}
    for p in protocols.items:
        if p.id in incomplete_ids:
            incomplete_map[p.id] = get_incomplete_fields(p)

    return render_template('protocols/list.html',
        protocols=protocols, search=search, search_mode=search_mode,
        comp_type_filter=comp_type_filter,
        type_filter=type_filter, status_filter=status_filter, mes_filter=mes_filter,
        incomplete_map=incomplete_map, incomplete_count=incomplete_count,
        incompletos_filter=incompletos_filter)

@protocols_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def create_protocol():
    if not current_user.is_manager():
        flash('Você não tem permissão para criar protocolos.', 'danger')
        return redirect(url_for('protocols.list_protocols'))

    form = ProtocolForm()
    if form.validate_on_submit():
        components = parse_components(request.form, form.type.data)
        if not form.type.data:
            msgs = ['O campo Tipo de Protocolo é obrigatório.']
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'ok': False, 'errors': msgs})
            for msg in msgs:
                flash(msg, 'warning')
            return redirect(url_for('protocols.create_protocol'))

        protocol_number = gerar_numero_protocolo()

        entry = form.entry_date.data
        exit = form.exit_date.data

        rma_passagens = request.form.get('rma_passagens_json', '').strip() or None
        rma_equip_itens = parse_rma_equip(request.form)
        rma_test_result = parse_rma_test_items(request.form)

        protocol = Protocol(
            protocol_number=protocol_number,
            type=form.type.data,
            venda_pe=bool(form.venda_pe.data) if form.type.data == 'venda' else False,
            client_name=form.client_name.data,
            lote=form.lote.data,
            order_number=form.order_number.data,
            seller=form.seller.data or None,
            status=form.status.data,
            entry_date=parse_date_br(form.entry_date.data) if form.entry_date.data else datetime.utcnow(),
            exit_date=parse_date_br(form.exit_date.data) if form.exit_date.data else None,
            observations=form.observations.data,
            ref_ns=form.ref_ns.data or None,
            base_defect=form.base_defect.data or None,
            original_order=form.original_order.data or None,
            rma_extra_equip=form.rma_extra_equip.data or None,
            rma_equip_itens=rma_equip_itens,
            rma_test_result=rma_test_result,
            rma_trocados=parse_rma_trocados(request.form),
            rma_entry_date=parse_date_br(form.rma_entry_date.data) if form.rma_entry_date.data else None,
            rma_in_warranty=form.type.data == 'rma',
            rma_passagens=rma_passagens,
            power_cables=parse_power_cables(request.form),
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
        msgs = build_validation_messages(form)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'errors': msgs})
        for msg in msgs:
            flash(msg, 'warning')
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
        machines=build_machine_names(comp_data),
        produtos_catalogo=json.dumps([{'id': p.id, 'component_type': p.component_type, 'model_name': p.model_name} for p in Produto.query.order_by(Produto.component_type, Produto.model_name).all()]),
        component_types=build_component_types())

def build_component_types():
    """Build component types list from Produto table for dynamic dropdowns."""
    tipos_db = db.session.query(Produto.component_type).distinct().all()
    tipos_existentes = {t[0] for t in tipos_db}
    default_order = ['processador', 'placa_mae', 'ram', 'ssd', 'fonte', 'placa_de_video', 'gpu', 'gabinete', 'monitor']
    order = [t for t in default_order if t in tipos_existentes]
    for t in tipos_existentes:
        if t not in order:
            order.append(t)
    labels = Produto.TYPE_LABELS
    return json.dumps([{'key': t, 'label': labels.get(t, t)} for t in order])

@protocols_bp.route('/<int:id>')
@login_required
def detail_protocol(id):
    protocol = Protocol.query.get_or_404(id)
    incomplete_fields = get_incomplete_fields(protocol)
    return render_template('protocols/detail.html', protocol=protocol, incomplete_fields=incomplete_fields)

@protocols_bp.route('/<int:id>/ignorar-incompletos', methods=['POST'])
@login_required
def toggle_ignored_incompletos(id):
    protocol = Protocol.query.get_or_404(id)
    protocol.incomplete_ignored = not protocol.incomplete_ignored
    db.session.commit()
    if protocol.incomplete_ignored:
        flash('Alerta de dados incompletos ignorado.', 'success')
    else:
        flash('Alerta de dados incompletos reativado.', 'info')
    return redirect(url_for('protocols.detail_protocol', id=id))

@protocols_bp.route('/<int:id>/pdf')
@login_required
def protocol_pdf(id):
    from xhtml2pdf import pisa
    protocol = Protocol.query.get_or_404(id)

    def _load_json(text):
        try:
            return json.loads(text) if text else []
        except (json.JSONDecodeError, TypeError):
            return []

    rma_test = _load_json(protocol.rma_test_result) if protocol.type in ('rma', 'servico') else []
    passagens = _load_json(protocol.rma_passagens) if protocol.type in ('rma', 'servico') else []

    html = render_template('protocols/pdf.html', protocol=protocol,
                           rma_test=rma_test, passagens=passagens,
                           now=datetime.utcnow(),
                           logo_path=os.path.join(current_app.root_path, 'static', 'img', 'techbuy-logo.png'))
    result = io.BytesIO()
    pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result, encoding='utf-8')
    if pdf_status.err:
        flash('Erro ao gerar o PDF.', 'danger')
        return redirect(url_for('protocols.detail_protocol', id=protocol.id))
    result.seek(0)
    return send_file(result, mimetype='application/pdf', as_attachment=True,
                     download_name=f'{protocol.protocol_number}.pdf')

def build_component_data(protocol):
    """Build {unit: {name: str, components: [{type, serial, model, product_id, material_comum}], is_prebuilt}} dict for editing."""
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
            'model': c.specification or '',
            'product_id': c.product_id or '',
            'material_comum': c.material_comum or False
        })
    return json.dumps(data)

def build_comp_data_from_form(request_form):
    """Build {unit: {name, components, is_prebuilt}} JSON from submitted form data (for preserving input on validation error)."""
    data = {}
    material_comum = request_form.get('material_comum') == 'on'
    for key in request_form.keys():
        if key.startswith('comp_type_') and key.endswith('[]'):
            unit = key[len('comp_type_'):-2]
            if unit in data:
                continue
            types = request_form.getlist(f'comp_type_{unit}[]')
            models = request_form.getlist(f'comp_model_{unit}[]')
            serials = request_form.getlist(f'comp_serial_{unit}[]')
            product_ids = request_form.getlist(f'comp_product_id_{unit}[]')
            machine_name = request_form.get(f'machine_name_{unit}', '').strip() or f'Máquina {unit}'
            is_prebuilt = request_form.get(f'pe_switch_{unit}') == 'on'
            comps = []
            for i in range(len(types)):
                if types[i].strip():
                    pid = product_ids[i].strip() if i < len(product_ids) else ''
                    comps.append({
                        'type': types[i].strip(),
                        'model': models[i].strip() if i < len(models) else '',
                        'serial': serials[i].strip() if i < len(serials) else '',
                        'product_id': pid if pid else '',
                        'material_comum': material_comum
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
        components = parse_components(request.form, form.type.data)

        form.populate_obj(protocol)
        protocol.venda_pe = bool(form.venda_pe.data) if form.type.data == 'venda' else False
        protocol.entry_date = parse_date_br(form.entry_date.data) if form.entry_date.data else datetime.utcnow()
        protocol.exit_date = parse_date_br(form.exit_date.data) if form.exit_date.data else None
        protocol.updated_at = datetime.utcnow()

        protocol.rma_in_warranty = form.type.data == 'rma'
        protocol.rma_passagens = request.form.get('rma_passagens_json', '').strip() or None
        protocol.original_order = form.original_order.data or None
        protocol.rma_extra_equip = form.rma_extra_equip.data or None
        protocol.rma_equip_itens = parse_rma_equip(request.form)
        protocol.rma_test_result = parse_rma_test_items(request.form)
        protocol.rma_trocados = parse_rma_trocados(request.form)
        protocol.rma_entry_date = parse_date_br(form.rma_entry_date.data) if form.rma_entry_date.data else None
        protocol.power_cables = parse_power_cables(request.form)

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
        msgs = build_validation_messages(form)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'errors': msgs})
        for msg in msgs:
            flash(msg, 'warning')
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
        form.rma_entry_date.data = protocol.rma_entry_date.strftime('%d/%m/%Y') if protocol.rma_entry_date else ''
    return render_template('protocols/create.html', form=form, editing=True, protocol=protocol,
        comp_data=comp_data, rma_comp_data=rma_comp_data, rma_test_data=rma_test_data,
        rma_trocados_data=rma_trocados_data, defect_data=defect_data, win_keys_data=win_keys_data,
        machines=build_machine_names(comp_data),
        produtos_catalogo=json.dumps([{'id': p.id, 'component_type': p.component_type, 'model_name': p.model_name} for p in Produto.query.order_by(Produto.component_type, Produto.model_name).all()]),
        component_types=build_component_types())

@protocols_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def delete_protocol(id):
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
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
    ano_sel = request.args.get('ano', type=int)
    mes_sel = request.args.get('mes', type=int)

    protocols = Protocol.query.order_by(Protocol.created_at.desc()).all()
    anos = sorted({(p.entry_date or p.created_at).year for p in protocols if (p.entry_date or p.created_at)}, reverse=True)

    def data_ref(p):
        return p.entry_date or p.created_at

    if ano_sel:
        protocols = [p for p in protocols if data_ref(p) and data_ref(p).year == ano_sel]
    if mes_sel:
        protocols = [p for p in protocols if data_ref(p) and data_ref(p).month == mes_sel]

    total = len(protocols)
    by_type = {}
    for p in protocols:
        by_type[p.type] = by_type.get(p.type, 0) + 1

    protocol_ids = {p.id for p in protocols}
    defect_totals = {}
    for d in Defect.query.all():
        if d.protocol_id not in protocol_ids:
            continue
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
        d = data_ref(p)
        if d:
            por_mes[(d.year, d.month)] = por_mes.get((d.year, d.month), 0) + 1
    entradas_por_mes = [{
        'chave': f'{ano:04d}-{mes:02d}',
        'rotulo': f'{MESES_ABREV[mes]}/{ano}',
        'count': count
    } for (ano, mes), count in sorted(por_mes.items())]

    tempo_por_tipo = {}
    for p in protocols:
        if p.entry_date and p.exit_date:
            dias = (p.exit_date - p.entry_date).days
            if dias < 0:
                continue
            chave = 'rma_servico' if p.type in ('rma', 'servico') else p.type
            acc = tempo_por_tipo.setdefault(chave, {'soma': 0, 'n': 0})
            acc['soma'] += dias
            acc['n'] += 1
    tempo_medio = [{
        'tipo': TEMPO_LABELS.get(chave, chave),
        'dias': round(acc['soma'] / acc['n'], 1),
        'n': acc['n']
    } for chave, acc in sorted(tempo_por_tipo.items(), key=lambda kv: -kv[1]['n'])]

    return render_template('protocols/report.html',
        protocols=protocols, total=total, by_type=by_type,
        defect_totals=defect_totals, entradas_por_mes=entradas_por_mes,
        anos=anos, ano_sel=ano_sel, mes_sel=mes_sel,
        MESES=MESES_ABREV, tempo_medio=tempo_medio)


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

