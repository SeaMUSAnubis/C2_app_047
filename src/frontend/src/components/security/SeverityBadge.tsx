import type { Severity } from '../../types/security';
import { baselineLabels, postureLabels, resultLabels, severityLabels, statusLabels } from '../../lib/labels';

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`severity-badge severity-${severity}`}>{severityLabels[severity]}</span>;
}

type StatusTone = 'neutral' | 'success' | 'info' | 'warning' | 'danger';

function statusTone(value?: string | null): StatusTone {
  if (!value) return 'neutral';
  const normalized = value.toLowerCase();
  if (['resolved', 'active', 'hoạt động', 'cho phép', 'ổn định'].some((item) => normalized.includes(item))) return 'success';
  if (['investigating', 'đang điều tra', 'theo dõi', 'cần xác minh'].some((item) => normalized.includes(item))) return 'info';
  if (['new', 'open', 'mới', 'đang mở', 'lệch', 'rủi ro cao'].some((item) => normalized.includes(item))) return 'warning';
  if (['blocked', 'bị chặn', 'cô lập', 'locked', 'khóa', 'critical'].some((item) => normalized.includes(item))) return 'danger';
  return 'neutral';
}

function statusText(value?: string | null): string {
  if (!value) return 'Không xác định';
  return statusLabels[value] ?? postureLabels[value] ?? resultLabels[value] ?? baselineLabels[value] ?? value;
}

export function StatusBadge({ value, tone }: { value?: string | null; tone?: StatusTone }) {
  const resolvedTone = tone ?? statusTone(value);
  return <span className={`status-badge status-${resolvedTone}`}>{statusText(value)}</span>;
}
