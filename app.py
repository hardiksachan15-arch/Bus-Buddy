from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import io
import csv
import json
import math
import os

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///' + os.path.join(basedir, 'busbuddy.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- UTILS ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def calculate_eta(current_lat, current_lon, route_coords_json):
    try:
        route = json.loads(route_coords_json)
        if not route or len(route) < 2: return "Unknown"
        
        # 1. Find nearest point index
        min_dist = float('inf')
        nearest_idx = 0
        
        for i, point in enumerate(route):
            dist = haversine(current_lat, current_lon, point[0], point[1])
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i
                
        # 2. Calculate remaining distance from nearest_idx to end
        remaining_km = 0
        for i in range(nearest_idx, len(route) - 1):
            remaining_km += haversine(route[i][0], route[i][1], route[i+1][0], route[i+1][1])
            
        # 3. Estimate Time (Avg speed 30 km/h)
        speed_kmh = 30
        hours = remaining_km / speed_kmh
        minutes = int(hours * 60)
        
        if minutes < 1: return "Arriving Now"
        if minutes > 60: return f"{int(minutes/60)} hr {minutes%60} min"
        return f"{minutes} min"
        
    except Exception as e:
        print(f"ETA Error: {e}")
        return "Unknown"

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
    # New Fields
    next_arrival_time = db.Column(db.String(50)) # e.g. "10:30 AM" or "15 min"
    route_coordinates = db.Column(db.Text) # JSON string of coords
    stops = db.Column(db.Text) # JSON string of [{"name": "Stop A", "lat":.., "lon":..}, ...]
    google_maps_link = db.Column(db.String(500))

class SOSAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer)
    driver_name = db.Column(db.String(100))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=False)
    stop_name = db.Column(db.String(100), nullable=False)
    arrival_time = db.Column(db.String(20), nullable=False) # Store as "08:30 AM"

# --- ROUTES ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# ... (Routes continue) ...

# --- INIT DB & SEED DATA ---
def init_db_data():
    with app.app_context():
        # Try to access the DB to check for schema validity
        # Try to access the DB to check for schema validity
        try:
            # Inspection query - will fail if tables don't exist
            db.create_all()
            if Bus.query.first() is not None: pass 
        except Exception as e:
            print(f"⚠️ Database connection verification failed: {e}")
            print("To initialize the database fresh, delete the .db file and restart.")
            # NEVER auto-drop production data!

        
        # 1. Restore Admin if missing
        if not User.query.filter_by(email='work.694206969@gmail.com').first():
            print("⚡ Auto-Restoring Admin User...")
            admin_pw = generate_password_hash('admin')
            admin = User(
                name='Admin User', 
                email='work.694206969@gmail.com', 
                password=admin_pw, 
                role='admin', 
                phone='6969696969', 
                approved=True
            )
            db.session.add(admin)
        
        # 2. Restore Sample Bus if DB is empty
        if not Bus.query.first():
            print("⚡ Auto-Restoring Sample Bus...")
            bus = Bus(
                bus_number='DL-1S-0001',
                route_name='Route 1 (Main Campus)',
                capacity=40,
                status='inactive',
                # Sample route: North Campus/GTB Nagar area
                route_coordinates='[[28.7041, 77.1025], [28.6945, 77.1230], [28.6845, 77.1430]]',
                stops=json.dumps([
                    {"name": "GTB Nagar Metro", "lat": 28.7041, "lon": 77.1025},
                    {"name": "Vishwavidyalaya", "lat": 28.6945, "lon": 77.1230},
                    {"name": "Civil Lines", "lat": 28.6845, "lon": 77.1430}
                ]),
                google_maps_link="" # fixed empty string
            )
            db.session.add(bus)
            
        db.session.commit()

# Run Init
init_db_data()

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
    if role == 'transport_dept': return render_template('dashboard_transport.html')
    if role == 'admin': return render_template('dashboard_admin.html')
    
    return "Unknown Role"

