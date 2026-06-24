import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Cpu, Power, RefreshCcw, ShieldOff, UserPlus } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { DataTable } from '../components/security/DataTable';
import type { Column } from '../components/security/DataTable';
import { useAuth } from '../store/useAuth';
import {
  createEnrollmentToken,
  listAgents,
  markStaleAgents,
  revokeAgent,
} from '../lib/apiClient';
import type { AgentEntity, AgentEnrollmentToken } from '../types';
import {
  AGENT_STATUS_LABEL,
  AGENT_STATUS_TONE,
  formatTimestamp,
  timeSince,
} from '../lib/labels';

export default function AgentsPage() {
  const { user } = useAuth();
  const [agents, setAgents] = useState<AgentEntity[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [tokenModal, setTokenModal] = useState<AgentEnrollmentToken | null>(null);
  const [actionMessage, setActionMessage] = useState<string>('');

  const loadAgents = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { rows, total: count } = await listAgents({ limit: 200, offset: 0 });
      setAgents(rows);
      setTotal(count);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể tải danh sách agent');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadAgents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredAgents = useMemo(() => {
    if (statusFilter === 'all') return agents;
    return agents.filter((a) => a.status === statusFilter);
  }, [agents, statusFilter]);

  const counts = useMemo(() => {
    const out: Record<string, number> = { all: agents.length };
    for (const a of agents) {
      out[a.status] = (out[a.status] ?? 0) + 1;
    }
    return out;
  }, [agents]);

  async function handleRevoke(agent: AgentEntity) {
    if (!window.confirm(`Thu hồi agent "${agent.hostname}" (${agent.agent_id})?\nAgent sẽ không thể gửi log nữa.`)) {
      return;
    }
    setBusyId(agent.agent_id);
    setActionMessage('');
    try {
      await revokeAgent(agent.agent_id);
      setActionMessage(`Đã thu hồi agent ${agent.hostname}`);
      await loadAgents();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Thu hồi thất bại');
    } finally {
      setBusyId(null);
    }
  }

  async function handleIssueToken() {
    setActionMessage('');
    try {
      const token = await createEnrollmentToken(120);
      setTokenModal(token);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Tạo token thất bại');
    }
  }

  async function handleMarkStale() {
    setActionMessage('');
    try {
      const result = await markStaleAgents();
      setActionMessage(`Đã đánh dấu ${result.flipped_to_offline} agent quá hạn là offline.`);
      await loadAgents();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Đánh dấu thất bại');
    }
  }

  const isAdmin = user?.role === 'admin';

  const columns: Column<AgentEntity>[] = [
    {
      key: 'agent_id',
      header: 'Agent ID',
      render: (a) => (
        <Link to={`/admin/agents/${encodeURIComponent(a.agent_id)}`} className="link-strong">
          {a.agent_id}
        </Link>
      ),
    },
    { key: 'hostname', header: 'Hostname', render: (a) => <strong>{a.hostname}</strong> },
    {
      key: 'os',
      header: 'OS',
      render: (a) => (a.os ? `${a.os}${a.os_version ? ` ${a.os_version}` : ''}` : '—'),
    },
    {
      key: 'status',
      header: 'Trạng thái',
      render: (a) => (
        <span className={AGENT_STATUS_TONE[a.status] ?? 'status-pill'}>{AGENT_STATUS_LABEL[a.status] ?? a.status}</span>
      ),
    },
    {
      key: 'policy_version',
      header: 'Policy v',
      align: 'center',
      render: (a) => <span className="mono">{a.policy_version}</span>,
    },
    {
      key: 'last_heartbeat',
      header: 'Heartbeat',
      render: (a) => (
        <span title={formatTimestamp(a.last_heartbeat)}>
          {timeSince(a.last_heartbeat)}
        </span>
      ),
    },
    {
      key: 'enrolled_at',
      header: 'Đăng ký',
      render: (a) => formatTimestamp(a.enrolled_at),
    },
    {
      key: 'actions',
      header: 'Thao tác',
      align: 'center',
      render: (a) => (
        <button
          className="table-action table-action--danger"
          disabled={a.status === 'revoked' || busyId === a.agent_id || !isAdmin}
          onClick={(e) => {
            e.stopPropagation();
            void handleRevoke(a);
          }}
          title={a.status === 'revoked' ? 'Agent đã thu hồi' : 'Thu hồi agent'}
        >
          <ShieldOff size={14} /> Thu hồi
        </button>
      ),
    },
  ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Quản trị agent"
        title="Quản lý endpoint agent"
        description="Danh sách agent đã cài trên máy nhân viên. Cấp token đăng ký, theo dõi heartbeat, thu hồi khi cần."
        actions={
          isAdmin ? (
            <div className="action-row">
              <button className="secondary-action" onClick={() => void handleMarkStale()}>
                <RefreshCcw size={16} /> Đánh dấu quá hạn
              </button>
              <button className="primary-action" onClick={() => void handleIssueToken()}>
                <UserPlus size={16} /> Cấp enrollment token
              </button>
            </div>
          ) : null
        }
      />

      {error && <div className="form-error">{error}</div>}
      {actionMessage && <div className="form-success">{actionMessage}</div>}

      <section className="filter-row">
        <div className="filter-pills">
          {(['all', 'active', 'offline', 'enrolled', 'revoked'] as const).map((s) => (
            <button
              key={s}
              className={`filter-pill ${statusFilter === s ? 'active' : ''}`}
              onClick={() => setStatusFilter(s)}
            >
              {s === 'all' ? 'Tất cả' : AGENT_STATUS_LABEL[s] ?? s}
              <span className="filter-pill-count">{counts[s] ?? 0}</span>
            </button>
          ))}
        </div>
        <span className="text-muted">
          Hiển thị {filteredAgents.length} / {total} agent
        </span>
      </section>

      <section className="panel-card">
        {loading ? (
          <p>Đang tải danh sách agent...</p>
        ) : (
          <DataTable<AgentEntity>
            columns={columns}
            rows={filteredAgents}
            rowKey={(a) => a.agent_id}
            emptyText="Chưa có agent nào đăng ký. Cấp enrollment token để bắt đầu."
          />
        )}
      </section>

      {tokenModal && (
        <div className="modal-backdrop" onClick={() => setTokenModal(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <Cpu size={20} />
              <h3>Enrollment token mới</h3>
            </div>
            <p className="text-muted">
              Token này chỉ hiển thị <strong>một lần</strong>. Hãy sao chép và đưa cho quản trị viên máy
              trạm để chạy lệnh enroll. Token hết hạn lúc <code>{formatTimestamp(tokenModal.expires_at)}</code>.
            </p>
            <pre className="token-block">{tokenModal.token}</pre>
            <div className="modal-actions">
              <button
                className="secondary-action"
                onClick={() => {
                  if (navigator.clipboard) {
                    void navigator.clipboard.writeText(tokenModal.token);
                  }
                }}
              >
                Sao chép
              </button>
              <button className="primary-action" onClick={() => setTokenModal(null)}>
                <Power size={14} /> Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
