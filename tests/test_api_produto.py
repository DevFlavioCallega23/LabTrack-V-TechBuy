"""API de criação rápida de produto (alerta nos formulários)."""

from app import db
from app.models import Produto


def _criar(client, tipo, modelo):
    return client.post('/produtos/api/criar', json={
        'component_type': tipo, 'model_name': modelo})


def test_api_criar_cria_produto(logged_client, app):
    r = _criar(logged_client, 'tipo_api_teste', 'Modelo API')
    assert r.status_code == 200
    dados = r.get_json()
    assert dados['id'] > 0
    assert dados['ja_existia'] is False
    with app.app_context():
        p = Produto.query.get(dados['id'])
        assert p is not None
        assert p.component_type == 'tipo_api_teste'
        assert p.model_name == 'Modelo API'
        db.session.delete(p)
        db.session.commit()


def test_api_criar_duplicata_case_insensitive(logged_client, app):
    r1 = _criar(logged_client, 'tipo_api_teste', 'SSD Kingston A400')
    id1 = r1.get_json()['id']
    r2 = _criar(logged_client, 'tipo_api_teste', 'ssd kingston a400')
    dados = r2.get_json()
    assert r2.status_code == 200
    assert dados['id'] == id1
    assert dados['ja_existia'] is True
    with app.app_context():
        assert Produto.query.filter_by(
            component_type='tipo_api_teste').count() == 1
        Produto.query.filter_by(component_type='tipo_api_teste').delete()
        db.session.commit()


def test_api_criar_valida_campos(logged_client):
    r = logged_client.post('/produtos/api/criar', json={})
    assert r.status_code == 400
    assert 'erro' in r.get_json()

    r = logged_client.post('/produtos/api/criar', json={
        'component_type': 'ssd', 'model_name': '   '})
    assert r.status_code == 400


def test_api_criar_exige_login(app):
    with app.test_client() as c:
        r = c.post('/produtos/api/criar', json={
            'component_type': 'ssd', 'model_name': 'X'})
        assert r.status_code == 302
        assert '/login' in r.headers.get('Location', '')
