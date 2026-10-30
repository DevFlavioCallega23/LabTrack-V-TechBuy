import json
import itertools
from datetime import datetime
from types import SimpleNamespace

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


def _criar_ntb_com_teste(app):
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
        p = Protocol(
            protocol_number=f'PRO-2097-{next(_contador)}',
            type='nao_comprado',
            client_name='Cliente NTB',
            seller='Myris',
            status='andamento',
            rma_test_result=json.dumps([{
                'component': 'ssd',
                'model': 'SSD 500GB',
                'serial': 'NSNTB123',
                'defeito': 'Falha ao iniciar',
                'status': 'aguardando_peca',
            }]),
            created_by=uid,
        )
        _db.session.add(p)
        _db.session.commit()
        return p.id


def test_controle_defeitos_mostra_itens_do_teste_de_mesa(logged_client, app):
    pid = _criar_rma_com_teste(app)
    r = logged_client.get('/defeitos/')
    assert r.status_code == 200
    assert b'NSUNICO42' in r.data


def test_todos_os_ns_lista_e_filtra(logged_client, app):
    pid = _criar_rma_com_teste(app)
    with app.app_context():
        ns = json.loads(Protocol.query.get(pid).rma_test_result)[0]['serial']

    r = logged_client.get('/ns/todos')
    assert r.status_code == 200
    assert ns.encode() in r.data

    r = logged_client.get(f'/ns/todos?q={ns.lower()}')
    assert ns.encode() in r.data

    r = logged_client.get('/ns/todos?q=zzzinexistente999')
    assert ns.encode() not in r.data


def test_pdf_gera_documento(logged_client, app):
    pid = _criar_rma_com_teste(app)
    r = logged_client.get(f'/protocolos/{pid}/pdf')
    assert r.status_code == 200
    assert r.content_type == 'application/pdf'
    assert r.data[:5] == b'%PDF-'


def test_ntb_compartilhamento_inclui_defeitos_do_teste_de_mesa(logged_client, app):
    pid = _criar_ntb_com_teste(app)
    r = logged_client.get(f'/protocolos/{pid}')

    assert r.status_code == 200
    assert b'*Resultado do Teste de Mesa / Defeitos encontrados:*' in r.data
    assert b'Defeito: Falha ao iniciar' in r.data
    assert 'Aguardando peça'.encode() not in r.data


def test_pdf_ntb_inclui_defeitos_do_teste_de_mesa(logged_client, app, monkeypatch):
    from xhtml2pdf import pisa

    pid = _criar_ntb_com_teste(app)
    html_gerado = []

    def capturar_html(source, dest, encoding):
        html_gerado.append(source.getvalue())
        dest.write(b'%PDF-teste')
        return SimpleNamespace(err=0)

    monkeypatch.setattr(pisa, 'CreatePDF', capturar_html)
    r = logged_client.get(f'/protocolos/{pid}/pdf')

    assert r.status_code == 200
    assert r.data.startswith(b'%PDF-')
    assert 'Resultado do Teste de Mesa / Defeitos encontrados' in html_gerado[0]
    assert 'Falha ao iniciar' in html_gerado[0]
    assert 'Aguardando peça' not in html_gerado[0]
    assert '<th>Situação</th>' not in html_gerado[0]