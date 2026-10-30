"""Registro rápido da Home: cria o protocolo com o básico e abre a edição."""
from app import db as _db
from app.models import Protocol, User


def _contar():
    return Protocol.query.count()


def test_registro_rapido_cria_protocolo_e_abre_edicao(logged_client, app):
    with app.app_context():
        antes = _contar()

    resposta = logged_client.post('/registro-rapido', data={
        'type': 'rma',
        'client_name': '  Cliente do Registro Rápido  ',
        'seller': 'Janay',
        'base_defect': 'Não liga',
    })

    with app.app_context():
        assert _contar() == antes + 1
        protocolo = Protocol.query.order_by(Protocol.id.desc()).first()
        assert resposta.status_code == 302
        assert resposta.headers['Location'].endswith(f'/protocolos/{protocolo.id}/editar')
        assert protocolo.protocol_number.startswith('PRO-')
        assert protocolo.type == 'rma'
        assert protocolo.client_name == 'Cliente do Registro Rápido'
        assert protocolo.seller == 'Janay'
        assert protocolo.base_defect == 'Não liga'
        assert protocolo.status == 'andamento'
        assert protocolo.rma_in_warranty is True
        assert protocolo.created_by is not None
        _db.session.delete(protocolo)
        _db.session.commit()


def test_registro_rapido_de_venda_guarda_relato_nas_observacoes(logged_client, app):
    with app.app_context():
        antes = _contar()

    logged_client.post('/registro-rapido', data={
        'type': 'venda',
        'client_name': 'Cliente Venda Rápida',
        'seller': 'TechBuy',
        'base_defect': 'Chegou com a tampa riscada',
    })

    with app.app_context():
        assert _contar() == antes + 1
        protocolo = Protocol.query.order_by(Protocol.id.desc()).first()
        assert protocolo.type == 'venda'
        assert protocolo.base_defect is None
        assert protocolo.observations == 'Chegou com a tampa riscada'
        assert protocolo.rma_in_warranty is False
        _db.session.delete(protocolo)
        _db.session.commit()


def test_registro_rapido_de_venda_guarda_pedido_quantidade_e_data(logged_client, app):
    with app.app_context():
        antes = _contar()

    logged_client.post('/registro-rapido', data={
        'type': 'venda',
        'client_name': 'Cliente Venda Completa',
        'seller': 'Erica',
        'pedido': '  PED-7788  ',
        'lote': '5',
        'entry_date': '05/03/2026',
    })

    with app.app_context():
        assert _contar() == antes + 1
        protocolo = Protocol.query.order_by(Protocol.id.desc()).first()
        assert protocolo.order_number == 'PED-7788'
        assert protocolo.lote == '5'
        assert protocolo.entry_date.date().isoformat() == '2026-03-05'
        assert protocolo.original_order is None
        assert protocolo.rma_entry_date is None
        _db.session.delete(protocolo)
        _db.session.commit()


def test_registro_rapido_de_rma_usa_pedido_original_e_data_de_entrada(logged_client, app):
    with app.app_context():
        antes = _contar()

    logged_client.post('/registro-rapido', data={
        'type': 'rma',
        'client_name': 'Cliente RMA',
        'seller': 'Myris',
        'pedido': 'PED-1234',
        'lote': '2',
        'entry_date': '10/02/2026',
        'base_defect': 'Não liga',
    })

    with app.app_context():
        assert _contar() == antes + 1
        protocolo = Protocol.query.order_by(Protocol.id.desc()).first()
        assert protocolo.original_order == 'PED-1234'
        assert protocolo.order_number is None
        assert protocolo.lote == '2'
        assert protocolo.entry_date.date().isoformat() == '2026-02-10'
        assert protocolo.rma_entry_date is not None
        assert protocolo.base_defect == 'Não liga'
        _db.session.delete(protocolo)
        _db.session.commit()


def test_registro_rapido_de_pronta_entrega_nao_pede_cliente(logged_client, app):
    with app.app_context():
        antes = _contar()

    resposta = logged_client.post('/registro-rapido', data={
        'type': 'ponta_entrega',
        'lote': '3',
        'base_defect': 'Faltou um parafuso',
    })

    with app.app_context():
        assert _contar() == antes + 1
        protocolo = Protocol.query.order_by(Protocol.id.desc()).first()
        assert resposta.headers['Location'].endswith(f'/protocolos/{protocolo.id}/editar')
        assert protocolo.type == 'ponta_entrega'
        assert protocolo.client_name is None
        assert protocolo.seller is None
        assert protocolo.lote == '3'
        assert protocolo.entry_date is not None
        assert protocolo.observations == 'Faltou um parafuso'
        _db.session.delete(protocolo)
        _db.session.commit()


def test_registro_rapido_de_nao_comprado_exige_cliente(logged_client, app):
    with app.app_context():
        antes = _contar()

    resposta = logged_client.post('/registro-rapido', data={
        'type': 'nao_comprado',
        'base_defect': 'Trazido de outra loja',
    })

    with app.app_context():
        assert _contar() == antes
    assert resposta.status_code == 302
    assert resposta.headers['Location'].endswith('/')


def test_registro_rapido_exige_tipo(logged_client, app):
    with app.app_context():
        antes = _contar()

    resposta = logged_client.post('/registro-rapido', data={
        'type': '',
        'client_name': 'Sem tipo escolhido',
    })

    with app.app_context():
        assert _contar() == antes
    assert resposta.status_code == 302
    assert resposta.headers['Location'].endswith('/')


def test_home_mostra_campos_do_registro_rapido_por_tipo(logged_client):
    pagina = logged_client.get('/').get_data(as_text=True)
    assert 'data-quick-for="venda,rma,servico"' in pagina
    assert 'data-quick-for="venda,rma,servico,ponta_entrega"' in pagina
    assert 'id="quickPedido"' in pagina
    assert 'id="quickLote"' in pagina
    assert 'id="quickData"' in pagina


def test_registro_rapido_exige_cliente(logged_client, app):
    with app.app_context():
        antes = _contar()

    resposta = logged_client.post('/registro-rapido', data={
        'type': 'servico',
        'client_name': '   ',
    })

    with app.app_context():
        assert _contar() == antes
    assert resposta.status_code == 302
    assert resposta.headers['Location'].endswith('/')


def test_registro_rapido_bloqueia_quem_nao_e_gerente(client, app):
    with app.app_context():
        viewer = User.query.filter_by(role='viewer').first()
        if viewer is None:
            viewer = User(username='viewer_teste', email='viewer@teste.local', role='viewer')
            viewer.set_password('senha123')
            _db.session.add(viewer)
            _db.session.commit()
        viewer_id = viewer.id
        antes = _contar()

    with client.session_transaction() as sessao:
        sessao['_user_id'] = str(viewer_id)
        sessao['_fresh'] = True

    resposta = client.post('/registro-rapido', data={
        'type': 'venda',
        'client_name': 'Não deveria criar',
    })

    with app.app_context():
        assert _contar() == antes
    assert resposta.status_code == 302
    assert resposta.headers['Location'].endswith('/')


def test_home_mostra_registro_rapido_so_para_gerente(logged_client, app, client):
    pagina = logged_client.get('/').get_data(as_text=True)
    assert 'Registro rápido' in pagina

    with app.app_context():
        viewer_id = User.query.filter_by(role='viewer').first().id
    with client.session_transaction() as sessao:
        sessao['_user_id'] = str(viewer_id)
        sessao['_fresh'] = True
    pagina_viewer = client.get('/').get_data(as_text=True)
    assert 'Registro rápido' not in pagina_viewer
