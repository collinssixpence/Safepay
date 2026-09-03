import os
import uuid
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Order, OrderStatus

app = Flask(__name__)

# Security Key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'safepay-dev-secret-key-change-in-production')

# Database Configuration (Reads from Render/Supabase environment variable, defaults to SQLite locally)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///safepay.db')

# Fix for SQLAlchemy requiring 'postgresql://' instead of older 'postgres://' schema
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Login Manager Initialization
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Auto-create database tables on startup
with app.app_context():
    db.create_all()

# WEB ROUTES
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')

        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))

        user = User(email=email, merchant_phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))

        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    merchant_orders = Order.query.filter_by(merchant_phone=current_user.merchant_phone).all()
    return render_template('index.html', user=current_user, orders=merchant_orders)

@app.route('/checkout/<order_ref>')
def checkout(order_ref):
    order = Order.query.filter_by(order_ref=order_ref).first_or_404()
    return render_template('checkout.html', order=order)

# API ENDPOINTS
@app.route('/api/orders/create', methods=['POST'])
def create_order():
    data = request.get_json()
    if not data or not all(k in data for k in ('merchant_phone', 'buyer_phone', 'amount')):
        return jsonify({"error": "Missing required fields"}), 400

    order_ref = f"SP-{uuid.uuid4().hex[:6].upper()}"
    new_order = Order(
        order_ref=order_ref,
        merchant_phone=data['merchant_phone'],
        buyer_phone=data['buyer_phone'],
        amount=float(data['amount']),
        status=OrderStatus.CREATED,
        verification_pin=Order.generate_pin()
    )
    db.session.add(new_order)
    db.session.commit()
    return jsonify({"order_ref": order_ref}), 201

@app.route('/api/payments/webhook', methods=['POST'])
def payment_webhook():
    data = request.get_json()
    order = Order.query.filter_by(order_ref=data.get('order_ref')).first_or_404()
    
    if data.get('status') == 'SUCCESS':
        order.status = OrderStatus.HELD
        db.session.commit()
        return jsonify({"message": "Funds locked in vault", "status": order.status.value}), 200
        
    return jsonify({"error": "Payment failed"}), 400

@app.route('/api/orders/verify-pin', methods=['POST'])
def verify_pin():
    data = request.get_json()
    order = Order.query.filter_by(order_ref=data.get('order_ref')).first_or_404()
    
    if order.status != OrderStatus.HELD:
        return jsonify({"error": "Order is not in HELD state"}), 400
        
    if order.verification_pin != str(data.get('pin')):
        return jsonify({"error": "Invalid verification PIN"}), 401
    
    order.status = OrderStatus.RELEASED
    db.session.commit()
    return jsonify({"message": "PIN verified, funds released", "status": order.status.value}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)