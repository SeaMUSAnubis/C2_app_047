export const APP_ROUTES = {
  login: '/login',
  dashboard: '/dashboard',
  alerts: '/alerts',
  users: '/users',
  devices: '/devices',
  logs: '/logs',
  dataImport: '/data-import',
  models: '/models',
  settings: '/settings',
} as const;

export const SIDEBAR_ITEMS = [
  { label: 'Overview', path: APP_ROUTES.dashboard },
  { label: 'Alerts', path: APP_ROUTES.alerts },
  { label: 'Users', path: APP_ROUTES.users },
  { label: 'Devices', path: APP_ROUTES.devices },
  { label: 'Logs', path: APP_ROUTES.logs },
  { label: 'Data Import', path: APP_ROUTES.dataImport },
  { label: 'ML Models', path: APP_ROUTES.models },
  { label: 'Settings', path: APP_ROUTES.settings },
];
