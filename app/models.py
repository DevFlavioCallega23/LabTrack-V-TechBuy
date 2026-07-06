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

    def is_admin(self):
        return self.role == 'admin'

    def is_manager(self):
        return self.role in ('admin', 'manager')

    def __repr__(self):
        return f'<User {self.username}>'

    @classmethod
    def create_admin(cls):
        admin = cls.query.filter_by(username='admin').first()
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
    status = db.Column(db.String(20), default='pendente')
    entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    exit_date = db.Column(db.DateTime, nullable=True)
    observations = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    components = db.relationship('Component', backref='protocol', lazy=True,
                                order_by='Component.sort_order',
                                cascade='all, delete-orphan')

    TYPE_LABELS = {
        'venda': 'Venda',
        'ponta_entrega': 'Ponta Entrega',
        'venda_ponta_entrega': 'Venda Ponta Entrega',
        'rma': 'RMA (Garantia)',
        'servico': 'Serviço Fora de Garantia'
    }

    STATUS_LABELS = {
        'pendente': 'Pendente',
        'andamento': 'Em Andamento',
        'concluido': 'Concluído',
        'cancelado': 'Cancelado'
    }

    def type_label(self):
        return self.TYPE_LABELS.get(self.type, self.type)

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
    sort_order = db.Column(db.Integer, default=0)

    FIXED_TYPES = ['processador', 'placa_mae', 'ram', 'ssd', 'fonte']

    TYPE_LABELS = {
        'processador': 'Processador',
        'placa_mae': 'Placa-Mãe (Soquete)',
        'ram': 'RAM',
        'ssd': 'SSD',
        'fonte': 'Fonte'
    }

    def type_label(self):
        return self.TYPE_LABELS.get(self.component_type, self.component_type)

    def __repr__(self):
        return f'<Component {self.component_type}: {self.serial_number}>'
