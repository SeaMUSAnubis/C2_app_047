export type UserRole = "admin" | "analyst";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}

export type Severity = "low" | "medium" | "high" | "critical";

export type AlertStatus =
  | "new"
  | "investigating"
  | "resolved"
  | "false_positive";

export interface Alert {
  id: string;
  user_id: string;
  user_name?: string;
  device_id?: string;
  risk_score: number;
  severity: Severity;
  status: AlertStatus;
  main_reason: string;
  created_at: string;
  model_version?: string;
  top_anomalous_features?: string[];
  suspicious_urls?: SuspiciousUrl[];
}

export interface SuspiciousUrl {
  url: string;
  domain: string;
  reason?: string;
  risk_score?: number;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  event_type: "logon" | "device" | "file" | "http" | "email" | "ldap" | "psychometric";
  user_id?: string;
  device_id?: string;
  description: string;
  source_file?: string;
  risk_marker?: boolean;
}

export interface AlertExplanation {
  alert_id: string;
  summary: string;
  why_suspicious: string[];
  evidence: string[];
  baseline_comparison?: string;
  recommended_action: string[];
  generated_by: "llm" | "rule_based";
}

export interface DashboardSummary {
  total_users: number;
  total_devices: number;
  total_logs: number;
  active_alerts: number;
  high_risk_users: number;
  critical_alerts: number;
  blocked_websites: number;
}

export interface AppUser {
  id: string;
  name: string;
  email?: string;
  department?: string;
  role?: string;
  status: "active" | "inactive" | "disabled";
  risk_score: number;
  last_seen?: string;
}

export interface Device {
  id: string;
  hostname?: string;
  assigned_user_id?: string;
  assigned_user_name?: string;
  status: "active" | "inactive" | "unknown";
  risk_score: number;
  last_seen?: string;
}

export interface EventLog {
  id: string;
  timestamp: string;
  event_type: string;
  user_id?: string;
  device_id?: string;
  source_file?: string;
  description: string;
  risk_marker?: boolean;
}

export interface BlockedWebsite {
  id: string;
  url: string;
  domain: string;
  reason: string;
  severity: Severity;
  source_alert_id?: string;
  status: "active" | "inactive";
  created_by: string;
  created_at: string;
  updated_at?: string;
}
