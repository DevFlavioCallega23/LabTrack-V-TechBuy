import re
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar o sistema.'

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.template_filter('nl2br')
    def nl2br_filter(text):
        if not text:
            return ''
        return re.sub(r'\n', '<br>', text)

    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.protocols import protocols_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(protocols_bp)

    with app.app_context():
        db.create_all()
        User.create_admin()

    return app
