import { Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { Activity, Bell, BrainCircuit, Cpu, FileSearch, Gauge, LogOut, Monitor, Search, ShieldAlert, ShieldBan, UserCog, Users, Brain } from 'lucide-react';
import { useAuth } from '../../store/useAuth';
import { roleLabel } from '../../lib/labels';

const mainNavItems = [
  { label: 'Tổng quan', path: '/dashboard', icon: Gauge },
  { label: 'Cảnh báo', path: '/alerts', icon: ShieldAlert },
  { label: 'Người dùng', path: '/users', icon: Users },
  { label: 'Thiết bị', path: '/devices', icon: Monitor },
  { label: 'Nhật ký', path: '/logs', icon: FileSearch },
  { label: 'Kiểm thử ML', path: '/model-test', icon: BrainCircuit },
];

const employeeNavItems = [
  { label: 'Tổng quan của tôi', path: '/my-risk', icon: Gauge },
  { label: 'Kiểm thử ML', path: '/model-test', icon: BrainCircuit },
];

const adminNavItems = [
  { label: 'Endpoint agents', path: '/admin/agents', icon: Cpu },
  { label: 'Blocklist', path: '/admin/blocklist', icon: ShieldBan },
  { label: 'Website bị chặn', path: '/admin/blocked-websites', icon: ShieldBan },
  { label: 'LLM Memory', path: '/admin/llm-memory', icon: Brain },
  { label: 'Tài khoản hệ thống', path: '/admin/accounts', icon: UserCog },
];

const securityManagerNavItems = [
  { label: 'Endpoint agents', path: '/admin/agents', icon: Cpu },
  { label: 'Blocklist', path: '/admin/blocklist', icon: ShieldBan },
  { label: 'Website bị chặn', path: '/admin/blocked-websites', icon: ShieldBan },
];

function Sidebar() {
  const location = useLocation();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const isSecurityManager = user?.role === 'security_manager';
  const isEmployee = user?.role === 'employee';

  const navItems = isEmployee ? employeeNavItems : mainNavItems;
  const adminItems = isAdmin ? adminNavItems : isSecurityManager ? securityManagerNavItems : [];

  return (
    <aside className="soc-sidebar">
      <div className="brand-block">
        <div className="brand-mark"><Activity size={22} /></div>
        <div>
          <strong>Vespionage</strong>
          <span>UEBA Console</span>
        </div>
      </div>

      <nav className="soc-nav" aria-label="Điều hướng chính">
        {navItems.map(({ label, path, icon: Icon }) => {
          const active = location.pathname === path || location.pathname.startsWith(`${path}/`);
          return (
            <NavLink key={path} to={path} className={active ? 'soc-nav-link active' : 'soc-nav-link'}>
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          );
        })}
      </nav>

      {adminItems.length > 0 && (
        <nav className="soc-nav soc-nav-admin" aria-label="Quản trị">
          <span className="soc-nav-section">Quản trị</span>
          {adminItems.map(({ label, path, icon: Icon }) => {
            const active = location.pathname === path || location.pathname.startsWith(`${path}/`);
            return (
              <NavLink key={path} to={path} className={active ? 'soc-nav-link active' : 'soc-nav-link'}>
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            );
          })}
        </nav>
      )}

      <div className="sidebar-status">
        <span>Mô hình phát hiện</span>
        <strong>ocsvm-cert-r42</strong>
        <span className="sidebar-session">{user?.email ?? ''}</span>
      </div>
    </aside>
  );
}

function Topbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    const term = query.trim();
    if (term) {
      navigate(`/logs?q=${encodeURIComponent(term)}`);
    }
  }

  return (
    <header className="soc-topbar">
      <form className="global-search" onSubmit={submitSearch}>
        <Search size={17} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm người dùng, thiết bị, IP, cảnh báo..." />
      </form>
      <div className="topbar-actions">
        <span className="env-badge">Môi trường demo</span>
        <button className="icon-button" aria-label="Thông báo" onClick={() => navigate('/alerts')}><Bell size={18} /></button>
        <div className="profile-chip">
          <span>{user?.name ?? 'Quản trị viên'}</span>
          <small>{user?.role ? roleLabel(user.role) : ''}</small>
        </div>
        <button className="logout-icon" onClick={logout} aria-label="Đăng xuất"><LogOut size={18} /></button>
      </div>
    </header>
  );
}

export default function AppLayout() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="soc-shell">
      <Sidebar />
      <div className="soc-main">
        <Topbar />
        <main className="soc-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
