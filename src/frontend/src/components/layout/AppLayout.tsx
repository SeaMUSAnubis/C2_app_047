import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../store/authStore';
import { Activity, LayoutDashboard, ShieldAlert, Users, Monitor, FileText, ShieldBan, LogOut } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';

function Sidebar() {
  const { user } = useAuth();
  const location = useLocation();

  const links = [
    { name: 'Dashboard', path: '/dashboard', icon: <LayoutDashboard size={20} /> },
    { name: 'Alerts', path: '/alerts', icon: <ShieldAlert size={20} /> },
    { name: 'Users', path: '/users', icon: <Users size={20} /> },
    { name: 'Devices', path: '/devices', icon: <Monitor size={20} /> },
    { name: 'Logs', path: '/logs', icon: <FileText size={20} /> },
  ];

  if (user?.role === 'admin') {
    links.push({ name: 'Blocked Websites', path: '/admin/blocked-websites', icon: <ShieldBan size={20} /> });
  }

  return (
    <div className="w-64 bg-surface border-r border-border h-full flex flex-col">
      <div className="p-4 border-b border-border flex items-center gap-2">
        <Activity className="text-primary" />
        <span className="font-bold text-lg text-white">Vespionage</span>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        {links.map((link) => {
          const active = location.pathname.startsWith(link.path);
          return (
            <Link
              key={link.path}
              to={link.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${active ? 'bg-primary/10 text-primary' : 'text-slate-400 hover:bg-slate-800 hover:text-white'}`}
            >
              {link.icon}
              {link.name}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function Header() {
  const { user, logout } = useAuth();
  return (
    <header className="h-16 border-b border-border bg-surface flex items-center justify-between px-6">
      <div className="font-semibold">UEBA Endpoint Monitoring</div>
      <div className="flex items-center gap-4">
        <div className="text-right">
          <div className="text-sm font-medium text-white">{user?.name}</div>
          <div className="text-xs text-slate-400 capitalize">{user?.role}</div>
        </div>
        <button onClick={logout} className="p-2 text-slate-400 hover:text-white rounded-full hover:bg-slate-800 transition-colors">
          <LogOut size={20} />
        </button>
      </div>
    </header>
  );
}

export default function AppLayout() {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
