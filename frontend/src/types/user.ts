export interface User {
  id: string;
  account: string;
  name?: string;
  department?: string;
  role?: string;
  status: 'active' | 'inactive' | 'locked';
  riskScore?: number;
  assignedDevices?: number;
  openAlerts?: number;
  lastSeen?: string;
}
