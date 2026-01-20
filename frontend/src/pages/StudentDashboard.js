import React, { useState, useEffect, useCallback } from 'react';
import { Bus, MapPin, Clock, LogOut, Navigation } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '../App';
import { toast } from 'sonner';

// Fix for default marker icons in Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Custom bus icon
const busIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="32" height="32">
      <circle cx="12" cy="12" r="11" fill="#F59E0B" stroke="#fff" stroke-width="2"/>
      <path d="M3 6h18v10H3z M7 16v2 M17 16v2 M6 3h12v3H6z" fill="#fff"/>
    </svg>
  `),
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32],
});

// Component to auto-fit map bounds to show all buses
function MapBounds({ buses }) {
  const map = useMap();
  
  useEffect(() => {
    if (buses.length > 0) {
      const bounds = buses
        .filter(bus => bus.last_location?.latitude && bus.last_location?.longitude)
        .map(bus => [bus.last_location.latitude, bus.last_location.longitude]);
      
      if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
      }
    }
  }, [buses, map]);
  
  return null;
}

// Component to recenter map when bus is selected
function MapRecenter({ center }) {
  const map = useMap();
  
  useEffect(() => {
    if (center) {
      map.setView([center.lat, center.lng], 15);
    }
  }, [center, map]);
  
  return null;
}

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws';

export default function StudentDashboard({ user, onLogout }) {
  const [buses, setBuses] = useState([]);
  const [selectedBus, setSelectedBus] = useState(null);
  const [mapCenter, setMapCenter] = useState({ lat: 28.6139, lng: 77.2090 });

  const { sendJsonMessage, lastJsonMessage, readyState } = useWebSocket(WS_URL, {
    onOpen: () => console.log('WebSocket connected'),
    shouldReconnect: () => true,
    reconnectInterval: 3000
  });

  const handleBusClick = (bus) => {
    setSelectedBus(bus);
    if (bus.last_location) {
      setMapCenter({ 
        lat: bus.last_location.latitude, 
        lng: bus.last_location.longitude 
      });
    }
  };

  useEffect(() => {
    if (readyState === 1) {
      sendJsonMessage({ event: 'subscribe', channel: 'bus_locations' });
      sendJsonMessage({ event: 'subscribe', channel: 'emergency_alerts' });
    }
  }, [readyState, sendJsonMessage]);

  useEffect(() => {
    const fetchBuses = async () => {
      try {
        const response = await api.get('/locations/latest');
        setBuses(response.data);
      } catch (error) {
        console.error('Failed to fetch buses:', error);
      }
    };
    fetchBuses();
  }, []);

  useEffect(() => {
    if (lastJsonMessage) {
      if (lastJsonMessage.event === 'location_update') {
        const data = lastJsonMessage.data;
        setBuses(prev => {
          const index = prev.findIndex(b => b.id === data.bus_id);
          const newBus = {
            id: data.bus_id,
            bus_number: data.bus_number,
            status: 'active',
            last_location: {
              latitude: data.latitude,
              longitude: data.longitude,
              speed: data.speed,
              timestamp: data.timestamp
            }
          };
          if (index > -1) {
            const updated = [...prev];
            updated[index] = newBus;
            return updated;
          }
          return [...prev, newBus];
        });
      } else if (lastJsonMessage.event === 'emergency_alert') {
        toast.error(`Emergency Alert: Bus ${lastJsonMessage.data.bus_number}`, {
          description: lastJsonMessage.data.description
        });
      }
    }
  }, [lastJsonMessage]);

  return (
    <div className="h-screen flex flex-col" data-testid="student-dashboard">
      <div className="glass-panel fixed top-0 left-0 right-0 z-20 border-b" data-testid="student-header">
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <Bus className="w-8 h-8 text-indigo-600" data-testid="app-logo" />
            <div>
              <h1 className="text-xl font-bold text-slate-900" data-testid="app-title">CampusTransit</h1>
              <p className="text-sm text-slate-600" data-testid="welcome-message">Welcome, {user.name}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={readyState === 1 ? 'default' : 'secondary'} data-testid="connection-status">
              {readyState === 1 ? 'Live' : 'Connecting...'}
            </Badge>
            <Button variant="ghost" size="sm" onClick={onLogout} data-testid="logout-button">
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 relative mt-16" data-testid="map-container">
        <MapContainer
          center={[mapCenter.lat, mapCenter.lng]}
          zoom={13}
          style={{ height: '100%', width: '100%' }}
          className="z-0"
          data-testid="leaflet-map"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          {buses.filter(b => b.status === 'active' && b.last_location).map(bus => (
            <Marker
              key={bus.id}
              position={[bus.last_location.latitude, bus.last_location.longitude]}
              icon={busIcon}
            >
              <Popup>
                <div className="text-center p-2">
                  <p className="font-bold text-lg">Bus {bus.bus_number}</p>
                  <p className="text-sm text-slate-600">{bus.route_name || 'Campus Route'}</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Last updated: {new Date(bus.last_location.timestamp).toLocaleTimeString()}
                  </p>
                  {bus.last_location.speed > 0 && (
                    <p className="text-xs text-emerald-600 mt-1">
                      Speed: {bus.last_location.speed.toFixed(1)} km/h
                    </p>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}
          
          <MapBounds buses={buses.filter(b => b.status === 'active' && b.last_location)} />
          <MapRecenter center={selectedBus?.last_location ? { lat: selectedBus.last_location.latitude, lng: selectedBus.last_location.longitude } : null} />
        </MapContainer>

        <div className="absolute bottom-0 left-0 right-0 glass-panel rounded-t-3xl p-6 max-h-80 overflow-y-auto z-10" data-testid="bus-list">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2" data-testid="bus-list-title">
            <Navigation className="w-5 h-5 text-indigo-600" />
            Active Buses ({buses.filter(b => b.status === 'active').length})
          </h2>
          
          {buses.filter(b => b.status === 'active').length === 0 ? (
            <p className="text-center text-slate-500 py-8" data-testid="no-buses-message">No active buses at the moment</p>
          ) : (
            <div className="space-y-3" data-testid="active-buses-list">
              {buses.filter(b => b.status === 'active').map(bus => (
                <Card
                  key={bus.id}
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => handleBusClick(bus)}
                  data-testid={`bus-item-${bus.bus_number}`}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-amber-500 flex items-center justify-center" data-testid={`bus-icon-${bus.bus_number}`}>
                          <Bus className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <p className="font-bold bus-number" data-testid={`bus-number-${bus.bus_number}`}>Bus {bus.bus_number}</p>
                          <p className="text-sm text-slate-600" data-testid={`bus-route-${bus.bus_number}`}>{bus.route_name || 'Campus Route'}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <Badge className="bg-emerald-500" data-testid={`bus-status-${bus.bus_number}`}>Active</Badge>
                        {bus.last_location && (
                          <p className="text-xs text-slate-500 mt-1" data-testid={`bus-time-${bus.bus_number}`}>
                            <Clock className="w-3 h-3 inline" /> {new Date(bus.last_location.timestamp).toLocaleTimeString()}
                          </p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}