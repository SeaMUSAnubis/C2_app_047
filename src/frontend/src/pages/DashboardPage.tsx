import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, Database, Monitor, Play, ShieldCheck, TrendingUp, Users } from 'lucide-react';
import { ChartCard } from '../components/security/ChartCard';
import { BarChart, DonutChart, LineChart } from '../components/security/Charts';
import { DataTable } from '../components/security/DataTable';
import { RiskScore } from '../components/security/RiskScore';
import { SeverityBadge } from '../components/security/SeverityBadge';
import { StatCard } from '../components/security/StatCard';
import { analyzeAllDemo, getDashboardOverview } from '../lib/apiClient';
import type { DashboardOverview, RiskyEntity } from '../types/security';

const icons = [Users, Monitor, Database, AlertTriangle, ShieldCheck, TrendingUp];

export default function DashboardPage() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [timeRange, setTimeRange] = useState('24h');
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
    getDashboardOverview()
      .then((result) => {
        if (!ignore) setData(result);
      })
      .catch((err: unknown) => {
        if (!ignore) setError(err instanceof Error ? err.message : 'Không thể tải dashboard từ API');
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => { ignore = true; };
  }, []);

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
          <DonutChart data={data.riskDistribution} />
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
                  <span>{alert.user} · {alert.device} · {alert.time}</span>
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
              <p>Các sự kiện bất thường trong 24 giờ gần nhất</p>
            </div>
          </div>
          <div className="timeline">
            {data.timeline.map((event) => (
              <div className={`timeline-row severity-${event.severity}`} key={`${event.time}-${event.title}`}>
                <time>{event.time}</time>
                <div>
                  <strong>{event.title}</strong>
                  <p>{event.detail}</p>
                  <span>{event.type}</span>
                </div>
              </div>
            ))}
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
            { key: 'name', header: 'Người dùng / thiết bị', render: (e) => <strong>{e.name}</strong> },
            { key: 'role', header: 'Vai trò' },
            { key: 'department', header: 'Phòng ban' },
            { key: 'device', header: 'Thiết bị', render: (e) => <code>{e.device}</code> },
            { key: 'lastActivity', header: 'Hoạt động cuối' },
            { key: 'anomaly', header: 'Bất thường' },
            { key: 'riskScore', header: 'Rủi ro', align: 'right', sortable: true, value: (e) => e.riskScore, render: (e) => <RiskScore value={e.riskScore} size="sm" /> },
          ]}
          rows={data.riskyEntities}
          rowKey={(e) => e.name}
          initialSort={{ key: 'riskScore', dir: 'desc' }}
        />
      </section>
    </div>
  );
}
