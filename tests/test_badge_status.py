from datetime import datetime
from pathlib import Path

from app import db as _db
from app.labels import PROTO_STATUS_BADGES
from app.models import Protocol, User

CSS = Path(__file__).resolve().parents[1] / 'app' / 'static' / 'css' / 'style.css'


def test_status_usam_selos_harmonizados():
    assert PROTO_STATUS_BADGES == {
        'pendente': 'badge-status-pendente',
        'andamento': 'badge-status-andamento',
        'concluido': 'badge-status-concluido',
        'cancelado': 'badge-status-cancelado',
    }


def test_css_tem_uma_classe_para_cada_status():
    css = CSS.read_text(encoding='utf-8')
    for classe in PROTO_STATUS_BADGES.values():
        assert f'.{classe}' in css


def test_detalhe_usa_o_selo_novo_de_status(app, logged_client):
    with app.app_context():
        autor = User.query.filter_by(role='master').first()
        protocolo = Protocol(
            protocol_number='PRO-2099-9503',
            type='servico',
            status='pendente',
            client_name='Cliente Status',
            entry_date=datetime(2026, 11, 11),
            created_by=autor.id,
        )
        _db.session.add(protocolo)
        _db.session.commit()
        pid = protocolo.id

    html = logged_client.get(f'/protocolos/{pid}').get_data(as_text=True)

    assert 'badge-status-pendente' in html
