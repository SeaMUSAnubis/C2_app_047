import { useCallback, useEffect, useState } from 'react';
import { Activity, Brain, Cpu, Database, DollarSign } from 'lucide-react';
import {
  forgetMemory,
  getLLMStats,
  getPoolStats,
  listMemoriesAdmin,
  type LLMStats,
  type MemoryEntry,
  type MemoryKind,
  type MemoryScope,
  type PoolStats,
} from '../../lib/apiClient';

const SCOPES: MemoryScope[] = ['user', 'device', 'pattern', 'global'];
const KINDS: MemoryKind[] = ['fact', 'preference', 'analyst_pattern', 'historical'];

function formatCost(value: number | undefined, currency: string | undefined): string {
  const amount = value ?? 0;
  const unit = currency || 'USD';
  return `${amount.toLocaleString(undefined, {
    minimumFractionDigits: amount > 0 && amount < 0.01 ? 6 : 2,
    maximumFractionDigits: 6,
  })} ${unit}`;
}

export function MemoryAdminPage() {
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [scope, setScope] = useState<MemoryScope | ''>('');
  const [kind, setKind] = useState<MemoryKind | ''>('');
  const [tag, setTag] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [llmStats, setLlmStats] = useState<LLMStats | null>(null);
  const [poolStats, setPoolStats] = useState<PoolStats | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rows, llm, pool] = await Promise.all([
        listMemoriesAdmin({
          scope: scope || undefined,
          kind: kind || undefined,
          tag: tag.trim() || undefined,
          limit: 200,
        }),
        getLLMStats().catch(() => null),
        getPoolStats().catch(() => null),
      ]);
      setMemories(rows);
      setLlmStats(llm);
      setPoolStats(pool);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [kind, scope, tag]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void reload();
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, kind]);

  const handleForget = async (id: number) => {
    if (!confirm(`Xóa memory #${id}?`)) return;
    try {
      await forgetMemory(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      alert((err as Error).message);
    }
  };

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <div>
          <span className="eyebrow">Quản trị</span>
          <h1>Bộ nhớ LLM &amp; Thống kê</h1>
          <p>Quản lý bộ nhớ dài hạn và theo dõi tình trạng LLM + connection pool.</p>
        </div>
      </div>

      {error && <div className="state-error"><h3>Lỗi</h3><p>{error}</p></div>}

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-icon"><Brain size={22} /></div>
          <p>Tổng bộ nhớ</p>
          <strong>{memories.length}</strong>
          <span>trong trang hiện tại</span>
        </div>
        <div className="stat-card tone-green">
          <div className="stat-icon"><Activity size={22} /></div>
          <p>Lượt gọi LLM</p>
          <strong>{llmStats?.total_calls ?? '—'}</strong>
          <span>
            dự phòng: {llmStats?.total_fallback ?? 0} · TB {llmStats?.avg_latency_ms ?? 0}ms
          </span>
        </div>
        <div className="stat-card tone-violet">
          <div className="stat-icon"><Cpu size={22} /></div>
          <p>Tokens</p>
          <strong>
            {((llmStats?.total_input_tokens ?? 0) + (llmStats?.total_output_tokens ?? 0)).toLocaleString()}
          </strong>
          <span>
            vào {llmStats?.total_input_tokens ?? 0} / ra {llmStats?.total_output_tokens ?? 0}
          </span>
        </div>
        <div className="stat-card">
          <div className="stat-icon"><DollarSign size={22} /></div>
          <p>Chi phí LLM</p>
          <strong>{formatCost(llmStats?.total_estimated_cost, llmStats?.cost_currency)}</strong>
          <span>
            {llmStats?.input_cost_per_1m_tokens ?? 0}/{llmStats?.output_cost_per_1m_tokens ?? 0} mỗi 1M token
          </span>
        </div>
        <div className="stat-card tone-orange">
          <div className="stat-icon"><Database size={22} /></div>
          <p>DB Pool</p>
          <strong>{poolStats?.pool_in_use ?? 0}/{poolStats?.max_size ?? '—'}</strong>
          <span>đang chờ: {poolStats?.requests_waiting ?? 0}</span>
        </div>
      </div>

      <div className="panel-card">
        <div className="filter-row">
          <div className="filter-pills">
            <span className="filter-pill filter-pill-label">Phạm vi:</span>
            <button
              type="button"
              className={`filter-pill ${scope === '' ? 'active' : ''}`}
              onClick={() => setScope('')}
            >
              Tất cả
            </button>
            {SCOPES.map((s) => (
              <button
                key={s}
                type="button"
                className={`filter-pill ${scope === s ? 'active' : ''}`}
                onClick={() => setScope(s)}
              >
                {s}
              </button>
            ))}
          </div>
          <div className="filter-pills">
            <span className="filter-pill filter-pill-label">Loại:</span>
            <button
              type="button"
              className={`filter-pill ${kind === '' ? 'active' : ''}`}
              onClick={() => setKind('')}
            >
              Tất cả
            </button>
            {KINDS.map((k) => (
              <button
                key={k}
                type="button"
                className={`filter-pill ${kind === k ? 'active' : ''}`}
                onClick={() => setKind(k)}
              >
                {k}
              </button>
            ))}
          </div>
          <div className="filter-row">
            <input
              className="search-input"
              type="text"
              placeholder="Lọc theo thẻ..."
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void reload()}
            />
            <button type="button" className="primary-action" onClick={() => void reload()}>
              Tìm
            </button>
          </div>
        </div>

        {loading ? (
          <div className="state-message state-loading">Đang tải…</div>
        ) : memories.length === 0 ? (
          <div className="state-message state-empty">Chưa có memory nào khớp filter.</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Scope</th>
                  <th>Kind</th>
                  <th>Content</th>
                  <th>Tags</th>
                  <th>Uses</th>
                  <th>Last used</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {memories.map((m) => (
                  <tr key={m.id}>
                    <td className="mono">{m.id}</td>
                    <td>
                      <span className="status-pill">{m.scope}</span>
                      {m.scope_id && <small className="text-muted-small"> · {m.scope_id}</small>}
                    </td>
                    <td><span className="status-pill">{m.kind}</span></td>
                    <td className="cell-content">
                      <div className="text-ellipsis">{m.content}</div>
                    </td>
                    <td>
                      <div className="chip-row">
                        {m.tags.slice(0, 4).map((t) => (
                          <span key={t} className="chip">{t}</span>
                        ))}
                      </div>
                    </td>
                    <td>{m.use_count}</td>
                    <td className="text-muted-small">{m.last_used_at ?? '—'}</td>
                    <td className="col-center">
                      <button
                        type="button"
                        className="table-action table-action--danger"
                        onClick={() => void handleForget(m.id)}
                        aria-label="Xóa memory"
                      >
                        Xóa
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
