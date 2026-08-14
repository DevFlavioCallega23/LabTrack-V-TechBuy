import os
import shutil
import zipfile
import sys
from datetime import datetime

BASEDIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASEDIR, 'labtrack.db')
ONE_DRIVE_DIR = r'C:\Users\BigBossTechBuy\OneDrive'
ZIP_NAME = 'labtrack_backup.zip'

def fazer_backup_one_drive(destino=None):
    if not os.path.exists(DB_PATH):
        print(f'ERRO: banco não encontrado em {DB_PATH}')
        return False

    destino = destino or ONE_DRIVE_DIR
    os.makedirs(destino, exist_ok=True)
    zip_path = os.path.join(destino, ZIP_NAME)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(DB_PATH, arcname=os.path.basename(DB_PATH))

    print(f'Backup enviado: {zip_path} ({os.path.getsize(zip_path)} bytes, {datetime.now().strftime("%d/%m/%Y %H:%M")})')
    return True

if __name__ == '__main__':
    ok = fazer_backup_one_drive()
    sys.exit(0 if ok else 1)