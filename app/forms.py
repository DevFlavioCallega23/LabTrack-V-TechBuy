from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError

from app.datas import parse_date_br
from app.labels import PROTO_FIELD_LABELS as PL

def valida_data_br(form, field):
    """Aceita DD/MM/AAAA, DD/MM/AA ou AAAA-MM-DD; vazio passa pelo Optional()."""
    if field.data and not parse_date_br(field.data):
        raise ValidationError('Data inválida (use DD/MM/AAAA).')

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

PROTO_TYPE_CHOICES = [
    ('', 'Selecione...'),
    ('venda', 'Venda'),
    ('ponta_entrega', 'Pronta-Entrega'),
    ('rma', 'RMA (Garantia)'),
    ('servico', 'Serviço (Fora de Garantia)'),
    ('nao_comprado', 'Não comprado na TechBuy')
]

SELLER_CHOICES = [
    ('', 'Selecione...'),
    ('Myris', 'Myris'),
    ('Janay', 'Janay'),
    ('Herbert', 'Herbert'),
    ('Erica', 'Erica'),
    ('Roberto', 'Roberto'),
    ('TechBuy', 'TechBuy'),
    ('NIL', 'NIL (Não informado ao Laboratório)')
]

class ProtocolForm(FlaskForm):
    type = SelectField(PL['type'], choices=PROTO_TYPE_CHOICES, default='')
    venda_pe = BooleanField(PL['venda_pe'], default=False)
    client_name = StringField(PL['client_name'], validators=[Optional(), Length(max=200)])
    lote = StringField(PL['lote'], validators=[Optional(), Length(max=50)])
    order_number = StringField(PL['order_number'], validators=[Optional(), Length(max=100)])
    seller = SelectField(PL['seller'], choices=SELLER_CHOICES, default='')
    status = SelectField(PL['status'], choices=[
        ('pendente', 'Pendente'),
        ('andamento', 'Em Andamento'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado')
    ], default='pendente')
    entry_date = StringField(PL['entry_date'], validators=[Optional(), valida_data_br])
    exit_date = StringField(PL['exit_date'], validators=[Optional(), valida_data_br])
    ref_ns = StringField(PL['ref_ns'], validators=[Optional(), Length(max=100)])
    base_defect = TextAreaField(PL['base_defect'], validators=[Optional()])
    original_order = StringField(PL['original_order'], validators=[Optional(), Length(max=100)])
    rma_extra_equip = StringField(PL['rma_extra_equip'], validators=[Optional(), Length(max=200)])
    rma_test_result = TextAreaField(PL['rma_test_result'], validators=[Optional()])
    rma_entry_date = StringField(PL['rma_entry_date'], validators=[Optional(), valida_data_br])
    observations = TextAreaField(PL['observations'], validators=[Optional()])
    submit = SubmitField(PL['submit'])


class QuickProtocolForm(FlaskForm):
    """Registro rápido da Home: cria o protocolo e abre a edição para completar.

    Os campos aparecem conforme o tipo escolhido (ver dashboard.html); o
    servidor só aproveita o que faz sentido para cada tipo.
    """
    type = SelectField('Tipo de Protocolo', choices=[('', 'Selecione...')] + PROTO_TYPE_CHOICES[1:], default='')
    client_name = StringField('Cliente', validators=[Optional(), Length(max=200)])
    seller = SelectField('Vendedor', choices=SELLER_CHOICES, default='')
    pedido = StringField('Pedido', validators=[Optional(), Length(max=100)])
    lote = StringField('Quantidade', validators=[Optional(), Length(max=50)])
    entry_date = StringField('Data', validators=[Optional(), valida_data_br])
    base_defect = TextAreaField('Defeito relatado', validators=[Optional()])
    submit = SubmitField('Criar protocolo')
