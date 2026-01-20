import requests
import sys
import json
from datetime import datetime

class CampusTransitAPITester:
    def __init__(self, base_url="https://busbuddy-campus-1.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tokens = {}
        self.users = {}
        self.buses = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.timestamp = datetime.now().strftime("%H%M%S")

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None, description=""):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        if description:
            print(f"   Description: {description}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Response: {response.text}")
                self.failed_tests.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append(f"{name}: {str(e)}")
            return False, {}

    def test_user_registration(self):
        """Test user registration for all roles"""
        print("\n" + "="*50)
        print("TESTING USER REGISTRATION")
        print("="*50)
        
        # Test student registration
        student_data = {
            "email": f"student{self.timestamp}@test.com",
            "password": "test123",
            "name": "Test Student New",
            "role": "student"
        }
        success, response = self.run_test(
            "Student Registration",
            "POST",
            "auth/register",
            200,
            data=student_data,
            description="Register a new student user"
        )
        if success and 'access_token' in response:
            self.tokens['student_new'] = response['access_token']
            self.users['student_new'] = response['user']
            print(f"   Student ID: {response['user']['id']}")

        # Test driver registration
        driver_data = {
            "email": f"driver{self.timestamp}@test.com",
            "password": "test123",
            "name": "Test Driver New",
            "role": "driver",
            "phone": "+1234567890"
        }
        success, response = self.run_test(
            "Driver Registration",
            "POST",
            "auth/register",
            200,
            data=driver_data,
            description="Register a new driver user"
        )
        if success and 'access_token' in response:
            self.tokens['driver_new'] = response['access_token']
            self.users['driver_new'] = response['user']
            print(f"   Driver ID: {response['user']['id']}")

        # Test transport dept registration
        transport_data = {
            "email": f"transport{self.timestamp}@test.com",
            "password": "test123",
            "name": "Transport Admin New",
            "role": "transport_dept",
            "phone": "+1234567891"
        }
        success, response = self.run_test(
            "Transport Dept Registration",
            "POST",
            "auth/register",
            200,
            data=transport_data,
            description="Register a new transport department user"
        )
        if success and 'access_token' in response:
            self.tokens['transport_dept_new'] = response['access_token']
            self.users['transport_dept_new'] = response['user']
            print(f"   Transport Admin ID: {response['user']['id']}")
            
        # Test duplicate email registration (should fail)
        success, response = self.run_test(
            "Duplicate Email Registration",
            "POST",
            "auth/register",
            400,
            data=student_data,
            description="Duplicate email should be rejected"
        )

    def test_user_login(self):
        """Test user login for all roles"""
        print("\n" + "="*50)
        print("TESTING USER LOGIN")
        print("="*50)
        
        # Test student login with newly registered user
        if 'student_new' in self.users:
            login_data = {"email": f"student{self.timestamp}@test.com", "password": "test123"}
            success, response = self.run_test(
                "Student Login",
                "POST",
                "auth/login",
                200,
                data=login_data,
                description="Login with student credentials"
            )
            if success and 'access_token' in response:
                self.tokens['student'] = response['access_token']
                self.users['student'] = response['user']
                print(f"   Student ID: {response['user']['id']}")
        
        # Test driver login with newly registered user
        if 'driver_new' in self.users:
            login_data = {"email": f"driver{self.timestamp}@test.com", "password": "test123"}
            success, response = self.run_test(
                "Driver Login",
                "POST",
                "auth/login",
                200,
                data=login_data,
                description="Login with driver credentials"
            )
            if success and 'access_token' in response:
                self.tokens['driver'] = response['access_token']
                self.users['driver'] = response['user']
                print(f"   Driver ID: {response['user']['id']}")
        
        # Test transport dept login with newly registered user
        if 'transport_dept_new' in self.users:
            login_data = {"email": f"transport{self.timestamp}@test.com", "password": "test123"}
            success, response = self.run_test(
                "Transport Dept Login",
                "POST",
                "auth/login",
                200,
                data=login_data,
                description="Login with transport department credentials"
            )
            if success and 'access_token' in response:
                self.tokens['transport_dept'] = response['access_token']
                self.users['transport_dept'] = response['user']
                print(f"   Transport Admin ID: {response['user']['id']}")
            
        # Test invalid login
        login_data = {"email": "invalid@test.com", "password": "wrongpass"}
        success, response = self.run_test(
            "Invalid Login",
            "POST",
            "auth/login",
            401,
            data=login_data,
            description="Invalid credentials should be rejected"
        )

    def test_auth_me_endpoint(self):
        """Test /auth/me endpoint with tokens"""
        print("\n" + "="*50)
        print("TESTING AUTH/ME ENDPOINT")
        print("="*50)
        
        for role in ['student', 'driver', 'transport_dept']:
            if role in self.tokens:
                success, response = self.run_test(
                    f"{role.title()} Auth/Me",
                    "GET",
                    "auth/me",
                    200,
                    token=self.tokens[role],
                    description=f"Verify {role} token validity"
                )

    def test_bus_management(self):
        """Test bus CRUD operations"""
        print("\n" + "="*50)
        print("TESTING BUS MANAGEMENT")
        print("="*50)
        
        if 'transport_dept' not in self.tokens:
            print("❌ No transport dept token available for bus management tests")
            return

        # Test creating a bus
        bus_data = {
            "bus_number": "101",
            "capacity": 50,
            "route_name": "Main Campus Route"
        }
        success, response = self.run_test(
            "Create Bus",
            "POST",
            "buses",
            200,
            data=bus_data,
            token=self.tokens['transport_dept'],
            description="Create a new bus (transport dept only)"
        )
        if success and 'id' in response:
            self.buses['main_bus'] = response
            print(f"   Bus ID: {response['id']}")

        # Test getting all buses
        success, response = self.run_test(
            "Get All Buses",
            "GET",
            "buses",
            200,
            token=self.tokens['transport_dept'],
            description="Retrieve all buses"
        )
        if success:
            print(f"   Found {len(response)} buses")

        # Test unauthorized bus creation (student trying to create bus)
        if 'student' in self.tokens:
            success, response = self.run_test(
                "Unauthorized Bus Creation",
                "POST",
                "buses",
                403,
                data=bus_data,
                token=self.tokens['student'],
                description="Student should not be able to create buses"
            )

    def test_location_updates(self):
        """Test location update functionality"""
        print("\n" + "="*50)
        print("TESTING LOCATION UPDATES")
        print("="*50)
        
        if 'driver' not in self.tokens or 'main_bus' not in self.buses:
            print("❌ No driver token or bus available for location tests")
            return

        # Test location update by driver
        location_data = {
            "bus_id": self.buses['main_bus']['id'],
            "latitude": 28.6139,
            "longitude": 77.2090,
            "speed": 30.5,
            "heading": 180
        }
        success, response = self.run_test(
            "Driver Location Update",
            "POST",
            "locations",
            200,
            data=location_data,
            token=self.tokens['driver'],
            description="Driver updates bus location"
        )

        # Test getting latest locations
        success, response = self.run_test(
            "Get Latest Locations",
            "GET",
            "locations/latest",
            200,
            token=self.tokens['driver'],
            description="Retrieve latest bus locations"
        )
        if success:
            print(f"   Found {len(response)} active buses")

        # Test unauthorized location update (student trying to update location)
        if 'student' in self.tokens:
            success, response = self.run_test(
                "Unauthorized Location Update",
                "POST",
                "locations",
                403,
                data=location_data,
                token=self.tokens['student'],
                description="Student should not be able to update locations"
            )

    def test_emergency_alerts(self):
        """Test emergency alert system"""
        print("\n" + "="*50)
        print("TESTING EMERGENCY ALERTS")
        print("="*50)
        
        if 'driver' not in self.tokens or 'main_bus' not in self.buses:
            print("❌ No driver token or bus available for emergency tests")
            return

        # Test emergency alert creation by driver
        alert_data = {
            "bus_id": self.buses['main_bus']['id'],
            "driver_id": self.users['driver']['id'],
            "latitude": 28.6139,
            "longitude": 77.2090,
            "description": "Bus breakdown on highway"
        }
        success, response = self.run_test(
            "Trigger Emergency Alert",
            "POST",
            "emergency",
            200,
            data=alert_data,
            token=self.tokens['driver'],
            description="Driver triggers emergency alert"
        )
        alert_id = None
        if success and 'alert_id' in response:
            alert_id = response['alert_id']
            print(f"   Alert ID: {alert_id}")

        # Test getting emergency alerts (transport dept only)
        if 'transport_dept' in self.tokens:
            success, response = self.run_test(
                "Get Emergency Alerts",
                "GET",
                "emergency",
                200,
                token=self.tokens['transport_dept'],
                description="Transport dept views emergency alerts"
            )
            if success:
                print(f"   Found {len(response)} emergency alerts")

            # Test resolving alert
            if alert_id:
                success, response = self.run_test(
                    "Resolve Emergency Alert",
                    "PATCH",
                    f"emergency/{alert_id}/resolve",
                    200,
                    token=self.tokens['transport_dept'],
                    description="Transport dept resolves emergency alert"
                )

        # Test unauthorized emergency alert access (student trying to view alerts)
        if 'student' in self.tokens:
            success, response = self.run_test(
                "Unauthorized Emergency Access",
                "GET",
                "emergency",
                403,
                token=self.tokens['student'],
                description="Student should not be able to view emergency alerts"
            )

    def test_role_based_access_control(self):
        """Test role-based access control"""
        print("\n" + "="*50)
        print("TESTING ROLE-BASED ACCESS CONTROL")
        print("="*50)
        
        # Test student accessing driver endpoints
        if 'student' in self.tokens and 'main_bus' in self.buses:
            location_data = {
                "bus_id": self.buses['main_bus']['id'],
                "latitude": 28.6139,
                "longitude": 77.2090,
                "speed": 30.5,
                "heading": 180
            }
            success, response = self.run_test(
                "Student Access to Driver Endpoint",
                "POST",
                "locations",
                403,
                data=location_data,
                token=self.tokens['student'],
                description="Student should not access driver endpoints"
            )

        # Test driver accessing transport dept endpoints
        if 'driver' in self.tokens:
            bus_data = {
                "bus_number": "102",
                "capacity": 40,
                "route_name": "Secondary Route"
            }
            success, response = self.run_test(
                "Driver Access to Transport Endpoint",
                "POST",
                "buses",
                403,
                data=bus_data,
                token=self.tokens['driver'],
                description="Driver should not access transport dept endpoints"
            )

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚌 Starting CampusTransit API Testing...")
        print(f"Backend URL: {self.base_url}")
        
        try:
            self.test_user_registration()
            self.test_user_login()
            self.test_auth_me_endpoint()
            self.test_bus_management()
            self.test_location_updates()
            self.test_emergency_alerts()
            self.test_role_based_access_control()
            
            # Print final results
            print("\n" + "="*60)
            print("FINAL TEST RESULTS")
            print("="*60)
            print(f"📊 Tests passed: {self.tests_passed}/{self.tests_run}")
            
            if self.failed_tests:
                print(f"\n❌ Failed Tests ({len(self.failed_tests)}):")
                for i, failure in enumerate(self.failed_tests, 1):
                    print(f"   {i}. {failure}")
            else:
                print("\n🎉 All tests passed!")
            
            return 0 if self.tests_passed == self.tests_run else 1
            
        except Exception as e:
            print(f"\n💥 Critical error during testing: {str(e)}")
            return 1

def main():
    tester = CampusTransitAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())