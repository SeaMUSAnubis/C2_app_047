export interface DashboardSummary {
  totalUsers: number;
  totalDevices: number;
  totalLogs: number;
  openAlerts: number;
  highCriticalAlerts: number;
  averageRiskScore: number;
  currentModelVersion?: string;
  lastImportTime?: string;
}
