from datetime import datetime

from app import db as _db
from app.models import Protocol, User
from app.routes.protocols import gerar_numero_protocolo


def test_numeracao_comeca_em_0001(app):
    with app.app_context():
        numero = gerar_numero_protocolo()
        ano = datetime.utcnow().year
        assert numero == f'PRO-{ano}-0001'


def test_numeracao_incrementa_e_reinicia_por_ano(app):
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
        ano = datetime.utcnow().year

        n1 = gerar_numero_protocolo()
        _db.session.add(Protocol(protocol_number=n1, type='venda',
                                 client_name='t', created_by=uid))
        _db.session.commit()

        n2 = gerar_numero_protocolo()
        assert n1.startswith(f'PRO-{ano}-')
        assert int(n2[-4:]) == int(n1[-4:]) + 1

        # exclusão não pode causar número duplicado
        _db.session.add(Protocol(protocol_number=n2, type='venda',
                                 client_name='t2', created_by=uid))
        _db.session.commit()
        _db.session.delete(Protocol.query.filter_by(protocol_number=n1).first())
        _db.session.commit()
        n3 = gerar_numero_protocolo()
        assert int(n3[-4:]) == int(n2[-4:]) + 1


def test_numeracao_ignora_outros_anos(app):
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
        _db.session.add(Protocol(protocol_number='PRO-2095-7777', type='venda',
                                 client_name='futuro', created_by=uid))
        _db.session.commit()
        ano = datetime.utcnow().year
        numero = gerar_numero_protocolo()
        assert numero.startswith(f'PRO-{ano}-')
        assert '7777' not in numero