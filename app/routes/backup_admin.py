import os
import zipfile
import tempfile
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user
from app import db

backup_bp = Blueprint('backup_admin', __name__)


def _listar():
    import backup
    itens = []
    if os.path.isdir(backup.ONE_DRIVE_DIR):
        for f in os.listdir(backup.ONE_DRIVE_DIR):
            low = f.lower()
            if low.startswith('labtrack_backup') and low.endswith('.zip'):
                p = os.path.join(backup.ONE_DRIVE_DIR, f)
                itens.append({
                    'nome': f,
                    'tamanho': os.path.getsize(p),
                    'quando': datetime.fromtimestamp(os.path.getmtime(p))
                })
    itens.sort(key=lambda i: i['quando'], reverse=True)
    return itens


@backup_bp.route('/admin/backup', methods=['GET'])
@login_required
def index():
    if not current_user.is_master():
        flash('Apenas o Master acessa backups.', 'danger')
        return redirect(url_for('main.dashboard'))
    return render_template('admin/backup.html', backups=_listar())


@backup_bp.route('/admin/backup/criar', methods=['POST'])
@login_required
def criar():
    if not current_user.is_master():
        flash('Apenas o Master acessa backups.', 'danger')
        return redirect(url_for('main.dashboard'))
    import backup
    ok = backup.fazer_backup_one_drive()
    if ok:
        flash('Backup criado com sucesso no OneDrive.', 'success')
    else:
        flash('Falha ao criar backup: banco não encontrado.', 'danger')
    return redirect(url_for('backup_admin.index'))


@backup_bp.route('/admin/backup/baixar/<nome>')
@login_required
def baixar(nome):
    if not current_user.is_master():
        flash('Apenas o Master acessa backups.', 'danger')
        return redirect(url_for('main.dashboard'))
    import backup
    if nome not in {i['nome'] for i in _listar()}:
        abort(404)
    return send_file(os.path.join(backup.ONE_DRIVE_DIR, nome), as_attachment=True)


@backup_bp.route('/admin/backup/restaurar', methods=['POST'])
@login_required
def restaurar():
    if not current_user.is_master():
        flash('Apenas o Master acessa backups.', 'danger')
        return redirect(url_for('main.dashboard'))
    import backup
    if request.form.get('confirmacao', '').strip() != 'RESTAURAR':
        flash('Confirmação inválida: digite RESTAURAR para confirmar.', 'warning')
        return redirect(url_for('backup_admin.index'))

    tmp_path = None
    origem = request.form.get('origem')
    try:
        if origem == 'upload':
            f = request.files.get('arquivo')
            if not f or not f.filename.lower().endswith('.zip'):
                flash('Envie um arquivo .zip válido.', 'warning')
                return redirect(url_for('backup_admin.index'))
            fd, tmp_path = tempfile.mkstemp(suffix='.zip')
            os.close(fd)
            f.save(tmp_path)
            zip_path = tmp_path
        else:
            nome = request.form.get('zip_nome', '')
            if nome not in {i['nome'] for i in _listar()}:
                flash('Backup selecionado não existe mais.', 'danger')
                return redirect(url_for('backup_admin.index'))
            zip_path = os.path.join(backup.ONE_DRIVE_DIR, nome)

        with zipfile.ZipFile(zip_path) as zf:
            alvo = None
            for n in zf.namelist():
                if os.path.basename(n) == 'labtrack.db':
                    alvo = n
                    break
            if not alvo:
                flash('Este zip não contém o labtrack.db.', 'danger')
                return redirect(url_for('backup_admin.index'))

            snap_nome = None
            if os.path.exists(backup.DB_PATH):
                ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
                snap_nome = f'labtrack_backup_pre-restore_{ts}.zip'
                snap_path = os.path.join(backup.ONE_DRIVE_DIR, snap_nome)
                with zipfile.ZipFile(snap_path, 'w', zipfile.ZIP_DEFLATED) as zs:
                    zs.write(backup.DB_PATH, arcname='labtrack.db')

            fd2, tmp_db = tempfile.mkstemp(suffix='.db')
            os.close(fd2)
            with open(tmp_db, 'wb') as out:
                out.write(zf.read(alvo))

        db.session.remove()
        db.engine.dispose()
        os.replace(tmp_db, backup.DB_PATH)
        for ext in ('-wal', '-shm'):
            p = backup.DB_PATH + ext
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass

        msg = 'Banco restaurado com sucesso.'
        if snap_nome:
            msg += f' O estado anterior foi salvo como {snap_nome}.'
        flash(msg, 'success')
    except zipfile.BadZipFile:
        flash('Arquivo zip inválido.', 'danger')
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return redirect(url_for('backup_admin.index'))