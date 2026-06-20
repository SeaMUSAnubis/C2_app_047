import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../store/authStore';
import { mockAdmin, mockAnalyst } from '../mocks/mockData';
import { Activity } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Simulate API delay
    await new Promise(r => setTimeout(r, 500));

    if (email === 'admin@demo.com' && password === 'password123') {
      login(mockAdmin, 'fake-jwt-token-admin');
      navigate('/dashboard');
    } else if (email === 'analyst@demo.com' && password === 'password123') {
      login(mockAnalyst, 'fake-jwt-token-analyst');
      navigate('/dashboard');
    } else {
      setError('Invalid email or password');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-surface p-8 rounded-xl shadow-2xl border border-border">
        <div className="flex justify-center mb-6">
          <div className="bg-primary/20 p-3 rounded-full">
            <Activity className="w-10 h-10 text-primary" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-center text-white mb-2">Vespionage UEBA</h1>
        <p className="text-slate-400 text-center mb-8">Sign in to your account</p>
        
        {error && <div className="bg-red-500/10 border border-red-500/50 text-red-500 p-3 rounded-md mb-4 text-sm">{error}</div>}
        
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary transition-colors"
              placeholder="admin@demo.com"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary transition-colors"
              placeholder="password123"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary hover:bg-blue-600 text-white font-medium py-2 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-border">
          <p className="text-sm text-slate-400 mb-2">Demo Accounts:</p>
          <div className="text-xs text-slate-500 space-y-1">
            <p>Admin: admin@demo.com / password123</p>
            <p>Analyst: analyst@demo.com / password123</p>
          </div>
        </div>
      </div>
    </div>
  );
}
