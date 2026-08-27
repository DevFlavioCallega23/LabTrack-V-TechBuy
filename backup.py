import os
import json
import shutil
import zipfile
import sys
from datetime import datetime

BASEDIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASEDIR, 'labtrack.db')
CONFIG_PATH = os.path.join(BASEDIR, 'backup_config.json')
ZIP_PREFIX = 'labtrack_backup_'
RETENCAO = 7


def _detect_one_drive():
    home = os.path.expanduser('~')
    for candidate in [
        os.path.join(home, 'OneDrive'),
        os.path.join(home, 'OneDrive - BigBossTechBuy'),
    ]:
        if os.path.isdir(candidate):
            return candidate
    fallback = os.path.join(BASEDIR, 'backups')
    os.makedirs(fallback, exist_ok=True)
    return fallback


def get_backup_dir():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            path = cfg.get('backup_dir', '')
            if path and os.path.isabs(path):
                return path
        except (json.JSONDecodeError, OSError):
            pass
    return _detect_one_drive()


def set_backup_dir(path):
    path = os.path.abspath(path)
    os.makedirs(path, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump({'backup_dir': path}, f, indent=2)
    return path


ONE_DRIVE_DIR = get_backup_dir()


def fazer_backup_one_drive(destino=None):
    if not os.path.exists(DB_PATH):
        print(f'ERRO: banco não encontrado em {DB_PATH}')
        return False

    destino = destino or ONE_DRIVE_DIR
    os.makedirs(destino, exist_ok=True)
    zip_path = os.path.join(destino, f'{ZIP_PREFIX}{datetime.now().strftime("%Y-%m-%d")}.zip')

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(DB_PATH, arcname=os.path.basename(DB_PATH))

    antigos = sorted(
        (f for f in os.listdir(destino) if f.startswith(ZIP_PREFIX) and f.endswith('.zip')),
        reverse=True
    )
    for nome in antigos[RETENCAO:]:
        try:
            os.remove(os.path.join(destino, nome))
            print(f'Antigo removido: {nome}')
        except OSError:
            pass

    print(f'Backup enviado: {zip_path} ({os.path.getsize(zip_path)} bytes, {datetime.now().strftime("%d/%m/%Y %H:%M")})')
    return True

if __name__ == '__main__':
    ok = fazer_backup_one_drive()
    sys.exit(0 if ok else 1)
