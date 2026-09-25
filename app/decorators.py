from flask import flash, redirect, url_for
from flask_login import current_user


def master_required():
    """Retorna redirect se o usuário não for master, senão None.

    Uso:  bloqueio = master_required()
          if bloqueio: return bloqueio
    """
    if not current_user.is_master():
        flash('Acesso restrito ao Master.', 'danger')
        return redirect(url_for('main.dashboard'))
    return None
