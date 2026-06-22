import { useEffect, useMemo, useState } from 'react';
import { ShieldBan } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { DataTable } from '../components/security/DataTable';
import type { Column } from '../components/security/DataTable';
import { getAlerts } from '../lib/apiClient';
import type { AlertItem } from '../types/security';

interface BlockedSite {
  domain: string;
  reason: string;
  alert: string;
  status: string;
}

function extractDomain(alert: AlertItem) {
  const resource = alert.evidence?.find((item) => item.toLowerCase().includes('resource:')) ?? alert.device;
  const value = resource.replace(/^resource:\s*/i, '').trim();
  try {
    return new URL(value).hostname;
  } catch {
    return value || alert.device;
  }
}

export default function AdminBlockedWebsitesPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;
    getAlerts({ limit: 200, offset: 0 })
      .then(({ rows }) => { if (!ignore) setAlerts(rows.filter((alert) => alert.riskScore >= 70)); })
      .catch((err: unknown) => { if (!ignore) setError(err instanceof Error ? err.message : 'Không thể tải danh sách chặn'); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, []);

  const blockedSites = useMemo(() => alerts.map((alert) => ({
    domain: extractDomain(alert),
    reason: alert.title,
    alert: alert.id,
    status: 'Đang chặn',
  })), [alerts]);

  const columns: Column<BlockedSite>[] = [
    { key: 'domain', header: 'Tên miền', render: (s) => <strong>{s.domain}</strong> },
    { key: 'reason', header: 'Lý do' },
    { key: 'alert', header: 'Cảnh báo nguồn' },
    { key: 'status', header: 'Trạng thái', render: (s) => <span className="status-pill">{s.status}</span> },
    { key: 'actions', header: 'Thao tác', align: 'center', render: () => <button className="table-action">Cập nhật</button> },
  ];

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Quản trị danh sách chặn" title="Website bị chặn" description="Quản lý tên miền/URL được chặn dựa trên cảnh báo UEBA." actions={<button className="secondary-action"><ShieldBan size={17} /> Thêm tên miền</button>} />
      <section className="panel-card">
        {loading && <p>Đang tải danh sách chặn...</p>}
        {error && <p className="error-message">{error}</p>}
        {!loading && !error && blockedSites.length === 0 && <p>Chưa có tên miền cần chặn từ cảnh báo.</p>}
        <DataTable<BlockedSite>
          columns={columns}
          rows={blockedSites}
          rowKey={(s) => s.domain}
          emptyText="Chưa có tên miền cần chặn"
        />
      </section>
    </div>
  );
}

