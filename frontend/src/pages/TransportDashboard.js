import React, { useState, useEffect } from 'react';
import { Bus, MapPin, ShieldAlert, LogOut, Plus, CheckCircle, AlertTriangle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from '../components/ui/dialog';
import useWebSocket from 'react-use-websocket';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '../App';
import { toast } from 'sonner';

// Custom bus icon for transport dashboard
const busIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="32" height="32">
      <circle cx="12" cy="12" r="11" fill="#10B981" stroke="#fff" stroke-width="2"/>
      <path d="M3 6h18v10H3z M7 16v2 M17 16v2 M6 3h12v3H6z" fill="#fff"/>
    </svg>
  `),
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32],
});

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws';

export default function TransportDashboard({ user, onLogout }) {
  const [buses, setBuses] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [newBus, setNewBus] = useState({ bus_number: '', capacity: '', route_name: '' });
  const [showAddBus, setShowAddBus] = useState(false);

  const { sendJsonMessage, lastJsonMessage, readyState } = useWebSocket(WS_URL, {
    onOpen: () => console.log('WebSocket connected'),
    shouldReconnect: () => true,
    reconnectInterval: 3000
  });

  useEffect(() => {
    if (readyState === 1) {
      sendJsonMessage({ event: 'subscribe', channel: 'bus_locations' });
      sendJsonMessage({ event: 'subscribe', channel: 'emergency_alerts' });
    }
  }, [readyState, sendJsonMessage]);

  useEffect(() => {
    fetchBuses();
    fetchAlerts();
    
    // Debug: Check auth token
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');
    console.log('Auth check:', { 
      hasToken: !!token, 
      tokenLength: token?.length,
      user: user ? JSON.parse(user) : null 
    });
  }, []);

  useEffect(() => {
    if (lastJsonMessage) {
      if (lastJsonMessage.event === 'location_update') {
        const data = lastJsonMessage.data;
        setBuses(prev => {
          const index = prev.findIndex(b => b.id === data.bus_id);
          if (index > -1) {
            const updated = [...prev];
            updated[index] = {
              ...updated[index],
              status: 'active',
              last_location: {
                latitude: data.latitude,
                longitude: data.longitude,
                speed: data.speed,
                timestamp: data.timestamp
              }
            };
            return updated;
          }
          return prev;
        });
      } else if (lastJsonMessage.event === 'emergency_alert') {
        toast.error(`🚨 Emergency Alert: Bus ${lastJsonMessage.data.bus_number}`, {
          description: lastJsonMessage.data.description,
          duration: 10000
        });
        setAlerts(prev => [lastJsonMessage.data, ...prev]);
      }
    }
  }, [lastJsonMessage]);

  const fetchBuses = async () => {
    try {
      const response = await api.get('/buses');
      setBuses(response.data);
    } catch (error) {
      toast.error('Failed to fetch buses');
    }
  };

  const fetchAlerts = async () => {
    try {
      const response = await api.get('/emergency');
      setAlerts(response.data);
    } catch (error) {
      toast.error('Failed to fetch alerts');
    }
  };

  const handleAddBus = async () => {
    if (!newBus.bus_number || !newBus.capacity || !newBus.route_name) {
      toast.error('Please fill all fields');
      return;
    }
    
    try {
      await api.post('/buses', {
        bus_number: newBus.bus_number,
        capacity: parseInt(newBus.capacity),
        route_name: newBus.route_name
      });
      toast.success('✓ Bus added successfully!');
      setNewBus({ bus_number: '', capacity: '', route_name: '' });
      setShowAddBus(false);
      fetchBuses();
    } catch (error) {
      console.error('Bus creation error:', error);
      
      let errorMsg = 'Failed to add bus';
      if (error.response?.status === 401) {
        errorMsg = 'Session expired. Please login again.';
        setTimeout(() => {
          localStorage.clear();
          window.location.href = '/';
        }, 2000);
      } else if (error.response?.status === 403) {
        errorMsg = 'You do not have permission to add buses';
      } else if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        errorMsg = typeof detail === 'string' ? detail : 'Failed to add bus';
      }
      
      toast.error(errorMsg);
    }
  };

  const handleResolveAlert = async (alertId) => {
    try {
      await api.patch(`/emergency/${alertId}/resolve`);
      toast.success('Alert resolved');
      fetchAlerts();
    } catch (error) {
      toast.error('Failed to resolve alert');
    }
  };

  const handleToggleBusStatus = async (busId, currentStatus) => {
    try {
      const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
      await api.patch(`/buses/${busId}/status?status=${newStatus}`);
      toast.success(`Bus ${newStatus === 'active' ? 'activated' : 'deactivated'} successfully`);
      fetchBuses();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to update bus status';
      toast.error(errorMsg);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="transport-dashboard">
      <div className="bg-white border-b shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Bus className="w-8 h-8 text-indigo-600" />
            <div>
              <h1 className="text-2xl font-bold">Transport Control Center</h1>
              <p className="text-sm text-slate-600">Welcome, {user.name}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={readyState === 1 ? 'default' : 'secondary'} data-testid="connection-status">
              {readyState === 1 ? 'Connected' : 'Connecting...'}
            </Badge>
            <Button variant="ghost" onClick={onLogout} data-testid="logout-button">
              <LogOut className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Card data-testid="map-widget">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MapPin className="w-5 h-5" /> Live Map
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-96 rounded-lg overflow-hidden border">
                  <MapContainer
                    center={[28.6139, 77.2090]}
                    zoom={12}
                    style={{ height: '100%', width: '100%' }}
                  >
                    <TileLayer
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    
                    {buses.filter(b => b.status === 'active' && b.last_location).map(bus => (
                      <Marker
                        key={bus.id}
                        position={[bus.last_location.latitude, bus.last_location.longitude]}
                        icon={busIcon}
                      >
                        <Popup>
                          <div className="text-center p-1">
                            <p className="font-bold">Bus {bus.bus_number}</p>
                            <p className="text-xs">{bus.route_name}</p>
                            <p className="text-xs text-slate-500">
                              {new Date(bus.last_location.timestamp).toLocaleTimeString()}
                            </p>
                          </div>
                        </Popup>
                      </Marker>
                    ))}
                  </MapContainer>
                </div>
              </CardContent>
            </Card>

            <Card data-testid="buses-list">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Bus className="w-5 h-5" /> Fleet Management ({buses.length} buses)
                </CardTitle>
                <Dialog open={showAddBus} onOpenChange={setShowAddBus}>
                  <DialogTrigger asChild>
                    <Button size="sm" data-testid="add-bus-button">
                      <Plus className="w-4 h-4 mr-1" /> Add Bus
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Add New Bus to Fleet</DialogTitle>
                      <DialogDescription>
                        Fill in the details below to add a new bus to your fleet
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label>Bus Number *</Label>
                        <Input
                          placeholder="Enter bus number (e.g., 101)"
                          value={newBus.bus_number}
                          onChange={(e) => setNewBus({...newBus, bus_number: e.target.value})}
                          data-testid="bus-number-input"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Passenger Capacity *</Label>
                        <Input
                          type="number"
                          min="1"
                          placeholder="Enter capacity (e.g., 50)"
                          value={newBus.capacity}
                          onChange={(e) => setNewBus({...newBus, capacity: e.target.value})}
                          data-testid="bus-capacity-input"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Route Name *</Label>
                        <Input
                          placeholder="Enter route name (e.g., Main Campus Route)"
                          value={newBus.route_name}
                          onChange={(e) => setNewBus({...newBus, route_name: e.target.value})}
                          data-testid="bus-route-input"
                        />
                      </div>
                      <Button 
                        onClick={handleAddBus} 
                        className="w-full" 
                        data-testid="submit-bus-button"
                        disabled={!newBus.bus_number || !newBus.capacity || !newBus.route_name}
                      >
                        <Plus className="w-4 h-4 mr-2" /> Add Bus to Fleet
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {buses.map(bus => (
                    <div
                      key={bus.id}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-slate-50"
                      data-testid={`bus-item-${bus.bus_number}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                          bus.status === 'active' ? 'bg-emerald-500' : 'bg-slate-300'
                        }`}>
                          <Bus className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <p className="font-bold bus-number">Bus {bus.bus_number}</p>
                          <p className="text-sm text-slate-600">{bus.route_name}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant={bus.status === 'active' ? 'destructive' : 'default'}
                          onClick={() => handleToggleBusStatus(bus.id, bus.status)}
                          data-testid={`bus-toggle-${bus.bus_number}`}
                        >
                          {bus.status === 'active' ? 'Deactivate' : 'Activate'}
                        </Button>
                        <Badge className={bus.status === 'active' ? 'bg-emerald-500' : 'bg-slate-400'} data-testid={`bus-status-badge-${bus.bus_number}`}>
                          {bus.status || 'Inactive'}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card className={alerts.some(a => a.status === 'active') ? 'border-red-500 border-2' : ''} data-testid="emergency-feed">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-red-600">
                  <ShieldAlert className="w-5 h-5" /> Emergency Alerts
                  {alerts.filter(a => a.status === 'active').length > 0 && (
                    <Badge className="bg-red-600 ml-2 animate-pulse">
                      {alerts.filter(a => a.status === 'active').length} Active
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {alerts.length === 0 ? (
                    <p className="text-center text-slate-500 py-8">No emergency alerts</p>
                  ) : (
                    alerts.map(alert => (
                      <Card
                        key={alert.id}
                        className={alert.status === 'active' ? 'border-red-400' : 'border-slate-200'}
                        data-testid={`alert-${alert.id}`}
                      >
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              {alert.status === 'active' ? (
                                <AlertTriangle className="w-5 h-5 text-red-500" />
                              ) : (
                                <CheckCircle className="w-5 h-5 text-emerald-500" />
                              )}
                              <span className="font-bold">Bus {alert.bus_number || 'Unknown'}</span>
                            </div>
                            <Badge className={alert.status === 'active' ? 'bg-red-500' : 'bg-emerald-500'}>
                              {alert.status}
                            </Badge>
                          </div>
                          <p className="text-sm text-slate-600 mb-2">{alert.description}</p>
                          <p className="text-xs text-slate-500 mb-2">
                            {new Date(alert.timestamp).toLocaleString()}
                          </p>
                          {alert.status === 'active' && (
                            <Button
                              size="sm"
                              onClick={() => handleResolveAlert(alert.id)}
                              className="w-full"
                              data-testid={`resolve-alert-${alert.id}`}
                            >
                              Mark as Resolved
                            </Button>
                          )}
                        </CardContent>
                      </Card>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            <Card data-testid="stats-card">
              <CardHeader>
                <CardTitle>Statistics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600">Total Buses</span>
                    <span className="font-bold text-xl">{buses.length}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600">Active Buses</span>
                    <span className="font-bold text-xl text-emerald-600">
                      {buses.filter(b => b.status === 'active').length}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600">Active Alerts</span>
                    <span className="font-bold text-xl text-red-600">
                      {alerts.filter(a => a.status === 'active').length}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
