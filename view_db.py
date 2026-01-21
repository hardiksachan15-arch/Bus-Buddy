from app import app, db, User, Bus

def view_data():
    with app.app_context():
        with open("db_dump.txt", "w") as f:
            f.write("=== SYSTEM USERS ===\n")
            users = User.query.all()
            if not users:
                f.write("No users found.\n")
            else:
                f.write(f"{'ID':<5} {'Name':<20} {'Email':<30} {'Role':<15} {'Approved'}\n")
                f.write("-" * 80 + "\n")
                for u in users:
                    f.write(f"{u.id:<5} {u.name:<20} {u.email:<30} {u.role:<15} {u.approved}\n")

            f.write("\n=== FLEET BUSES ===\n")
            buses = Bus.query.all()
            if not buses:
                f.write("No buses found.\n")
            else:
                f.write(f"{'ID':<5} {'Number':<15} {'Route':<20} {'Status'}\n")
                f.write("-" * 60 + "\n")
                for b in buses:
                    f.write(f"{b.id:<5} {b.bus_number:<15} {b.route_name:<20} {b.status}\n")
        
        print("Database content exported to db_dump.txt")

if __name__ == "__main__":
    view_data()
