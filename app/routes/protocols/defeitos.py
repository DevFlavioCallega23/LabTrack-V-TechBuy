import json
import io
from datetime import datetime
from flask import Blueprint, render_template, request, send_file
from flask_login import login_required, current_user
from app import db
from app.models import Protocol, Defect, EstoqueUso
from app.labels import (
    DEFEITO_RESP_LABELS, DEFEITO_STATUS_LABELS,
    PROTO_TYPE_LABELS, peca_label,
)


defeitos_bp = Blueprint('defeitos', __name__, url_prefix='/defeitos')

def build_defeitos_agrupados():
    """Aggregate defects grouped by situation.

    Teste de Mesa items = produto que voltou do cliente (RMA garantia / fora / NTB).
    Defeitos Encontrados (tabela defect) = sempre equipamento novo de estoque TechBuy.
    """
    grupos = {'rma_garantia': [], 'rma_fora': [], 'ntb': [], 'venda': []}
    protocols = Protocol.query.order_by(Protocol.created_at.desc()).all()
    for p in protocols:
        if p.type in ('rma', 'servico'):
            situacao = 'rma_garantia' if p.rma_in_warranty else 'rma_fora'
        elif p.type == 'nao_comprado':
            situacao = 'ntb'
        else:
            situacao = None

        # Defeitos Encontrados: equipamento novo TechBuy, independentemente do protocolo
        for d in p.defects:
            grupos['venda'].append({
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
                'venda_pe': p.venda_pe,
                'garantia': p.rma_in_warranty if p.type in ('rma', 'servico') else None
            })
        # Itens do Teste de Mesa (RMA/Serviço)
        if p.rma_test_result and p.type in ('rma', 'servico'):
            try:
                itens = json.loads(p.rma_test_result)
                for idx, item in enumerate(itens):
                    if not item.get('component'):
                        continue
                    grupos[situacao].append({
                        'fonte': 'teste',
                        'defect_id': None,
                        'teste_idx': idx,
                        'protocolo_id': p.id,
                        'protocolo_status': p.status,
                        'component': item.get('component', ''),
                        'model': item.get('model', ''),
                        'serial': item.get('serial', ''),
                        'desc': item.get('defeito', ''),
                        'responsavel': 'loja' if situacao == 'rma_garantia' else ('cliente' if situacao == 'rma_fora' else ''),
                        'status': item.get('status', ''),
                        'maquina': item.get('machine', ''),
                        'protocolo': p.protocol_number,
                        'cliente': p.client_name or '',
                        'data': p.entry_date,
                        'tipo': p.type,
                        'garantia': p.rma_in_warranty if p.type in ('rma', 'servico') else None
                    })
            except (json.JSONDecodeError, TypeError):
                pass

    estoque_itens = EstoqueUso.query.order_by(EstoqueUso.created_at.desc()).all()
    for eu in estoque_itens:
        for d in eu.defeitos:
            grupos['venda'].append({
                'fonte': 'estoque',
                'defect_id': d.id,
                'component': d.component_type,
                'model': d.specification or '',
                'serial': d.serial_number or '',
                'desc': d.description or '',
                'responsavel': '',
                'status': '',
                'maquina': d.maquina or '',
                'protocolo': f'Estoque #{eu.id}',
                'protocolo_id': None,
                'protocolo_status': '',
                'cliente': '',
                'data': eu.created_at,
                'tipo': 'estoque',
                'venda_pe': False,
                'garantia': None,
                'vindo_estoque': d.vindo_estoque,
                'equipamento': eu.equipamento or '',
                'ns_estoque': eu.ns or '',
                'uso': eu.uso or '',
                'laudo': eu.laudo or '',
            })
    return grupos

@defeitos_bp.route('/')
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
                    'component', 'model', 'serial', 'desc', 'protocolo', 'cliente', 'maquina',
                    'equipamento', 'ns_estoque', 'uso', 'laudo')).lower()
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
        resp_labels=DEFEITO_RESP_LABELS, status_labels=DEFEITO_STATUS_LABELS,
        q_filter=q, status_filtro=f_status, resp_filtro=f_resp)

@defeitos_bp.route('/exportar')
@login_required
def exportar_defeitos_excel():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    grupos = build_defeitos_agrupados()
    all_items = []
    for itens in grupos.values():
        all_items.extend(itens)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Defeitos'

    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='2C3E50', end_color='2C3E50', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    headers = ['Componente', 'Máquina', 'Modelo', 'NS', 'Defeito', 'Tipo',
               'Responsável', 'Status', 'Cliente', 'Protocolo', 'Data Entrada', 'Fonte']
    ws.append(headers)

    for col_idx, _header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    tipo_map = dict(PROTO_TYPE_LABELS, estoque='Estoque')

    for item in all_items:
        comp = peca_label(item.get('component', ''))
        tipo = tipo_map.get(item.get('tipo', ''), item.get('tipo', ''))
        data_val = item.get('data')
        data_str = data_val.strftime('%d/%m/%Y') if data_val else ''
        fonte = item.get('fonte', '')
        if fonte == 'estoque':
            protocolo = f"Estoque #{item.get('protocolo', '').split('#')[-1]}"
        else:
            protocolo = item.get('protocolo', '')

        row = [
            comp,
            item.get('maquina', ''),
            item.get('model', ''),
            item.get('serial', ''),
            item.get('desc', ''),
            tipo,
            item.get('responsavel', ''),
            item.get('status', ''),
            item.get('cliente', ''),
            protocolo,
            data_str,
            fonte.capitalize()
        ]
        ws.append(row)
        for col_idx in range(1, len(row) + 1):
            ws.cell(row=len(ws['A']), column=col_idx).border = thin_border

    col_widths = [18, 14, 18, 20, 25, 16, 14, 14, 18, 20, 14, 12]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = 'A2'

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f'defeitos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)


@defeitos_bp.route('/<int:id>/status', methods=['POST'])
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

@defeitos_bp.route('/teste/<int:id>/<int:idx>/status', methods=['POST'])
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
