"""Regra de "dados incompletos" do NTB (não comprado na TechBuy).

NTB não tem pedido nem data de compra; o alerta deve cobrar apenas
cliente, vendedor e algum equipamento registrado.
"""
import json

from app import db as _db
from app.models import Protocol, User
from app.routes.protocols.helpers import get_incomplete_fields


def _criar(numero, **campos):
    uid = User.query.filter_by(role='master').first().id
    protocol = Protocol(protocol_number=numero, type='nao_comprado',
                        created_by=uid, **campos)
    _db.session.add(protocol)
    _db.session.commit()
    return protocol


def _apagar(protocol):
    _db.session.delete(protocol)
    _db.session.commit()


def test_ntb_com_teste_de_mesa_nao_exige_pedido(app):
    with app.app_context():
        p = _criar('PRO-2097-9001', client_name='Cliente', seller='Janay',
                   rma_test_result=json.dumps([
                       {'component': 'ssd', 'model': 'HDM 500GB', 'defeito': 'Lento'}
                   ]))
        assert get_incomplete_fields(p) == []
        _apagar(p)


def test_ntb_com_equipamento_do_cliente_esta_completo(app):
    with app.app_context():
        p = _criar('PRO-2097-9002', client_name='Cliente', seller='Janay',
                   rma_equip_itens=json.dumps({
                       '1': {'name': 'PC', 'components': [{'type': 'ssd'}]}
                   }))
        assert get_incomplete_fields(p) == []
        _apagar(p)


def test_ntb_vazio_avisa_apenas_equipamento(app):
    with app.app_context():
        p = _criar('PRO-2097-9003', client_name='Cliente', seller='Janay',
                   rma_test_result='[]')
        assert get_incomplete_fields(p) == ['Equipamento']
        _apagar(p)
