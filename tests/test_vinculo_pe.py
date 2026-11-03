import json
from datetime import datetime

from werkzeug.datastructures import MultiDict

from app import db as _db
from app.models import Component, Protocol, User
from app.routes.protocols.helpers import (
    aplicar_vinculos_pe,
    buscar_pronta_entrega,
    limpar_vinculos_pe,
    normalizar_ns,
    ns_bate,
    parse_pe_refs,
    parse_sale_refs,
    pe_por_maquina,
    vendas_por_maquina_pe,
)


def _uid(app):
    with app.app_context():
        return User.query.filter_by(role='master').first().id


def _criar_protocolo(app, numero, tipo, **kwargs):
    with app.app_context():
        p = Protocol(
            protocol_number=numero,
            type=tipo,
            created_by=_uid(app),
            entry_date=datetime(2026, 2, 1),
            status='concluido',
            **kwargs
        )
        _db.session.add(p)
        _db.session.commit()
        return p.id


def _add_comp(app, pid, unit, tipo, modelo, ns, nome='Máquina 01'):
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


def _pe_com_maquina(app, numero, unit='01', fonte='158418', nome='Máquina 05'):
    pid = _criar_protocolo(app, numero, 'ponta_entrega')
    _add_comp(app, pid, unit, 'processador', 'I3-2120', '158410', nome)
    _add_comp(app, pid, unit, 'placa_mae', 'H61 UpGamer', '701268', nome)
    _add_comp(app, pid, unit, 'ram', '8GB DDR3', '144606', nome)
    _add_comp(app, pid, unit, 'ssd', 'SSD 120GB', '144560', nome)
    _add_comp(app, pid, unit, 'fonte', 'Fonte 230W VxPro', fonte, nome)
    return pid


def _venda_com_pe(app, numero, pe_id, unit='01', fonte='158418'):
    refs = {
        unit: {
            'protocol_id': pe_id,
            'unit': unit,
            'fonte': fonte,
            'machine_name': 'Máquina 05',
        }
    }
    venda_id = _criar_protocolo(
        app, numero, 'venda',
        venda_pe=True,
        client_name='Leandro Rosales',
        pe_refs=json.dumps(refs),
    )
    _add_comp(app, venda_id, unit, 'fonte', 'Fonte 230W VxPro', fonte, 'M?quina 01')
    return venda_id


def test_normalizacao_de_ns():
    assert normalizar_ns(' R - 157579 ') == '157579'
    assert normalizar_ns('r-15 75 79') == '157579'
    assert ns_bate('R - 157579', '157579')
    assert ns_bate('001062', '1062')
    assert not ns_bate('144003', '')
    assert not ns_bate('144003', '144004')


def test_busca_por_ns_encontra_pe_e_ignora_outros_tipos(app):
    pe_id = _pe_com_maquina(app, 'PRO-2099-9201')
    # Mesmo NS existindo como RAM em outro protocolo não pode aparecer.
    outro = _criar_protocolo(app, 'PRO-2099-9202', 'venda')
    _add_comp(app, outro, '01', 'ram', '8GB DDR3', '158418')

    with app.app_context():
        achados = buscar_pronta_entrega(ns='R - 15 8418')
        assert len(achados) == 1
        assert achados[0]['protocol_id'] == pe_id
        assert achados[0]['unit'] == '01'
        assert achados[0]['fonte'] == '158418'
        assert achados[0]['disponivel'] is True
        assert any(c['type'] == 'fonte' and c['serial'] == '158418'
                   for c in achados[0]['components'])


def test_busca_por_protocolo_e_bloco(app):
    pe_id = _pe_com_maquina(app, 'PRO-2099-9203', unit='09', fonte='158418')
    with app.app_context():
        achados = buscar_pronta_entrega(pe_numero='PRO-2099-9203', unit='9')
        assert len(achados) == 1
        assert achados[0]['protocol_id'] == pe_id
        assert achados[0]['unit'] == '09'
        achados = buscar_pronta_entrega(pe_numero='2099-9203')
        assert len(achados) == 1


def test_api_de_busca_responde_json(logged_client, app):
    _pe_com_maquina(app, 'PRO-2099-9204', fonte='158419')
    r = logged_client.get('/protocolos/api/pronta-entrega/buscar?ns=R%20-%20158419')
    assert r.status_code == 200
    dados = r.get_json()
    assert dados['ok'] is True
    assert dados['total'] == 1
    assert dados['resultados'][0]['protocol_number'] == 'PRO-2099-9204'


def test_api_de_busca_sem_termo(logged_client):
    r = logged_client.get('/protocolos/api/pronta-entrega/buscar')
    assert r.status_code == 200
    assert r.get_json()['ok'] is False


