import type { User } from '../types/user';
import type { Device } from '../types/device';
import type { EventLog } from '../types/log';
import type { DashboardSummary } from '../types/dashboard';

export const mockDashboardSummary: DashboardSummary = {
  totalUsers: 128,
  totalDevices: 96,
  totalLogs: 54210,
  openAlerts: 14,
  highCriticalAlerts: 5,
  averageRiskScore: 42,
  currentModelVersion: 'iForest-v0.1-demo',
  lastImportTime: '2026-06-13T09:30:00+07:00',
};

export const mockUsers: User[] = [
  {
    id: 'U001',
    account: 'user_001',
    name: 'Nguyen Van A',
    department: 'Finance',
    role: 'Employee',
    status: 'active',
    riskScore: 72,
    assignedDevices: 1,
    openAlerts: 2,
    lastSeen: '2026-06-13T16:20:00+07:00',
  },
  {
    id: 'U002',
    account: 'user_002',
    name: 'Tran Thi B',
    department: 'HR',
    role: 'Manager',
    status: 'inactive',
    riskScore: 12,
    assignedDevices: 2,
    openAlerts: 0,
    lastSeen: '2026-06-10T09:15:00+07:00',
  },
];

export const mockDevices: Device[] = [
  {
    id: 'D001',
    hostname: 'PC-FIN-001',
    assignedUser: 'user_001',
    department: 'Finance',
    status: 'active',
    riskScore: 61,
    openAlerts: 1,
    lastSeen: '2026-06-13T16:18:00+07:00',
  },
  {
    id: 'D002',
    hostname: 'LT-HR-002',
    assignedUser: 'user_002',
    department: 'HR',
    status: 'inactive',
    riskScore: 5,
    openAlerts: 0,
    lastSeen: '2026-06-10T09:10:00+07:00',
  },
];

export const mockLogs: EventLog[] = [
  {
    id: 'L001',
    timestamp: '2026-06-13T16:10:00+07:00',
    eventType: 'logon',
    userId: 'U001',
    deviceId: 'D001',
    action: 'LOGIN_SUCCESS',
    sourceFile: 'logon.csv',
    sourceId: 'row-1001',
    rawDetail: 'Successful logon from PC-FIN-001',
  },
  {
    id: 'L002',
    timestamp: '2026-06-13T16:12:00+07:00',
    eventType: 'file',
    userId: 'U001',
    deviceId: 'D001',
    action: 'FILE_ACCESSED',
    sourceFile: 'file_server.log',
    sourceId: 'row-205',
    rawDetail: 'Accessed sensitive finance document',
  },
];
