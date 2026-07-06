from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TextAreaField, DateField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional

class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')

class ProtocolForm(FlaskForm):
    type = SelectField('Tipo', choices=[
        ('venda', 'Venda'),
        ('ponta_entrega', 'Ponta Entrega'),
        ('venda_ponta_entrega', 'Venda Ponta Entrega'),
        ('rma', 'RMA (Garantia)'),
        ('servico', 'Serviço Fora de Garantia')
    ], validators=[DataRequired()])
    client_name = StringField('Cliente / Nome', validators=[DataRequired(), Length(max=200)])
    contact = StringField('Contato', validators=[Optional(), Length(max=100)])
    serial_number = StringField('Número de Série', validators=[Optional(), Length(max=100)])
    order_number = StringField('Número do Pedido', validators=[Optional(), Length(max=100)])
    brand = StringField('Marca', validators=[Optional(), Length(max=100)])
    model = StringField('Modelo', validators=[Optional(), Length(max=100)])
    status = SelectField('Status', choices=[
        ('pendente', 'Pendente'),
        ('andamento', 'Em Andamento'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado')
    ], default='pendente')
    entry_date = DateField('Data de Entrada', format='%Y-%m-%d', validators=[Optional()])
    exit_date = DateField('Data de Saída', format='%Y-%m-%d', validators=[Optional()])
    observations = TextAreaField('Observações', validators=[Optional()])
    submit = SubmitField('Salvar')

class UserForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired(), Length(max=80)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=4)])
    role = SelectField('Nível de Acesso', choices=[
        ('viewer', 'Visualização'),
        ('manager', 'Gerente'),
        ('admin', 'Administrador')
    ], default='viewer')
    submit = SubmitField('Criar Usuário')
