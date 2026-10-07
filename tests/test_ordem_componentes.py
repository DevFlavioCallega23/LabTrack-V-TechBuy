"""Regras do Registro de Uso: só tipos com produto e ordem definida em Produtos."""

from app import db
from app.labels import COMPONENT_ORDER
from app.models import Produto, TipoOrdem
from app.routes.estoque import componentes_select


def restaura_ordem():
    return list(COMPONENT_ORDER)


def test_componentes_select_so_com_produto(logged_client, app):
    with app.app_context():
        db.session.add(Produto(component_type='tipo_raro_teste', model_name='Modelo X'))
        db.session.commit()

        tipos = dict(componentes_select())
        assert 'tipo_raro_teste' in tipos

        com_produto = {t for (t,) in db.session.query(Produto.component_type).distinct()}
        sem_produto = [k for k in COMPONENT_ORDER if k not in com_produto]
        for k in sem_produto:
            assert k not in tipos, f'{k} sem produto nao pode aparecer'

        Produto.query.filter_by(component_type='tipo_raro_teste').delete()
        db.session.commit()


def test_componentes_select_preserva_tipo_atual_do_item(app):
    from app.models import EstoqueUso, Component

    original = restaura_ordem()
    with app.app_context():
        item = EstoqueUso.query.first() or EstoqueUso(equipamento='-')
        if not item.id:
            db.session.add(item)
            db.session.flush()
        db.session.add(Component(
            estoque_uso_id=item.id, component_type='tipo_fora_catalogo_teste',
            specification='x'))
        db.session.commit()

        tipos = dict(componentes_select(item))
        assert 'tipo_fora_catalogo_teste' in tipos

        Component.query.filter_by(component_type='tipo_fora_catalogo_teste').delete()
        db.session.commit()
        if not item.components:
            db.session.delete(item)
            db.session.commit()
    COMPONENT_ORDER[:] = original


def test_ordem_salva_e_reordena(logged_client, app):
    original = restaura_ordem()
    try:
        with app.app_context():
            db.session.add_all([
                Produto(component_type='ssd', model_name='A'),
                Produto(component_type='processador', model_name='B'),
            ])
            db.session.commit()

        nova = list(reversed(original))
        r = logged_client.post('/produtos/ordem', data={'ordem[]': nova})
        assert r.status_code == 302
        assert list(COMPONENT_ORDER) == nova

        with app.app_context():
            linhas = TipoOrdem.query.order_by(TipoOrdem.posicao).all()
            assert [l.key for l in linhas] == nova

        r = logged_client.get('/produtos/ordem')
        assert r.status_code == 200
        corpo = r.get_data(as_text=True)
        assert corpo.index('(ssd)') < corpo.index('(processador)')
        assert '(hdd)' not in corpo
        assert '(placa_de_video)' not in corpo
        assert '(cabo_de_forca)' not in corpo
        assert '(outro)' not in corpo
    finally:
        COMPONENT_ORDER[:] = original
        with app.app_context():
            TipoOrdem.query.delete()
            Produto.query.filter_by(component_type='ssd').delete()
            Produto.query.filter_by(component_type='processador').delete()
            db.session.commit()


def test_ordem_lista_so_tipos_com_produto(logged_client, app):
    with app.app_context():
        db.session.add(Produto(component_type='tipo_ordem_teste', model_name='Z'))
        db.session.commit()

        r = logged_client.get('/produtos/ordem')
        corpo = r.get_data(as_text=True)
        assert r.status_code == 200
        assert 'tipo_ordem_teste' in corpo

        com_produto = {
            t for (t,) in db.session.query(Produto.component_type).distinct() if t
        }
        for k in COMPONENT_ORDER:
            if k not in com_produto:
                assert f'({k})' not in corpo, f'{k} sem produto nao pode listar'

        Produto.query.filter_by(component_type='tipo_ordem_teste').delete()
        db.session.commit()


def test_ordem_vazia_nao_quebra(logged_client, app):
    original = restaura_ordem()
    try:
        r = logged_client.post('/produtos/ordem', data={})
        assert r.status_code == 302
        assert list(COMPONENT_ORDER) == original
    finally:
        COMPONENT_ORDER[:] = original
        with app.app_context():
            TipoOrdem.query.delete()
            db.session.commit()