def test_aplicar_e_limpar_vinculo_entre_venda_e_pe(app):
    pe_id = _pe_com_maquina(app, 'PRO-2099-9205', fonte='158420')
    venda_id = _venda_com_pe(app, 'PRO-2099-9206', pe_id, fonte='158420')

    with app.app_context():
        venda = Protocol.query.get(venda_id)
        aplicar_vinculos_pe(venda)
        _db.session.commit()

        pe = Protocol.query.get(pe_id)
        ref = pe.get_sale_refs()['01']
        assert ref['sale_id'] == venda_id
        assert ref['sale_number'] == 'PRO-2099-9206'
        assert 'Leandro Rosales' in ref['text']

        vendas = vendas_por_maquina_pe(pe)
        assert vendas['01'][0]['protocol_number'] == 'PRO-2099-9206'

        origens = pe_por_maquina(venda)
        assert origens['01']['protocol_number'] == 'PRO-2099-9205'

        limpar_vinculos_pe(venda, venda.get_pe_refs(), {})
        _db.session.commit()
        pe = Protocol.query.get(pe_id)
        assert pe.get_sale_refs() == {}


def test_cancelar_venda_libera_a_maquina_e_reativar_vincula(logged_client, app):
    pe_id = _pe_com_maquina(app, 'PRO-2099-9207', fonte='158421')
    venda_id = _venda_com_pe(app, 'PRO-2099-9208', pe_id, fonte='158421')

    with app.app_context():
        aplicar_vinculos_pe(Protocol.query.get(venda_id))
        _db.session.commit()

    r = logged_client.post(f'/protocolos/{venda_id}/status', json={'status': 'cancelado'})
    assert r.status_code == 200
    with app.app_context():
        assert Protocol.query.get(pe_id).get_sale_refs() == {}
        assert buscar_pronta_entrega(ns='158421')[0]['disponivel'] is True

    r = logged_client.post(f'/protocolos/{venda_id}/status', json={'status': 'concluido'})
    assert r.status_code == 200
    with app.app_context():
        assert Protocol.query.get(pe_id).get_sale_refs()['01']['sale_number'] == 'PRO-2099-9208'


def test_parse_dos_vinculos_da_venda_e_da_pe():
    pe_form = MultiDict([
        ('pe_ref_json_01', json.dumps({
            'protocol_id': 42, 'unit': '9', 'fonte': '158418',
            'machine_name': 'Máquina 05',
        })),
    ])
    refs = json.loads(parse_pe_refs(pe_form))
    assert refs['01']['protocol_id'] == 42
    assert refs['01']['unit'] == '09'

    sale_form = MultiDict([
        ('sale_ref_01', 'PRO-2099-9209 · Cliente'),
        ('sale_ref_id_01', '99'),
        ('sale_ref_number_01', 'PRO-2099-9209'),
    ])
    refs = json.loads(parse_sale_refs(sale_form))
    assert refs['01']['sale_id'] == 99
    assert refs['01']['sale_number'] == 'PRO-2099-9209'

    # Texto alterado à mão deixa de ser vínculo automático.
    sale_form = MultiDict([
        ('sale_ref_01', 'Venda antiga sem número'),
        ('sale_ref_id_01', '99'),
        ('sale_ref_number_01', 'PRO-2099-9209'),
    ])
    refs = json.loads(parse_sale_refs(sale_form))
    assert refs['01']['sale_id'] is None
    assert refs['01']['sale_number'] is None


def test_detalhe_da_pe_mostra_referencia_de_venda(logged_client, app):
    pe_id = _pe_com_maquina(app, 'PRO-2099-9210', fonte='158422')
    venda_id = _venda_com_pe(app, 'PRO-2099-9211', pe_id, fonte='158422')
    with app.app_context():
        aplicar_vinculos_pe(Protocol.query.get(venda_id))
        _db.session.commit()

    r = logged_client.get(f'/protocolos/{pe_id}')
    assert r.status_code == 200
    texto = r.data.decode('utf-8')
    assert 'Referência de Venda' in texto
    assert 'PRO-2099-9211' in texto
    assert 'Nº 01' in texto
    # O selo PE não aparece dentro de uma Pronta-Entrega.
    assert '>PE<' not in texto


def test_detalhe_da_venda_mostra_origem_pe(logged_client, app):
    pe_id = _pe_com_maquina(app, 'PRO-2099-9212', fonte='158423')
    venda_id = _venda_com_pe(app, 'PRO-2099-9213', pe_id, fonte='158423')
    r = logged_client.get(f'/protocolos/{venda_id}')
    assert r.status_code == 200
    texto = r.data.decode('utf-8')
    assert 'Pronta-Entrega de origem' in texto
    assert 'PRO-2099-9212' in texto


