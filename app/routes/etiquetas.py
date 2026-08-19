import socket
from io import BytesIO
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from app import db
from app.models import Protocol, EtiquetaSalva

etiquetas_bp = Blueprint('etiquetas', __name__, url_prefix='/etiquetas')

LABEL_SIZES = {'pequena': (50, 30), 'media': (100, 50), 'grande': (100, 60)}

# Tipografia por tamanho de etiqueta (margens em pt, gap/offsets em mm)
LABEL_FONTS = {
    'pequena': dict(font_tit=8, font_txt=6.5, pad=1.5, gap=2.0, flag_off=2.3, flag_extra=1.0, step_extra=2.0, min_linhas=1),
    'media': dict(font_tit=12, font_txt=10, pad=2.0, gap=3.0, flag_off=3.0, flag_extra=1.2, step_extra=2.0, min_linhas=2),
    'grande': dict(font_tit=13, font_txt=11, pad=2.0, gap=3.0, flag_off=3.2, flag_extra=1.3, step_extra=2.2, min_linhas=3),
}

CENARIO_FLAGS = {
    'case': 'IDENTIFICACAO DO SERVICO',
    'estoque': 'VOLTA AO ESTOQUE',
    'descarte': 'DESCARTE',
}


def get_lan_ip():
    """Return o IP local da máquina na rede (funciona para os outros PCs da loja)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return '127.0.0.1'


def share_url(e):
    """Monta o link com o IP da máquina, não com o hostname (labtracktb)."""
    try:
        port = request.host.partition(':')[2] or '5000'
    except Exception:
        port = '5000'
    return f'http://{get_lan_ip()}:{port}/etiquetas/salva/{e.id}'


def _wrap_text(text, max_chars):
    """Divide o texto em linhas respeitando o tamanho da etiqueta."""
    text = text or ''
    lines = []
    while len(text) > max_chars:
        cut = text.rfind(' ', 0, max_chars + 1)
        if cut < max_chars // 2:
            cut = max_chars
        lines.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        lines.append(text)
    return lines


def _draw_label(c, x, y, w, h, ref, flag, linhas, obs, params):
    """Desenha uma etiqueta em (x, y, w, h) — coordenadas em pt do canto superior esquerdo."""
    c.saveState()
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(0.08, 0.08, 0.08)
    c.setLineWidth(0.8)
    c.roundRect(x, y - h, w, h, 2, stroke=1, fill=1)

    pad = params['pad'] * mm
    font_tit = params['font_tit']
    font_txt = params['font_txt']
    step = font_txt + params['step_extra'] * mm
    flag_h = params['flag_off'] * mm + font_txt * 0.95 + params['flag_extra'] * mm

    # cabeçalho
    c.setFillColorRGB(0, 0, 0)
    c.setFont('Helvetica-Bold', font_tit)
    c.drawString(x + pad, y - pad - font_tit, 'LABTRACK')
    c.setFont('Helvetica-Bold', font_tit * 1.4)
    c.drawRightString(x + w - pad, y - pad - font_tit, ref or '—')
    yy = y - pad - font_tit - params['gap'] * mm - 1.5
    c.setLineWidth(0.5)
    c.line(x + pad, yy, x + w - pad, yy)

    # bandeira do cenário
    c.setFont('Helvetica-Bold', font_txt * 0.95)
    c.drawCentredString(x + w / 2.0, yy - params['flag_off'] * mm, flag or '')
    y_base = yy - flag_h

    # observações embaixo — reserva espaço apenas se sobrar após o mínimo de linhas de dados
    obs_h = 0
    linhas_obs = []
    if obs:
        c.setFont('Helvetica-Oblique', font_txt * 0.95)
        max_w = w - 2 * pad
        max_chars = max(8, int(max_w / (font_txt * 0.6)))
        linhas_obs = _wrap_text(obs, max_chars)
        obs_h = (len(linhas_obs) + 0.5) * (font_txt * 1.25) + 2 * mm + 1.5 * mm
        # deixa sempre espaço pra pelo menos `min_linhas` linhas de dados
        top = y_base - step
        obs_max = max(0, (top - 2 * mm) - params['min_linhas'] * step)
        obs_h = min(obs_h, obs_max)
        # ajusta o texto ao espaço final
        if obs_h > 0:
            avail = obs_h - 3.5 * mm
            n_fit = max(1, int(avail / (font_txt * 1.25)))
            linhas_obs = linhas_obs[:n_fit]

    # quantas linhas de dados cabem (prioridade já vem ordenada: Produto/NS primeiro)
    ttop = y_base - step
    bottom = y - h + obs_h + 2 * mm
    max_linhas = max(1, int((ttop - bottom) / step))
    linhas = linhas[:max_linhas]

    cur = top
    for campo, valor in linhas:
        c.setFont('Helvetica-Bold', font_txt)
        wcampo = c.stringWidth(f'{campo}:', 'Helvetica-Bold', font_txt)
        c.drawString(x + pad, cur, f'{campo}:')
        c.setFont('Helvetica', font_txt)
        c.drawString(x + pad + wcampo + 2 * mm, cur, valor or '—')
        cur -= step

    if obs and linhas_obs:
        box_y = bottom - 3 * mm
        c.setDash(2, 2)
        c.setStrokeColorRGB(0.2, 0.2, 0.2)
        c.roundRect(x + pad, box_y, w - 2 * pad, obs_h - 3 * mm, 2, stroke=1, fill=0)
        c.setDash()
        ty = box_y + (obs_h - 3 * mm)
        for ln in linhas_obs:
            ty -= font_txt * 1.25
            c.drawString(x + pad + 1 * mm, ty, ln)
    c.restoreState()


def gerar_pdf(etiqueta):
    """Gera PDF em A4 paisagem com a grade de etiquetas."""
    w_mm, h_mm = LABEL_SIZES.get(etiqueta.tamanho or 'media', LABEL_SIZES['media'])
    params = LABEL_FONTS.get(etiqueta.tamanho or 'media', LABEL_FONTS['media'])
    w = w_mm * mm
    h = h_mm * mm
    copies = max(1, etiqueta.copias or 1)

    buf = BytesIO()
    pw, ph = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    margin = 6 * mm
    gap = 4 * mm

    per_row = max(1, int((pw - 2 * margin + gap) / (w + gap)))
    per_page = max(1, int((ph - 2 * margin + gap) / (h + gap)) * per_row)

    flag = CENARIO_FLAGS.get(etiqueta.cenario, etiqueta.cenario)
    linhas = [
        ('Produto', etiqueta.produto),
        ('NS', etiqueta.ns),
        ('Cliente', etiqueta.cliente),
        ('Vendedor', etiqueta.vendedor),
        ('Entrada', etiqueta.entrada),
        ('Pedido', etiqueta.pedido),
    ]
    if etiqueta.garantia:
        linhas.append(('Garantia', etiqueta.garantia))

    idx = 0
    page_num = 0
    while idx < copies:
        page_num += 1
        if page_num > 1:
            c.showPage()
        placed = 0
        row = 0
        col = 0
        while placed < per_page and idx < copies:
            x = margin + col * (w + gap)
            y = ph - margin - row * (h + gap)
            _draw_label(c, x, y, w, h, etiqueta.ref, flag, linhas,
                        etiqueta.obs if etiqueta.cenario != 'case' else '', params)
            idx += 1
            placed += 1
            col += 1
            if col >= per_row:
                col = 0
                row += 1
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


@etiquetas_bp.route('/')
@login_required
def index():
    protocolos = Protocol.query.order_by(Protocol.created_at.desc()).limit(300).all()
    salvas = EtiquetaSalva.query.order_by(EtiquetaSalva.created_at.desc()).limit(50).all()
    return render_template('etiquetas/index.html', protocolos=protocolos, salvas=salvas)


def _dados_form():
    return {
        'protocolo_id': request.form.get('protocolo_id', '') or None,
        'ref': request.form.get('ref', '').strip(),
        'cliente': request.form.get('cliente', '').strip(),
        'vendedor': request.form.get('vendedor', '').strip(),
        'entrada': request.form.get('entrada', '').strip(),
        'pedido': request.form.get('pedido', '').strip(),
        'garantia': request.form.get('garantia', '').strip(),
        'cenario': request.form.get('cenario', '').strip() or 'case',
        'tamanho': request.form.get('tamanho', '').strip() or 'media',
        'produto': request.form.get('produto', '').strip(),
        'ns': request.form.get('ns', '').strip(),
        'obs': request.form.get('obs', '').strip(),
    }


def _copias_form():
    try:
        return max(1, min(99, int(request.form.get('copias', '1'))))
    except (TypeError, ValueError):
        return 1


@etiquetas_bp.route('/salvar', methods=['POST'])
@login_required
def salvar():
    dados = _dados_form()
    if not dados['ref'] and not dados['produto']:
        flash('Preencha ao menos a referência ou o produto da etiqueta.', 'warning')
        return redirect(url_for('etiquetas.index'))
    etiqueta = EtiquetaSalva(**dados, copias=_copias_form(), created_by=current_user.username)
    db.session.add(etiqueta)
    db.session.commit()
    flash('Etiqueta salva! Envie o link para alguém imprimir.', 'success')
    return redirect(url_for('etiquetas.salva', id=etiqueta.id))


@etiquetas_bp.route('/pdf', methods=['POST'])
@login_required
def pdf():
    """Gera e baixa o PDF direto do formulário, sem precisar salvar."""
    etiqueta = EtiquetaSalva(**{k: v for k, v in _dados_form().items() if k != 'protocolo_id'},
                             copias=_copias_form())
    buf = gerar_pdf(etiqueta)
    nome = (etiqueta.ref or etiqueta.produto or 'etiqueta').strip().replace('/', '-').replace(' ', '_')
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name=f'etiqueta_{nome}.pdf')


@etiquetas_bp.route('/salva/<int:id>/pdf')
@login_required
def salva_pdf(id):
    etiqueta = EtiquetaSalva.query.get_or_404(id)
    buf = gerar_pdf(etiqueta)
    nome = (etiqueta.ref or etiqueta.produto or 'etiqueta').strip().replace('/', '-').replace(' ', '_')
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name=f'etiqueta_{nome}.pdf')


@etiquetas_bp.route('/salva/<int:id>')
@login_required
def salva(id):
    etiqueta = EtiquetaSalva.query.get_or_404(id)
    return render_template('etiquetas/salva.html', e=etiqueta, url_compartilhar=share_url(etiqueta))


@etiquetas_bp.route('/salva/<int:id>/excluir', methods=['POST'])
@login_required
def salva_excluir(id):
    etiqueta = EtiquetaSalva.query.get_or_404(id)
    db.session.delete(etiqueta)
    db.session.commit()
    flash('Etiqueta excluída.', 'success')
    return redirect(url_for('etiquetas.index'))