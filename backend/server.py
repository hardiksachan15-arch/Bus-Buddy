from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Set
import uuid
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
import jwt
import json
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

SECRET_KEY = os.environ['JWT_SECRET_KEY']
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

twilio_client = None
if os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"):
    twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.client_subscriptions: dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.client_subscriptions[websocket] = set()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.client_subscriptions.pop(websocket, None)

    async def broadcast(self, message: dict, channel: str = None):
        disconnected = set()
        for connection in self.active_connections:
            subscriptions = self.client_subscriptions.get(connection, set())
            if channel is None or channel in subscriptions:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    disconnected.add(connection)
        for connection in disconnected:
            self.disconnect(connection)

    def subscribe(self, websocket: WebSocket, channel: str):
        if websocket in self.client_subscriptions:
            self.client_subscriptions[websocket].add(channel)

manager = ConnectionManager()

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserApproval(BaseModel):
    user_id: str
    approved: bool
    reason: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class BusCreate(BaseModel):
    bus_number: str
    capacity: int
    route_name: str
    driver_id: Optional[str] = None

class BusLocation(BaseModel):
    bus_id: str
    latitude: float
    longitude: float
    speed: float = 0.0
    heading: float = 0.0
    timestamp: Optional[datetime] = None
    passenger_count: Optional[int] = 0

class EmergencyAlert(BaseModel):
    bus_id: str
    driver_id: str
    latitude: float
    longitude: float
    description: str
    timestamp: Optional[datetime] = None

