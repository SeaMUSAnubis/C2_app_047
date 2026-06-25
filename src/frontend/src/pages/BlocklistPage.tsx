import { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus, ShieldBan, Trash2, X } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { DataTable } from '../components/security/DataTable';
import type { Column } from '../components/security/DataTable';
import { StateMessage } from '../components/security/StateMessage';
import {
  addBlocklistEntry,
  listBlocklist,
  removeBlocklistEntry,
  updateBlocklistEntry,
} from '../lib/apiClient';
import type { BlocklistEntry, BlocklistPatternType } from '../types';

const TYPE_LABEL: Record<BlocklistPatternType, string> = {
  domain: 'Domain',
  url: 'URL',
  ip: 'IP',
  regex: 'Regex',
};

interface NewEntryForm {
  pattern: string;
  pattern_type: BlocklistPatternType;
  category: string;
  reason: string;
  enabled: boolean;
}

const EMPTY_FORM: NewEntryForm = {
  pattern: '',
  pattern_type: 'domain',
  category: '',
  reason: '',
  enabled: true,
};

function matchPreview(value: string, type: BlocklistPatternType): string {
  if (!value) return '';
  if (type === 'domain') {
    if (value.startsWith('.')) return `*.${value.slice(1)}`;
    return `*.${value}`;
  }
  if (type === 'url') return value;
  if (type === 'ip') return value;
  return value;
}

