import json
from datetime import datetime

from app import db as _db
from app.models import Component, Protocol, User
from app.routes.protocols.helpers import sugestoes_preenchimento


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


def test_teia_coloca_mesmo_ns_outra_maquina_como_ramo_lateral(app, logged_client):
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
    assert 'Ramo de peça' in html
    # O NS repetido aparece na conferência de ligações reais
    assert 'NS que aparecem em mais de um protocolo' in html


def test_teia_mostra_contexto_do_mesmo_cliente(app, logged_client):
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


def test_teia_mostra_linha_do_tempo_vertical(app, logged_client):
    antigo = _criar(app, 'PRO-2099-9413', 'rma',
                    client_name='Cliente Desenho Teia',
                    entry_date=datetime(2026, 7, 1))
    _add_comp(app, antigo, ns='TEIA-NS-9413')
    novo = _criar(app, 'PRO-2099-9415', 'rma',
                  client_name='Cliente Desenho Teia',
                  entry_date=datetime(2026, 8, 1))
    _add_comp(app, novo, ns='TEIA-NS-9413')

    html = _html(logged_client, antigo)
    assert 'Linha do tempo da máquina' in html
    assert 'Mais antigo embaixo' in html
    assert 'NS de cada protocolo' in html
    assert 'TEIA-NS-9413' in html
    # Mais novo aparece antes (em cima) na linha do tempo.
    trecho = html.split('Linha do tempo da máquina', 1)[1]
    assert trecho.index('PRO-2099-9415') < trecho.index('PRO-2099-9413')


def test_teia_nao_liga_ns_com_peca_diferente(app, logged_client):
    a = _criar(app, 'PRO-2099-9416', 'venda',
               client_name='Cliente Peca Diferente')
    _add_comp(app, a, tipo='ram', ns='TEIA-NS-9416')
    b = _criar(app, 'PRO-2099-9417', 'rma',
               client_name='Cliente Peca Diferente')
    _add_comp(app, b, tipo='fonte', ns='TEIA-NS-9416')

    html = _html(logged_client, a)
    assert 'Conferir: NS repetido com peça diferente' in html
    assert 'PRO-2099-9417' in html
    assert 'Memória RAM' in html
    assert 'Fonte' in html


def test_teia_sugere_preencher_pedido_nil(app, logged_client):
    venda = _criar(app, 'PRO-2099-9418', 'venda',
                   client_name='Cliente NIL Teia', order_number='NIL')
    _add_comp(app, venda, ns='TEIA-NS-9418')
    rma = _criar(app, 'PRO-2099-9419', 'rma',
                 client_name='Cliente NIL Teia', order_number='957890')
    _add_comp(app, rma, ns='TEIA-NS-9418')

    html = _html(logged_client, venda)
    assert 'Preenchimento automático?' in html
    assert '957890' in html

    with app.app_context():
        protocolo = _db.session.get(Protocol, venda)
        pacote = sugestoes_preenchimento(protocolo)
        indices = [
            str(i) for i, item in enumerate(pacote['itens'])
            if item['protocolo_id'] == venda and item['campo'] == 'order_number'
        ]
    assert indices

    resp = logged_client.post(f'/protocolos/{venda}/teia/preencher',
                              data={'sugestao': indices})
    assert resp.status_code == 302

    with app.app_context():
        assert _db.session.get(Protocol, venda).order_number == '957890'


def test_teia_sugere_vinculo_e_passagem_de_rma(app, logged_client):
    antigo = _criar(app, 'PRO-2099-9420', 'rma',
                    client_name='Cliente Passagem Teia',
                    order_number='957891')
    _add_comp(app, antigo, ns='TEIA-NS-9420')
    novo = _criar(app, 'PRO-2099-9421', 'rma',
                  client_name='Cliente Passagem Teia',
                  order_number='957891',
                  entry_date=datetime(2026, 8, 1))
    _add_comp(app, novo, ns='TEIA-NS-9420')

    with app.app_context():
        protocolo = _db.session.get(Protocol, novo)
        pacote = sugestoes_preenchimento(protocolo)
        tipos = {item['tipo'] for item in pacote['itens']
                 if item['protocolo_id'] == novo}
        indices = [
            str(i) for i, item in enumerate(pacote['itens'])
            if item['protocolo_id'] == novo
            and item['tipo'] in ('origem', 'passagem')
        ]
    assert 'origem' in tipos
    assert 'passagem' in tipos
    assert indices

    resp = logged_client.post(f'/protocolos/{novo}/teia/preencher',
                              data={'sugestao': indices})
    assert resp.status_code == 302

    with app.app_context():
        atualizado = _db.session.get(Protocol, novo)
        assert atualizado.origin_id == antigo
        passagens = json.loads(atualizado.rma_passagens or '[]')
        assert any(p.get('protocolo') == 'PRO-2099-9420' for p in passagens)


