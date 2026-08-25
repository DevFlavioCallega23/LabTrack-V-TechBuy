import json
import itertools
from datetime import datetime

from app import db as _db
from app.models import Protocol, User

_seq = itertools.count(6000)


def _seed(app):
    n1, n2 = f'PRO-2096-{next(_seq)}', f'PRO-2096-{next(_seq)}'
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
        a = Protocol(protocol_number=n1, type='venda',
                     client_name='Saude na Panela LTDA', seller='Myris',
                     order_number='PED-100', status='concluido',
                     entry_date=datetime(2026, 8, 1),
                     exit_date=datetime(2026, 8, 10), created_by=uid)
        b = Protocol(protocol_number=n2, type='servico',
                     client_name='Contrate Engenharia', seller='Janay',
                     original_order='PED-200', status='andamento',
                     rma_in_warranty=False,
                     rma_test_result=json.dumps([{
                         'component': 'fonte', 'model': 'Fonte 500W',
                         'serial': 'NSBUSCA77', 'pedido': 'PED-200',
                         'status': 'em_teste'}]),
                     entry_date=datetime(2026, 7, 15), created_by=uid)
        _db.session.add_all([a, b])
        _db.session.commit()
    return {'a': n1, 'b': n2}


def test_busca_por_cliente_parcial(logged_client, app):
    nums = _seed(app)
    r = logged_client.get('/protocolos/busca?cliente=panela')
    assert nums['a'].encode() in r.data and nums['b'].encode() not in r.data


def test_busca_combinada_vendedor_tipo(logged_client, app):
    nums = _seed(app)
    r = logged_client.get('/protocolos/busca?vendedor=Janay&tipo=servico')
    assert nums['b'].encode() in r.data and nums['a'].encode() not in r.data
    r = logged_client.get('/protocolos/busca?vendedor=Janay&tipo=venda')
    assert nums['a'].encode() not in r.data and nums['b'].encode() not in r.data


def test_busca_pedido_inclui_pedido_original(logged_client, app):
    nums = _seed(app)
    r = logged_client.get('/protocolos/busca?pedido=PED-200')
    assert nums['b'].encode() in r.data


def test_busca_por_ns_e_periodo(logged_client, app):
    nums = _seed(app)
    r = logged_client.get('/protocolos/busca?ns=nsbusca77')
    assert nums['b'].encode() in r.data

    r = logged_client.get('/protocolos/busca?ns=nsbusca77&cliente=panela')
    assert b'Nenhum protocolo encontrado' in r.data

    r = logged_client.get('/protocolos/busca?data_de=01/07/2026&data_ate=31/07/2026')
    assert nums['b'].encode() in r.data and nums['a'].encode() not in r.data


def test_busca_sem_filtros_mostra_dica(logged_client):
    r = logged_client.get('/protocolos/busca')
    assert r.status_code == 200
    assert b'Preencha pelo menos um filtro' in r.data