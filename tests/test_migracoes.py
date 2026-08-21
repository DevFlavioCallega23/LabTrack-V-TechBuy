from datetime import datetime

from sqlalchemy import text

from app import db as _db, add_missing_columns


def _sql_insert(app, sql):
    with _db.engine.begin() as conn:
        conn.execute(text(sql))


def test_migracao_venda_ponta_entrega(app):
    with app.app_context():
        uid = _db.session.execute(text('select id from user where role=\'master\' limit 1')).scalar()
        _sql_insert(app,
            "INSERT INTO protocol (protocol_number, type, client_name, created_by) "
            "VALUES ('PRO-2098-8001', 'venda_ponta_entrega', 'Legacy PE', %d)" % uid)
        add_missing_columns()
        tipo, pe = _db.session.execute(text(
            "select type, venda_pe from protocol where protocol_number='PRO-2098-8001'")).fetchone()
        assert tipo == 'venda'
        assert int(pe) == 1
        _db.session.execute(text("delete from protocol where protocol_number='PRO-2098-8001'"))
        _db.session.commit()


def test_migracao_rma_fora_de_garantia_vira_servico(app):
    with app.app_context():
        uid = _db.session.execute(text('select id from user where role=\'master\' limit 1')).scalar()
        _sql_insert(app,
            "INSERT INTO protocol (protocol_number, type, client_name, created_by, rma_in_warranty) "
            "VALUES ('PRO-2098-8002', 'rma', 'Legacy RMA', %d, 0)" % uid)
        add_missing_columns()
        tipo = _db.session.execute(text(
            "select type from protocol where protocol_number='PRO-2098-8002'")).fetchone()[0]
        assert tipo == 'servico'
        _db.session.execute(text("delete from protocol where protocol_number='PRO-2098-8002'"))
        _db.session.commit()


def test_migracoes_sao_idempotentes(app):
    with app.app_context():
        add_missing_columns()
        add_missing_columns()
        total = _db.session.execute(
            text("select count(*) from protocol where type in ('venda_ponta_entrega')")).scalar()
        assert total == 0