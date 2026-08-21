import os
import shutil
import tempfile
import zipfile

import backup as backup_mod


def test_backup_fluxo_completo(logged_client, app, monkeypatch):
    tmp = tempfile.mkdtemp(prefix='bktest_')
    fake_od = os.path.join(tmp, 'onedrive')
    os.makedirs(fake_od)
    tmp_db = os.path.join(tmp, 'labtrack.db')
    shutil.copy2(backup_mod.DB_PATH, tmp_db)
    monkeypatch.setattr(backup_mod, 'ONE_DRIVE_DIR', fake_od)
    monkeypatch.setattr(backup_mod, 'DB_PATH', tmp_db)

    r = logged_client.get('/admin/backup')
    assert r.status_code == 200

    r = logged_client.post('/admin/backup/criar', follow_redirects=False)
    assert r.status_code == 302
    zips = [f for f in os.listdir(fake_od) if f.startswith('labtrack_backup_')]
    assert len(zips) == 1

    r = logged_client.get('/admin/backup/baixar/' + zips[0])
    assert r.status_code == 200
    assert 'attachment' in r.headers.get('Content-Disposition', '')

    r = logged_client.get('/admin/backup/baixar/..%5Cevil.zip')
    assert r.status_code == 404

    original = open(tmp_db, 'rb').read()
    open(tmp_db, 'wb').write(b'CORROMPIDO')

    r = logged_client.post('/admin/backup/restaurar',
                           data={'origem': 'lista', 'zip_nome': zips[0], 'confirmacao': 'errado'},
                           follow_redirects=True)
    assert open(tmp_db, 'rb').read() == b'CORROMPIDO'

    r = logged_client.post('/admin/backup/restaurar',
                           data={'origem': 'lista', 'zip_nome': zips[0], 'confirmacao': 'RESTAURAR'},
                           follow_redirects=True)
    assert open(tmp_db, 'rb').read() == original
    snaps = [f for f in os.listdir(fake_od) if f.startswith('labtrack_backup_pre-restore_')]
    assert len(snaps) == 1

    fd, upzip = tempfile.mkstemp(suffix='.zip')
    os.close(fd)
    with zipfile.ZipFile(upzip, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('sub/labtrack.db', b'BANCO-DO-UPLOAD')
    with open(upzip, 'rb') as fh:
        r = logged_client.post('/admin/backup/restaurar',
                               data={'origem': 'upload', 'arquivo': fh, 'confirmacao': 'RESTAURAR'},
                               content_type='multipart/form-data', follow_redirects=True)
    assert open(tmp_db, 'rb').read() == b'BANCO-DO-UPLOAD'
    os.remove(upzip)
    shutil.rmtree(tmp, ignore_errors=True)


def test_retencao_apaga_os_mais_antigos(monkeypatch):
    tmp = tempfile.mkdtemp(prefix='bkret_')
    fake_db = os.path.join(tmp, 'labtrack.db')
    open(fake_db, 'wb').write(b'dummy')
    monkeypatch.setattr(backup_mod, 'ONE_DRIVE_DIR', tmp)
    monkeypatch.setattr(backup_mod, 'DB_PATH', fake_db)
    for dia in range(1, 11):
        open(os.path.join(tmp, f'labtrack_backup_2026-08-{dia:02d}.zip'), 'wb').write(b'x')
    backup_mod.fazer_backup_one_drive()
    restantes = sorted(f for f in os.listdir(tmp) if f.startswith('labtrack_backup_'))
    assert len(restantes) == backup_mod.RETENCAO
    shutil.rmtree(tmp, ignore_errors=True)