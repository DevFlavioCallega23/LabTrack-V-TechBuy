"""Rotas de protocolos, divididas em blueprints:

- protocols (prefixo /protocolos): CRUD, relatório e status do protocolo
- usuarios: cadastro de usuários e conta própria
- defeitos (prefixo /defeitos): listagem, exportação e status de defeitos
- busca: busca avançada, NS e rastreios
"""
from flask import Blueprint

protocols_bp = Blueprint('protocols', __name__, url_prefix='/protocolos')

from app.routes.protocols import core  # noqa: E402,F401
from app.routes.protocols import usuarios as _usuarios  # noqa: E402,F401
from app.routes.protocols import defeitos as _defeitos  # noqa: E402,F401
from app.routes.protocols import busca as _busca  # noqa: E402,F401

# Reexporta simbolos usados fora (testes e outras rotas).
from app.routes.protocols.usuarios import usuarios_bp  # noqa: E402,F401
from app.routes.protocols.defeitos import defeitos_bp  # noqa: E402,F401
from app.routes.protocols.busca import busca_bp  # noqa: E402,F401
from app.routes.protocols.helpers import gerar_numero_protocolo, get_incomplete_fields  # noqa: E402,F401
from app.routes.protocols.ocorrencias import _ns_ocorrencias_protocolo  # noqa: E402,F401
