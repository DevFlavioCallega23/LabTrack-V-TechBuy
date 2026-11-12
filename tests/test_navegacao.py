"""Salvar protocolo sem deixar a tela de edição no histórico do navegador."""
from datetime import datetime
from pathlib import Path

from app import db as _db
from app.models import Protocol, User

JS = Path(__file__).resolve().parents[1] / 'app' / 'static' / 'js' / 'protocol_form.js'


def _criar(app, numero):
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
        p = Protocol(
            protocol_number=numero,
            type='servico',
            status='andamento',
            client_name='Cliente Navegação',
            entry_date=datetime(2026, 2, 1),
            created_by=uid,
        )
        _db.session.add(p)
        _db.session.commit()
        return p.id


def _remover(app, pid):
    with app.app_context():
        p = Protocol.query.get(pid)
        if p:
            _db.session.delete(p)
            _db.session.commit()


def _dados_edicao():
    return {
        'type': 'servico',
        'status': 'andamento',
        'seller': '',
        'client_name': 'Cliente Navegação',
        'entry_date': '01/02/2026',
    }


def test_edicao_ajax_devolve_url_do_detalhe(app, logged_client):
    pid = _criar(app, 'PRO-2099-9801')
    try:
        resposta = logged_client.post(
            f'/protocolos/{pid}/editar',
            data=_dados_edicao(),
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resposta.status_code == 200
        dados = resposta.get_json()
        assert dados['ok'] is True
        assert dados['url'].endswith(f'/protocolos/{pid}')
    finally:
        _remover(app, pid)


def test_edicao_normal_continua_redirecionando(app, logged_client):
    pid = _criar(app, 'PRO-2099-9802')
    try:
        resposta = logged_client.post(
            f'/protocolos/{pid}/editar',
            data=_dados_edicao(),
            follow_redirects=False,
        )
        assert resposta.status_code == 302
        assert resposta.headers['Location'].endswith(f'/protocolos/{pid}')
    finally:
        _remover(app, pid)


def test_formulario_troca_a_entrada_do_formulario_ao_salvar():
    js = JS.read_text(encoding='utf-8')
    assert 'irParaDepoisDeSalvar' in js
    assert 'window.location.href = resp.url' not in js
    assert 'window.location.replace(destino)' in js
    # Nada de history.back()/replaceState: o resultado depende do navegador.
    assert 'history.back()' not in js
    assert 'history.replaceState' not in js


def test_botao_editar_do_detalhe_substitui_a_pagina_no_historico(app, logged_client):
    pid = _criar(app, 'PRO-2099-9803')
    try:
        html = logged_client.get(f'/protocolos/{pid}').get_data(as_text=True)
        assert 'id="btnEditarProtocolo"' in html
        assert 'window.location.replace(botao.href)' in html
    finally:
        _remover(app, pid)


def test_arquivos_estaticos_tem_versao_no_endereco(app, logged_client):
    html = logged_client.get('/protocolos/novo').get_data(as_text=True)
    assert 'js/protocol_form.js?v=' in html
    assert 'css/style.css?v=' in html
