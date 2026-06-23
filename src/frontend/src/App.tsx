import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './store/authStore';
import AppLayout from './components/layout/AppLayout';
import ProtectedRoute from './components/layout/ProtectedRoute';
import RoleGuard from './components/layout/RoleGuard';

import LoginPage from './pages/LoginPage';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const UsersPage = lazy(() => import('./pages/UsersPage').then((m) => ({ default: m.UsersPage })));
const DevicesPage = lazy(() => import('./pages/DevicesPage').then((m) => ({ default: m.DevicesPage })));
const LogsPage = lazy(() => import('./pages/LogsPage').then((m) => ({ default: m.LogsPage })));
const AdminBlockedWebsitesPage = lazy(() => import('./pages/AdminBlockedWebsitesPage'));
const AdminAccountsPage = lazy(() => import('./pages/AdminAccountsPage'));
const ModelTestPage = lazy(() => import('./pages/ModelTestPage'));
const MyRiskPage = lazy(() => import('./pages/MyRiskPage'));
const AgentsPage = lazy(() => import('./pages/AgentsPage'));
const AgentDetailPage = lazy(() => import('./pages/AgentDetailPage'));
const BlocklistPage = lazy(() => import('./pages/BlocklistPage'));
const MemoryAdminPage = lazy(() => import('./features/admin/MemoryAdminPage').then((m) => ({ default: m.MemoryAdminPage })));

function PageFallback() {
  return <div className="panel-card">Đang tải trang...</div>;
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Suspense fallback={<PageFallback />}><DashboardPage /></Suspense>} />
            <Route path="/alerts" element={<Suspense fallback={<PageFallback />}><AlertsPage /></Suspense>} />
            <Route path="/users" element={<Suspense fallback={<PageFallback />}><UsersPage /></Suspense>} />
            <Route path="/devices" element={<Suspense fallback={<PageFallback />}><DevicesPage /></Suspense>} />
            <Route path="/logs" element={<Suspense fallback={<PageFallback />}><LogsPage /></Suspense>} />
            <Route path="/model-test" element={<Suspense fallback={<PageFallback />}><ModelTestPage /></Suspense>} />
            <Route path="/my-risk" element={<Suspense fallback={<PageFallback />}><MyRiskPage /></Suspense>} />

            <Route element={<RoleGuard allowedRoles={['admin', 'security_manager']} />}>
              <Route path="/admin/blocked-websites" element={<Suspense fallback={<PageFallback />}><AdminBlockedWebsitesPage /></Suspense>} />
              <Route path="/admin/blocklist" element={<Suspense fallback={<PageFallback />}><BlocklistPage /></Suspense>} />
              <Route path="/admin/agents" element={<Suspense fallback={<PageFallback />}><AgentsPage /></Suspense>} />
              <Route path="/admin/agents/:agentId" element={<Suspense fallback={<PageFallback />}><AgentDetailPage /></Suspense>} />
            </Route>

            <Route element={<RoleGuard allowedRoles={['admin']} />}>
              <Route path="/admin/accounts" element={<Suspense fallback={<PageFallback />}><AdminAccountsPage /></Suspense>} />
              <Route path="/admin/llm-memory" element={<Suspense fallback={<PageFallback />}><MemoryAdminPage /></Suspense>} />
            </Route>
          </Route>

        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
