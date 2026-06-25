export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type AlertStatus = 'new' | 'open' | 'investigating' | 'resolved' | 'false_positive';

export interface KpiItem {
  label: string;
  value: string;
  delta: string;
  tone: string;
}

export interface RiskTrendPoint {
  label: string;
  value: number;
}

export interface SeverityVolumeItem {
  label: string;
  value: number;
  severity: Severity;
}

export interface RiskDistributionItem {
  label: string;
  value: number;
  color: string;
}

export interface AlertItem {
  id: string;
  numericId?: number;
  title: string;
  user: string;
  device: string;
  severity: Severity;
  status: AlertStatus;
  riskScore: number;
  time: string;
  timestamp?: string;
  explanation?: string;
  evidence?: string[];
  action?: string;
  mitre?: string;
}

export interface RiskyEntity {
  name: string;
  role: string;
  department: string;
  device: string;
  lastActivity: string;
  anomaly: string;
  riskScore: number;
}

export interface TimelineEvent {
  time: string;
  type: string;
  title: string;
  detail: string;
  severity: Severity;
}

export interface DashboardOverview {
  kpis: KpiItem[];
  riskTrend: RiskTrendPoint[];
  severityVolume: SeverityVolumeItem[];
  riskDistribution: RiskDistributionItem[];
  alerts: AlertItem[];
  riskyEntities: RiskyEntity[];
  timeline: TimelineEvent[];
}

export interface UserEntity {
  id: string;
  account: string;
  name: string;
  department?: string;
  role?: string;
  status: string;
  riskScore?: number;
  assignedDevices?: number;
  openAlerts?: number;
  lastSeen?: string;
  devices?: number;
  baseline?: string;
  anomalies?: number;
  loginHours?: string;
  commonDevices?: string;
  explanation?: string;
}

export interface DeviceEntity {
  id: string;
  hostname: string;
  owner?: string;
  assignedUser?: string;
  department?: string;
  os?: string;
  ip?: string;
  status: string;
  posture?: string;
  riskScore?: number;
  openAlerts?: number;
  suspiciousEvents?: number;
  lastSeen?: string;
}

export interface EventLogItem {
  id: string;
  timestamp: string;
  eventType: string;
  userId?: string;
  deviceId?: string;
  user?: string;
  device?: string;
  action: string;
  sourceFile?: string;
  sourceId?: string;
  sourceIp?: string;
  resource?: string;
  result?: string;
  riskScore?: number;
  severity?: Severity;
}