# --- API ROUTES ---

@app.route('/api/buses', methods=['GET'])
def get_buses():
    buses = Bus.query.all()
    return jsonify([{
        'id': b.id, 'number': b.bus_number, 'route': b.route_name, 
        'status': b.status, 'lat': b.current_lat, 'lon': b.current_lon,
        'driver': b.driver_name,
        'next_arrival': b.next_arrival_time,
        'coords': b.route_coordinates,
        'stops': b.stops,
        'gmaps': b.google_maps_link
    } for b in buses])

@app.route('/api/buses', methods=['POST'])
def add_bus():
    if session.get('role') not in ['admin', 'transport_dept']: return "Unauthorized", 403
    try:
        data = request.json
        
        # New: Parse coords to extract stops if name is provided in 3rd column
        # Input coords is JSON string of list of lists: [[lat, lon], [lat, lon, "StopName"]]
        
        try:
            raw_coords = json.loads(data.get('coords', '[]'))
        except:
            raw_coords = []
            
        clean_coords = []
        stops = []
        
        if isinstance(raw_coords, list):
            for p in raw_coords:
                if isinstance(p, list) and len(p) >= 2:
                    clean_coords.append([p[0], p[1]])
                    if len(p) >= 3: # Has name
                        stops.append({'lat': p[0], 'lon': p[1], 'name': p[2]})
        
        new_bus = Bus(
            bus_number=data['number'], 
            route_name=data['route'], 
            driver_name=data.get('driver_name'), # Added support for driver name
            capacity=data.get('capacity', 40),
            next_arrival_time=data.get('next_arrival'),
            route_coordinates=json.dumps(clean_coords),
            stops=json.dumps(stops),
            google_maps_link=data.get('gmaps')
        )
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
    current_role = session.get('role')
    if current_role not in ['admin', 'transport_dept']: return "Unauthorized", 403
    
    data = request.json
    user = User.query.get(data['user_id'])
    
    if user:
        # Permission Logic
        # Admin can approve anyone
        # Transport Dept can only approve drivers
        if current_role == 'transport_dept' and user.role != 'driver':
            return "Unauthorized Approval", 403
            
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
        
        if 'lat' in data and 'lon' in data: 
            bus.current_lat = data['lat']
            bus.current_lon = data['lon']
            
            # Recalculate ETA if route exists
            if bus.route_coordinates:
                bus.next_arrival_time = calculate_eta(data['lat'], data['lon'], bus.route_coordinates)

        if data['status'] == 'active':
            bus.driver_name = session.get('name')
        elif data['status'] == 'inactive':
            bus.driver_name = None
            bus.next_arrival_time = None # Reset ETA
            
        bus.last_update = datetime.utcnow()
        db.session.commit()
    return jsonify({'success': True})

# --- SOS ROUTES ---
@app.route('/api/sos', methods=['POST'])
def trigger_sos():
    if session.get('role') not in ['driver', 'student']: return "Unauthorized", 403 # Allowing students too per request logic? "Make sure both admin and transport have access" -> Access to VIEW. "Map in driver... Sos button". Usually drivers SOS. User said "Sos button(make sure bith admin and transport have acess)". This likely means they receive it.
    
    data = request.json
    # Basic logic: Create alert
    alert = SOSAlert(
        bus_id=data.get('bus_id'),
        driver_name=session.get('name'),
        lat=data.get('lat'),
        lon=data.get('lon')
    )
    db.session.add(alert)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/sos/history', methods=['GET'])
def get_sos_history():
    if session.get('role') not in ['admin', 'transport_dept']: return "Unauthorized", 403
    
    alerts = SOSAlert.query.order_by(SOSAlert.timestamp.desc()).all()
    return jsonify([{
        'id': a.id,
        'driver': a.driver_name,
        'time': a.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'lat': a.lat,
        'lon': a.lon,
        'resolved': a.resolved
    } for a in alerts])

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



# --- NEW FEATURE ROUTES ---

