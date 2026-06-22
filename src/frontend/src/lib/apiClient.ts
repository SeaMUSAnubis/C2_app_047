import { clearAuthSession, getAccessToken } from './authStore';
import type { AlertItem, DashboardOverview, DeviceEntity, EventLogItem, UserEntity } from '../types/security';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

type ApiPayload = Record<string, unknown>;

function handleAuthFailure(response: Response) {
  if (response.status === 401 || response.status === 403) {
    clearAuthSession();
    window.location.assign('/login');
    return true;
  }
  return false;
}

async function request<T>(path: string): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error('Thiếu cấu hình API base URL');
  }

  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    if (handleAuthFailure(response)) {
      throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    }
    throw new Error(`Lỗi API ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function requestWithTotal<T>(path: string): Promise<{ rows: T; total: number }> {
  if (!API_BASE_URL) {
    throw new Error('Thiếu cấu hình API base URL');
  }

  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    if (handleAuthFailure(response)) {
      throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    }
    throw new Error(`Lỗi API ${response.status}`);
  }

  const rows = await response.json() as T;
  const total = Number(response.headers.get('X-Total-Count') ?? 0);
  return { rows, total };
}

export interface PagedParams {
  limit?: number;
  offset?: number;
}

function buildQuery(params: PagedParams): string {
  const parts: string[] = [];
  if (params.limit != null) parts.push(`limit=${params.limit}`);
  if (params.offset != null) parts.push(`offset=${params.offset}`);
  return parts.length ? `?${parts.join('&')}` : '';
}

export async function login(email: string, password: string) {
  if (!API_BASE_URL) {
    throw new Error('Thiếu cấu hình API base URL');
  }

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error('Đăng nhập thất bại');
  }

  return response.json();
}

export async function getDashboardSummary() {
  return await request('/dashboard/summary');
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  return await request<DashboardOverview>('/dashboard/overview');
}

export async function getUsers(params?: PagedParams): Promise<{ rows: UserEntity[]; total: number }> {
  return await requestWithTotal<UserEntity[]>(`/users${buildQuery(params ?? { limit: 50 })}`);
}

export async function getDevices(params?: PagedParams): Promise<{ rows: DeviceEntity[]; total: number }> {
  return await requestWithTotal<DeviceEntity[]>(`/devices${buildQuery(params ?? { limit: 50 })}`);
}

export async function getLogs(params?: PagedParams): Promise<{ rows: EventLogItem[]; total: number }> {
  return await requestWithTotal<EventLogItem[]>(`/logs${buildQuery(params ?? { limit: 50 })}`);
}

export async function analyzeDemo(payload: ApiPayload) {
  if (!API_BASE_URL) {
    throw new Error('Thiếu API base URL để chạy phân tích demo');
  }

  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/demo/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Phân tích demo thất bại: ${errorText}`);
  }

  return response.json();
}

export async function analyzeAllDemo() {
  if (!API_BASE_URL) {
    throw new Error('Thiếu API base URL để chạy phân tích demo');
  }

  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/demo/analyze-all`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Phân tích toàn bộ thất bại: ${errorText}`);
  }

  return response.json();
}

export async function getAlerts(params?: PagedParams): Promise<{ rows: AlertItem[]; total: number }> {
  try {
    return await requestWithTotal<AlertItem[]>(`/alerts${buildQuery(params ?? { limit: 50 })}`);
  } catch {
    return { rows: [], total: 0 };
  }
}

export async function updateAlertStatus(alertId: number, status: string) {
  if (!API_BASE_URL) {
    throw new Error('Thiếu cấu hình API base URL. Hãy kiểm tra VITE_API_BASE_URL trong file .env.');
  }

  const token = getAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/status`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ status }),
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) {
      throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    }
    const errorText = await response.text();
    throw new Error(`Cập nhật trạng thái thất bại: ${errorText}`);
  }
  return response.json();
}

export interface AccountRow {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export async function listAccounts(): Promise<AccountRow[]> {
  return await request<AccountRow[]>('/admin/accounts');
}

export async function createAccount(payload: { email: string; full_name: string; role: string; password: string }): Promise<AccountRow> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/admin/accounts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    const errorText = await response.text();
    throw new Error(`Tạo tài khoản thất bại: ${errorText}`);
  }
  return response.json();
}

export async function updateAccount(accountId: number, payload: Partial<{ full_name: string; role: string; is_active: boolean; password: string }>): Promise<AccountRow> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/admin/accounts/${accountId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    const errorText = await response.text();
    throw new Error(`Cập nhật tài khoản thất bại: ${errorText}`);
  }
  return response.json();
}

export interface EmployeeOverview {
  user: {
    id: string;
    account: string;
    name: string;
    department?: string;
    role?: string;
    status: string;
    riskScore?: number;
    devices?: number;
    anomalies?: number;
    lastSeen?: string;
    baseline?: string;
    loginHours?: string;
    commonDevices?: string;
    explanation?: string;
  };
  kpis: { label: string; value: string; delta: string; tone: string }[];
  alerts: { id: string; title: string; severity: string; status: string; riskScore: number; device: string; time: string; timestamp?: string }[];
  devices: { id: string; hostname: string; os?: string; ip?: string; status: string; riskScore?: number; lastSeen?: string; posture?: string; suspiciousEvents?: number }[];
  logs: { id: string; timestamp: string; eventType: string; device?: string; sourceIp?: string; resource?: string; result?: string; riskScore?: number; severity?: string }[];
}

export async function getEmployeeOverview(): Promise<EmployeeOverview> {
  return await request<EmployeeOverview>('/me/overview');
}

export async function importDemoData() {
  if (!API_BASE_URL) {
    throw new Error('Thiếu cấu hình API base URL. Hãy kiểm tra VITE_API_BASE_URL trong file .env.');
  }

  const token = getAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/datasets/cert-r42/import`, {
    method: 'POST',
    headers,
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) {
      throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    }
    const errorText = await response.text();
    throw new Error(`Nạp dữ liệu thất bại: ${errorText}`);
  }
  return response.json();
}
