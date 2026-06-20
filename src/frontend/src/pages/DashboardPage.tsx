
import { mockDashboardSummary, mockAlerts } from '../mocks/mockData';
import { Users, Monitor, FileText, ShieldAlert } from 'lucide-react';

export default function DashboardPage() {
  const stats = [
    { label: 'Total Users', value: mockDashboardSummary.total_users, icon: <Users size={24} className="text-blue-500" /> },
    { label: 'Total Devices', value: mockDashboardSummary.total_devices, icon: <Monitor size={24} className="text-indigo-500" /> },
    { label: 'Total Logs', value: mockDashboardSummary.total_logs, icon: <FileText size={24} className="text-emerald-500" /> },
    { label: 'Active Alerts', value: mockDashboardSummary.active_alerts, icon: <ShieldAlert size={24} className="text-red-500" /> },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard Overview</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-surface border border-border rounded-xl p-4 flex items-center gap-4">
            <div className="bg-background p-3 rounded-lg">
              {stat.icon}
            </div>
            <div>
              <div className="text-sm text-slate-400">{stat.label}</div>
              <div className="text-2xl font-bold text-white">{stat.value}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-surface border border-border rounded-xl p-4">
          <h2 className="font-semibold text-lg text-white mb-4">Recent Alerts</h2>
          <div className="space-y-3">
            {mockAlerts.map(alert => (
              <div key={alert.id} className="bg-background rounded-lg p-3 border border-border flex justify-between items-center">
                <div>
                  <div className="text-sm font-medium text-white">{alert.main_reason}</div>
                  <div className="text-xs text-slate-400">User: {alert.user_name} • Device: {alert.device_id}</div>
                </div>
                <div className={`px-2 py-1 rounded text-xs font-medium uppercase ${alert.severity === 'critical' ? 'bg-red-500/20 text-red-500' : 'bg-orange-500/20 text-orange-500'}`}>
                  {alert.severity}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-surface border border-border rounded-xl p-4">
          <h2 className="font-semibold text-lg text-white mb-4">Risk Distribution</h2>
          <div className="flex h-48 items-center justify-center text-slate-400 border border-dashed border-border rounded-lg bg-background">
            Chart Placeholder (Requires Chart.js or Recharts)
          </div>
        </div>
      </div>
    </div>
  );
}
