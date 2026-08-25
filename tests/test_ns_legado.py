import json
from app import db as _db
from app.models import Protocol, User
from app.routes.protocols import _ns_ocorrencias_protocolo

def test_ns_todos_sobrevive_json_antigo(app):
    with app.app_context():
        uid = User.query.filter_by(role="master").first().id
        p = Protocol(protocol_number="PRO-2094-3001", type="rma",
                     client_name="legado", rma_in_warranty=True,
                     rma_passagens=json.dumps([{"protocolo": "PRO-2026-0001", "ns": "NSVELHO1"}]),
                     rma_test_result=json.dumps([{"component": "ram", "model": "8GB"}]),
                     created_by=uid)
        _db.session.add(p)
        _db.session.commit()
        ocs = _ns_ocorrencias_protocolo(p, None)
        valores = [o["valor"] for o in ocs if o["valor"]]
        assert "NSVELHO1" in valores
        assert None not in valores
