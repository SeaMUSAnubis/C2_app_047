import { useCallback, useEffect, useMemo, useState } from 'react';
import { Filter, MessageSquare, Search, ShieldAlert } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { DataTable } from '../components/security/DataTable';
import { RiskScore } from '../components/security/RiskScore';
import { SeverityBadge, StatusBadge } from '../components/security/SeverityBadge';
import { AlertDetailModal } from '../features/alerts/AlertDetailModal';
import { getAlerts } from '../lib/apiClient';
import { formatDateTime, severityOptions, shortText, statusOptions } from '../lib/labels';
import type { AlertItem } from '../types/security';

const PAGE_SIZE = 25;

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [selected, setSelected] = useState<AlertItem | null>(null);
  const [chatAlert, setChatAlert] = useState<AlertItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [severity, setSeverity] = useState('all');
  const [status, setStatus] = useState('all');
  const [entity, setEntity] = useState('all');
  const [timeRange, setTimeRange] = useState('all');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [page, setPage] = useState(1);

  const loadPage = useCallback(async (targetPage: number) => {
    setLoading(true);
    setError('');
    try {
      const { rows, total } = await getAlerts({ limit: PAGE_SIZE, offset: (targetPage - 1) * PAGE_SIZE });
      setAlerts(rows);
      setTotalCount(total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể tải cảnh báo');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    (async () => {
      setLoading(true);
      try {
        const { rows, total } = await getAlerts({ limit: PAGE_SIZE, offset: 0 });
        if (ignore) return;
        setAlerts(rows);
        setTotalCount(total);
        setSelected(rows[0] ?? null);
      } catch (err: unknown) {
        if (!ignore) setError(err instanceof Error ? err.message : 'Không thể tải cảnh báo');
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => { ignore = true; };
  }, []);

  const filteredAlerts = useMemo(() => {
    const term = search.trim().toLowerCase();
    return alerts.filter((alert) => {
      const matchesSearch = !term || [alert.title, alert.user, alert.device, alert.id, alert.explanation]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
      const matchesSeverity = severity === 'all' || alert.severity === severity;
      const matchesStatus = status === 'all' || alert.status === status;
      const matchesEntity = entity === 'all'
        || (entity === 'user' && Boolean(alert.user))
        || (entity === 'device' && Boolean(alert.device));
      const matchesTime = matchesDatasetTimeRange(alert.timestamp ?? alert.time, alerts.map((item) => item.timestamp ?? item.time), timeRange);
      return matchesSearch && matchesSeverity && matchesStatus && matchesEntity && matchesTime;
    });
  }, [alerts, entity, search, severity, status, timeRange]);

  function resetFilters() {
    setSearch('');
    setSeverity('all');
    setStatus('all');
    setEntity('all');
    setTimeRange('all');
  }

  function handlePageChange(next: number) {
    setPage(next);
    loadPage(next);
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Hàng đợi cảnh báo" title="Quản lý cảnh báo" description="Lọc, ưu tiên và xử lý cảnh báo bất thường theo thực thể, thiết bị và mức độ rủi ro." actions={<button className="secondary-action" onClick={() => setShowAdvanced((current) => !current)}><Filter size={17} /> Bộ lọc nâng cao</button>} />

      <section className="filter-panel">
        <label><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Tìm cảnh báo, người dùng, thiết bị..." /></label>
        <select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">Tất cả mức độ</option>{severityOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
        <select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">Tất cả trạng thái</option>{statusOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
        <select value={entity} onChange={(event) => setEntity(event.target.value)}><option value="all">Tất cả thực thể</option><option value="user">Người dùng</option><option value="device">Thiết bị</option></select>
        <select value={timeRange} onChange={(event) => setTimeRange(event.target.value)}><option value="all">Tất cả thời gian</option><option value="24h">24 giờ gần nhất</option><option value="7d">7 ngày gần nhất</option><option value="30d">30 ngày gần nhất</option></select>
      </section>
      {showAdvanced && <section className="filter-summary"><span>Đang hiển thị {filteredAlerts.length} / {totalCount} cảnh báo</span><button className="table-action" onClick={resetFilters}>Xóa lọc</button></section>}

      <section className="alerts-layout">
        <div className="panel-card">
          {loading && <p>Đang tải cảnh báo...</p>}
          {error && <p className="error-message">{error}</p>}
          {!loading && !error && alerts.length === 0 && <p>Chưa có cảnh báo. Hãy nạp dữ liệu hoặc chạy phân tích.</p>}
          {!loading && !error && alerts.length > 0 && filteredAlerts.length === 0 && <p>Không có cảnh báo khớp bộ lọc.</p>}
          <DataTable<AlertItem>
            columns={[
              { key: 'title', header: 'Cảnh báo', width: '24%', render: (a) => (<div className="cell-main" title={a.title}><strong>{a.title}</strong><span className="muted-line">{a.id}</span></div>) },
              { key: 'user', header: 'Thực thể', width: '14%', className: 'col-secondary', render: (a) => <span title={a.user}>{shortText(a.user, 'Không xác định')}</span> },
              { key: 'device', header: 'Thiết bị', width: '11%', className: 'cell-nowrap', render: (a) => <code>{shortText(a.device, 'Không xác định')}</code> },
              { key: 'severity', header: 'Mức độ', width: '11%', render: (a) => <SeverityBadge severity={a.severity} />, sortable: true, value: (a) => a.severity },
              { key: 'riskScore', header: 'Rủi ro', align: 'center', width: '9%', className: 'cell-risk', sortable: true, value: (a) => a.riskScore, render: (a) => <RiskScore value={a.riskScore} size="sm" /> },
              { key: 'status', header: 'Trạng thái', width: '12%', className: 'col-secondary', render: (a) => <StatusBadge value={a.status} /> },
              { key: 'time', header: 'Thời gian', align: 'right', width: '14%', className: 'cell-nowrap col-optional', render: (a) => formatDateTime(a.timestamp ?? a.time) },
              {
                key: 'chat',
                header: 'AI',
                align: 'center',
                width: '5%',
                className: 'cell-action',
                render: (a) => a.numericId != null ? (
                  <button
                    type="button"
                    className="icon-button"
                    title="Thảo luận với AI"
                    aria-label="Thảo luận với AI"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelected(a);
                      setChatAlert(a);
                    }}
                  >
                    <MessageSquare size={16} />
                  </button>
                ) : null,
              },
            ]}
            rows={filteredAlerts}
            rowKey={(a) => a.id}
            onRowClick={(a) => setSelected(a)}
            selectedKey={selected?.id}
            pageSize={PAGE_SIZE}
            total={totalCount}
            currentPage={page}
            onPageChange={handlePageChange}
            emptyText="Không có cảnh báo khớp bộ lọc"
          />
        </div>

        {selected && <aside className="detail-panel">
          <div className="detail-icon"><ShieldAlert size={24} /></div>
          <span className="eyebrow">Chi tiết cảnh báo</span>
          <div className="detail-heading-row">
            <h2>{selected.title}</h2>
            <RiskScore value={selected.riskScore} size="md" />
          </div>
          <div className="detail-block">
            <h3>Tóm tắt cảnh báo</h3>
            <p>{shortText(selected.explanation, 'Chưa có giải thích từ hệ thống.')}</p>
          </div>
          <div className="detail-meta">
            <span>{shortText(selected.user, 'Không xác định')}</span>
            <span>{shortText(selected.device, 'Không xác định')}</span>
            <SeverityBadge severity={selected.severity} />
            <StatusBadge value={selected.status} />
          </div>
          <div className="detail-block">
            <h3>Thực thể liên quan</h3>
            <div className="profile-grid compact">
              <div><span>Người dùng</span><strong>{shortText(selected.user, 'Không xác định')}</strong></div>
              <div><span>Thiết bị</span><strong>{shortText(selected.device, 'Không xác định')}</strong></div>
              <div><span>Thời gian</span><strong>{formatDateTime(selected.timestamp ?? selected.time)}</strong></div>
              <div><span>Trạng thái</span><strong>{shortText(selected.status)}</strong></div>
            </div>
          </div>
          <div className="detail-block">
            <h3>Bằng chứng</h3>
            {(selected.evidence ?? []).length > 0 ? <ul>{(selected.evidence ?? []).map((item) => <li key={item}>{item}</li>)}</ul> : <p>Chưa có bằng chứng chi tiết.</p>}
          </div>
          <div className="detail-block">
            <h3>Khuyến nghị xử lý</h3>
            <p>{shortText(selected.action, 'Xem xét phiên đăng nhập, thiết bị liên quan và xác minh với chủ sở hữu.')}</p>
          </div>
          <div className="detail-block">
            <h3>Thẻ kỹ thuật</h3>
            <span className="mitre-tag">{shortText(selected.mitre, 'Không xác định')}</span>
          </div>
          {selected.numericId != null && (
            <button
              type="button"
              className="primary-action"
              style={{ marginTop: 16, width: '100%' }}
              onClick={() => setChatAlert(selected)}
            >
              <MessageSquare size={16} />
              Thảo luận với AI
            </button>
          )}
        </aside>}
      </section>
      {chatAlert && chatAlert.numericId != null && (
        <AlertDetailModal
          alert={{
            id: chatAlert.numericId,
            title: chatAlert.title,
            severity: chatAlert.severity,
            explanation: chatAlert.explanation ?? null,
            user: chatAlert.user,
            device: chatAlert.device,
            risk_score: chatAlert.riskScore,
          }}
          onClose={() => setChatAlert(null)}
        />
      )}
    </div>
  );
}

function matchesDatasetTimeRange(value: string | undefined, allValues: (string | undefined)[], range: string) {
  if (range === 'all') return true;
  const current = parseTime(value);
  if (!current) return false;
  const maxTime = Math.max(...allValues.map((item) => parseTime(item)?.getTime() ?? 0));
  if (!maxTime) return true;
  const hours = range === '24h' ? 24 : range === '7d' ? 24 * 7 : 24 * 30;
  return current.getTime() >= maxTime - hours * 60 * 60 * 1000;
}

function parseTime(value: string | undefined) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}
