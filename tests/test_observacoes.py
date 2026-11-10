from datetime import datetime

from app import db as _db
from app.models import Protocol, User


def _criar_com_observacoes(app, numero, observacoes):
    with app.app_context():
        autor = User.query.filter_by(role='master').first()
        protocolo = Protocol(
            protocol_number=numero,
            type='servico',
            status='concluido',
            client_name='Cliente Observações',
            entry_date=datetime(2026, 11, 10),
            observations=observacoes,
            created_by=autor.id,
        )
        _db.session.add(protocolo)
        _db.session.commit()
        return protocolo.id


def test_observacoes_mostram_quebra_de_linha_de_verdade(app, logged_client):
    pid = _criar_com_observacoes(
        app, 'PRO-2099-9501',
        'Sem Registro de Defeito de mesa.\r\nFlavio Callega 10/11/2026')

    html = logged_client.get(f'/protocolos/{pid}').get_data(as_text=True)

    assert 'Sem Registro de Defeito de mesa.<br>Flavio Callega' in html
    assert '&lt;br&gt;' not in html


def test_observacoes_continuam_escapando_html(app, logged_client):
    pid = _criar_com_observacoes(
        app, 'PRO-2099-9502',
        '<script>alert(1)</script>\r\nTexto normal')

    html = logged_client.get(f'/protocolos/{pid}').get_data(as_text=True)

    assert '&lt;script&gt;alert(1)&lt;/script&gt;<br>Texto normal' in html
    assert '<script>alert(1)</script>' not in html
