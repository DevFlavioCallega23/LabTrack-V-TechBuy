import os
import sys
import shutil
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

_TMP = tempfile.mkdtemp(prefix='labtrack_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')

import pytest
from app import create_app, db as _db
from app.models import User


@pytest.fixture(scope='session')
def app():
    application = create_app()
    application.config.update(WTF_CSRF_ENABLED=False, TESTING=True)
    with application.app_context():
        admin = User.query.filter_by(username='admin').first()
        if admin.role != 'master':
            admin.role = 'master'
            _db.session.commit()
    yield application
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, user_id):
    with client.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True


@pytest.fixture
def logged_client(client, app):
    with app.app_context():
        uid = User.query.filter_by(role='master').first().id
    login(client, uid)
    return client