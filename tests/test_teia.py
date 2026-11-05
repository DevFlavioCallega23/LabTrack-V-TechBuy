import json
from datetime import datetime

from app import db as _db
from app.models import Component, Protocol, User


def _uid(app):
    with app.app_context():
        return User.query.filter_by(role='master').first().id


def _criar(app, numero, tipo, **kwargs):
    kwargs.setdefault('entry_date', datetime(2026, 7, 1))
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


def _add_comp(app, pid, tipo='ram', modelo='8GB DDR3 Kingston',
              ns='TEIA-NS-0001', unit='01'):
    with app.app_context():
        _db.session.add(Component(
            protocol_id=pid,
            component_type=tipo,
            specification=modelo,
            serial_number=ns,
            unit=unit,
            machine_name='Computador ' + unit,
            sort_order=int(unit) * 100,
            is_prebuilt=True,
        ))
        _db.session.commit()


def _html(client, pid):
    resp = client.get(f'/protocolos/{pid}/teia')
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def test_detalhe_tem_botao_teia(app, logged_client):
    pid = _criar(app, 'PRO-2099-9401', 'rma', client_name='Cliente Botao Teia')
    html = logged_client.get(f'/protocolos/{pid}').get_data(as_text=True)
    assert f'/protocolos/{pid}/teia' in html
    assert 'Teia' in html


def test_teia_liga_retorno_ao_protocolo_anterior(app, logged_client):
    origem_id = _criar(app, 'PRO-2099-9402', 'rma',
                       client_name='Cliente Retorno Teia')
    resp = logged_client.post(f'/protocolos/{origem_id}/novo-retorno',
                              data={'type': 'servico'})
    assert resp.status_code == 302

    with app.app_context():
        novo = Protocol.query.filter_by(origin_id=origem_id).one()
        novo_numero = novo.protocol_number

        html = _html(logged_client, novo.id)

    assert 'PRO-2099-9402' in html
    assert novo_numero in html
    assert 'Retorno' in html
    assert 'Somente leitura' in html


def test_teia_liga_protocolos_do_mesmo_pedido(app, logged_client):
    a = _criar(app, 'PRO-2099-9403', 'venda',
               client_name='Cliente Pedido Teia', order_number='TEIA-PED-1')
    b = _criar(app, 'PRO-2099-9404', 'rma',
               client_name='Cliente Pedido Teia', order_number='TEIA-PED-1')

    html = _html(logged_client, a)
    assert 'PRO-2099-9404' in html
    assert 'Mesmo pedido' in html
    assert 'Pedido TEIA-PED-1' in html

    html = _html(logged_client, b)
    assert 'PRO-2099-9403' in html
    assert 'Mesmo pedido' in html


def test_teia_liga_venda_com_pronta_entrega(app, logged_client):
    pe_id = _criar(app, 'PRO-2099-9405', 'ponta_entrega',
                   client_name='Cliente PE Teia')
    venda_id = _criar(
        app, 'PRO-2099-9406', 'venda',
        client_name='Cliente PE Teia',
        pe_refs=json.dumps({'01': {
            'protocol_id': pe_id,
            'protocol_number': 'PRO-2099-9405',
            'unit': '01',
            'fonte': 'TEIA-FONTE-9405',
            'machine_name': 'Computador 01',
        }}, ensure_ascii=False))

    html = _html(logged_client, venda_id)
    assert 'PRO-2099-9405' in html
    assert 'Venda ↔ PE' in html
    assert 'TEIA-FONTE-9405' in html

    html = _html(logged_client, pe_id)
    assert 'PRO-2099-9406' in html


def test_teia_liga_pelo_ns_mesmo_com_pedido_nil(app, logged_client):
    venda_id = _criar(app, 'PRO-2099-9407', 'venda',
                      client_name='Cliente NS Teia', order_number='NIL')
    _add_comp(app, venda_id, ns='TEIA-NS-9407')
    rma_id = _criar(app, 'PRO-2099-9408', 'rma',
                    client_name='Outro Cliente NS')
    _add_comp(app, rma_id, ns='TEIA-NS-9407')

    html = _html(logged_client, venda_id)
    assert 'PRO-2099-9408' in html
    assert 'Mesmo NS' in html
    assert 'TEIA-NS-9407' in html
    # O NS repetido aparece na conferência
    assert 'NS que aparecem em mais de um protocolo' in html


def test_teia_liga_protocolos_do_mesmo_cliente(app, logged_client):
    a = _criar(app, 'PRO-2099-9409', 'servico',
               client_name='CLIENTE REPETIDO TEIA')
    b = _criar(app, 'PRO-2099-9410', 'nao_comprado',
               client_name='CLIENTE REPETIDO TEIA')

    html = _html(logged_client, a)
    assert 'PRO-2099-9410' in html
    assert 'Mesmo cliente' in html


def test_teia_nao_altera_nenhum_protocolo(app, logged_client):
    origem_id = _criar(app, 'PRO-2099-9411', 'rma',
                       client_name='Cliente Intocado Teia')
    with app.app_context():
        novo = Protocol(
            protocol_number='PRO-2099-9412',
            type='rma',
            client_name='Cliente Intocado Teia',
            status='pendente',
            origin_id=origem_id,
            created_by=_uid(app),
        )
        _db.session.add(novo)
        _db.session.commit()
        novo_id = novo.id
        antes = {
            p.id: (p.origin_id, p.status, p.client_name, p.rma_equip_itens,
                   p.rma_trocados, p.rma_test_result, p.order_number)
            for p in Protocol.query.filter(
                Protocol.id.in_([origem_id, novo_id])).all()
        }

    _html(logged_client, origem_id)
    _html(logged_client, novo_id)

    with app.app_context():
        depois = {
            p.id: (p.origin_id, p.status, p.client_name, p.rma_equip_itens,
                   p.rma_trocados, p.rma_test_result, p.order_number)
            for p in Protocol.query.filter(
                Protocol.id.in_([origem_id, novo_id])).all()
        }
    assert antes == depois


def test_teia_mostra_caixa_do_protocolo_atual_e_tabela_de_ns(app, logged_client):
    pid = _criar(app, 'PRO-2099-9413', 'rma', client_name='Cliente Desenho Teia')
    _add_comp(app, pid, ns='TEIA-NS-9413')

    html = _html(logged_client, pid)
    assert '<svg' in html
    assert 'PRO-2099-9413' in html
    assert 'NS de cada protocolo' in html
    assert 'TEIA-NS-9413' in html
    assert 'Clique em uma caixa para abrir o protocolo' in html


def test_busca_de_historico_tem_link_para_teia(app, logged_client):
    pid = _criar(app, 'PRO-2099-9414', 'rma',
                 client_name='Cliente Link Teia', order_number='TEIA-LINK-1')
    html = logged_client.get(
        '/protocolos/buscar-historico?q=TEIA-LINK-1').get_data(as_text=True)
    assert f'/protocolos/{pid}/teia' in html
