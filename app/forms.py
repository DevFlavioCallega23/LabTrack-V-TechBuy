from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TextAreaField, DateField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional

class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')

class UserForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired(), Length(max=80)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    role = SelectField('Nível de Acesso', choices=[
        ('viewer', 'Visualização'),
        ('admin', 'Administrador')
    ], default='viewer')
    submit = SubmitField('Salvar')

class CreateUserForm(UserForm):
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=4)])
    submit = SubmitField('Criar Usuário')

class MasterUserForm(UserForm):
    role = SelectField('Nível de Acesso', choices=[
        ('viewer', 'Visualização'),
        ('admin', 'Administrador'),
        ('master', 'Master')
    ], default='viewer')
    submit = SubmitField('Salvar')

class MasterCreateUserForm(CreateUserForm):
    role = SelectField('Nível de Acesso', choices=[
        ('viewer', 'Visualização'),
        ('admin', 'Administrador'),
        ('master', 'Master')
    ], default='viewer')
    submit = SubmitField('Criar Usuário')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Senha Atual', validators=[DataRequired()])
    new_password = PasswordField('Nova Senha', validators=[DataRequired(), Length(min=4)])
    confirm_password = PasswordField('Confirmar Nova Senha', validators=[DataRequired()])
    submit = SubmitField('Alterar Senha')

class ProtocolForm(FlaskForm):
    type = SelectField('Tipo de Protocolo', choices=[
        ('', 'Selecione...'),
        ('venda', 'Venda'),
        ('ponta_entrega', 'Pronta-Entrega'),
        ('rma', 'RMA (Garantia)'),
        ('servico', 'Serviço (Fora de Garantia)'),
        ('nao_comprado', 'Não comprado na TechBuy')
    ], default='')
    venda_pe = BooleanField('Venda Pronta-Entrega (PE)', default=False)
    client_name = StringField('Cliente / Nome', validators=[Optional(), Length(max=200)])
    lote = StringField('Quantidade', validators=[Optional(), Length(max=50)])
    order_number = StringField('Número do Pedido', validators=[Optional(), Length(max=100)])
    seller = SelectField('Vendedor', choices=[
        ('', 'Selecione...'),
        ('Myris', 'Myris'),
        ('Janay', 'Janay'),
        ('Herbert', 'Herbert'),
        ('Erica', 'Erica'),
        ('Roberto', 'Roberto'),
        ('TechBuy', 'TechBuy'),
        ('NIL', 'NIL (Não informado ao Laboratório)')
    ], default='')
    status = SelectField('Status', choices=[
        ('pendente', 'Pendente'),
        ('andamento', 'Em Andamento'),
        ('concluido', 'Concluído')
    ], default='pendente')
    entry_date = StringField('Data da Compra', validators=[Optional()])
    exit_date = StringField('Data de Saída', validators=[Optional()])
    ref_ns = StringField('Referência NS', validators=[Optional(), Length(max=100)])
    base_defect = TextAreaField('Defeito de Base', validators=[Optional()])
    original_order = StringField('Pedido Original', validators=[Optional(), Length(max=100)])
    rma_extra_equip = StringField('Equipamento que chegou', validators=[Optional(), Length(max=200)])
    rma_test_result = TextAreaField('Resultado do Teste de Mesa', validators=[Optional()])
    rma_entry_date = StringField('Data de Entrada (RMA)', validators=[Optional()])
    observations = TextAreaField('Observações', validators=[Optional()])
    submit = SubmitField('Salvar')


