import json
import re
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
from sqlalchemy import inspect

db = SQLAlchemy()
login_manager = LoginManager()

def get_version():
    version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'VERSION')
    try:
        with open(version_file) as f:
            return f.read().strip()
    except:
        return '1.0.0-RMA'
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar o sistema.'

def add_missing_columns():
    """Add columns that may not exist in older databases."""
    engine = db.engine
    inspector = inspect(engine)
    protocol_cols = [c['name'] for c in inspector.get_columns('protocol')]
    defect_cols = [c['name'] for c in inspector.get_columns('defect')]
    with engine.connect() as conn:
        if 'specification' not in defect_cols:
            conn.execute(db.text('ALTER TABLE defect ADD COLUMN specification VARCHAR(200)'))
        if 'original_order' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN original_order VARCHAR(100)'))
        if 'rma_extra_equip' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_extra_equip VARCHAR(200)'))
        if 'rma_test_result' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_test_result TEXT'))
        if 'rma_test_component' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_test_component VARCHAR(50)'))
        if 'rma_test_serial' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_test_serial VARCHAR(100)'))
        if 'rma_in_warranty' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_in_warranty BOOLEAN DEFAULT 1'))
        if 'rma_passagens' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_passagens TEXT'))
        if 'rma_equip_itens' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_equip_itens TEXT'))
        if 'rma_trocados' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_trocados TEXT'))
        if 'rma_entry_date' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_entry_date VARCHAR(10)'))
        if 'rma_extra_qtd' not in protocol_cols:
            conn.execute(db.text('ALTER TABLE protocol ADD COLUMN rma_extra_qtd INTEGER DEFAULT 0'))
        conn.commit()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.context_processor
    def inject_version():
        return dict(app_version=get_version())

    db.init_app(app)
    login_manager.init_app(app)
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.template_filter('nl2br')
    def nl2br_filter(text):
        if not text:
            return ''
        return re.sub(r'\n', '<br>', text)

    @app.template_filter('from_json')
    def from_json_filter(text):
        if not text:
            return []
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return []

    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.protocols import protocols_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(protocols_bp)

    with app.app_context():
        db.create_all()
        add_missing_columns()
        User.create_admin()

    return app
