export interface Device {
  id: string;
  hostname: string;
  assignedUser?: string;
  department?: string;
  status: 'active' | 'inactive';
  riskScore?: number;
  openAlerts?: number;
  lastSeen?: string;
}
