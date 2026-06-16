import { useNavigate } from 'react-router-dom';
import { clearAuthSession, getAuthUser } from '../../lib/authStore';
import { APP_ROUTES } from '../../lib/constants';

export function Topbar() {
  const navigate = useNavigate();
  const user = getAuthUser();

  function handleLogout() {
    clearAuthSession();
    navigate(APP_ROUTES.login);
  }

  return (
    <header className="topbar">
      <input className="topbar-search" placeholder="Search user, device, log..." />

      <div className="topbar-right">
        <span className="api-status">Using mock/API data</span>
        <span className="role-badge">{user?.role ?? 'unknown'}</span>
        <button onClick={handleLogout} className="logout-btn">Logout</button>
      </div>
    </header>
  );
}
