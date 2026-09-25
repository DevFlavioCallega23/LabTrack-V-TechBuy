from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.decorators import master_required
from app.models import User
from app.forms import UserForm, CreateUserForm, MasterUserForm, MasterCreateUserForm, ChangePasswordForm

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/usuarios')
@login_required
def list_users():
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    users = User.query.all()
    return render_template('users.html', users=users)

@usuarios_bp.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
def create_user():
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    form = MasterCreateUserForm() if current_user.is_master() else CreateUserForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data or f'{form.username.data}@labtrack.local',
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'Usuário {user.username} criado com sucesso!', 'success')
        return redirect(url_for('usuarios.list_users'))
    return render_template('user_form.html', form=form, creating=True)

@usuarios_bp.route('/minha-conta', methods=['GET', 'POST'])
@login_required
def minha_conta():
    form = UserForm(obj=current_user)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data or f'{form.username.data}@labtrack.local'
        db.session.commit()
        flash('Dados atualizados com sucesso!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('user_form.html', form=form, editing=True, current_user_page=True)

@usuarios_bp.route('/minha-conta/alterar-senha', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Senha atual incorreta.', 'danger')
            return render_template('change_password.html', form=form)
        if form.new_password.data != form.confirm_password.data:
            flash('As novas senhas não conferem.', 'danger')
            return render_template('change_password.html', form=form)
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Senha alterada com sucesso!', 'success')
        return redirect(url_for('usuarios.minha_conta'))
    return render_template('change_password.html', form=form)


@usuarios_bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    bloqueio = master_required()
    if bloqueio:
        return bloqueio
    user = User.query.get_or_404(id)
    form = MasterUserForm(obj=user) if current_user.is_master() else UserForm(obj=user)
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data or f'{form.username.data}@labtrack.local'
        user.role = form.role.data
        db.session.commit()
        flash(f'Usuário {user.username} atualizado com sucesso!', 'success')
        return redirect(url_for('usuarios.list_users'))
    return render_template('user_form.html', form=form, editing=True, user=user)

