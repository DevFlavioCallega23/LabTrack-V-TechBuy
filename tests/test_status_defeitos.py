"""Status de Defeitos e Teste de Mesa na edição do protocolo.

O campo Responsável foi removido (o tipo de protocolo já define).
"""

import json
import re
from datetime import datetime

from werkzeug.datastructures import MultiDict

from app import db
from app.models import Defect, Protocol, User

ITEM_TESTE = {
    'machine': '01', 'component': 'ssd', 'model': '120GB', 'serial': 'NS1',
    'defeito': 'Nao grava SO', 'pedido': '', 'data_compra': '01/02/2026',
    'status': 'em_teste',
}


def _criar(app, numero='PRO-2099-9100'):
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
        p = Protocol(
            protocol_number=numero, type='rma',
            client_name='Cliente Status', seller='Myris',
            status='andamento', entry_date=datetime(2026, 2, 1),
            created_by=uid, rma_test_result=json.dumps([dict(ITEM_TESTE)]))
        db.session.add(p)
        db.session.flush()
        db.session.add(Defect(
            protocol_id=p.id, component_type='ssd', specification='120GB',
            serial_number='NS1', description='Nao liga',
            defeito_status='aguardando_peca', responsavel='loja',
            maquina='01'))
        db.session.commit()
        return p.id


def test_editar_mostra_status_e_nao_tem_responsavel(logged_client, app):
    pid = _criar(app, 'PRO-2099-9101')
    r = logged_client.get(f'/protocolos/{pid}/editar')
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    assert re.search(r'value="aguardando_peca"\s+selected', html), \
        'status do defeito deve vir selecionado'
    assert 'rmaTestData' in html and 'em_teste' in html, \
        'status do teste de mesa deve ir no config do JS'

    assert 'defect_resp[]' not in html
    assert 'name="resp"' not in html


def test_editar_atualiza_status_do_defeito_e_do_teste(logged_client, app):
    pid = _criar(app, 'PRO-2099-9102')
    item = dict(ITEM_TESTE, status='concluido')
    dados = MultiDict([
        ('type', 'rma'), ('client_name', 'Cliente Status'),
        ('seller', 'Myris'), ('status', 'andamento'),
        ('entry_date', '01/02/2026'),
        ('defect_type[]', 'ssd'), ('defect_maquina[]', '01'),
        ('defect_model[]', '120GB'), ('defect_serial[]', 'NS1'),
        ('defect_desc[]', 'Nao liga'), ('defect_status[]', 'devolvido'),
        ('rma_test_json', json.dumps([item])),
    ])
    r = logged_client.post(f'/protocolos/{pid}/editar', data=dados)
    assert r.status_code == 302, r.get_data(as_text=True)[:400]

    with app.app_context():
        p = Protocol.query.get(pid)
        assert len(p.defects) == 1
        assert p.defects[0].defeito_status == 'devolvido'
        itens = json.loads(p.rma_test_result)
        assert itens[0]['status'] == 'concluido'


def test_pagina_defeitos_nao_tem_responsavel(logged_client):
    r = logged_client.get('/defeitos/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'name="resp"' not in html
    assert 'Responsável' not in html


def test_select_status_tem_somente_duas_opcoes(logged_client, app):
    pid = _criar(app, 'PRO-2099-9103')
    r = logged_client.get(f'/protocolos/{pid}/editar')
    html = r.get_data(as_text=True)

    blocos = re.findall(
        r'<select name="defect_status\[\]".*?</select>', html, re.S)
    assert blocos, 'select de status do defeito deve existir'
    valores = {v for b in blocos for v in re.findall(r'value="([^"]*)"', b)}
    assert {'aguardando_peca', 'trocado'} <= valores
    assert not valores & {'em_teste', 'devolvido', 'concluido'}, \
        f'status removidos ainda como opcao: {valores}'

    # registro antigo continua sendo exibido com rotulo bonito
    r = logged_client.get(f'/protocolos/{pid}')
    detalhe = r.get_data(as_text=True)
    assert 'Em teste' in detalhe


def test_filtro_de_defeitos_tem_somente_duas_opcoes(logged_client):
    r = logged_client.get('/defeitos/')
    html = r.get_data(as_text=True)
    assert 'value="aguardando_peca"' in html
    assert 'value="trocado"' in html
    assert 'value="em_teste"' not in html
    assert 'value="concluido"' not in html
