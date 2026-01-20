import React, { useState } from 'react';
import { Bus, MapPin, Shield, ArrowRight } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { api } from '../App';

export default function Landing({ onLogin }) {
  const [showAuth, setShowAuth] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
    role: 'student',
    phone: ''
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const endpoint = isLogin ? '/auth/login' : '/auth/register';
      const payload = isLogin 
        ? { email: formData.email, password: formData.password }
        : formData;
      
      const response = await api.post(endpoint, payload);
      toast.success(isLogin ? 'Login successful!' : 'Registration successful!');
      onLogin(response.data.user, response.data.access_token);
    } catch (error) {
      let errorMessage = 'Authentication failed';
      
      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (Array.isArray(detail)) {
          errorMessage = detail.map(err => err.msg || err.message || 'Validation error').join(', ');
        } else if (typeof detail === 'object' && detail.msg) {
          errorMessage = detail.msg;
        }
      }
      
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  if (showAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
      }}>
        <Card className="w-full max-w-md shadow-2xl" data-testid="auth-card" style={{
          background: 'linear-gradient(to bottom, #ffffff, #f8fafc)'
        }}>
          <CardHeader className="space-y-2 pb-6">
            <CardTitle className="text-2xl font-bold text-slate-800" data-testid="auth-title">
              {isLogin ? 'Sign In' : 'Create Account'}
            </CardTitle>
            <CardDescription className="text-slate-600" data-testid="auth-description">
              {isLogin ? 'Welcome back to CampusTransit' : 'Join CampusTransit today'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {!isLogin && (
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-slate-700">Full Name</Label>
                  <Input
                    id="name"
                    data-testid="name-input"
                    placeholder="John Doe"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    required={!isLogin}
                    className="border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
                  />
                </div>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="email" className="text-slate-700">Email</Label>
                <Input
                  id="email"
                  data-testid="email-input"
                  type="email"
                  placeholder="you@example.com"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  required
                  className="border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-slate-700">Password</Label>
                <Input
                  id="password"
                  data-testid="password-input"
                  type="password"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={(e) => setFormData({...formData, password: e.target.value})}
                  required
                  className="border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>

              {!isLogin && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="role" className="text-slate-700">Role</Label>
                    <Select value={formData.role} onValueChange={(value) => setFormData({...formData, role: value})}>
                      <SelectTrigger data-testid="role-select" className="border-slate-300 focus:border-indigo-500 focus:ring-indigo-500">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-white">
                        <SelectItem value="student">Student</SelectItem>
                        <SelectItem value="driver">Bus Driver</SelectItem>
                        <SelectItem value="transport_dept">Transport Department</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {(formData.role === 'driver' || formData.role === 'transport_dept') && (
                    <div className="space-y-2">
                      <Label htmlFor="phone" className="text-slate-700">Phone Number</Label>
                      <Input
                        id="phone"
                        data-testid="phone-input"
                        type="tel"
                        placeholder="+1234567890"
                        value={formData.phone}
                        onChange={(e) => setFormData({...formData, phone: e.target.value})}
                        className="border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
                      />
                    </div>
                  )}
                </>
              )}

              <Button
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
                disabled={loading}
                data-testid="submit-button"
              >
                {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Create Account')}
              </Button>

              <div className="text-center text-sm">
                <button
                  type="button"
                  onClick={() => setIsLogin(!isLogin)}
                  className="text-indigo-600 hover:text-indigo-700 hover:underline font-medium"
                  data-testid="toggle-auth-mode"
                >
                  {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
                </button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div 
        className="relative min-h-screen flex flex-col items-center justify-center p-8"
        style={{
          backgroundImage: `linear-gradient(rgba(79, 70, 229, 0.85), rgba(99, 102, 241, 0.85)), url('https://images.unsplash.com/photo-1582203513826-d5887ec1a982?crop=entropy&cs=srgb&fm=jpg&q=85')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center'
        }}
      >
        <div className="max-w-4xl text-center space-y-8" data-testid="landing-hero">
          <div className="flex items-center justify-center mb-6">
            <Bus className="w-16 h-16 text-white" />
          </div>
          
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold text-white leading-tight" data-testid="hero-title">
            CampusTransit
          </h1>
          
          <p className="text-lg sm:text-xl text-white/90 max-w-2xl mx-auto">
            Track your campus buses in real-time. Never miss your ride again with live location updates and instant emergency alerts.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mt-8">
            <Button
              size="lg"
              className="bg-white text-indigo-600 hover:bg-white/90 font-bold text-lg px-8 py-6 rounded-full shadow-xl"
              onClick={() => setShowAuth(true)}
              data-testid="get-started-btn"
            >
              Get Started <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16">
            <Card className="glass-panel" data-testid="feature-card-tracking">
              <CardHeader>
                <MapPin className="w-12 h-12 text-indigo-600 mb-4" />
                <CardTitle>Live Tracking</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600">See all campus buses in real-time on an interactive map</p>
              </CardContent>
            </Card>

            <Card className="glass-panel" data-testid="feature-card-updates">
              <CardHeader>
                <Bus className="w-12 h-12 text-amber-500 mb-4" />
                <CardTitle>Manual Updates</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600">Drivers can manually update location when GPS fails</p>
              </CardContent>
            </Card>

            <Card className="glass-panel" data-testid="feature-card-emergency">
              <CardHeader>
                <Shield className="w-12 h-12 text-red-500 mb-4" />
                <CardTitle>Emergency Alerts</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600">Instant SMS and email notifications for emergency situations</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
