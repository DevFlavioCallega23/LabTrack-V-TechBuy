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
    with app.app_context():
        d = Defect.query.filter_by(protocol_id=pid).one()
        d.defeito_status = 'devolvido'
        db.session.commit()

    r = logged_client.get(f'/protocolos/{pid}')
    detalhe = r.get_data(as_text=True)
    assert 'Devolvido ao cliente' in detalhe


def test_filtro_de_defeitos_tem_somente_duas_opcoes(logged_client):
    r = logged_client.get('/defeitos/')
    html = r.get_data(as_text=True)
    assert 'value="aguardando_peca"' in html
    assert 'value="trocado"' in html
    assert 'value="em_teste"' not in html
    assert 'value="concluido"' not in html


def test_status_gravado_com_aspas_aparece_limpo(logged_client, app):
    """Registros antigos gravaram '\\"aguardando_peca\\"'; a tela mostra o rótulo."""
    pid = _criar(app, 'PRO-2099-9104')
    with app.app_context():
        d = Defect.query.filter_by(protocol_id=pid).one()
        d.defeito_status = r'\"aguardando_peca\"'
        db.session.commit()

    detalhe = logged_client.get(f'/protocolos/{pid}').get_data(as_text=True)
    assert 'Aguardando peça' in detalhe
    assert 'aguardando_peca' not in detalhe

    editar = logged_client.get(f'/protocolos/{pid}/editar').get_data(as_text=True)
    assert re.search(r'value="aguardando_peca"\s+selected', editar)

    lista = logged_client.get('/defeitos/').get_data(as_text=True)
    assert 'Aguardando peça' in lista
    assert '\\"aguardando_peca\\"' not in lista


def test_salvar_status_remove_aspas_antigas(logged_client, app):
    pid = _criar(app, 'PRO-2099-9105')
    dados = MultiDict([
        ('type', 'rma'), ('client_name', 'Cliente Status'),
        ('seller', 'Myris'), ('status', 'andamento'),
        ('entry_date', '01/02/2026'),
        ('defect_type[]', 'ssd'), ('defect_maquina[]', '01'),
        ('defect_model[]', '120GB'), ('defect_serial[]', 'NS1'),
        ('defect_desc[]', 'Nao liga'),
        ('defect_status[]', r'\"trocado\"'),
    ])
    r = logged_client.post(f'/protocolos/{pid}/editar', data=dados)
    assert r.status_code == 302, r.get_data(as_text=True)[:400]

    with app.app_context():
        p = Protocol.query.get(pid)
        assert p.defects[0].defeito_status == 'trocado'


def _post_edicao_com_trocado(client, pid, tipo_trocado, serial_novo='NS-NOVO',
                             nome_maquina='01', status='aguardando_peca'):
    trocados = json.dumps({'01': {'name': nome_maquina, 'components': [
        {'type': tipo_trocado, 'model': 'Modelo Novo', 'serial': serial_novo}]}})
    dados = MultiDict([
        ('type', 'rma'), ('client_name', 'Cliente Status'),
        ('seller', 'Myris'), ('status', 'andamento'),
        ('entry_date', '01/02/2026'),
        ('defect_type[]', 'ssd'), ('defect_maquina[]', '01'),
        ('defect_model[]', '120GB'), ('defect_serial[]', 'NS1'),
        ('defect_desc[]', 'Nao liga'),
        ('defect_status[]', status),
        ('rma_trocados_json', trocados),
    ])
    r = client.post(f'/protocolos/{pid}/editar', data=dados)
    assert r.status_code == 302, r.get_data(as_text=True)[:400]


def test_ns_novo_muda_aguardando_peca_para_trocado(logged_client, app):
    pid = _criar(app, 'PRO-2099-9106')
    _post_edicao_com_trocado(logged_client, pid, 'ssd')

    with app.app_context():
        p = Protocol.query.get(pid)
        assert p.defects[0].defeito_status == 'trocado'


def test_ns_novo_de_outro_tipo_nao_muda_status(logged_client, app):
    pid = _criar(app, 'PRO-2099-9107')
    _post_edicao_com_trocado(logged_client, pid, 'ram')

    with app.app_context():
        p = Protocol.query.get(pid)
        assert p.defects[0].defeito_status == 'aguardando_peca'


def test_ns_novo_sem_serial_nao_muda_status(logged_client, app):
    pid = _criar(app, 'PRO-2099-9108')
    _post_edicao_com_trocado(logged_client, pid, 'ssd', serial_novo='')

    with app.app_context():
        p = Protocol.query.get(pid)
        assert p.defects[0].defeito_status == 'aguardando_peca'


def test_ns_novo_muda_status_ao_criar_protocolo(logged_client, app):
    trocados = json.dumps({'01': {'name': '01', 'components': [
        {'type': 'ssd', 'model': '240GB', 'serial': 'NS-NOVO'}]}})
    resp = logged_client.post('/protocolos/novo', data={
        'type': 'servico',
        'client_name': 'Cliente Troca Automatica',
        'status': 'andamento',
        'entry_date': '01/02/2026',
        'defect_type[]': 'ssd',
        'defect_maquina[]': '01',
        'defect_model[]': '120GB',
        'defect_serial[]': 'NS1',
        'defect_desc[]': 'Nao liga',
        'defect_status[]': 'aguardando_peca',
        'rma_trocados_json': trocados,
    })
    assert resp.status_code == 302, resp.get_data(as_text=True)[:400]

    with app.app_context():
        p = Protocol.query.filter_by(client_name='Cliente Troca Automatica').one()
        assert p.defects[0].defeito_status == 'trocado'


def test_status_trocado_automatico_nao_vale_para_venda():
    from app.routes.protocols.helpers import aplicar_status_trocado_automatico
    d = Defect(component_type='ssd', specification='120GB',
               defeito_status='aguardando_peca')
    trocados = json.dumps({'01': {'name': '01', 'components': [
        {'type': 'ssd', 'model': '240GB', 'serial': 'NS-NOVO'}]}})
    aplicar_status_trocado_automatico([d], trocados, 'venda')
    assert d.defeito_status == 'aguardando_peca'


def test_status_trocado_automatico_aceita_nome_de_maquina_diferente():
    from app.routes.protocols.helpers import aplicar_status_trocado_automatico
    d = Defect(component_type='placa_mae', specification='Placa-Mãe 1155',
               maquina='Máquina 01', defeito_status='aguardando_peca')
    trocados = json.dumps({'01': {'name': 'Computador 01', 'components': [
        {'type': 'placa_mae', 'model': 'Placa-Mãe 1155', 'serial': 'NS-NOVO'}]}})
    aplicar_status_trocado_automatico([d], trocados, 'servico')
    assert d.defeito_status == 'trocado'


def test_status_trocado_automatico_nao_arrisca_quando_ambiguo():
    from app.routes.protocols.helpers import aplicar_status_trocado_automatico
    d = Defect(component_type='ssd', specification='120GB',
               maquina='Máquina 03', defeito_status='aguardando_peca')
    trocados = json.dumps({
        '01': {'name': 'Computador 01', 'components': [
            {'type': 'ssd', 'model': '240GB', 'serial': 'NS-A'}]},
        '02': {'name': 'Computador 02', 'components': [
            {'type': 'ssd', 'model': '480GB', 'serial': 'NS-B'}]},
    })
    aplicar_status_trocado_automatico([d], trocados, 'rma')
    assert d.defeito_status == 'aguardando_peca'