export default function BlocklistPage() {
  const [entries, setEntries] = useState<BlocklistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [form, setForm] = useState<NewEntryForm>(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [filterType, setFilterType] = useState<'all' | BlocklistPatternType>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const loadEntries = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const rows = await listBlocklist(false);
      setEntries(rows);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể tải blocklist');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadEntries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredEntries = useMemo(() => {
    return entries.filter((e) => {
      if (filterType !== 'all' && e.pattern_type !== filterType) return false;
      if (searchTerm && !e.pattern.toLowerCase().includes(searchTerm.toLowerCase())) return false;
      return true;
    });
  }, [entries, filterType, searchTerm]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.pattern.trim()) {
      setError('Pattern không được để trống');
      return;
    }
    setError('');
    setSuccess('');
    try {
      await addBlocklistEntry({
        pattern: form.pattern.trim(),
        pattern_type: form.pattern_type,
        category: form.category.trim() || undefined,
        reason: form.reason.trim() || undefined,
        enabled: form.enabled,
      });
      setSuccess(`Đã thêm ${form.pattern} vào blocklist`);
      setForm(EMPTY_FORM);
      setShowForm(false);
      await loadEntries();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Thêm thất bại');
    }
  }

  async function handleToggle(entry: BlocklistEntry) {
    setBusyId(entry.id);
    setError('');
    try {
      await updateBlocklistEntry(entry.id, { enabled: !entry.enabled });
      await loadEntries();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Cập nhật thất bại');
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(entry: BlocklistEntry) {
    if (!window.confirm(`Xóa mục blocklist "${entry.pattern}"?`)) return;
    setBusyId(entry.id);
    setError('');
    try {
      await removeBlocklistEntry(entry.id);
      setSuccess(`Đã xóa ${entry.pattern}`);
      await loadEntries();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Xóa thất bại');
    } finally {
      setBusyId(null);
    }
  }

  const columns: Column<BlocklistEntry>[] = [
    {
      key: 'pattern',
      header: 'Pattern',
      render: (e) => (
        <div>
          <code className="mono">{e.pattern}</code>
          <div className="text-muted-small">
            Sẽ khớp: <span className="mono">{matchPreview(e.pattern, e.pattern_type)}</span>
          </div>
        </div>
      ),
    },
    {
      key: 'pattern_type',
      header: 'Loại',
      render: (e) => <span className="status-pill">{TYPE_LABEL[e.pattern_type]}</span>,
    },
    { key: 'category', header: 'Danh mục', render: (e) => e.category ?? '—' },
    { key: 'reason', header: 'Lý do', render: (e) => e.reason ?? '—' },
    {
      key: 'enabled',
      header: 'Trạng thái',
      render: (e) => (
        <button
          className={`switch ${e.enabled ? 'switch-on' : 'switch-off'}`}
          onClick={() => void handleToggle(e)}
          disabled={busyId === e.id}
          title={e.enabled ? 'Đang bật — bấm để tắt' : 'Đang tắt — bấm để bật'}
        >
          {e.enabled ? 'Bật' : 'Tắt'}
        </button>
      ),
    },
    {
      key: 'actions',
      header: 'Thao tác',
      align: 'center',
      render: (e) => (
        <button
          className="table-action table-action--danger"
          disabled={busyId === e.id}
          onClick={() => void handleDelete(e)}
        >
          <Trash2 size={14} /> Xóa
        </button>
      ),
    },
  ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Quản trị danh sách chặn"
        title="Danh sách chặn"
        description="Tên miền/URL/IP sẽ bị agent chặn và gửi sự kiện 'http' với action=blocked. Đồng bộ xuống tất cả agent đang hoạt động."
        actions={
          <button
            className="primary-action"
            onClick={() => {
              setShowForm((s) => !s);
              setError('');
              setSuccess('');
            }}
          >
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Đóng' : 'Thêm mục'}
          </button>
        }
      />

      {error && <div className="form-error">{error}</div>}
      {success && <div className="form-success">{success}</div>}

      {showForm && (
        <section className="panel-card">
          <form className="form-grid" onSubmit={(e) => void handleCreate(e)}>
            <label>
              Pattern
              <input
                type="text"
                value={form.pattern}
                onChange={(e) => setForm({ ...form, pattern: e.target.value })}
                placeholder="vd: wikileaks.org, https://evil.com/path, 198.51.100.0/24"
                required
              />
            </label>
            <label>
              Loại
              <select
                value={form.pattern_type}
                onChange={(e) =>
                  setForm({ ...form, pattern_type: e.target.value as BlocklistPatternType })
                }
              >
                <option value="domain">Domain (khớp cả subdomain)</option>
                <option value="url">URL (substring match)</option>
                <option value="ip">IP (substring match)</option>
                <option value="regex">Regex</option>
              </select>
            </label>
            <label>
              Danh mục
              <input
                type="text"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                placeholder="vd: leak, malware, gambling"
              />
            </label>
            <label>
              Lý do
              <input
                type="text"
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                placeholder="vd: chính sách công ty, GDPR, ..."
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              Bật ngay (agent sẽ chặn các match)
            </label>
            <div className="form-actions">
              <button type="button" className="secondary-action" onClick={() => setShowForm(false)}>
                Hủy
              </button>
              <button type="submit" className="primary-action">
                <ShieldBan size={16} /> Thêm vào blocklist
              </button>
            </div>
          </form>
        </section>
      )}

      <section className="filter-row">
        <div className="filter-pills">
          {(['all', 'domain', 'url', 'ip', 'regex'] as const).map((t) => (
            <button
              key={t}
              className={`filter-pill ${filterType === t ? 'active' : ''}`}
              onClick={() => setFilterType(t)}
            >
              {t === 'all' ? 'Tất cả' : TYPE_LABEL[t]}
            </button>
          ))}
        </div>
        <input
          className="search-input"
          type="search"
          placeholder="Tìm theo pattern..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </section>

      <section className="panel-card">
        {loading ? (
          <StateMessage variant="loading" title="Đang tải danh sách chặn..." />
        ) : (
          <DataTable<BlocklistEntry>
            columns={columns}
            rows={filteredEntries}
            rowKey={(e) => String(e.id)}
            emptyText={
              entries.length === 0
                ? 'Chưa có mục nào trong blocklist. Bấm "Thêm mục" để bắt đầu.'
                : 'Không tìm thấy mục nào khớp filter.'
            }
          />
        )}
      </section>
    </div>
  );
}
