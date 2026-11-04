import json
from datetime import datetime

from app import db as _db
from app.models import Component, Protocol, User
from app.routes.protocols.helpers import historico_por_pedido


def _uid(app):
    with app.app_context():
        return User.query.filter_by(role='master').first().id


def _criar(app, numero, tipo, **kwargs):
    kwargs.setdefault('entry_date', datetime(2026, 6, 16))
    with app.app_context():
        p = Protocol(
            protocol_number=numero,
            type=tipo,
            created_by=_uid(app),
            status='concluido',
            **kwargs
        )
        _db.session.add(p)
        _db.session.commit()
        return p.id


def _add_comp(app, pid, unit='01', tipo='ram', modelo='8GB DDR3 Kingston',
              ns='144010', nome='Computador 01'):
    with app.app_context():
        _db.session.add(Component(
            protocol_id=pid,
            component_type=tipo,
            specification=modelo,
            serial_number=ns,
            unit=unit,
            machine_name=nome,
            sort_order=int(unit) * 100,
            is_prebuilt=True,
        ))
        _db.session.commit()


def _rma_base(app, numero='PRO-2099-9301', pedido=None):
    """RMA com defeito registrado, peça trocada e um componente."""
    extras = {'order_number': pedido} if pedido else {}
    pid = _criar(
        app, numero, 'rma',
        client_name='FABIO CANDIDO SILVA SANTOS',
        seller='Myris',
        entry_date=datetime(2026, 6, 16),
        exit_date=datetime(2026, 10, 30),
        rma_entry_date=datetime(2026, 10, 30),
        rma_in_warranty=True,
        rma_test_result=json.dumps([{
            'machine': 'Computador 01', 'component': 'ram',
            'model': '8GB DDR3 Kingston', 'serial': '144010',
            'defeito': 'Sem Start', 'pedido': '95789',
            'data_compra': '16/06/2026', 'status': 'trocado',
        }], ensure_ascii=False),
        rma_trocados=json.dumps({'01': {
            'name': 'Computador 01',
            'components': [{'type': 'ram', 'model': '8GB DDR3 XIIByte',
                            'serial': '144657'}],
        }}, ensure_ascii=False),
        **extras,
    )
    _add_comp(app, pid)
    return pid


def test_novo_retorno_cria_rma_ligado_e_copia_dados(app, logged_client):
    origem_id = _rma_base(app)

    resp = logged_client.post(
        f'/protocolos/{origem_id}/novo-retorno', data={'type': 'rma'})
    assert resp.status_code == 302

    with app.app_context():
        origem = _db.session.get(Protocol, origem_id)
        novo = Protocol.query.filter_by(origin_id=origem_id).one()

        assert resp.headers['Location'].endswith(f'/protocolos/{novo.id}/editar')
        assert novo.id != origem.id
        assert novo.type == 'rma'
        assert novo.status == 'pendente'
        assert novo.client_name == 'FABIO CANDIDO SILVA SANTOS'
        assert novo.seller == 'Myris'
        assert novo.rma_in_warranty is True
        # RMA mantém a data da compra do anterior e entra hoje no laboratório
        assert novo.entry_date.date() == datetime(2026, 6, 16).date()
        assert novo.rma_entry_date.date() == datetime.utcnow().date()
        # defeitos e trocados NÃO são copiados
        assert not novo.rma_test_result
        assert not novo.rma_trocados


def test_novo_retorno_copia_equipamento_e_passagem_anterior(app, logged_client):
    origem_id = _rma_base(app, 'PRO-2099-9302')

    logged_client.post(f'/protocolos/{origem_id}/novo-retorno',
                       data={'type': 'servico'})

    with app.app_context():
        novo = Protocol.query.filter_by(origin_id=origem_id).one()
        equip = json.loads(novo.rma_equip_itens)
        assert equip['01']['name'] == 'Computador 01'
        # A peça antiga (144010) foi trocada: o equipamento já vem com a nova.
        assert equip['01']['components'][0]['serial'] == '144657'
        assert 'XIIByte' in equip['01']['components'][0]['model']
        # Serviço é fora de garantia e também registra a passagem anterior
        assert novo.rma_in_warranty is False
        passagens = json.loads(novo.rma_passagens)
        assert passagens[-1]['protocolo'] == 'PRO-2099-9302'
        assert passagens[-1]['ns'] == '144010'
        assert passagens[-1]['ns_novo'] == '144657'


