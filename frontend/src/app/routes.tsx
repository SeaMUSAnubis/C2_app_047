import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { LoginPage } from '../pages/LoginPage';
import { DashboardPage } from '../pages/DashboardPage';
import { UsersPage } from '../pages/UsersPage';
import { DevicesPage } from '../pages/DevicesPage';
import { LogsPage } from '../pages/LogsPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';
import { DemoPage } from '../pages/DemoPage';
import { APP_ROUTES } from '../lib/constants';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to={APP_ROUTES.dashboard} replace />} />
      <Route path={APP_ROUTES.login} element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path={APP_ROUTES.dashboard} element={<DashboardPage />} />
          <Route path={APP_ROUTES.users} element={<UsersPage />} />
          <Route path={APP_ROUTES.devices} element={<DevicesPage />} />
          <Route path={APP_ROUTES.logs} element={<LogsPage />} />
          <Route path={APP_ROUTES.demo} element={<DemoPage />} />
          <Route path={APP_ROUTES.alerts} element={<PlaceholderPage title="Alerts" />} />
          <Route path={APP_ROUTES.dataImport} element={<PlaceholderPage title="Data Import" />} />
          <Route path={APP_ROUTES.models} element={<PlaceholderPage title="ML Models" />} />
          <Route path={APP_ROUTES.settings} element={<PlaceholderPage title="Settings" />} />
        </Route>
      </Route>
      
      {/* Catch all */}
      <Route path="*" element={<Navigate to={APP_ROUTES.dashboard} replace />} />
    </Routes>
  );
}