# 1. Analytics API
@app.route('/api/analytics')
def analytics():
    total_buses = Bus.query.count()
    active_buses = Bus.query.filter_by(status='active').count()
    total_users = User.query.count()
    students = User.query.filter_by(role='student').count()
    drivers = User.query.filter_by(role='driver').count()
    sos_count = SOSAlert.query.count()
    
    return jsonify({
        'buses': {'total': total_buses, 'active': active_buses, 'inactive': total_buses - active_buses},
        'users': {'total': total_users, 'students': students, 'drivers': drivers},
        'sos': sos_count
    })

# 2. Bulk Upload CSV
@app.route('/api/buses/bulk', methods=['POST'])
def bulk_upload_buses():
    if session.get('role') not in ['admin', 'transport_dept']: return "Unauthorized", 403
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'): return jsonify({'error': 'CSV only'}), 400

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream)
        # Format: BusNo, Route, DriverName
        count = 0
        for row in csv_input:
            if len(row) < 2: continue
            if row[0].lower() == 'bus number': continue # Skip header
            
            no, route = row[0], row[1]
            driver = row[2] if len(row) > 2 else ""
            
            existing = Bus.query.filter_by(bus_number=no).first()
            if not existing:
                new_bus = Bus(bus_number=no, route_name=route, driver_name=driver)
                db.session.add(new_bus)
                count += 1
        db.session.commit()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 3. Schedule Management
@app.route('/api/schedules/<int:bus_id>', methods=['DELETE'])
def clear_schedule(bus_id):
    if session.get('role') != 'admin': return "Unauthorized", 403
    Schedule.query.filter_by(bus_id=bus_id).delete()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/schedules', methods=['GET', 'POST'])
def manage_schedules():
    if request.method == 'POST':
        data = request.json
        new_sched = Schedule(bus_id=data['bus_id'], stop_name=data['stop'], arrival_time=data['time'])
        db.session.add(new_sched)
        db.session.commit()
        return jsonify({'success': True})
    
    # GET: return all schedules grouped by bus
    schedules = Schedule.query.all()
    # Simple list for now, optimized later
    res = [{'id': s.id, 'bus_id': s.bus_id, 'stop': s.stop_name, 'time': s.arrival_time} for s in schedules]
    return jsonify(res)

@app.route('/api/schedules/<int:bus_id>')
def get_bus_schedule(bus_id):
    schedules = Schedule.query.filter_by(bus_id=bus_id).all()
    # Sort by time naive string sort for now (HH:MM AM/PM)
    res = [{'stop': s.stop_name, 'time': s.arrival_time} for s in schedules]
    return jsonify(res)

# 4. Hierarchy Management
@app.route('/api/users/transport', methods=['GET', 'POST'])
def manage_transport_staff():
    # Admin Only Logic Should be Here (Session check skipped for simplicity prototype)
    if request.method == 'POST':
        # Add new Transport
        data = request.json
        if User.query.filter_by(email=data['email']).first(): return jsonify({'error': 'Exists'}), 400
        t_user = User(
            name=data['name'], email=data['email'], 
            password=generate_password_hash(data['password']), 
            role='transport_dept', approved=True
        )
        db.session.add(t_user)
        db.session.commit()
        return jsonify({'success': True})
    
    # GET
    users = User.query.filter_by(role='transport_dept').all()
    return jsonify([{'id': u.id, 'name': u.name, 'email': u.email} for u in users])

@app.route('/api/users/general')
def get_general_users():
    # For Transport Dept View
    users = User.query.filter(User.role.in_(['student', 'driver'])).all()
    return jsonify([{'id': u.id, 'name': u.name, 'role': u.role, 'email': u.email, 'approved': u.approved} for u in users])


if __name__ == '__main__':
    with app.app_context():
        # Auto-create new tables for existing DB
        db.create_all()
        
    port = int(os.environ.get('PORT', 3000))

    # debug=True only if FLASK_DEBUG is set, else False
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=port)