def test_teia_marca_retorno_de_rma_no_detalhe(app, logged_client):
    origem = _criar(app, 'PRO-2099-9422', 'rma',
                    client_name='Cliente Selo Teia')
    novo = _criar(app, 'PRO-2099-9423', 'rma',
                  client_name='Cliente Selo Teia',
                  origin_id=origem)
    html = logged_client.get(f'/protocolos/{novo}').get_data(as_text=True)
    assert 'Retorno de RMA' in html


def test_teia_tem_aba_de_ajuste_da_identificacao(app, logged_client):
    pid = _criar(app, 'PRO-2099-9424', 'venda',
                 client_name='Cliente Ajuste Teia', order_number='NIL')

    html = logged_client.get(f'/protocolos/{pid}/teia/ajustar').get_data(as_text=True)
    assert 'Ajustar identificação' in html
    assert 'client_name' in html
    assert 'original_order' in html

    resp = logged_client.post(f'/protocolos/{pid}/teia/ajustar', data={
        'client_name': 'Cliente Ajustado',
        'order_number': '957892',
        'original_order': '957892',
        'seller': 'Myris',
        'lote': '2',
    })
    assert resp.status_code == 302

    with app.app_context():
        protocolo = _db.session.get(Protocol, pid)
        assert protocolo.client_name == 'Cliente Ajustado'
        assert protocolo.order_number == '957892'
        assert protocolo.original_order == '957892'
        assert protocolo.seller == 'Myris'
        assert protocolo.lote == '2'


def test_busca_de_historico_tem_link_para_teia(app, logged_client):
    pid = _criar(app, 'PRO-2099-9414', 'rma',
                 client_name='Cliente Link Teia', order_number='TEIA-LINK-1')
    html = logged_client.get(
        '/protocolos/buscar-historico?q=TEIA-LINK-1').get_data(as_text=True)
    assert f'/protocolos/{pid}/teia' in html


def test_voltar_do_protocolo_retorna_para_a_teia(app, logged_client):
    pid = _criar(app, 'PRO-2099-9430', 'rma', client_name='Cliente Voltar Teia')
    html = logged_client.get(
        f'/protocolos/{pid}?voltar=/protocolos/{pid}/teia').get_data(as_text=True)
    assert 'Voltar para a teia' in html
    assert f'href="/protocolos/{pid}/teia"' in html


def test_voltar_do_protocolo_retorna_para_o_rastreio_de_ns(app, logged_client):
    pid = _criar(app, 'PRO-2099-9431', 'rma', client_name='Cliente Voltar NS')
    html = logged_client.get(
        f'/protocolos/{pid}',
        headers={'Referer': '/ns?busca=NS-VOLTAR-1'}).get_data(as_text=True)
    assert 'Voltar para o rastreio de NS' in html
    assert 'href="/ns?busca=NS-VOLTAR-1"' in html


def test_voltar_ignora_endereco_externo(app, logged_client):
    pid = _criar(app, 'PRO-2099-9432', 'rma', client_name='Cliente Voltar Externo')
    html = logged_client.get(
        f'/protocolos/{pid}?voltar=https://exemplo.com/fora').get_data(as_text=True)
    assert 'Voltar para protocolos' in html
    assert 'exemplo.com' not in html


def test_links_da_teia_levam_o_caminho_de_volta(app, logged_client):
    origem_id = _criar(app, 'PRO-2099-9433', 'rma',
                       client_name='Cliente Link Volta Teia')
    novo_id = _criar(app, 'PRO-2099-9434', 'rma',
                     client_name='Cliente Link Volta Teia', origin_id=origem_id)
    html = _html(logged_client, novo_id)
    assert f'/protocolos/{origem_id}?voltar=/protocolos/{novo_id}/teia' in html


def test_links_do_rastreio_ns_levam_o_caminho_de_volta(app, logged_client):
    pid = _criar(app, 'PRO-2099-9435', 'rma', client_name='Cliente Link Volta NS')
    _add_comp(app, pid, ns='NS-VOLTA-9435')
    html = logged_client.get(
        '/ns?busca=NS-VOLTA-9435').get_data(as_text=True)
    from urllib.parse import unquote
    import re
    achado = re.search(r'href="(/protocolos/%d\?voltar=[^"]+)"' % pid, html)
    assert achado, html
    assert unquote(achado.group(1)) == (
        f'/protocolos/{pid}?voltar=/ns?busca=NS-VOLTA-9435')
