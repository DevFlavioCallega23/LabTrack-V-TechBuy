def test_anonimo_redireciona_para_login(client):
    r = client.get('/')
    assert r.status_code == 302
    assert r.headers['Location'].startswith('/login')


def test_logado_ve_dashboard(logged_client):
    r = logged_client.get('/')
    assert r.status_code == 200


def test_admin_backup_exige_master(client):
    r = client.get('/admin/backup', follow_redirects=False)
    assert r.status_code == 302


def test_login_volta_para_next(client):
    r = client.post('/login?next=/ns?busca=ABC',
                    data={'username': 'admin', 'password': 'admin123'})
    assert r.status_code == 302
    assert r.headers['Location'] == '/ns?busca=ABC'


def test_login_sem_next_vai_para_home(client):
    r = client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    assert r.status_code == 302
    assert r.headers['Location'] == '/'


def test_login_next_externo_cai_na_home(client):
    r = client.post('/login?next=https://evil.com',
                    data={'username': 'admin', 'password': 'admin123'})
    assert r.status_code == 302
    assert r.headers['Location'] == '/'