class SpeedAlert(BaseModel):
    bus_id: str
    driver_id: str
    speed: float
    max_speed: float = 80.0
    timestamp: Optional[datetime] = None

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@api_router.post("/auth/register", response_model=Token)
async def register(user: UserCreate):
    existing = await db.users.find_one({"email": user.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    
    # Students are auto-approved, drivers and transport need approval
    is_approved = user.role == "student"
    approval_status = "approved" if is_approved else "pending"
    
    user_doc = {
        "id": user_id,
        "email": user.email,
        "password": get_password_hash(user.password),
        "name": user.name,
        "role": user.role,
        "phone": user.phone,
        "approved": is_approved,
        "approval_status": approval_status,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    insert_doc = user_doc.copy()
    await db.users.insert_one(insert_doc)
    
    # For drivers and transport, send notification to transport dept
    if not is_approved:
        await manager.broadcast({
            "event": "new_user_request",
            "data": {
                "user_id": user_id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "phone": user.phone,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }, channel="approval_requests")
    
    if not is_approved:
        return {
            "access_token": "",
            "token_type": "pending_approval",
            "user": {
                "id": user_id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "approved": False,
                "approval_status": "pending"
            }
        }
    
    access_token = create_access_token(data={"sub": user_id, "role": user.role})
    user_data = {k: v for k, v in user_doc.items() if k != "password" and k != "_id"}
    return {"access_token": access_token, "token_type": "bearer", "user": user_data}

@api_router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check if user is approved
    if not user.get("approved", False):
        raise HTTPException(
            status_code=403, 
            detail="Your account is pending approval from the transport department. Please wait for confirmation."
        )
    
    access_token = create_access_token(data={"sub": user["id"], "role": user["role"]})
    user_data = {k: v for k, v in user.items() if k != "password"}
    return {"access_token": access_token, "token_type": "bearer", "user": user_data}

@api_router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@api_router.get("/users/pending")
async def get_pending_users(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "transport_dept":
        raise HTTPException(status_code=403, detail="Only transport department can view pending users")
    
    pending_users = await db.users.find(
        {"approved": False, "approval_status": "pending"},
        {"_id": 0, "password": 0}
    ).to_list(1000)
    return pending_users

@api_router.post("/users/approve")
async def approve_user(approval: UserApproval, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "transport_dept":
        raise HTTPException(status_code=403, detail="Only transport department can approve users")
    
    user = await db.users.find_one({"id": approval.user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if approval.approved:
        await db.users.update_one(
            {"id": approval.user_id},
            {"$set": {
                "approved": True,
                "approval_status": "approved",
                "approved_by": current_user["id"],
                "approved_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Notify user via broadcast
        await manager.broadcast({
            "event": "user_approved",
            "data": {
                "user_id": approval.user_id,
                "email": user["email"],
                "name": user["name"],
                "role": user["role"]
            }
        }, channel="approval_requests")
        
        return {"status": "approved", "user_id": approval.user_id}
    else:
        await db.users.update_one(
            {"id": approval.user_id},
            {"$set": {
                "approval_status": "rejected",
                "rejection_reason": approval.reason,
                "rejected_by": current_user["id"],
                "rejected_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return {"status": "rejected", "user_id": approval.user_id}

@api_router.post("/buses")
async def create_bus(bus: BusCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "transport_dept":
        raise HTTPException(status_code=403, detail="Only transport department can create buses")
    
    bus_id = str(uuid.uuid4())
    bus_doc = {
        "id": bus_id,
        "bus_number": bus.bus_number,
        "capacity": bus.capacity,
        "route_name": bus.route_name,
        "driver_id": bus.driver_id,
        "status": "inactive",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    insert_doc = bus_doc.copy()
    await db.buses.insert_one(insert_doc)
    return {"id": bus_id, "bus_number": bus.bus_number, "capacity": bus.capacity, "route_name": bus.route_name, "status": "inactive"}

@api_router.patch("/buses/{bus_id}/status")
async def update_bus_status(bus_id: str, status: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["driver", "transport_dept"]:
        raise HTTPException(status_code=403, detail="Only drivers and transport department can update bus status")
    
    if status not in ["active", "inactive"]:
        raise HTTPException(status_code=400, detail="Status must be 'active' or 'inactive'")
    
    # If driver, verify they have access to this bus
    if current_user["role"] == "driver":
        bus = await db.buses.find_one({"id": bus_id}, {"_id": 0})
        if not bus:
            raise HTTPException(status_code=404, detail="Bus not found")
        if bus.get("driver_id") and bus.get("driver_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="You can only control buses assigned to you")
    
    result = await db.buses.update_one(
        {"id": bus_id},
        {"$set": {"status": status}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Bus not found")
    
    # Broadcast status change
    bus = await db.buses.find_one({"id": bus_id}, {"_id": 0})
    await manager.broadcast({
        "event": "bus_status_update",
        "data": {
            "bus_id": bus_id,
            "bus_number": bus.get("bus_number", ""),
            "status": status
        }
    }, channel="bus_locations")
    
    return {"status": "success", "bus_id": bus_id, "new_status": status}

@api_router.get("/buses")
async def get_buses(current_user: dict = Depends(get_current_user)):
    buses = await db.buses.find({}, {"_id": 0}).to_list(1000)
    return buses

@api_router.post("/locations")
async def update_location(location: BusLocation, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["driver", "transport_dept"]:
        raise HTTPException(status_code=403, detail="Only drivers can update location")
    
    timestamp = location.timestamp or datetime.now(timezone.utc)
    location_doc = {
        "bus_id": location.bus_id,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "speed": location.speed,
        "heading": location.heading,
        "passenger_count": location.passenger_count,
        "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp
    }
    insert_doc = location_doc.copy()
    await db.bus_locations.insert_one(insert_doc)
    
    await db.buses.update_one(
        {"id": location.bus_id},
        {"$set": {
            "status": "active",
            "last_location": location_doc,
            "current_speed": location.speed
        }}
    )
    
    bus = await db.buses.find_one({"id": location.bus_id}, {"_id": 0})
    
    # Broadcast location update
    await manager.broadcast({
        "event": "location_update",
        "data": {
            "bus_id": location.bus_id,
            "bus_number": bus.get("bus_number", "") if bus else "",
            "latitude": location.latitude,
            "longitude": location.longitude,
            "speed": location.speed,
            "heading": location.heading,
            "passenger_count": location.passenger_count,
            "timestamp": location_doc["timestamp"]
        }
    }, channel="bus_locations")
    
    # Speed monitoring - trigger alert if speed exceeds 80 km/h
    MAX_SPEED = 80.0
    if location.speed > MAX_SPEED:
        speed_alert_doc = {
            "id": str(uuid.uuid4()),
            "bus_id": location.bus_id,
            "driver_id": current_user["id"],
            "speed": location.speed,
            "max_speed": MAX_SPEED,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acknowledged": False
        }
        await db.speed_alerts.insert_one(speed_alert_doc)
        
        # Broadcast speed alert
        await manager.broadcast({
            "event": "speed_alert",
            "data": {
                "alert_id": speed_alert_doc["id"],
                "bus_id": location.bus_id,
                "bus_number": bus.get("bus_number", "") if bus else "",
                "driver_id": current_user["id"],
                "driver_name": current_user.get("name", "Unknown"),
                "speed": location.speed,
                "max_speed": MAX_SPEED,
                "message": f"⚠️ SPEED ALERT: Bus {bus.get('bus_number', '')} is traveling at {location.speed:.1f} km/h (Limit: {MAX_SPEED} km/h). Please reduce speed immediately!",
                "timestamp": speed_alert_doc["timestamp"]
            }
        }, channel="speed_alerts")
    
    return {"status": "success", "speed_alert": location.speed > MAX_SPEED}

@api_router.get("/locations/latest")
async def get_latest_locations(current_user: dict = Depends(get_current_user)):
    buses = await db.buses.find({"status": "active"}, {"_id": 0}).to_list(1000)
    # Ensure all data is JSON serializable
    result = []
    for bus in buses:
        bus_data = {
            "id": bus.get("id"),
            "bus_number": bus.get("bus_number"),
            "capacity": bus.get("capacity"),
            "route_name": bus.get("route_name"),
            "driver_id": bus.get("driver_id"),
            "status": bus.get("status"),
            "last_location": bus.get("last_location"),
            "created_at": bus.get("created_at")
        }
        result.append(bus_data)
    return result

@api_router.post("/emergency")
async def trigger_emergency(alert: EmergencyAlert, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "driver":
        raise HTTPException(status_code=403, detail="Only drivers can trigger emergency alerts")
    
    alert_id = str(uuid.uuid4())
    timestamp = alert.timestamp or datetime.now(timezone.utc)
    alert_doc = {
        "id": alert_id,
        "bus_id": alert.bus_id,
        "driver_id": alert.driver_id,
        "latitude": alert.latitude,
        "longitude": alert.longitude,
        "description": alert.description,
        "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        "status": "active"
    }
    insert_doc = alert_doc.copy()
    await db.emergency_alerts.insert_one(insert_doc)
    
    bus = await db.buses.find_one({"id": alert.bus_id}, {"_id": 0})
    driver = await db.users.find_one({"id": alert.driver_id}, {"_id": 0})
    
    broadcast_data = {
        "alert_id": alert_id,
        "bus_id": alert.bus_id,
        "bus_number": bus.get("bus_number", "") if bus else "",
        "driver_name": driver.get("name", "Unknown") if driver else "Unknown",
        "latitude": alert.latitude,
        "longitude": alert.longitude,
        "description": alert.description,
        "timestamp": alert_doc["timestamp"],
        "status": "active"
    }
    
    await manager.broadcast({
        "event": "emergency_alert",
        "data": broadcast_data
    }, channel="emergency_alerts")
    
    transport_users = await db.users.find({"role": "transport_dept"}, {"_id": 0}).to_list(1000)
    
    message = f"EMERGENCY ALERT!\nBus: {bus.get('bus_number', 'Unknown')}\nDriver: {driver.get('name', 'Unknown')}\nLocation: {alert.latitude}, {alert.longitude}\nDescription: {alert.description}"
    
    for user in transport_users:
        if twilio_client and user.get("phone"):
            try:
                twilio_client.messages.create(
                    body=message,
                    from_=os.getenv("TWILIO_PHONE_NUMBER"),
                    to=user["phone"]
                )
            except Exception as e:
                logging.error(f"SMS failed: {e}")
        
        if os.getenv("SENDGRID_API_KEY") and user.get("email"):
            try:
                sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
                email_message = Mail(
                    from_email=os.getenv("SENDGRID_FROM_EMAIL", "alerts@campustransit.com"),
                    to_emails=user["email"],
                    subject="🚨 EMERGENCY ALERT - Bus Incident",
                    html_content=f"<h2>Emergency Alert</h2><p>{message.replace(chr(10), '<br>')}</p>"
                )
                sg.send(email_message)
            except Exception as e:
                logging.error(f"Email failed: {e}")
    
    return {"alert_id": alert_id, "status": "alert_sent"}

@api_router.get("/emergency")
async def get_emergency_alerts(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "transport_dept":
        raise HTTPException(status_code=403, detail="Only transport department can view alerts")
    alerts = await db.emergency_alerts.find({}, {"_id": 0}).sort("timestamp", -1).to_list(100)
    return alerts

@api_router.patch("/emergency/{alert_id}/resolve")
async def resolve_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "transport_dept":
        raise HTTPException(status_code=403, detail="Only transport department can resolve alerts")
    await db.emergency_alerts.update_one({"id": alert_id}, {"$set": {"status": "resolved"}})
    return {"status": "resolved"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("event") == "subscribe":
                channel = message.get("channel", "bus_locations")
                manager.subscribe(websocket, channel)
                await websocket.send_text(json.dumps({"event": "subscription_confirmed", "channel": channel}))
            elif message.get("event") == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()