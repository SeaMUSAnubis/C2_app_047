import { useEffect, useState } from 'react';
import { Activity, HardDrive, ShieldAlert, UserRoundCheck } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { DataTable } from '../components/security/DataTable';
import type { Column } from '../components/security/DataTable';
import { RiskScore } from '../components/security/RiskScore';
import { SeverityBadge } from '../components/security/SeverityBadge';
import { StatCard } from '../components/security/StatCard';
import { StateMessage } from '../components/security/StateMessage';
import { AlertDetailModal } from '../features/alerts/AlertDetailModal';
import { eventTypeLabel, statusLabel } from '../lib/labels';
import { getEmployeeOverview } from '../lib/apiClient';
import type { EmployeeOverview } from '../lib/apiClient';

const icons = [Activity, ShieldAlert, HardDrive, UserRoundCheck];

interface MyAlert {
  id: string;
  numericId?: number;
  title: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: string;
  riskScore: number;
  device: string;
  time: string;
}

interface MyDevice {
  id: string;
  hostname: string;
  os?: string;
  ip?: string;
  status: string;
  riskScore?: number;
  posture?: string;
  suspiciousEvents?: number;
}

interface MyLog {
  id: string;
  timestamp: string;
  eventType: string;
  device?: string;
  sourceIp?: string;
  resource?: string;
  result?: string;
  riskScore?: number;
  severity?: 'low' | 'medium' | 'high' | 'critical';
}

