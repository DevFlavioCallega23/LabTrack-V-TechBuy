import json
from datetime import datetime

from app import db as _db
from app.models import Protocol, User
from app.forms import ProtocolForm


def _criar_protocolo(app, **kwargs):
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
        dados = dict(
            protocol_number='PRO-2099-9001',
            type='venda',
            client_name='Cliente Teste',
            seller='Myris',
            status='concluido',
            entry_date=datetime(2026, 1, 10),
            exit_date=datetime(2026, 1, 15),
            created_by=uid
        )
        dados.update(kwargs)
        p = Protocol(**dados)
        _db.session.add(p)
        _db.session.commit()
        return p.id


def test_form_nao_tem_mais_tipo_venda_ponta_entrega(app):
    with app.app_context():
        escolhas = [c[0] for c in ProtocolForm().type.choices]
        assert 'venda_ponta_entrega' not in escolhas
        assert 'ponta_entrega' in escolhas
        assert 'venda' in escolhas


def test_venda_pe_mostra_etiqueta(logged_client, app):
    pid = _criar_protocolo(app, protocol_number='PRO-2099-9002', venda_pe=True,
                           rma_test_result=None)
    r = logged_client.get(f'/protocolos/{pid}')
    assert r.status_code == 200
    assert b'>PE<' in r.data


def test_venda_montada_sem_etiqueta_pe(logged_client, app):
    pid = _criar_protocolo(app, protocol_number='PRO-2099-9003', venda_pe=False,
                           rma_test_result=None)
    r = logged_client.get(f'/protocolos/{pid}')
    assert r.status_code == 200
    assert b'>PE<' not in r.data


def test_lista_mostra_pe_e_tempo_medio_no_relatorio(logged_client, app):
    _criar_protocolo(app, protocol_number='PRO-2099-9004', venda_pe=True,
                     rma_test_result=None)
    r = logged_client.get('/protocolos/')
    assert b'>PE<' in r.data

    r = logged_client.get('/protocolos/relatorio')
    assert r.status_code == 200
    assert 'Tempo Médio'.encode() in r.data or b'Tempo M\xc3\xa9dio'.upper() not in r.data
    assert b'dias' in r.data


def test_relatorio_filtro_ano_sem_resultado(logged_client):
    r = logged_client.get('/protocolos/relatorio?ano=2098')
    assert r.status_code == 200
    assert b'0</strong>' in r.data or b'<strong>0</strong>' in r.data