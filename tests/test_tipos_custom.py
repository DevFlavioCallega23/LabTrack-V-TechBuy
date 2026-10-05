"""Cadastro de tipos de componente pelo botão + (nome exato preservado)."""

import pytest

from app import db
from app.labels import COMPONENT_LABELS, COMPONENT_ORDER, COMPONENT_OPTIONS
from app.models import Produto, ComponenteTipo

CHAVE = 'adaptador_de_wifi'
LABEL = 'Adaptador de Wi-Fi'
MODELO = 'TP-Link Archer T3'


@pytest.fixture
def limpa_tipo(app):
    yield
    COMPONENT_LABELS.pop(CHAVE, None)
    if CHAVE in COMPONENT_ORDER:
        COMPONENT_ORDER.remove(CHAVE)
    COMPONENT_OPTIONS[:] = [(k, COMPONENT_LABELS[k]) for k in COMPONENT_ORDER]
    with app.app_context():
        Produto.query.filter_by(component_type=CHAVE).delete()
        ComponenteTipo.query.filter_by(key=CHAVE).delete()
        db.session.commit()


def test_novo_tipo_salva_nome_exato_e_aparece_no_sistema(logged_client, app, limpa_tipo):
    r = logged_client.post('/produtos/novo', data={
        'component_type': CHAVE,
        'component_type_label': LABEL,
        'model_name': MODELO,
    })
    assert r.status_code == 302

    with app.app_context():
        linha = ComponenteTipo.query.get(CHAVE)
        assert linha is not None
        assert linha.label == LABEL

    assert COMPONENT_LABELS.get(CHAVE) == LABEL
    assert CHAVE in COMPONENT_ORDER
    assert (CHAVE, LABEL) in COMPONENT_OPTIONS

    r = logged_client.get('/produtos/')
    assert r.status_code == 200
    assert ('>' + LABEL + '</option>').encode() in r.data

    r = logged_client.get('/protocolos/novo')
    assert r.status_code == 200
    assert CHAVE.encode() in r.data
    assert LABEL.encode() in r.data

    r = logged_client.get('/protocolos/')
    assert r.status_code == 200
    assert CHAVE.encode() in r.data
    assert LABEL.encode() in r.data


def test_tipo_oficial_nao_e_sobrescrito(logged_client, app, limpa_tipo):
    r = logged_client.post('/produtos/novo', data={
        'component_type': 'ram',
        'component_type_label': 'Nome Errado',
        'model_name': 'Memoria X',
    })
    assert r.status_code == 302

    with app.app_context():
        assert ComponenteTipo.query.get('ram') is None
        assert COMPONENT_LABELS['ram'] == 'Memória RAM'
        Produto.query.filter_by(component_type='ram', model_name='Memoria X').delete()
        db.session.commit()


def test_submit_sem_label_nao_quebra(logged_client, app, limpa_tipo):
    r = logged_client.post('/produtos/novo', data={
        'component_type': 'monitor',
        'model_name': 'LG 24MK430',
    })
    assert r.status_code == 302

    with app.app_context():
        assert ComponenteTipo.query.get('monitor') is None
        Produto.query.filter_by(component_type='monitor', model_name='LG 24MK430').delete()
        db.session.commit()