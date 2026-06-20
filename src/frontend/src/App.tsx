import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './store/authStore';
import AppLayout from './components/layout/AppLayout';
import ProtectedRoute from './components/layout/ProtectedRoute';
import RoleGuard from './components/layout/RoleGuard';

// Pages
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AlertsPage from './pages/AlertsPage';
import AdminBlockedWebsitesPage from './pages/AdminBlockedWebsitesPage';

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          
          <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            {/* MVP Placeholders for others */}
            
            {/* Admin only routes */}
            <Route element={<RoleGuard allowedRoles={['admin']} />}>
              <Route path="/admin/blocked-websites" element={<AdminBlockedWebsitesPage />} />
            </Route>
          </Route>
          
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
