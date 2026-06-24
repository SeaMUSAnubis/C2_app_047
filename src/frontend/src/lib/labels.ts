import type { Severity } from '../types/security';

export const roleLabels: Record<string, string> = {
  admin: 'Quản trị',
  security_manager: 'Quản lý bảo mật',
  analyst: 'Phân tích viên',
  employee: 'Nhân viên',
};

export const roleOptions: { value: string; label: string }[] = [
  { value: 'admin', label: 'Quản trị' },
  { value: 'security_manager', label: 'Quản lý bảo mật' },
  { value: 'analyst', label: 'Phân tích viên' },
  { value: 'employee', label: 'Nhân viên' },
];

export function roleLabel(value: string): string {
  return roleLabels[value] ?? value;
}

export const eventTypeLabels: Record<string, string> = {
  logon: 'Đăng nhập',
  logoff: 'Đăng xuất',
  device: 'Sử dụng thiết bị',
  http: 'Truy cập web',
  file: 'Truy cập tệp',
  email: 'Gửi email',
  process: 'Tiến trình',
  network: 'Kết nối mạng',
  ldap: 'LDAP',
  psychometric: 'Tâm lý học',
  custom: 'Tùy chỉnh',
};

export function eventTypeLabel(value: string): string {
  return eventTypeLabels[value?.toLowerCase()] ?? value;
}

export const severityLabels: Record<Severity, string> = {
  low: 'Thấp',
  medium: 'Trung bình',
  high: 'Cao',
  critical: 'Nghiêm trọng',
};

export const severityOptions: { value: Severity; label: string }[] = [
  { value: 'critical', label: 'Nghiêm trọng' },
  { value: 'high', label: 'Cao' },
  { value: 'medium', label: 'Trung bình' },
  { value: 'low', label: 'Thấp' },
];

export const statusLabels: Record<string, string> = {
  new: 'Mới',
  open: 'Đang mở',
  investigating: 'Đang điều tra',
  resolved: 'Đã xử lý',
  false_positive: 'Dương tính giả',
};

export const statusOptions: { value: string; label: string }[] = [
  { value: 'new', label: 'Mới' },
  { value: 'open', label: 'Đang mở' },
  { value: 'investigating', label: 'Đang điều tra' },
  { value: 'resolved', label: 'Đã xử lý' },
  { value: 'false_positive', label: 'Dương tính giả' },
];

export const riskLevelOptions: { value: string; label: string }[] = [
  { value: 'high', label: 'Cao' },
  { value: 'medium', label: 'Trung bình' },
  { value: 'low', label: 'Thấp' },
];

export const timeRangeOptions: { value: string; label: string }[] = [
  { value: '24h', label: '24 giờ gần nhất' },
  { value: '7d', label: '7 ngày gần nhất' },
  { value: '30d', label: '30 ngày gần nhất' },
];

export const postureLabels: Record<string, string> = {
  'Cần cô lập': 'Cần cô lập',
  'Đang điều tra': 'Đang điều tra',
  'Rủi ro cao': 'Rủi ro cao',
  'Cần xác minh': 'Cần xác minh',
  'Theo dõi': 'Theo dõi',
  active: 'Hoạt động',
  inactive: 'Không hoạt động',
  unknown: 'Không rõ',
};

export const resultLabels: Record<string, string> = {
  'Cho phép': 'Cho phép',
  'Cảnh báo': 'Cảnh báo',
  'Cần xác minh': 'Cần xác minh',
  'Bị chặn': 'Bị chặn',
};

export const baselineLabels: Record<string, string> = {
  'Lệch mạnh': 'Lệch mạnh',
  'Đang lệch': 'Đang lệch',
  'Cần xác minh': 'Cần xác minh',
  'Ổn định': 'Ổn định',
};

export function severityLabel(value: Severity): string {
  return severityLabels[value] ?? value;
}

export function statusLabel(value: string): string {
  return statusLabels[value] ?? value;
}

export function formatDateTime(value?: string | null): string {
  if (!value) return 'Chưa có';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function displayValue(value?: string | number | null, fallback = 'Chưa có'): string {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

export function shortText(value?: string | null, fallback = 'Chưa có'): string {
  return displayValue(value, fallback);
}

// ---- Shared utilities extracted from pages ----

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString('vi-VN');
  } catch {
    return value;
  }
}

export function timeSince(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    const d = new Date(value).getTime();
    if (Number.isNaN(d)) return value;
    const diff = Date.now() - d;
    if (diff < 0) return 'vừa xong';
    const s = Math.floor(diff / 1000);
    if (s < 60) return `${s}s trước`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m} phút trước`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h} giờ trước`;
    const days = Math.floor(h / 24);
    return `${days} ngày trước`;
  } catch {
    return value;
  }
}

export const AGENT_STATUS_TONE: Record<string, string> = {
  active: 'status-pill status-pill--ok',
  enrolled: 'status-pill status-pill--info',
  offline: 'status-pill status-pill--warn',
  revoked: 'status-pill status-pill--danger',
};

export const AGENT_STATUS_LABEL: Record<string, string> = {
  active: 'Đang hoạt động',
  enrolled: 'Đã đăng ký',
  offline: 'Mất kết nối',
  revoked: 'Đã thu hồi',
};

export function parseTimestamp(value: string | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function matchesTimeRange(
  value: string | undefined,
  allValues: (string | undefined)[],
  range: string,
): boolean {
  if (range === 'all') return true;
  const current = parseTimestamp(value);
  if (!current) return false;
  const maxTime = Math.max(...allValues.map((item) => parseTimestamp(item)?.getTime() ?? 0));
  if (!maxTime) return true;
  const hours = range === '24h' ? 24 : range === '7d' ? 24 * 7 : 24 * 30;
  return current.getTime() >= maxTime - hours * 60 * 60 * 1000;
}
