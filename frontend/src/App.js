import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import Landing from './pages/Landing';
import StudentDashboard from './pages/StudentDashboard';
import DriverDashboard from './pages/DriverDashboard';
import TransportDashboard from './pages/TransportDashboard';
import { Toaster } from './components/ui/sonner';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  headers: {
    'Content-Type': 'application/json'
  }
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');
    if (token && storedUser) {
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  const handleLogin = (userData, token) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={!user ? <Landing onLogin={handleLogin} /> : <Navigate to={`/${user.role}`} />} />
          <Route path="/student" element={user && user.role === 'student' ? <StudentDashboard user={user} onLogout={handleLogout} /> : <Navigate to="/" />} />
          <Route path="/driver" element={user && user.role === 'driver' ? <DriverDashboard user={user} onLogout={handleLogout} /> : <Navigate to="/" />} />
          <Route path="/transport_dept" element={user && user.role === 'transport_dept' ? <TransportDashboard user={user} onLogout={handleLogout} /> : <Navigate to="/" />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;