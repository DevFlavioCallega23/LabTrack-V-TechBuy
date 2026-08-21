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