import json
import itertools
from datetime import datetime

from app import db as _db
from app.models import Protocol, User

_contador = itertools.count(9100)


def _criar_rma_com_teste(app):
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
        itens = [{
            'component': 'fonte',
            'model': 'Fonte 400W',
            'pedido': 'PED-777',
            'data_compra': '10/01/2026',
            'serial': f'NSUNICO42{next(_contador)}',
            'defeito': 'Nao liga',
            'status': 'em_teste'
        }]
        p = Protocol(
            protocol_number=f'PRO-2097-{next(_contador)}',
            type='servico',
            client_name='Cliente Defeito',
            seller='Myris',
            status='andamento',
            entry_date=datetime(2026, 2, 1),
            rma_in_warranty=False,
            rma_test_result=json.dumps(itens),
            created_by=uid
        )
        _db.session.add(p)
        _db.session.commit()
        return p.id


def test_controle_defeitos_mostra_itens_do_teste_de_mesa(logged_client, app):
    pid = _criar_rma_com_teste(app)
    r = logged_client.get('/protocolos/defeitos')
    assert r.status_code == 200
    assert b'NSUNICO42' in r.data


def test_todos_os_ns_lista_e_filtra(logged_client, app):
    pid = _criar_rma_com_teste(app)
    with app.app_context():
        ns = json.loads(Protocol.query.get(pid).rma_test_result)[0]['serial']

    r = logged_client.get('/protocolos/ns/todos')
    assert r.status_code == 200
    assert ns.encode() in r.data

    r = logged_client.get(f'/protocolos/ns/todos?q={ns.lower()}')
    assert ns.encode() in r.data

    r = logged_client.get('/protocolos/ns/todos?q=zzzinexistente999')
    assert ns.encode() not in r.data


def test_pdf_gera_documento(logged_client, app):
    pid = _criar_rma_com_teste(app)
    r = logged_client.get(f'/protocolos/{pid}/pdf')
    assert r.status_code == 200
    assert r.content_type == 'application/pdf'
    assert r.data[:5] == b'%PDF-'