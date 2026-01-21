from app import app, db, User, Bus
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()
    
    # 1. Restore Admin
    if not User.query.filter_by(email='work.694206969@gmail.com').first():
        print("Restoring Admin...")
        admin = User(
            name='Admin User', 
            email='work.694206969@gmail.com', 
            password=generate_password_hash('admin'), 
            role='admin', 
            approved=True
        )
        db.session.add(admin)

    # 2. Restore Sample Bus to avoid empty screen
    if not Bus.query.first():
        print("Restoring Sample Bus...")
        bus = Bus(
            bus_number='DL-1S-0001',
            route_name='Route 1 (Main Campus)',
            capacity=40,
            status='inactive',
            route_coordinates='[[28.7041, 77.1025], [28.7045, 77.1030]]',
            stops='[{"name": "Main Gate", "lat": 28.7041, "lon": 77.1025}, {"name": "Hostel", "lat": 28.7045, "lon": 77.1030}]'
        )
        db.session.add(bus)

    db.session.commit()
    print("✅ Data Restored Successfully!")
