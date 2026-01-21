import os

# Set env var before import to avoid using production DB
os.environ['FLASK_ENV'] = 'testing'

try:
    from app import app, db, User, Bus, calculate_eta
    
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///busbuddy_test_adv.db'
    
    with app.app_context():
        print("--- Testing Advanced Features ---")
        db.drop_all()
        db.create_all()
        
        # 1. Test ETA Logic Unit Test
        print("1. Testing ETA Logic...")
        # Route: Point A (0,0) -> Point B (0, 0.1) -> Point C (0, 0.2)
        # Approx 11km per 0.1 deg lat/lon? No. 
        # 0.1 deg lat is approx 11.1 km. 
        route = "[[28.0, 77.0], [28.1, 77.0], [28.2, 77.0]]" # Straight line north
        
        # Current at start (28.0, 77.0) -> ETA should be large (distance to end is ~22km)
        # Using simplified haversine for check
        eta_start = calculate_eta(28.0, 77.0, route)
        print(f"   ETA at Start: {eta_start}")
        
        # Current near end (28.19, 77.0) -> ETA should be small (Arriving Now or < 1 min)
        eta_end = calculate_eta(28.199, 77.0, route)
        print(f"   ETA near End: {eta_end}")
        
        assert "min" in eta_start or "hr" in eta_start
        assert eta_end == "Arriving Now" or "1 min" in eta_end
        print("✅ ETA Logic Verified.")
        
        # 2. Integration Test via Client
        client = app.test_client()
        
        # Create Users
        admin = User(name='Admin', email='admin@test.com', password='pw', role='admin', approved=True)
        driver = User(name='Driver', email='driver@test.com', password='pw', role='driver', approved=True)
        db.session.add_all([admin, driver])
        db.session.commit()
        
        # Add Bus with Route
        with client.session_transaction() as sess:
            sess['user_id'] = admin.id
            sess['role'] = 'admin'
            
        print("2. Testing Bus w/ Route Upload...")
        client.post('/api/buses', json={
            'number': 'BUS-ADV',
            'route': 'Advanced Route',
            'coords': route,
            'capacity': 50
        })
        
        bus = Bus.query.filter_by(bus_number='BUS-ADV').first()
        assert bus.route_coordinates == route
        
        # Driver Update & ETA Recalculation
        with client.session_transaction() as sess:
            sess['user_id'] = driver.id
            sess['role'] = 'driver'
            sess['name'] = 'Driver'
            
        print("3. Testing Driver Update & ETA...")
        # Driver updates location to middle of route
        client.post('/api/driver/update', json={
            'bus_id': bus.id,
            'status': 'active',
            'lat': 28.1,
            'lon': 77.0
        })
        
        # Verify ETA updated in DB
        db.session.refresh(bus)
        print(f"   Updated Bus ETA: {bus.next_arrival_time}")
        assert bus.next_arrival_time is not None
        assert "min" in bus.next_arrival_time
        print("✅ Driver Update triggers ETA calc.")
        
        print("\n--- ALL ADVANCED TESTS PASSED ---")

except Exception as e:
    print(f"\n❌ SCRIPT ERROR: {e}")
    import traceback
    traceback.print_exc()
