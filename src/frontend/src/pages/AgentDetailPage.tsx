import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, Cpu, RefreshCcw, ShieldOff } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { useAuth } from '../store/useAuth';
import {
  getAgent,
  getAgentConfig,
  getAlerts,
  revokeAgent,
} from '../lib/apiClient';
import type { AgentConfigResponse, AgentEntity } from '../types';
import type { AlertItem } from '../types/security';
import {
  AGENT_STATUS_LABEL,
  AGENT_STATUS_TONE,
  formatTimestamp,
} from '../lib/labels';

export default function AgentDetailPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const { user } = useAuth();
  const [agent, setAgent] = useState<AgentEntity | null>(null);
  const [config, setConfig] = useState<AgentConfigResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    if (!agentId) return;
    setLoading(true);
    setError('');
    try {
      const a = await getAgent(agentId);
      setAgent(a);
      try {
        const c = await getAgentConfig(agentId);
        setConfig(c);
      } catch {
        // /agents/{id}/config requires agent auth — expected to fail for admin.
        setConfig(null);
      }
      // If agent is bound to a user, surface their recent alerts as a "timeline".
      if (a.assigned_user_id) {
        const { rows } = await getAlerts({ limit: 50, offset: 0 });
        setAlerts(
          rows
            .filter(
              (al: AlertItem & { user_id?: string }) =>
                al.user_id === a.assigned_user_id || al.user === a.assigned_user_id,
            )
            .slice(0, 30),
        );
      } else {
        setAlerts([]);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể tải thông tin agent');
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleRevoke() {
    if (!agent) return;
    if (!window.confirm(`Thu hồi agent "${agent.hostname}"?`)) return;
    setBusy(true);
    try {
      await revokeAgent(agent.agent_id);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Thu hồi thất bại');
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="page-stack">
        <p>Đang tải thông tin agent...</p>
      </div>
    );
  }

  if (error && !agent) {
    return (
      <div className="page-stack">
        <div className="form-error">{error}</div>
        <Link to="/admin/agents" className="secondary-action">
          <ArrowLeft size={16} /> Quay lại danh sách
        </Link>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="page-stack">
        <p>Agent không tồn tại.</p>
        <Link to="/admin/agents" className="secondary-action">
          <ArrowLeft size={16} /> Quay lại
        </Link>
      </div>
    );
  }

  const isAdmin = user?.role === 'admin';

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={`Agent ${agent.agent_id}`}
        title={agent.hostname}
        description={`OS: ${agent.os ?? '—'}${agent.os_version ? ` ${agent.os_version}` : ''} · Đăng ký: ${formatTimestamp(agent.enrolled_at)}`}
        actions={
          <div className="action-row">
            <Link to="/admin/agents" className="secondary-action">
              <ArrowLeft size={16} /> Quay lại
            </Link>
            <button className="secondary-action" onClick={() => void loadAll()}>
              <RefreshCcw size={16} /> Làm mới
            </button>
            {isAdmin && agent.status !== 'revoked' && (
              <button
                className="primary-action primary-action--danger"
                onClick={() => void handleRevoke()}
                disabled={busy}
              >
                <ShieldOff size={16} /> Thu hồi
              </button>
            )}
          </div>
        }
      />

      {error && <div className="form-error">{error}</div>}

      <section className="info-grid">
        <div className="info-card">
          <Cpu size={18} />
          <div>
            <span className="info-label">Trạng thái</span>
            <span className={AGENT_STATUS_TONE[agent.status] ?? 'status-pill'}>
              {AGENT_STATUS_LABEL[agent.status] ?? agent.status}
            </span>
          </div>
        </div>
        <div className="info-card">
          <span className="info-label">Phiên bản chính sách</span>
          <strong className="mono">{agent.policy_version}</strong>
        </div>
        <div className="info-card">
          <span className="info-label">Heartbeat gần nhất</span>
          <strong>{formatTimestamp(agent.last_heartbeat)}</strong>
        </div>
        <div className="info-card">
          <span className="info-label">Lần cuối lấy cấu hình</span>
          <strong>{formatTimestamp(agent.last_config_pull)}</strong>
        </div>
        <div className="info-card">
          <span className="info-label">Thiết bị gán</span>
          <strong>{agent.device_id ?? '—'}</strong>
        </div>
        <div className="info-card">
          <span className="info-label">Người dùng gán</span>
          <strong>{agent.assigned_user_id ?? '—'}</strong>
        </div>
      </section>

      {config && (
        <section className="panel-card">
          <h3>Cấu hình hiện tại (agent đang dùng)</h3>
          <div className="info-grid">
            <div className="info-card">
              <span className="info-label">Tỷ lệ thu thập</span>
              <strong>{config.policy.sampling_rate}%</strong>
            </div>
            <div className="info-card">
              <span className="info-label">Phiên bản cấu hình</span>
              <strong className="mono">{config.config_version}</strong>
            </div>
          </div>
          <h4>Collector đang bật</h4>
          <div className="chip-row">
            {config.policy.enabled_collectors.map((c) => (
              <span key={c} className="chip">
                {c}
              </span>
            ))}
          </div>
          <h4>Blocklist đồng bộ ({config.blocklist.length} mục)</h4>
          {config.blocklist.length === 0 ? (
            <p className="text-muted">Blocklist rỗng.</p>
          ) : (
            <ul className="blocklist-preview">
              {config.blocklist.slice(0, 20).map((b) => (
                <li key={b.id}>
                  <code className="mono">{b.pattern}</code>
                  <span className="text-muted-small">({b.pattern_type})</span>
                </li>
              ))}
              {config.blocklist.length > 20 && (
                <li className="text-muted">… và {config.blocklist.length - 20} mục khác</li>
              )}
            </ul>
          )}
        </section>
      )}

      <section className="panel-card">
        <h3>Cảnh báo gần đây của người dùng được gán</h3>
        {alerts.length === 0 ? (
          <p className="text-muted">
            {agent.assigned_user_id
              ? 'Chưa có cảnh báo cho người dùng này.'
              : 'Agent chưa được gán cho người dùng cụ thể — không có cảnh báo liên kết.'}
          </p>
        ) : (
          <ul className="alert-timeline">
            {alerts.map((a) => (
              <li key={a.id}>
                <AlertTriangle size={14} />
                <span className="alert-title">{a.title}</span>
                <span className={`severity-pill severity-pill--${a.severity}`}>{a.severity}</span>
                <span className="text-muted-small">{formatTimestamp(a.timestamp ?? a.time)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
