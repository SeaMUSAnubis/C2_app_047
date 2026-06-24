import { clearAuthSession, getAccessToken } from './authStore';
import type {
  AgentConfigResponse,
  AgentEntity,
  AgentEnrollmentToken,
  AgentPolicyRead,
  BlocklistEntry,
  BlocklistPatternType,
} from '../types';
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

async function safeParseJSON<T>(response: Response, path: string): Promise<T> {
  const text = await response.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    // Nếu response không phải JSON (VD: HTML error page từ proxy/backend)
    const preview = text.slice(0, 200).replace(/\n/g, ' ');
    throw new Error(`API trả về dữ liệu không hợp lệ cho ${path}: "${preview}..."`);
  }
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
    throw new Error(`Lỗi API ${response.status} (${path})`);
  }

  return safeParseJSON<T>(response, path);
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
    throw new Error(`Lỗi API ${response.status} (${path})`);
  }

  const text = await response.text();
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    const preview = text.slice(0, 200).replace(/\n/g, ' ');
    throw new Error(`API trả về dữ liệu không hợp lệ cho ${path}: "${preview}..."`);
  }
  const total = Number(response.headers.get('X-Total-Count') ?? 0);
  const rows: T = Array.isArray(parsed) ? (parsed as T) : (parsed as { items: T }).items;
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

