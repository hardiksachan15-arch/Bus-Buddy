from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import io
import csv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///busbuddy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20))
    approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bus_number = db.Column(db.String(20), unique=True, nullable=False)
    route_name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer)
    status = db.Column(db.String(20), default='inactive')
    current_lat = db.Column(db.Float)
    current_lon = db.Column(db.Float)
    last_update = db.Column(db.DateTime)
    driver_name = db.Column(db.String(100))

# --- ROUTES ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            if not user.approved:
                flash('Account pending approval.', 'warning')
                return redirect(url_for('login'))
                
            session['user_id'] = user.id
            session['role'] = user.role
            session['name'] = user.name
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        phone = request.form.get('phone')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password)
        
        is_approved = False
        if role == 'student': is_approved = True
        if email == 'work.694206969@gmail.com': 
            role = 'admin'
            is_approved = True
            
        new_user = User(name=name, email=email, password=hashed_pw, role=role, phone=phone, approved=is_approved)
        db.session.add(new_user)
        db.session.commit()
        
        if is_approved:
            flash('Registration successful! Please login.', 'success')
        else:
            flash('Registration successful! Please wait for admin approval.', 'info')
            
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')
        new_pass = request.form.get('new_password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.phone == phone:
            # Identity Verified -> Reset Password
            user.password = generate_password_hash(new_pass)
            db.session.commit()
            flash('Password reset successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Verification failed. Email or Phone incorrect.', 'danger')
            
    return render_template('forgot_password.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    role = session['role']
    if role == 'student': return render_template('dashboard_student.html')
    if role == 'driver': return render_template('dashboard_driver.html')
    if role in ['admin', 'transport_dept']: return render_template('dashboard_admin.html')
    
    return "Unknown Role"

# --- API ROUTES ---

@app.route('/api/buses', methods=['GET'])
def get_buses():
    buses = Bus.query.all()
    return jsonify([{
        'id': b.id, 'number': b.bus_number, 'route': b.route_name, 
        'status': b.status, 'lat': b.current_lat, 'lon': b.current_lon,
        'driver': b.driver_name
    } for b in buses])

@app.route('/api/buses', methods=['POST'])
def add_bus():
    if session.get('role') not in ['admin', 'transport_dept']: return "Unauthorized", 403
    try:
        data = request.json
        new_bus = Bus(bus_number=data['number'], route_name=data['route'], capacity=data['capacity'])
        db.session.add(new_bus)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/users/all', methods=['GET'])
def get_all_users():
    if session.get('role') not in ['admin', 'transport_dept']: return "Unauthorized", 403
    users = User.query.all()
    return jsonify([{
        'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role, 'approved': u.approved, 'phone': u.phone
    } for u in users])

@app.route('/api/users/pending', methods=['GET'])
def get_pending_users():
    if session.get('role') not in ['admin', 'transport_dept']: return "Unauthorized", 403
    users = User.query.filter_by(approved=False).all()
    return jsonify([{
        'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role
    } for u in users])

@app.route('/api/users/approve', methods=['POST'])
def approve_user():
    if session.get('role') not in ['admin', 'transport_dept']: return "Unauthorized", 403
    data = request.json
    user = User.query.get(data['user_id'])
    if user:
        if data['approved']:
            user.approved = True
        else:
            db.session.delete(user)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/driver/update', methods=['POST'])
def driver_update():
    if session.get('role') != 'driver': return "Unauthorized", 403
    data = request.json
    bus = Bus.query.get(data['bus_id'])
    if bus:
        bus.status = data['status']
        if 'lat' in data: bus.current_lat = data['lat']
        if 'lon' in data: bus.current_lon = data['lon']
        
        if data['status'] == 'active':
            bus.driver_name = session.get('name')
        elif data['status'] == 'inactive':
            bus.driver_name = None
            
        bus.last_update = datetime.utcnow()
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/export/csv')
def export_csv():
    if session.get('role') not in ['admin', 'transport_dept']: return "Unauthorized", 403
    
    users = User.query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['ID', 'Name', 'Email', 'Role', 'Phone', 'Approved'])
    for u in users:
        writer.writerow([u.id, u.name, u.email, u.role, u.phone, u.approved])
        
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=users_export.csv"}
    )

# --- INIT DB ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='work.694206969@gmail.com').first():
        admin_pw = generate_password_hash('admin')
        admin = User(name='Admin69', email='work.694206969@gmail.com', password=admin_pw, role='admin', phone='6969696969', approved=True)
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=3000)
