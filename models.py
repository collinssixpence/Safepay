import enum
import random
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class OrderStatus(enum.Enum):
    CREATED = "CREATED"
    HELD = "HELD"           # Funds locked in escrow vault
    RELEASED = "RELEASED"   # PIN verified; Payout sent to merchant
    DISPUTED = "DISPUTED"

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    merchant_phone = db.Column(db.String(15), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='merchant', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_ref = db.Column(db.String(12), unique=True, nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    merchant_phone = db.Column(db.String(15), nullable=False)
    buyer_phone = db.Column(db.String(15), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.CREATED)
    verification_pin = db.Column(db.String(4), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_pin():
        return f"{random.randint(1000, 9999)}"