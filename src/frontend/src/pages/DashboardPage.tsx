import { useEffect, useState } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { KpiCard } from '../components/common/KpiCard';
import { LoadingState } from '../components/common/LoadingState';
import { getDashboardSummary } from '../lib/apiClient';
import type { DashboardSummary } from '../types/dashboard';

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    getDashboardSummary().then(data => setSummary(data as DashboardSummary));
  }, []);

  if (!summary) return <LoadingState message="Loading dashboard..." />;

  return (
    <section>
      <PageHeader
        title="Overview"
        description="UEBA endpoint monitoring summary"
      />

      <div className="kpi-grid">
        <KpiCard label="Total Users" value={summary.totalUsers} />
        <KpiCard label="Total Devices" value={summary.totalDevices} />
        <KpiCard label="Total Logs" value={summary.totalLogs} />
        <KpiCard label="Open Alerts" value={summary.openAlerts} />
        <KpiCard label="High/Critical" value={summary.highCriticalAlerts} />
        <KpiCard label="Avg Risk" value={summary.averageRiskScore} />
      </div>
    </section>
  );
}