def test_novo_retorno_para_venda_copia_componentes_e_entra_hoje(app, logged_client):
    origem_id = _rma_base(app, 'PRO-2099-9303')

    logged_client.post(f'/protocolos/{origem_id}/novo-retorno',
                       data={'type': 'venda'})

    with app.app_context():
        novo = Protocol.query.filter_by(origin_id=origem_id).one()
        assert novo.type == 'venda'
        assert novo.entry_date.date() == datetime.utcnow().date()
        assert novo.rma_entry_date is None
        assert len(novo.components) == 1
        assert novo.components[0].serial_number == '144010'
        assert novo.client_name == 'FABIO CANDIDO SILVA SANTOS'


def test_edicao_do_retorno_mostra_historico_do_anterior(app, logged_client):
    origem_id = _rma_base(app, 'PRO-2099-9304')
    logged_client.post(f'/protocolos/{origem_id}/novo-retorno',
                       data={'type': 'rma'})

    with app.app_context():
        novo = Protocol.query.filter_by(origin_id=origem_id).one()
        novo_id = novo.id

    resp = logged_client.get(f'/protocolos/{novo_id}/editar')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'Histórico do protocolo anterior' in html
    assert 'PRO-2099-9304' in html
    assert 'Sem Start' in html
    assert '144657' in html  # peça trocada aparece no painel


def test_corrente_de_tres_protocolos(app, logged_client):
    venda_id = _criar(app, 'PRO-2099-9305', 'venda',
                      client_name='Cliente Corrente')
    logged_client.post(f'/protocolos/{venda_id}/novo-retorno',
                       data={'type': 'rma'})
    with app.app_context():
        rma_id = Protocol.query.filter_by(origin_id=venda_id).one().id

    logged_client.post(f'/protocolos/{rma_id}/novo-retorno',
                       data={'type': 'rma'})
    with app.app_context():
        ultimo = Protocol.query.filter_by(origin_id=rma_id).one()
        cadeia = _db.session.get(Protocol, ultimo.id).get_return_chain()
        assert [p.id for p in cadeia] == [venda_id, rma_id, ultimo.id]
        assert [p.type for p in cadeia] == ['venda', 'rma', 'rma']
        assert len(_db.session.get(Protocol, venda_id).get_returns()) == 1
        assert len(_db.session.get(Protocol, rma_id).get_returns()) == 1


def test_detalhe_mostra_vinculo_nos_dois_lados(app, logged_client):
    origem_id = _rma_base(app, 'PRO-2099-9306')
    logged_client.post(f'/protocolos/{origem_id}/novo-retorno',
                       data={'type': 'rma'})
    with app.app_context():
        novo = Protocol.query.filter_by(origin_id=origem_id).one()

    html_origem = logged_client.get(f'/protocolos/{origem_id}').get_data(as_text=True)
    html_novo = logged_client.get(f'/protocolos/{novo.id}').get_data(as_text=True)
    assert novo.protocol_number in html_origem
    assert 'Retorno do protocolo' in html_novo
    assert 'PRO-2099-9306' in html_novo


def test_tipo_invalido_nao_cria_retorno(app, logged_client):
    origem_id = _rma_base(app, 'PRO-2099-9307')

    resp = logged_client.post(f'/protocolos/{origem_id}/novo-retorno',
                              data={'type': 'inexistente'})
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith(f'/protocolos/{origem_id}')
    with app.app_context():
        assert Protocol.query.filter_by(origin_id=origem_id).count() == 0


def test_retorno_de_pronta_entrega_para_venda(app, logged_client):
    pe_id = _criar(app, 'PRO-2099-9308', 'ponta_entrega',
                   client_name='Cliente PE')
    _add_comp(app, pe_id, tipo='fonte', modelo='Fonte 230W',
              ns='159999', nome='Máquina 05')

    logged_client.post(f'/protocolos/{pe_id}/novo-retorno',
                       data={'type': 'venda'})

    with app.app_context():
        novo = Protocol.query.filter_by(origin_id=pe_id).one()
        assert novo.type == 'venda'
        assert novo.client_name == 'Cliente PE'
        assert [c.serial_number for c in novo.components] == ['159999']


def test_pedido_do_retorno_e_copiado_e_agrupa_a_corrente(app, logged_client):
    origem_id = _rma_base(app, 'PRO-2099-9310', pedido='95789')

    logged_client.post(f'/protocolos/{origem_id}/novo-retorno',
                       data={'type': 'rma'})
    with app.app_context():
        novo = Protocol.query.filter_by(origin_id=origem_id).one()
        novo_id = novo.id
        assert novo.order_number == '95789'

        itens = historico_por_pedido(' 95789 ')
        assert [h['protocol'].id for h in itens] == [origem_id, novo_id]

        so_do_novo = historico_por_pedido('95789', ignorar_id=origem_id)
        assert [h['protocol'].id for h in so_do_novo] == [novo_id]


