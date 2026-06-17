import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../../lib/apiClient';
import { saveAuthSession } from '../../lib/authStore';
import { APP_ROUTES } from '../../lib/constants';

export function LoginForm() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const session = await login(email, password);
      saveAuthSession(session);
      navigate(APP_ROUTES.dashboard);
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="login-form" onSubmit={handleSubmit}>
      <h2>Sign in to Vespionage</h2>
      {error && <div className="error-message">{error}</div>}
      <div className="form-group">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          placeholder="admin@demo.com"
        />
      </div>
      <div className="form-group">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>
      <button type="submit" disabled={loading} className="login-btn">
        {loading ? 'Signing in...' : 'Sign in'}
      </button>
      <div className="login-hints">
        <p>Demo accounts:</p>
        <ul>
          <li>admin@demo.com</li>
          <li>analyst@demo.com</li>
        </ul>
      </div>
      <p className="privacy-note">Dashboard only uses metadata/logs for security purposes.</p>
    </form>
  );
}