export default function MyRiskPage() {
  const [data, setData] = useState<EmployeeOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chatAlert, setChatAlert] = useState<MyAlert | null>(null);

  useEffect(() => {
    let ignore = false;
    getEmployeeOverview()
      .then((result) => { if (!ignore) setData(result); })
      .catch((err: unknown) => {
        if (!ignore) setError(err instanceof Error ? err.message : 'Không thể tải hồ sơ cá nhân');
      })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, []);

  if (loading) return <div className="panel-card"><StateMessage variant="loading" title="Đang tải hồ sơ rủi ro cá nhân..." /></div>;
  if (error) return <div className="panel-card"><StateMessage variant="error" title="Lỗi tải dữ liệu">{error}</StateMessage></div>;
  if (!data) return <div className="panel-card"><StateMessage variant="empty">Tài khoản chưa được liên kết với người dùng nào. Hãy liên hệ quản trị viên.</StateMessage></div>;

  const user = data.user;

  const alertColumns: Column<MyAlert>[] = [
    { key: 'title', header: 'Cảnh báo', render: (a) => <strong>{a.title}</strong> },
    { key: 'severity', header: 'Mức độ', render: (a) => <SeverityBadge severity={a.severity} /> },
    { key: 'riskScore', header: 'Rủi ro', align: 'right', className: 'cell-risk', sortable: true, value: (a) => a.riskScore, render: (a) => <RiskScore value={a.riskScore} size="sm" /> },
    { key: 'status', header: 'Trạng thái', render: (a) => <span className="status-pill">{statusLabel(a.status)}</span> },
    { key: 'device', header: 'Thiết bị' },
    { key: 'time', header: 'Thời gian', align: 'right' },
  ];

  const deviceColumns: Column<MyDevice>[] = [
    { key: 'hostname', header: 'Thiết bị', render: (d) => <code>{d.hostname}</code> },
    { key: 'os', header: 'Hệ điều hành', render: (d) => d.os ?? '-' },
    { key: 'ip', header: 'IP', render: (d) => d.ip ?? '-' },
    { key: 'posture', header: 'Tình trạng', render: (d) => <span className="status-pill">{d.posture ?? d.status}</span> },
    { key: 'riskScore', header: 'Rủi ro', align: 'right', className: 'cell-risk', sortable: true, value: (d) => d.riskScore ?? 0, render: (d) => <RiskScore value={d.riskScore ?? 0} size="sm" /> },
  ];

  const logColumns: Column<MyLog>[] = [
    { key: 'timestamp', header: 'Thời gian' },
    { key: 'eventType', header: 'Loại sự kiện', render: (l) => (<span className="event-name">{eventTypeLabel(l.eventType)}</span>) },
    { key: 'device', header: 'Thiết bị', render: (l) => <code>{l.device ?? '-'}</code> },
    { key: 'sourceIp', header: 'IP nguồn', render: (l) => l.sourceIp ?? '-' },
    { key: 'resource', header: 'Tài nguyên', render: (l) => l.resource ?? '-' },
    { key: 'result', header: 'Kết quả', render: (l) => <span className="status-pill">{l.result ?? '-'}</span> },
    { key: 'riskScore', header: 'Rủi ro', align: 'right', className: 'cell-risk', sortable: true, value: (l) => l.riskScore ?? 0, render: (l) => <RiskScore value={l.riskScore ?? 0} size="sm" /> },
  ];

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Hồ sơ cá nhân" title="Rủi ro của tôi" description="Theo dõi điểm rủi ro, cảnh báo, thiết bị và hoạt động liên quan đến tài khoản của bạn." />

      <section className="stat-grid">
        {data.kpis.map((item, index) => {
          const Icon = icons[index] ?? Activity;
          return <StatCard key={item.label} {...item} icon={<Icon size={22} />} />;
        })}
      </section>

      <section className="two-column-grid">
        <div className="panel-card">
          <div className="section-heading">
            <div>
              <h2>Điểm rủi ro cá nhân</h2>
              <p>Đánh giá tổng hợp từ mô hình ML</p>
            </div>
          </div>
          <div className="my-risk-summary">
            <RiskScore value={user.riskScore ?? 0} size="lg" />
            <div className="profile-grid">
              <div><span>Vai trò</span><strong>{user.role ?? '-'}</strong></div>
              <div><span>Phòng ban</span><strong>{user.department ?? '-'}</strong></div>
              <div><span>Hoạt động cuối</span><strong>{user.lastSeen ?? '-'}</strong></div>
              <div><span>Hồ sơ chuẩn</span><strong>{user.baseline ?? '-'}</strong></div>
              <div><span>Giờ đăng nhập thường lệ</span><strong>{user.loginHours ?? '-'}</strong></div>
              <div><span>Thiết bị phổ biến</span><strong>{user.commonDevices ?? '-'}</strong></div>
            </div>
            <h3>Giải thích</h3>
            <p>{user.explanation ?? 'Chưa có giải thích.'}</p>
          </div>
        </div>

        <div className="panel-card">
          <div className="section-heading">
            <div>
              <h2>Cảnh báo của tôi</h2>
              <p>{data.alerts.length} cảnh báo liên quan</p>
            </div>
            <ShieldAlert size={20} />
          </div>
          <DataTable<MyAlert>
            columns={alertColumns}
            rows={data.alerts as MyAlert[]}
            rowKey={(a) => a.id}
            initialSort={{ key: 'riskScore', dir: 'desc' }}
            pageSize={10}
            emptyText="Chưa có cảnh báo"
            onRowClick={(a) => {
              if (a.numericId != null) setChatAlert(a);
            }}
          />
        </div>
      </section>

      <section className="two-column-grid">
        <div className="panel-card">
          <div className="section-heading">
            <div>
              <h2>Thiết bị của tôi</h2>
              <p>{data.devices.length} thiết bị đang gán</p>
            </div>
            <HardDrive size={20} />
          </div>
          <DataTable<MyDevice>
            columns={deviceColumns}
            rows={data.devices as MyDevice[]}
            rowKey={(d) => d.id}
            emptyText="Chưa có thiết bị"
          />
        </div>

        <div className="panel-card">
          <div className="section-heading">
            <div>
              <h2>Hoạt động gần đây</h2>
              <p>20 sự kiện mới nhất</p>
            </div>
            <Activity size={20} />
          </div>
          <DataTable<MyLog>
            columns={logColumns}
            rows={data.logs as MyLog[]}
            rowKey={(l) => l.id}
            initialSort={{ key: 'timestamp', dir: 'desc' }}
            pageSize={10}
            emptyText="Chưa có hoạt động"
          />
        </div>
      </section>
      {chatAlert && chatAlert.numericId != null && (
        <AlertDetailModal
          alert={{
            id: chatAlert.numericId,
            title: chatAlert.title,
            severity: chatAlert.severity,
          }}
          onClose={() => setChatAlert(null)}
        />
      )}
    </div>
  );
}