def test_endpoint_historico_do_pedido_mostra_defeitos_e_trocados(app, logged_client):
    _rma_base(app, 'PRO-2099-9311', pedido='95790')

    resp = logged_client.get('/protocolos/historico-pedido?pedido=95790')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'PRO-2099-9311' in html
    assert '95790' in html
    assert 'Sem Start' in html
    assert '144657' in html
    assert 'Defeitos registrados' in html
    assert 'Produtos trocados' in html


def test_historico_por_pedido_tambem_olha_o_pedido_original(app):
    pid = _criar(app, 'PRO-2099-9312', 'rma', original_order='95791')
    with app.app_context():
        itens = historico_por_pedido('95791')
        assert [h['protocol'].id for h in itens] == [pid]


def test_tela_de_edicao_tem_area_do_historico_do_pedido(app, logged_client):
    origem_id = _rma_base(app, 'PRO-2099-9313', pedido='95792')

    html = logged_client.get(f'/protocolos/{origem_id}/editar').get_data(as_text=True)
    assert 'id="historicoPedido"' in html
    assert f'data-protocol-id="{origem_id}"' in html


def test_retorno_usa_a_peca_certa_quando_tem_duas_iguais(app, logged_client):
    pid = _criar(
        app, 'PRO-2099-9318', 'rma',
        client_name='Cliente Duas Peças',
        rma_equip_itens=json.dumps({'01': {
            'name': 'Computador 01',
            'components': [
                {'type': 'ssd', 'model': 'SSD A', 'serial': '111'},
                {'type': 'ssd', 'model': 'SSD B', 'serial': '222'},
                {'type': 'ram', 'model': 'RAM X', 'serial': '333'},
            ],
        }}, ensure_ascii=False),
        rma_test_result=json.dumps([{
            'machine': 'Computador 01', 'component': 'ssd',
            'model': 'SSD B', 'serial': '222', 'status': 'trocado',
        }], ensure_ascii=False),
        rma_trocados=json.dumps({'01': {
            'name': 'Computador 01',
            'components': [{'type': 'ssd', 'model': 'SSD Novo', 'serial': '999'}],
        }}, ensure_ascii=False),
    )

    logged_client.post(f'/protocolos/{pid}/novo-retorno', data={'type': 'rma'})

    with app.app_context():
        novo = Protocol.query.filter_by(origin_id=pid).one()
        comps = json.loads(novo.rma_equip_itens)['01']['components']
        ssds = [(c['model'], c['serial']) for c in comps if c['type'] == 'ssd']
        assert ssds == [('SSD A', '111'), ('SSD Novo', '999')]
        assert any(c['type'] == 'ram' and c['serial'] == '333' for c in comps)


def test_detalhe_mostra_outros_protocolos_do_mesmo_pedido(app, logged_client):
    primeiro = _rma_base(app, 'PRO-2099-9314', pedido='95793')
    _criar(app, 'PRO-2099-9315', 'servico', order_number='95793')

    html = logged_client.get(f'/protocolos/{primeiro}').get_data(as_text=True)
    assert 'Outros protocolos deste pedido' in html
    assert 'PRO-2099-9315' in html


def test_tela_de_novo_protocolo_tem_caixa_de_busca(app, logged_client):
    html = logged_client.get('/protocolos/novo').get_data(as_text=True)
    assert 'Puxar de um protocolo existente' in html
    assert 'id="buscarProtocoloInput"' in html
    assert 'id="resultadoBuscaAnterior"' in html


def test_busca_historico_por_numero_de_protocolo(app, logged_client):
    _rma_base(app, 'PRO-2099-9316', pedido='95794')

    resp = logged_client.get('/protocolos/buscar-historico?q=PRO-2099-9316')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'PRO-2099-9316' in html
    assert 'Criar retorno deste' in html
    assert 'Sem Start' in html


def test_busca_historico_por_pedido_mostra_passagens(app, logged_client):
    passagens = json.dumps([{
        'protocolo': 'PRO-2099-9000', 'ns': '111111', 'ns_novo': '222222',
        'pedido': '95795', 'data_entrada': '01/01/2026', 'data_saida': '10/01/2026',
    }], ensure_ascii=False)
    _criar(app, 'PRO-2099-9317', 'rma', order_number='95795',
           rma_passagens=passagens)

    resp = logged_client.get('/protocolos/buscar-historico?q=95795')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'PRO-2099-9317' in html
    assert 'Passagens registradas' in html
    assert '111111' in html and '222222' in html
