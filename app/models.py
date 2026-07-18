from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='viewer')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    protocols = db.relationship('Protocol', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_master(self):
        return self.role == 'master'

    def is_admin(self):
        return self.role in ('master', 'admin')

    def is_manager(self):
        return self.role in ('master', 'admin')

    def __repr__(self):
        return f'<User {self.username}>'

    @classmethod
    def create_admin(cls):
        admin = cls.query.filter_by(username='admin').first()
        if not admin:
            admin = cls.query.filter_by(email='admin@labtrack.local').first()
        if not admin:
            admin = cls(
                username='admin',
                email='admin@labtrack.local',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

class Protocol(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    protocol_number = db.Column(db.String(20), unique=True, nullable=False)
    type = db.Column(db.String(30), nullable=False)
    client_name = db.Column(db.String(200))
    contact = db.Column(db.String(100))
    lote = db.Column(db.String(50))
    order_number = db.Column(db.String(100))
    seller = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pendente')
    entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    exit_date = db.Column(db.DateTime, nullable=True)
    observations = db.Column(db.Text)
    power_cable = db.Column(db.String(10))
    power_cable_fonte_serial = db.Column(db.String(100))
    power_cables = db.Column(db.Text)
    ref_ns = db.Column(db.String(100))
    base_defect = db.Column(db.Text)
    original_order = db.Column(db.String(100))
    rma_extra_equip = db.Column(db.String(200))
    rma_equip_itens = db.Column(db.Text)
    rma_test_result = db.Column(db.Text)
    rma_test_component = db.Column(db.String(50))
    rma_test_serial = db.Column(db.String(100))
    rma_in_warranty = db.Column(db.Boolean, default=True)
    rma_passagens = db.Column(db.Text)
    rma_trocados = db.Column(db.Text)
    rma_entry_date = db.Column(db.String(10))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    components = db.relationship('Component', backref='protocol', lazy=True,
                                order_by='Component.sort_order',
                                cascade='all, delete-orphan')
    defects = db.relationship('Defect', backref='protocol', lazy=True,
                             order_by='Defect.sort_order',
                             cascade='all, delete-orphan')
    windows_keys = db.relationship('WindowsKey', backref='protocol', lazy=True,
                                   order_by='WindowsKey.sort_order',
                                   cascade='all, delete-orphan')

    TYPE_LABELS = {
        'venda': 'Venda',
        'ponta_entrega': 'Pronta-Entrega',
        'venda_ponta_entrega': 'Venda Pronta-Entrega',
        'rma': 'RMA',
        'nao_comprado': 'Não comprado na TechBuy'
    }

    TYPE_BADGES = {
        'venda': 'bg-success',
        'ponta_entrega': 'bg-warning text-dark',
        'venda_ponta_entrega': 'bg-info',
        'rma': 'bg-primary',
        'nao_comprado': 'bg-secondary'
    }

    STATUS_LABELS = {
        'pendente': 'Pendente',
        'andamento': 'Em Andamento',
        'concluido': 'Concluído',
        'cancelado': 'Cancelado'
    }

    def type_label(self):
        return self.TYPE_LABELS.get(self.type, self.type)

    def type_badge(self):
        return self.TYPE_BADGES.get(self.type, 'bg-secondary')

    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    def __repr__(self):
        return f'<Protocol {self.protocol_number}>'

class Component(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    protocol_id = db.Column(db.Integer, db.ForeignKey('protocol.id'), nullable=False)
    component_type = db.Column(db.String(50), nullable=False)
    specification = db.Column(db.String(200))
    serial_number = db.Column(db.String(100))
    unit = db.Column(db.String(10))
    machine_name = db.Column(db.String(100))
    sort_order = db.Column(db.Integer, default=0)

    FIXED_TYPES = ['processador', 'placa_mae', 'ram', 'ssd', 'fonte', 'monitor']

    TYPE_LABELS = {
        'processador': 'Processador',
        'placa_mae': 'Placa-Mãe (Soquete)',
        'ram': 'RAM',
        'ssd': 'SSD',
        'fonte': 'Fonte',
        'monitor': 'Monitor'
    }

    def type_label(self):
        return self.TYPE_LABELS.get(self.component_type, self.component_type)

    def __repr__(self):
        return f'<Component {self.component_type}: {self.serial_number}>'

class Defect(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    protocol_id = db.Column(db.Integer, db.ForeignKey('protocol.id'), nullable=False)
    component_type = db.Column(db.String(50), nullable=False)
    specification = db.Column(db.String(200))
    serial_number = db.Column(db.String(100))
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)

    TYPE_LABELS = {
        'processador': 'Processador',
        'placa_mae': 'Placa-Mãe (Soquete)',
        'ram': 'RAM',
        'ssd': 'SSD',
        'fonte': 'Fonte',
        'monitor': 'Monitor',
        'outro': 'Outro'
    }

    def type_label(self):
        return self.TYPE_LABELS.get(self.component_type, self.component_type)

    def __repr__(self):
        return f'<Defect {self.component_type}>'

class WindowsKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    protocol_id = db.Column(db.Integer, db.ForeignKey('protocol.id'), nullable=False)
    chave = db.Column(db.String(50))
    fonte = db.Column(db.String(100))
    ativo = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
