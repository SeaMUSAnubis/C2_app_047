import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, LockKeyhole } from 'lucide-react';
import { login as loginRequest } from '../lib/apiClient';
import { useAuth } from '../store/useAuth';

export default function LoginPage() {
  const [email, setEmail] = useState('admin@demo.com');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleLogin(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const session = await loginRequest(email, password);
      login(session.user, session.accessToken);
      navigate(session.user.role === 'employee' ? '/my-risk' : '/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể đăng nhập. Vui lòng kiểm tra tài khoản.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-hero">
        <div className="brand-block large">
          <div className="brand-mark"><Activity size={24} /></div>
          <div><strong>Vespionage</strong><span>UEBA Console</span></div>
        </div>
        <h1>Phát hiện mối đe dọa nội bộ bằng UEBA &amp; Machine Learning</h1>
        <p>Giám sát hành vi người dùng và thiết bị, phát hiện lệch hồ sơ chuẩn và cảnh báo bất thường theo thời gian thực.</p>
        <div className="login-signal"><span>OCSVM</span><span>Phát hiện bất thường</span><span>Sẵn sàng tích hợp SIEM</span></div>
      </section>

      <form className="login-card" onSubmit={handleLogin}>
        <div className="detail-icon"><LockKeyhole size={24} /></div>
        <h2>Đăng nhập hệ thống</h2>
        <p>Đăng nhập để truy cập bảng điều khiển demo.</p>
        {error && <div className="form-error">{error}</div>}
        <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        <label>Mật khẩu<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
        <button className="primary-action full" type="submit" disabled={loading}>{loading ? 'Đang đăng nhập...' : 'Đăng nhập'}</button>
        <div className="demo-accounts">
          <strong>Tài khoản demo</strong>
          <span>Quản trị: admin@demo.com / admin123</span>
          <span>Quản lý bảo mật: security@demo.com / security123</span>
          <span>Phân tích viên: analyst@demo.com / analyst123</span>
          <span>Nhân viên: employee@demo.com / employee123</span>
        </div>
      </form>
    </main>
  );
}