export async function analyzeAllDemo(timeRange?: string) {
  if (!API_BASE_URL) {
    throw new Error('Thiếu API base URL để chạy phân tích demo');
  }

  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/demo/analyze-all`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ time_range: timeRange ?? '24h' }),
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
  alerts: { id: string; numericId?: number; title: string; severity: string; status: string; riskScore: number; device: string; time: string; timestamp?: string }[];
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

// ---------------------------------------------------------------------------
// Phase 4: agent + blocklist CRUD
// ---------------------------------------------------------------------------

function agentHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getAccessToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function handleAgentAuthFailure(response: Response): boolean {
  if (response.status === 401 || response.status === 403) {
    clearAuthSession();
    window.location.assign('/login');
    return true;
  }
  return false;
}

async function readErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const txt = await response.text();
    try {
      const obj = JSON.parse(txt) as { detail?: string };
      if (obj.detail) return obj.detail;
    } catch {
      // not JSON
    }
    return txt || fallback;
  } catch {
    return fallback;
  }
}

export async function listAgents(params?: PagedParams): Promise<{ rows: AgentEntity[]; total: number }> {
  try {
    return await requestWithTotal<AgentEntity[]>(`/agents${buildQuery(params ?? { limit: 50 })}`);
  } catch (err) {
    throw new Error(err instanceof Error ? err.message : 'Không thể tải danh sách agent', { cause: err });
  }
}

export async function getAgent(agentId: string): Promise<AgentEntity> {
  return await request<AgentEntity>(`/agents/${encodeURIComponent(agentId)}`);
}

export async function patchAgent(agentId: string, payload: Partial<{
  status: 'active' | 'offline' | 'revoked';
  policy_version: number;
  device_id: string | null;
  assigned_user_id: string | null;
}>): Promise<AgentEntity> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const response = await fetch(`${API_BASE_URL}/agents/${encodeURIComponent(agentId)}`, {
    method: 'PATCH',
    headers: agentHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (handleAgentAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(await readErrorMessage(response, 'Cập nhật agent thất bại'));
  }
  return response.json() as Promise<AgentEntity>;
}

export async function revokeAgent(agentId: string): Promise<AgentEntity> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const response = await fetch(`${API_BASE_URL}/agents/${encodeURIComponent(agentId)}`, {
    method: 'DELETE',
    headers: agentHeaders(),
  });
  if (!response.ok) {
    if (handleAgentAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(await readErrorMessage(response, 'Thu hồi agent thất bại'));
  }
  return response.json() as Promise<AgentEntity>;
}

export async function markStaleAgents(timeoutMinutes?: number): Promise<{ flipped_to_offline: number }> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const params = timeoutMinutes != null ? `?timeout_minutes=${timeoutMinutes}` : '';
  const response = await fetch(`${API_BASE_URL}/admin/agents/mark-stale${params}`, {
    method: 'POST',
    headers: agentHeaders(),
  });
  if (!response.ok) {
    if (handleAgentAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(await readErrorMessage(response, 'Đánh dấu agent quá hạn thất bại'));
  }
  return response.json();
}

export async function createEnrollmentToken(expiresMinutes = 60): Promise<AgentEnrollmentToken> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const response = await fetch(`${API_BASE_URL}/agents/enrollment-tokens`, {
    method: 'POST',
    headers: agentHeaders(),
    body: JSON.stringify({ expires_minutes: expiresMinutes }),
  });
  if (!response.ok) {
    if (handleAgentAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(await readErrorMessage(response, 'Tạo enrollment token thất bại'));
  }
  return response.json() as Promise<AgentEnrollmentToken>;
}

export async function listBlocklist(enabledOnly = false): Promise<BlocklistEntry[]> {
  const q = enabledOnly ? '?enabled_only=true' : '';
  return await request<BlocklistEntry[]>(`/agents/blocklist${q}`);
}

export async function addBlocklistEntry(payload: {
  pattern: string;
  pattern_type?: BlocklistPatternType;
  category?: string;
  reason?: string;
  enabled?: boolean;
}): Promise<BlocklistEntry> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const response = await fetch(`${API_BASE_URL}/agents/blocklist`, {
    method: 'POST',
    headers: agentHeaders(),
    body: JSON.stringify({ pattern_type: 'domain', enabled: true, ...payload }),
  });
  if (!response.ok) {
    if (handleAgentAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(await readErrorMessage(response, 'Thêm mục blocklist thất bại'));
  }
  return response.json() as Promise<BlocklistEntry>;
}

export async function updateBlocklistEntry(
  entryId: number,
  payload: Partial<Pick<BlocklistEntry, 'pattern' | 'category' | 'reason' | 'enabled' | 'pattern_type'>>,
): Promise<BlocklistEntry> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const response = await fetch(`${API_BASE_URL}/agents/blocklist/${entryId}`, {
    method: 'PATCH',
    headers: agentHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (handleAgentAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(await readErrorMessage(response, 'Cập nhật mục blocklist thất bại'));
  }
  return response.json() as Promise<BlocklistEntry>;
}

export async function removeBlocklistEntry(entryId: number): Promise<{ id: number }> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const response = await fetch(`${API_BASE_URL}/agents/blocklist/${entryId}`, {
    method: 'DELETE',
    headers: agentHeaders(),
  });
  if (!response.ok) {
    if (handleAgentAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(await readErrorMessage(response, 'Xóa mục blocklist thất bại'));
  }
  return response.json();
}

export async function getAgentPolicy(): Promise<AgentPolicyRead> {
  return await request<AgentPolicyRead>('/agents/policy');
}

export async function updateAgentPolicy(payload: Partial<{
  sampling_rate: number;
  enabled_collectors: string[];
}>): Promise<AgentPolicyRead> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const response = await fetch(`${API_BASE_URL}/agents/policy`, {
    method: 'PATCH',
    headers: agentHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (handleAgentAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(await readErrorMessage(response, 'Cập nhật policy thất bại'));
  }
  return response.json() as Promise<AgentPolicyRead>;
}

export async function getAgentConfig(agentId: string): Promise<AgentConfigResponse> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  // This endpoint is typically called by the agent using X-API-Key, not the
  // admin UI. We still expose it for completeness (returns 200/4xx normally).
  const response = await fetch(`${API_BASE_URL}/agents/${encodeURIComponent(agentId)}/config`, {
    headers: agentHeaders(),
  });
  if (!response.ok) {
    if (handleAgentAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(await readErrorMessage(response, 'Lấy cấu hình agent thất bại'));
  }
  return response.json() as Promise<AgentConfigResponse>;
}


// ---------------------------------------------------------------------------
// LLM / chat / memory / feedback (Phase 4 of PLAN_LLM.md)
// ---------------------------------------------------------------------------

export type ChatRole = 'user' | 'assistant' | 'system';
export type FeedbackVerdict = 'true_positive' | 'false_positive' | 'benign' | 'needs_investigation';
export type MemoryScope = 'user' | 'device' | 'pattern' | 'global';
export type MemoryKind = 'fact' | 'preference' | 'analyst_pattern' | 'historical';

export interface ChatMessage {
  id: number;
  role: ChatRole;
  content: string;
  model: string | null;
  latency_ms: number | null;
  memory_used_ids: number[] | null;
  created_at: string;
}

export interface Conversation {
  id: number;
  alert_id: number;
  user_id: string;
  title: string;
  summary: string | null;
  messages: ChatMessage[];
  updated_at: string;
}

export interface ConversationSummary {
  id: number;
  alert_id: number;
  user_id: string;
  title: string;
  message_count: number;
  updated_at: string;
}

export interface FeedbackEntry {
  id: number;
  alert_id: number;
  analyst_id: string;
  verdict: FeedbackVerdict;
  note: string | null;
  created_at: string;
}

export interface MemoryEntry {
  id: number;
  scope: MemoryScope;
  scope_id: string | null;
  kind: MemoryKind;
  content: string;
  tags: string[];
  use_count: number;
  last_used_at: string | null;
  created_at: string;
}

export interface LLMStats {
  total_calls: number;
  total_streamed_calls: number;
  total_fallback: number;
  total_retries: number;
  total_input_tokens: number;
  total_output_tokens: number;
  avg_latency_ms: number;
  model: string;
  provider: string;
  enabled: boolean;
  recent: Array<{
    provider: string;
    model: string;
    latency_ms: number;
    status: string;
    fallback_reason: string | null;
    streamed: boolean;
  }>;
}

export interface PoolStats {
  initialised: boolean;
  min_size: number;
  max_size: number;
  acquire_timeout_seconds: number;
  statement_timeout_read_ms: number;
  statement_timeout_write_ms: number;
  statement_timeout_streaming_ms: number;
  idle_in_transaction_timeout_ms: number;
  pool_size: number;
  pool_available: number;
  pool_in_use: number;
  requests_waiting: number;
  requests_errors: number;
  requests_num: number;
  usage_ms: number;
}

export async function getConversation(alertId: number): Promise<Conversation> {
  return await request<Conversation>(`/alerts/${alertId}/conversation`);
}

export async function listConversations(alertId: number): Promise<ConversationSummary[]> {
  return await request<ConversationSummary[]>(`/alerts/${alertId}/conversations`);
}

export async function createConversation(alertId: number, title?: string): Promise<Conversation> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(`Tạo hội thoại thất bại: ${response.status}`);
  }
  return response.json();
}

export async function getConversationById(alertId: number, conversationId: number): Promise<Conversation> {
  return await request<Conversation>(`/alerts/${alertId}/conversations/${conversationId}`);
}

export async function resetConversation(alertId: number): Promise<{ reset: boolean }> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/conversation/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(`Reset conversation thất bại: ${response.status}`);
  }
  return response.json();
}

export async function updateConversationTitle(alertId: number, title: string, conversationId?: number): Promise<Conversation> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const token = getAccessToken();
  const path = conversationId
    ? `/alerts/${alertId}/conversations/${conversationId}`
    : `/alerts/${alertId}/conversation`;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(`Cập nhật hội thoại thất bại: ${response.status}`);
  }
  return response.json();
}

export async function deleteConversation(alertId: number, conversationId?: number): Promise<{ deleted: boolean; conversation_id: number }> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const token = getAccessToken();
  const path = conversationId
    ? `/alerts/${alertId}/conversations/${conversationId}`
    : `/alerts/${alertId}/conversation`;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(`Xóa hội thoại thất bại: ${response.status}`);
  }
  return response.json();
}

export async function submitFeedback(alertId: number, payload: { verdict: FeedbackVerdict; note?: string }): Promise<FeedbackEntry> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    const err = await response.text();
    throw new Error(`Gửi feedback thất bại: ${err}`);
  }
  return response.json();
}

export async function listFeedback(alertId: number): Promise<FeedbackEntry[]> {
  return await request<FeedbackEntry[]>(`/alerts/${alertId}/feedback`);
}

export async function listMemoriesAdmin(filters: { scope?: MemoryScope; kind?: MemoryKind; tag?: string; limit?: number } = {}): Promise<MemoryEntry[]> {
  const params = new URLSearchParams();
  if (filters.scope) params.set('scope', filters.scope);
  if (filters.kind) params.set('kind', filters.kind);
  if (filters.tag) params.set('tag', filters.tag);
  if (filters.limit) params.set('limit', String(filters.limit));
  const qs = params.toString();
  return await request<MemoryEntry[]>(`/admin/llm-memory${qs ? `?${qs}` : ''}`);
}

export async function forgetMemory(memoryId: number): Promise<{ forgotten: number }> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/admin/llm-memory/${memoryId}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!response.ok) {
    if (handleAuthFailure(response)) throw new Error('Phiên đăng nhập đã hết hạn.');
    throw new Error(`Forget memory thất bại: ${response.status}`);
  }
  return response.json();
}

export async function getLLMStats(): Promise<LLMStats> {
  return await request<LLMStats>('/admin/llm-stats');
}

export async function getPoolStats(): Promise<PoolStats> {
  return await request<PoolStats>('/admin/db-pool-stats');
}

export interface ChatStreamEvent {
  type: 'token' | 'done' | 'error' | 'memory_used';
  text?: string;
  message_id?: number;
  latency_ms?: number;
  model?: string;
  code?: string;
  message?: string;
  ids?: number[];
  count?: number;
}

export interface StreamChatHandlers {
  onEvent: (ev: ChatStreamEvent) => void;
  onError?: (err: Error) => void;
  onDone?: () => void;
  signal?: AbortSignal;
}

export async function streamChatMessage(
  alertId: number,
  content: string,
  conversationId: number | null,
  handlers: StreamChatHandlers,
): Promise<void> {
  if (!API_BASE_URL) throw new Error('Thiếu cấu hình API base URL');
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ content, stream: true, conversation_id: conversationId || undefined }),
    signal: handlers.signal,
  });
  if (!response.ok || !response.body) {
    if (handleAuthFailure(response)) {
      handlers.onError?.(new Error('Phiên đăng nhập đã hết hạn.'));
      return;
    }
    handlers.onError?.(new Error(`Lỗi ${response.status}`));
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  // SSE: events separated by \n\n, each line `data: <json>`.
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        if (!raw) continue;
        for (const line of raw.split('\n')) {
          if (!line.startsWith('data:')) continue;
          const payload = line.slice(5).trim();
          if (!payload || payload === '[DONE]') continue;
          try {
            const ev = JSON.parse(payload) as ChatStreamEvent;
            handlers.onEvent(ev);
            if (ev.type === 'done') {
              handlers.onDone?.();
              return;
            }
          } catch {
            // ignore malformed line
          }
        }
      }
    }
  } catch (err) {
    if ((err as Error).name === 'AbortError') {
      // user cancelled, normal
      return;
    }
    handlers.onError?.(err as Error);
  } finally {
    try { reader.releaseLock(); } catch { /* noop */ }
  }
}
