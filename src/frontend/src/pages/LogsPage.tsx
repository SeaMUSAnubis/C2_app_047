import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Download, FileSearch, Search } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { DataTable } from '../components/security/DataTable';
import type { Column } from '../components/security/DataTable';
import { RiskScore } from '../components/security/RiskScore';
import { StatusBadge } from '../components/security/SeverityBadge';
import { getLogs } from '../lib/apiClient';
import { eventTypeLabel, formatDateTime, severityOptions, shortText } from '../lib/labels';
import type { EventLogItem } from '../types/security';

const PAGE_SIZE = 25;

export function LogsPage() {
  const location = useLocation();
  const [logs, setLogs] = useState<EventLogItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [results, setResults] = useState<string[]>([]);
  const [selected, setSelected] = useState<EventLogItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const querySearch = useMemo(() => new URLSearchParams(location.search).get('q') ?? '', [location.search]);
  const [manualSearch, setManualSearch] = useState<string | null>(null);
  const search = manualSearch ?? querySearch;
  const [eventType, setEventType] = useState('all');
  const [severity, setSeverity] = useState('all');
  const [timeRange, setTimeRange] = useState('all');
  const [result, setResult] = useState('all');
  const [page, setPage] = useState(1);

  const loadPage = useCallback(async (targetPage: number) => {
    setLoading(true);
    setError('');
    try {
      const { rows, total } = await getLogs({ limit: PAGE_SIZE, offset: (targetPage - 1) * PAGE_SIZE });
      setLogs(rows);
      setTotalCount(total);
      if (targetPage === 1) {
        setEventTypes(Array.from(new Set(rows.map((l) => l.eventType).filter((v): v is string => Boolean(v)))).sort());
        setResults(Array.from(new Set(rows.map((l) => l.result).filter((v): v is string => Boolean(v)))).sort());
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể tải nhật ký');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    (async () => {
      setLoading(true);
      try {
        const { rows, total } = await getLogs({ limit: PAGE_SIZE, offset: 0 });
        if (ignore) return;
        setLogs(rows);
        setTotalCount(total);
        setSelected(rows[0] ?? null);
        setEventTypes(Array.from(new Set(rows.map((l) => l.eventType).filter((v): v is string => Boolean(v)))).sort());
        setResults(Array.from(new Set(rows.map((l) => l.result).filter((v): v is string => Boolean(v)))).sort());
      } catch (err: unknown) {
        if (!ignore) setError(err instanceof Error ? err.message : 'Không thể tải nhật ký');
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => { ignore = true; };
  }, []);

  const filteredLogs = useMemo(() => {
    const term = search.trim().toLowerCase();
    return logs.filter((log) => {
      const matchesSearch = !term || [log.user, log.userId, log.device, log.deviceId, log.sourceIp, log.resource, log.eventType, log.result]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
      const matchesType = eventType === 'all' || log.eventType === eventType;
      const matchesSeverity = severity === 'all' || log.severity === severity;
      const matchesTime = matchesDatasetTimeRange(log.timestamp, logs.map((item) => item.timestamp), timeRange);
      const matchesResult = result === 'all' || log.result === result;
      return matchesSearch && matchesType && matchesSeverity && matchesTime && matchesResult;
    });
  }, [eventType, logs, result, search, severity, timeRange]);

  const activeSelected = selected && filteredLogs.some((log) => getLogKey(log) === getLogKey(selected))
    ? selected
    : filteredLogs[0] ?? null;

  function exportCsv() {
    const headers = ['Thời gian', 'Người dùng', 'Thiết bị', 'Loại sự kiện', 'IP nguồn', 'Tài nguyên', 'Kết quả', 'Rủi ro'];
    const rows = filteredLogs.map((log) => [log.timestamp, log.user ?? log.userId ?? '', log.device ?? log.deviceId ?? '', log.eventType, log.sourceIp ?? '', log.resource ?? '', log.result ?? '', String(log.riskScore ?? 0)]);
    const csv = [headers, ...rows].map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'ueba-logs.csv';
    link.click();
    URL.revokeObjectURL(url);
  }

  function resetFilters() {
    setManualSearch('');
    setEventType('all');
    setSeverity('all');
    setTimeRange('all');
    setResult('all');
  }

  function handlePageChange(next: number) {
    setPage(next);
    loadPage(next);
  }

  const logColumns: Column<EventLogItem>[] = [
    { key: 'timestamp', header: 'Thời gian', width: '16%', className: 'cell-nowrap', sortable: true, value: (l) => l.timestamp, render: (l) => formatDateTime(l.timestamp) },
    { key: 'user', header: 'Người dùng', width: '14%', className: 'col-secondary', render: (l) => shortText(l.user ?? l.userId, 'Không xác định') },
    { key: 'device', header: 'Thiết bị', width: '12%', className: 'cell-nowrap', render: (l) => <code>{shortText(l.device ?? l.deviceId, 'Không xác định')}</code> },
    { key: 'eventType', header: 'Sự kiện', width: '17%', render: (l) => (<span className="event-name">{eventTypeLabel(l.eventType)}</span>) },
    { key: 'sourceIp', header: 'IP nguồn', width: '13%', className: 'cell-nowrap col-secondary', render: (l) => shortText(l.sourceIp, 'Không xác định') },
    { key: 'resource', header: 'Tài nguyên', width: '14%', className: 'col-optional', render: (l) => <span title={l.resource}>{shortText(l.resource, 'Chưa có')}</span> },
    { key: 'result', header: 'Kết quả', width: '7%', className: 'col-optional', render: (l) => <StatusBadge value={l.result} /> },
    { key: 'riskScore', header: 'Rủi ro', align: 'center', width: '7%', className: 'cell-risk', sortable: true, value: (l) => l.riskScore ?? 0, render: (l) => <RiskScore value={l.riskScore ?? 0} size="sm" /> },
  ];

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Nhật ký sự kiện" title="Truy vấn nhật ký bảo mật" description="Tìm kiếm sự kiện thiết bị đầu cuối, kết quả truy cập, tài nguyên và điểm rủi ro theo thời gian." actions={<button className="secondary-action" onClick={exportCsv}><Download size={17} /> Xuất CSV</button>} />

      <section className="filter-panel">
        <label><Search size={16} /><input value={search} onChange={(event) => setManualSearch(event.target.value)} placeholder="Tìm theo người dùng, thiết bị, IP, tài nguyên..." /></label>
        <select value={eventType} onChange={(event) => setEventType(event.target.value)}><option value="all">Tất cả loại sự kiện</option>{eventTypes.map((item) => <option key={item} value={item}>{eventTypeLabel(item)}</option>)}</select>
        <select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">Tất cả mức độ</option>{severityOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
        <select value={timeRange} onChange={(event) => setTimeRange(event.target.value)}><option value="all">Tất cả thời gian</option><option value="24h">24 giờ gần nhất</option><option value="7d">7 ngày gần nhất</option><option value="30d">30 ngày gần nhất</option></select>
        <select value={result} onChange={(event) => setResult(event.target.value)}><option value="all">Tất cả kết quả</option>{results.map((item) => <option key={item} value={item}>{item}</option>)}</select>
      </section>

      <section className="log-summary">
        <span>Đang hiển thị {filteredLogs.length} / {totalCount} nhật ký</span>
        <span>{filteredLogs.filter((log) => log.severity === 'critical').length} cảnh báo nghiêm trọng</span>
        <button className="table-action" onClick={resetFilters}>Xóa lọc</button>
      </section>

      <section className="entity-layout">
        <div className="panel-card">
          {loading && <p>Đang tải nhật ký...</p>}
          {error && <p className="error-message">{error}</p>}
          {!loading && !error && logs.length === 0 && <p>Chưa có nhật ký. Hãy nạp dữ liệu vào cơ sở dữ liệu.</p>}
          {!loading && !error && logs.length > 0 && filteredLogs.length === 0 && <p>Không có nhật ký khớp bộ lọc.</p>}
          <DataTable<EventLogItem>
            columns={logColumns}
            rows={filteredLogs}
            rowKey={getLogKey}
            onRowClick={(l) => setSelected(l)}
            selectedKey={activeSelected ? getLogKey(activeSelected) : undefined}
            pageSize={PAGE_SIZE}
            total={totalCount}
            currentPage={page}
            onPageChange={handlePageChange}
            emptyText="Không có nhật ký khớp bộ lọc"
          />
        </div>

        {activeSelected && <aside className="detail-panel">
          <div className="detail-icon"><FileSearch size={24} /></div>
          <span className="eyebrow">Chi tiết sự kiện</span>
          <div className="detail-heading-row">
            <h2>{activeSelected.eventType}</h2>
            <RiskScore value={activeSelected.riskScore ?? 0} size="md" />
          </div>
          <p>Nhật ký này được lấy từ cơ sở dữ liệu và dùng để tính điểm rủi ro cho người dùng, thiết bị và cảnh báo liên quan.</p>
          <div className="profile-grid">
            <div><span>Người dùng</span><strong>{shortText(activeSelected.user ?? activeSelected.userId, 'Không xác định')}</strong></div>
            <div><span>Thiết bị</span><strong>{shortText(activeSelected.device ?? activeSelected.deviceId, 'Không xác định')}</strong></div>
            <div><span>IP nguồn</span><strong>{shortText(activeSelected.sourceIp, 'Không xác định')}</strong></div>
            <div><span>Kết quả</span><StatusBadge value={activeSelected.result} /></div>
          </div>
          <h3>Tài nguyên</h3>
          <p>{activeSelected.resource ?? 'Không có tài nguyên đi kèm.'}</p>
          <h3>Thời gian</h3>
          <p>{formatDateTime(activeSelected.timestamp)}</p>
          <h3>Điểm rủi ro</h3>
          <RiskScore value={activeSelected.riskScore ?? 0} />
        </aside>}
      </section>
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

function getLogKey(log: EventLogItem) {
  // Use the unique event_logs primary key from the database.
  // The composite key (timestamp + eventType + user + device + resource)
  // can collide when multiple events share the same fields, causing
  // React to render stale or duplicate rows.
  return log.id ?? `${log.timestamp}-${log.eventType}-${log.userId ?? log.user ?? ''}-${log.deviceId ?? log.device ?? ''}-${log.resource ?? ''}`;
}

function parseTime(value: string | undefined) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}
