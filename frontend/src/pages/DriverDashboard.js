import React, { useState, useEffect } from 'react';
import { Bus, MapPin, Navigation, ShieldAlert, LogOut, Send } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { api } from '../App';
import { toast } from 'sonner';

export default function DriverDashboard({ user, onLogout }) {
  const [buses, setBuses] = useState([]);
  const [selectedBus, setSelectedBus] = useState('');
  const [location, setLocation] = useState({ latitude: '', longitude: '' });
  const [emergencyDesc, setEmergencyDesc] = useState('');
  const [loading, setLoading] = useState(false);
  const [busStatus, setBusStatus] = useState('inactive');

  useEffect(() => {
    const fetchBuses = async () => {
      try {
        const response = await api.get('/buses');
        const driverBuses = response.data.filter(b => b.driver_id === user.id || !b.driver_id);
        setBuses(driverBuses);
        if (driverBuses.length > 0) {
          setSelectedBus(driverBuses[0].id);
          setBusStatus(driverBuses[0].status || 'inactive');
        }
      } catch (error) {
        toast.error('Failed to load buses');
      }
    };
    fetchBuses();

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLocation({
            latitude: position.coords.latitude.toString(),
            longitude: position.coords.longitude.toString()
          });
        },
        () => toast.error('Could not get GPS location')
      );
    }
  }, [user.id]);

  useEffect(() => {
    // Update bus status when selection changes
    const selected = buses.find(b => b.id === selectedBus);
    if (selected) {
      setBusStatus(selected.status || 'inactive');
    }
  }, [selectedBus, buses]);

  const handleBusStatusToggle = async () => {
    if (!selectedBus) {
      toast.error('Please select a bus first');
      return;
    }

    setLoading(true);
    try {
      const newStatus = busStatus === 'active' ? 'inactive' : 'active';
      await api.patch(`/buses/${selectedBus}/status?status=${newStatus}`);
      setBusStatus(newStatus);
      toast.success(`Bus ${newStatus === 'active' ? 'activated' : 'deactivated'} successfully`);
      
      // Update local buses state
      setBuses(prev => prev.map(b => 
        b.id === selectedBus ? {...b, status: newStatus} : b
      ));
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to update bus status';
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateLocation = async () => {
    if (!selectedBus || !location.latitude || !location.longitude) {
      toast.error('Please select a bus and enter valid coordinates');
      return;
    }

    const lat = parseFloat(location.latitude);
    const lng = parseFloat(location.longitude);

    if (isNaN(lat) || isNaN(lng)) {
      toast.error('Please enter valid numeric coordinates');
      return;
    }

    if (lat < -90 || lat > 90) {
      toast.error('Latitude must be between -90 and 90');
      return;
    }

    if (lng < -180 || lng > 180) {
      toast.error('Longitude must be between -180 and 180');
      return;
    }

    setLoading(true);
    try {
      await api.post('/locations', {
        bus_id: selectedBus,
        latitude: lat,
        longitude: lng,
        speed: 0,
        heading: 0
      });
      toast.success('✓ Location updated successfully');
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to update location';
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleEmergency = async () => {
    if (!selectedBus || !location.latitude || !location.longitude) {
      toast.error('Please ensure bus and location are set');
      return;
    }

    setLoading(true);
    try {
      await api.post('/emergency', {
        bus_id: selectedBus,
        driver_id: user.id,
        latitude: parseFloat(location.latitude),
        longitude: parseFloat(location.longitude),
        description: emergencyDesc || 'Emergency situation reported by driver'
      });
      toast.success('Emergency alert sent to transport department');
      setEmergencyDesc('');
    } catch (error) {
      let errorMessage = 'Failed to send emergency alert';
      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        errorMessage = typeof detail === 'string' ? detail : 'Failed to send emergency alert';
      }
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6" data-testid="driver-dashboard">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between" data-testid="driver-header">
          <div className="flex items-center gap-3">
            <Bus className="w-10 h-10 text-amber-500" data-testid="driver-logo" />
            <div>
              <h1 className="text-3xl font-extrabold" data-testid="driver-title">Driver Control</h1>
              <p className="text-slate-400" data-testid="driver-welcome">Welcome, {user.name}</p>
            </div>
          </div>
          <Button variant="ghost" onClick={onLogout} className="text-white" data-testid="logout-button">
            <LogOut className="w-5 h-5" />
          </Button>
        </div>

        <Card className="bg-slate-800 border-slate-700" data-testid="bus-selection-card">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2" data-testid="bus-select-title">
              <Bus className="w-6 h-6" /> Select Your Bus
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select value={selectedBus} onValueChange={setSelectedBus}>
              <SelectTrigger className="bg-slate-700 border-slate-600 text-white" data-testid="bus-select">
                <SelectValue placeholder="Choose a bus" />
              </SelectTrigger>
              <SelectContent data-testid="bus-select-options">
                {buses.map(bus => (
                  <SelectItem key={bus.id} value={bus.id} data-testid={`bus-option-${bus.bus_number}`}>
                    Bus {bus.bus_number} - {bus.route_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {buses.length === 0 && (
              <p className="text-amber-400 text-sm mt-2" data-testid="no-buses-assigned">
                No buses assigned to you yet. Contact transport department.
              </p>
            )}
            
            {selectedBus && (
              <div className="mt-4 p-4 bg-slate-700/50 rounded-lg border border-slate-600" data-testid="bus-status-control">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white font-semibold">Bus Status</p>
                    <p className="text-sm text-slate-400">
                      {busStatus === 'active' ? 'Bus is currently active and visible to students' : 'Bus is inactive and not visible to students'}
                    </p>
                  </div>
                  <Button
                    onClick={handleBusStatusToggle}
                    disabled={loading}
                    className={`${busStatus === 'active' ? 'bg-red-600 hover:bg-red-700' : 'bg-emerald-600 hover:bg-emerald-700'} text-white font-bold`}
                    data-testid="bus-status-toggle"
                  >
                    {loading ? 'Updating...' : (busStatus === 'active' ? 'Deactivate Bus' : 'Activate Bus')}
                  </Button>
                </div>
                <div className="mt-2">
                  <Badge className={busStatus === 'active' ? 'bg-emerald-500' : 'bg-slate-500'} data-testid="bus-current-status">
                    {busStatus === 'active' ? 'ACTIVE' : 'INACTIVE'}
                  </Badge>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-slate-800 border-slate-700" data-testid="location-update-card">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <MapPin className="w-6 h-6 text-amber-500" /> Update Bus Location
            </CardTitle>
            <p className="text-slate-400 text-sm mt-2">Enter the location where your bus has reached</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-white">Latitude (North/South)</Label>
                <Input
                  type="number"
                  step="any"
                  placeholder="28.6139"
                  value={location.latitude}
                  onChange={(e) => setLocation({...location, latitude: e.target.value})}
                  className="bg-slate-700 border-slate-600 text-white h-14 text-lg"
                  data-testid="latitude-input"
                />
                <p className="text-xs text-slate-500">Example: 28.6139</p>
              </div>
              <div className="space-y-2">
                <Label className="text-white">Longitude (East/West)</Label>
                <Input
                  type="number"
                  step="any"
                  placeholder="77.2090"
                  value={location.longitude}
                  onChange={(e) => setLocation({...location, longitude: e.target.value})}
                  className="bg-slate-700 border-slate-600 text-white h-14 text-lg"
                  data-testid="longitude-input"
                />
                <p className="text-xs text-slate-500">Example: 77.2090</p>
              </div>
            </div>
            <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-600">
              <p className="text-slate-300 text-sm">
                💡 <strong>Tip:</strong> You can get coordinates from Google Maps by dropping a pin at your current location
              </p>
            </div>
            <Button
              onClick={handleUpdateLocation}
              disabled={loading}
              className="w-full h-14 bg-indigo-600 hover:bg-indigo-700 text-lg font-bold"
              data-testid="update-location-button"
            >
              <Send className="w-5 h-5 mr-2" /> Update Current Location
            </Button>
          </CardContent>
        </Card>

        <Card className="bg-red-900/20 border-red-500/50" data-testid="emergency-card">
          <CardHeader>
            <CardTitle className="text-red-400 flex items-center gap-2 text-2xl">
              <ShieldAlert className="w-8 h-8" /> Emergency Alert
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="text-white">Describe the Emergency</Label>
              <Textarea
                placeholder="Describe what happened..."
                value={emergencyDesc}
                onChange={(e) => setEmergencyDesc(e.target.value)}
                className="bg-slate-700 border-slate-600 text-white min-h-24"
                data-testid="emergency-description"
              />
            </div>
            <Button
              onClick={handleEmergency}
              disabled={loading}
              className="w-full h-16 bg-red-600 hover:bg-red-700 text-white text-xl font-black uppercase tracking-wider animate-pulse hover:animate-none"
              data-testid="emergency-button"
            >
              <ShieldAlert className="w-6 h-6 mr-3" /> TRIGGER SOS ALERT
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}