import type {
  AuthUser,
  DashboardSummary,
  AppUser,
  Device,
  EventLog,
  Alert,
  BlockedWebsite,
  AlertExplanation,
  TimelineEvent
} from '../types';

export const mockAdmin: AuthUser = {
  id: 'acc_admin',
  email: 'admin@demo.com',
  name: 'Demo Admin',
  role: 'admin',
};

export const mockAnalyst: AuthUser = {
  id: 'acc_analyst',
  email: 'analyst@demo.com',
  name: 'Demo Analyst',
  role: 'analyst',
};

export const mockDashboardSummary: DashboardSummary = {
  total_users: 120,
  total_devices: 86,
  total_logs: 245000,
  active_alerts: 14,
  high_risk_users: 6,
  critical_alerts: 2,
  blocked_websites: 5,
};

export const mockUsers: AppUser[] = [
  { id: 'U001', name: 'Nguyen Van A', email: 'a.nguyen@demo.com', department: 'IT', role: 'Developer', status: 'active', risk_score: 87, last_seen: '2026-06-19T09:30:00Z' },
  { id: 'U002', name: 'Tran Thi B', email: 'b.tran@demo.com', department: 'HR', role: 'Manager', status: 'active', risk_score: 12, last_seen: '2026-06-19T08:15:00Z' },
  { id: 'U003', name: 'Le Van C', email: 'c.le@demo.com', department: 'Finance', role: 'Accountant', status: 'active', risk_score: 45, last_seen: '2026-06-18T17:00:00Z' },
  { id: 'U004', name: 'Pham N', email: 'n.pham@demo.com', department: 'IT', role: 'Sysadmin', status: 'inactive', risk_score: 95, last_seen: '2026-06-15T12:00:00Z' },
];

export const mockDevices: Device[] = [
  { id: 'D001', hostname: 'DESKTOP-IT-01', assigned_user_id: 'U001', assigned_user_name: 'Nguyen Van A', status: 'active', risk_score: 87, last_seen: '2026-06-19T09:30:00Z' },
  { id: 'D002', hostname: 'LAPTOP-HR-02', assigned_user_id: 'U002', assigned_user_name: 'Tran Thi B', status: 'active', risk_score: 10, last_seen: '2026-06-19T08:15:00Z' },
];

export const mockAlerts: Alert[] = [
  {
    id: 'ALERT-1021',
    user_id: 'U001',
    user_name: 'Nguyen Van A',
    device_id: 'D001',
    risk_score: 87,
    severity: 'high',
    status: 'new',
    main_reason: 'Unusual HTTP access outside baseline hours',
    created_at: '2026-06-19T09:30:00Z',
    model_version: 'iforest-v1',
    top_anomalous_features: ['after_hours_http_count', 'unique_external_domains'],
    suspicious_urls: [
      { url: 'https://suspicious-site.com/login', domain: 'suspicious-site.com', reason: 'Observed during high-risk anomaly window', risk_score: 91 }
    ]
  },
  {
    id: 'ALERT-1022',
    user_id: 'U004',
    user_name: 'Pham N',
    device_id: 'D005',
    risk_score: 95,
    severity: 'critical',
    status: 'investigating',
    main_reason: 'Multiple failed logins followed by large data transfer',
    created_at: '2026-06-18T22:10:00Z',
    top_anomalous_features: ['failed_logon_count', 'bytes_out'],
  }
];

export const mockAlertExplanation: AlertExplanation = {
  alert_id: 'ALERT-1021',
  summary: 'The user showed abnormal external web access outside normal working hours.',
  why_suspicious: [
    'The activity happened outside the user\'s historical baseline.',
    'The user accessed multiple external domains in a short time window.'
  ],
  evidence: [
    'Risk score is 87/100.',
    'Top anomalous feature: after_hours_http_count.'
  ],
  baseline_comparison: 'The user normally has low HTTP activity after working hours.',
  recommended_action: [
    'Review the timeline.',
    'Check whether the domain is business-related.',
    'Escalate or block the domain if confirmed suspicious.'
  ],
  generated_by: 'rule_based'
};

export const mockTimeline: TimelineEvent[] = [
  { id: 'E1', timestamp: '2026-06-19T09:00:00Z', event_type: 'logon', user_id: 'U001', device_id: 'D001', description: 'Successful logon to DESKTOP-IT-01', risk_marker: false },
  { id: 'E2', timestamp: '2026-06-19T09:15:00Z', event_type: 'http', user_id: 'U001', device_id: 'D001', description: 'Access to https://suspicious-site.com/login', risk_marker: true },
];

export const mockBlockedWebsites: BlockedWebsite[] = [
  {
    id: 'BW-001',
    url: 'https://suspicious-site.com/login',
    domain: 'suspicious-site.com',
    reason: 'Detected in high-risk HTTP anomaly alert',
    severity: 'high',
    source_alert_id: 'ALERT-1021',
    status: 'active',
    created_by: 'admin@demo.com',
    created_at: '2026-06-19T10:00:00Z'
  }
];

export const mockLogs: EventLog[] = [
  { id: 'L1', timestamp: '2026-06-19T09:00:00Z', event_type: 'logon', user_id: 'U001', device_id: 'D001', description: 'Successful logon', risk_marker: false },
  { id: 'L2', timestamp: '2026-06-19T09:15:00Z', event_type: 'http', user_id: 'U001', device_id: 'D001', description: 'Access suspicious-site.com', risk_marker: true },
];
