from pathlib import Path

from app.labels import PROTO_TYPE_BADGES

CSS = Path(__file__).resolve().parents[1] / 'app' / 'static' / 'css' / 'style.css'


def test_tipos_de_protocolo_usam_selos_harmonizados():
    assert PROTO_TYPE_BADGES == {
        'venda': 'badge-type-venda',
        'ponta_entrega': 'badge-type-ponta-entrega',
        'rma': 'badge-type-rma',
        'servico': 'badge-type-servico',
        'nao_comprado': 'badge-type-nao-comprado',
    }


def test_css_tem_uma_classe_para_cada_tipo():
    css = CSS.read_text(encoding='utf-8')
    for classe in PROTO_TYPE_BADGES.values():
        assert f'.{classe}' in css
