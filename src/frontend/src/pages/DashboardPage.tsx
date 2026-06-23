import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, Bot, Database, MessageSquare, Monitor, Play, ShieldCheck, TrendingUp, Users } from 'lucide-react';
import { ChartCard } from '../components/security/ChartCard';
import { BarChart, DonutChart, LineChart } from '../components/security/Charts';
import { DataTable } from '../components/security/DataTable';
import { RiskScore } from '../components/security/RiskScore';
import { SeverityBadge } from '../components/security/SeverityBadge';
import { StatCard } from '../components/security/StatCard';
import { AlertDetailModal } from '../features/alerts/AlertDetailModal';
import { analyzeAllDemo, getDashboardOverview } from '../lib/apiClient';
import { formatDateTime, shortText } from '../lib/labels';
import type { DashboardOverview, RiskyEntity } from '../types/security';

const icons = [Users, Monitor, Database, AlertTriangle, ShieldCheck, TrendingUp];

export default function DashboardPage() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [timeRange, setTimeRange] = useState('24h');
  const [chatAlert, setChatAlert] = useState<DashboardOverview['alerts'][number] | null>(null);
  const [runningAnalysis, setRunningAnalysis] = useState(false);
  const [analysisMessage, setAnalysisMessage] = useState('');

  const loadOverview = useCallback(async (ignore?: () => boolean, showLoading = true) => {
    if (showLoading) {
      setError('');
      setLoading(true);
    }
    try {
      const result = await getDashboardOverview();
      if (!ignore?.()) setData(result);
    } catch (err: unknown) {
      if (!ignore?.()) setError(err instanceof Error ? err.message : 'Không thể tải dashboard từ API');
    } finally {
      if (!ignore?.()) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    const isIgnored = () => ignore;
    const initialTimer = window.setTimeout(() => {
      void loadOverview(isIgnored);
    }, 0);
    const timer = window.setInterval(() => {
      void loadOverview(isIgnored, false);
    }, 10_000);
    return () => {
      ignore = true;
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [loadOverview]);

  async function runAnalysis() {
    setRunningAnalysis(true);
    setAnalysisMessage('Đang chạy analysis trên dữ liệu trong database...');
    try {
      const result = await analyzeAllDemo() as { total_users_analyzed?: number; anomalies_found?: number };
      setAnalysisMessage(`Analysis hoàn tất: ${result.total_users_analyzed ?? 0} users, ${result.anomalies_found ?? 0} anomalies.`);
      await loadOverview();
    } catch (err: unknown) {
      setAnalysisMessage(err instanceof Error ? err.message : 'Không thể chạy analysis');
    } finally {
      setRunningAnalysis(false);
    }
  }

  if (loading) return <div className="panel-card">Đang tải dữ liệu tổng quan...</div>;
  if (error) return <div className="panel-card error-state"><h3>Lỗi tải dữ liệu</h3><p>{error}</p></div>;
  if (!data) return <div className="panel-card">Chưa có dữ liệu. Hãy nạp dữ liệu hoặc chạy phân tích.</div>;

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div>
          <span className="eyebrow">Tổng quan</span>
          <h1>Bảng điều khiển UEBA</h1>
          <p>Giám sát bất thường hành vi người dùng, thiết bị, nhật ký và mẫu truy cập trên toàn bộ thiết bị đầu cuối.</p>
        </div>
        <div className="hero-actions">
          <div className="segmented-control" aria-label="Khoảng thời gian">
            <button className={timeRange === '24h' ? 'active' : ''} onClick={() => setTimeRange('24h')}>24 giờ</button>
            <button className={timeRange === '7d' ? 'active' : ''} onClick={() => setTimeRange('7d')}>7 ngày</button>
            <button className={timeRange === '30d' ? 'active' : ''} onClick={() => setTimeRange('30d')}>30 ngày</button>
          </div>
          <button className="primary-action" disabled={runningAnalysis} onClick={runAnalysis}><Play size={17} /> {runningAnalysis ? 'Đang chạy...' : 'Chạy phân tích'}</button>
        </div>
      </section>
      {analysisMessage && <section className="filter-summary"><span>{analysisMessage}</span><span>Khoảng thời gian: {timeRange === '24h' ? '24 giờ' : timeRange === '7d' ? '7 ngày' : '30 ngày'}</span></section>}

      <section className="stat-grid">
        {data.kpis.map((item, index) => {
          const Icon = icons[index];
          return <StatCard key={item.label} {...item} icon={<Icon size={22} />} />;
        })}
      </section>

      <section className="chart-grid">
        <ChartCard title="Xu hướng rủi ro" subtitle="Điểm rủi ro tổng hợp theo thời gian">
          <LineChart data={data.riskTrend} />
        </ChartCard>
        <ChartCard title="Cảnh báo theo mức độ" subtitle="Số lượng cảnh báo đang mở">
          <BarChart data={data.severityVolume} />
        </ChartCard>
        <ChartCard title="Phân bố rủi ro thực thể" subtitle="Tỷ lệ người dùng và thiết bị theo dải điểm">
          <DonutChart data={data.riskDistribution} centerLabel="đã phân loại" />
        </ChartCard>
      </section>

      <section className="two-column-grid">
        <div className="panel-card">
          <div className="section-heading">
            <div>
              <h2>Cảnh báo nghiêm trọng gần đây</h2>
              <p>Hàng đợi ưu tiên cho chuyên viên SOC</p>
            </div>
          </div>
          <div className="alert-list">
            {data.alerts.slice(0, 5).map((alert) => (
              <article className="alert-item" key={alert.id}>
                <div>
                  <div className="alert-title-row"><h3>{alert.title}</h3><SeverityBadge severity={alert.severity} /></div>
                  <p>{alert.explanation}</p>
                  <span>{shortText(alert.user, 'Không xác định')} · {shortText(alert.device, 'Không xác định')} · {formatDateTime(alert.timestamp ?? alert.time)}</span>
                  {alert.numericId != null && (
                    <button
                      type="button"
                      className="secondary-action"
                      style={{ marginTop: 8 }}
                      onClick={() => setChatAlert(alert)}
                    >
                      <MessageSquare size={14} />
                      Thảo luận
                    </button>
                  )}
                </div>
                <RiskScore value={alert.riskScore} />
              </article>
            ))}
          </div>
        </div>

        <div className="panel-card">
          <div className="section-heading">
            <div>
              <h2>Dòng thời gian hoạt động</h2>
              <p>Cập nhật từ nhật ký sự kiện mới nhất</p>
            </div>
          </div>
          <div className="timeline">
            {data.timeline.length === 0 ? (
              <div className="chart-empty">Chưa có nhật ký sự kiện realtime.</div>
            ) : (
              data.timeline.map((event) => (
                <div className={`timeline-row severity-${event.severity}`} key={`${event.time}-${event.title}-${event.detail}`}>
                  <time>{formatDateTime(event.time)}</time>
                  <div>
                    <strong>{event.title}</strong>
                    <p>{event.detail}</p>
                    <span>{event.type}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="panel-card">
        <div className="section-heading">
          <div>
            <h2>Thực thể rủi ro cao</h2>
            <p>Người dùng và thiết bị có độ lệch hồ sơ chuẩn lớn nhất</p>
          </div>
          <Activity size={20} />
        </div>
        <DataTable<RiskyEntity>
          columns={[
            { key: 'name', header: 'Người dùng / thiết bị', minWidth: '220px', render: (e) => <div className="cell-main" title={e.name}><strong>{e.name}</strong></div> },
            { key: 'role', header: 'Vai trò', minWidth: '150px', render: (e) => shortText(e.role, 'Không xác định') },
            { key: 'department', header: 'Phòng ban', minWidth: '150px', render: (e) => shortText(e.department, 'Không xác định') },
            { key: 'device', header: 'Thiết bị', minWidth: '110px', className: 'cell-nowrap', render: (e) => <code>{shortText(e.device, 'Không xác định')}</code> },
            { key: 'lastActivity', header: 'Hoạt động cuối', minWidth: '150px', className: 'cell-nowrap', render: (e) => formatDateTime(e.lastActivity) },
            { key: 'anomaly', header: 'Bất thường', minWidth: '170px', render: (e) => <span className="status-badge status-warning">{shortText(e.anomaly, 'Chưa có')}</span> },
            { key: 'riskScore', header: 'Rủi ro', align: 'center', minWidth: '92px', className: 'cell-risk', sortable: true, value: (e) => e.riskScore, render: (e) => <RiskScore value={e.riskScore} size="sm" /> },
          ]}
          rows={data.riskyEntities}
          rowKey={(e) => e.name}
          initialSort={{ key: 'riskScore', dir: 'desc' }}
        />
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

      <button
        type="button"
        className="global-chat-fab"
        title="Chat với AI"
        onClick={() => {
          if (data && data.alerts.length > 0) {
            setChatAlert(data.alerts[0]);
          } else {
            setAnalysisMessage('Chưa có cảnh báo nào để thảo luận với AI.');
          }
        }}
      >
        <Bot size={24} />
      </button>
    </div>
  );
}
