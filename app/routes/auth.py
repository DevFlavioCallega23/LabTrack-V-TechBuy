from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from app.models import User
from app.forms import LoginForm

auth_bp = Blueprint('auth', __name__)


def _destino_pos_login():
    """Honra o ?next= do Flask-Login (destino interno apenas)."""
    destino = request.args.get('next') or request.form.get('next') or ''
    if destino.startswith('/') and not destino.startswith('//') and '\\' not in destino:
        return destino
    return url_for('main.dashboard')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html', form=LoginForm())
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(_destino_pos_login())
        flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