def test_tela_de_edicao_carrega_os_vinculos(logged_client, app):
    pe_id = _pe_com_maquina(app, 'PRO-2099-9214', fonte='158424')
    venda_id = _venda_com_pe(app, 'PRO-2099-9215', pe_id, fonte='158424')
    with app.app_context():
        aplicar_vinculos_pe(Protocol.query.get(venda_id))
        _db.session.commit()

    r = logged_client.get(f'/protocolos/{pe_id}/editar')
    assert r.status_code == 200
    texto = r.data.decode('utf-8')
    assert 'protocolType: "ponta_entrega"' in texto
    assert 'saleRefs:' in texto
    assert 'PRO-2099-9215' in texto

    r = logged_client.get(f'/protocolos/{venda_id}/editar')
    assert r.status_code == 200
    texto = r.data.decode('utf-8')
    assert 'protocolType: "venda"' in texto
    assert 'peRefs:' in texto
    assert 'protocol_id' in texto


def test_referencia_editada_a_mao_aparece_no_detalhe(logged_client, app):
    pe_id = _pe_com_maquina(app, 'PRO-2099-9216', fonte='158425')
    venda_id = _venda_com_pe(app, 'PRO-2099-9217', pe_id, fonte='158425')
    with app.app_context():
        aplicar_vinculos_pe(Protocol.query.get(venda_id))
        _db.session.commit()
        pe = Protocol.query.get(pe_id)
        refs = pe.get_sale_refs()
        refs['01']['text'] += ' · SSD 240GB (144999)'
        pe.sale_refs = json.dumps(refs)
        _db.session.commit()

    r = logged_client.get(f'/protocolos/{pe_id}')
    assert r.status_code == 200
    texto = r.data.decode('utf-8')
    assert 'SSD 240GB (144999)' in texto
    assert 'Vendida' in texto


def test_excluir_pe_limpa_o_vinculo_da_venda(logged_client, app):
    pe_id = _pe_com_maquina(app, 'PRO-2099-9218', fonte='158426')
    venda_id = _venda_com_pe(app, 'PRO-2099-9219', pe_id, fonte='158426')
    with app.app_context():
        aplicar_vinculos_pe(Protocol.query.get(venda_id))
        _db.session.commit()

    r = logged_client.post(f'/protocolos/{pe_id}/excluir')
    assert r.status_code == 302
    with app.app_context():
        assert Protocol.query.get(venda_id).get_pe_refs() == {}
        assert Protocol.query.get(pe_id) is None


def test_pdf_da_pe_mostra_referencia_e_numero_do_bloco(logged_client, app, monkeypatch):
    from types import SimpleNamespace
    from xhtml2pdf import pisa

    pe_id = _pe_com_maquina(app, 'PRO-2099-9220', fonte='158427')
    venda_id = _venda_com_pe(app, 'PRO-2099-9221', pe_id, fonte='158427')
    with app.app_context():
        aplicar_vinculos_pe(Protocol.query.get(venda_id))
        _db.session.commit()

    capturado = []

    def capturar_html(source, dest, encoding):
        capturado.append(source.getvalue())
        dest.write(b'%PDF-teste')
        return SimpleNamespace(err=0)

    monkeypatch.setattr(pisa, 'CreatePDF', capturar_html)
    r = logged_client.get(f'/protocolos/{pe_id}/pdf')
    assert r.status_code == 200
    html = capturado[0]
    assert 'Nº 01' in html
    assert 'Referência de Venda' in html
    assert 'PRO-2099-9221' in html
    assert '>PE<' not in html


def test_pdf_da_venda_mostra_origem_pe(logged_client, app, monkeypatch):
    from types import SimpleNamespace
    from xhtml2pdf import pisa

    pe_id = _pe_com_maquina(app, 'PRO-2099-9222', fonte='158428')
    venda_id = _venda_com_pe(app, 'PRO-2099-9223', pe_id, fonte='158428')

    capturado = []

    def capturar_html(source, dest, encoding):
        capturado.append(source.getvalue())
        dest.write(b'%PDF-teste')
        return SimpleNamespace(err=0)

    monkeypatch.setattr(pisa, 'CreatePDF', capturar_html)
    r = logged_client.get(f'/protocolos/{venda_id}/pdf')
    assert r.status_code == 200
    html = capturado[0]
    assert 'Pronta-Entrega de origem' in html
    assert 'PRO-2099-9222' in html
    assert '158428' in html
