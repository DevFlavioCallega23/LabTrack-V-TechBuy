from datetime import datetime

from app import db as _db
from app.datas import parse_date_br
from app.forms import ProtocolForm
from app.models import Protocol, User


def test_parse_date_br_formatos():
    assert parse_date_br('05/03/2026') == datetime(2026, 3, 5)
    assert parse_date_br('13/07/26') == datetime(2026, 7, 13)
    assert parse_date_br('2026-03-05') == datetime(2026, 3, 5)
    assert parse_date_br(' 05/03/2026 ') == datetime(2026, 3, 5)


def test_parse_date_br_invalido_e_vazio():
    assert parse_date_br(None) is None
    assert parse_date_br('') is None
    assert parse_date_br('   ') is None
    assert parse_date_br('99/99/2026') is None
    assert parse_date_br('abc') is None


def _form(**dados):
    from werkzeug.datastructures import MultiDict
    dados.setdefault('type', 'rma')
    return ProtocolForm(MultiDict(dados), meta={'csrf': False})


def test_form_aceita_data_valida(app):
    with app.app_context():
        form = _form(entry_date='05/03/2026', rma_entry_date='07/03/2026')
        form.validate()
        assert 'entry_date' not in form.errors
        assert 'rma_entry_date' not in form.errors


def test_form_rejeita_data_invalida(app):
    with app.app_context():
        form = _form(entry_date='abc', rma_entry_date='99/99/2026', exit_date='31/02/2026')
        form.validate()
        assert 'entry_date' in form.errors
        assert 'rma_entry_date' in form.errors
        assert 'exit_date' in form.errors


def test_form_permite_data_vazia(app):
    with app.app_context():
        form = _form(entry_date='', rma_entry_date=None)
        form.validate()
        assert 'entry_date' not in form.errors
        assert 'rma_entry_date' not in form.errors


def test_rma_entry_date_e_datetime_no_modelo(app):
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
        p = Protocol(protocol_number='PRO-2099-7001', type='rma', status='pendente',
                     client_name='Cliente Datas', seller='Myris',
                     entry_date=datetime(2026, 3, 5),
                     rma_entry_date=datetime(2026, 3, 7),
                     created_by=uid)
        _db.session.add(p)
        _db.session.commit()
        pid = p.id

        p2 = _db.session.get(Protocol, pid)
        assert isinstance(p2.rma_entry_date, datetime)
        assert p2.rma_entry_date == datetime(2026, 3, 7)
        _db.session.delete(p2)
        _db.session.commit()
