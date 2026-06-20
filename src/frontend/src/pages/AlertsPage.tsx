
import { mockAlerts } from '../mocks/mockData';

export default function AlertsPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">Alerts Management</h1>
        <div className="flex gap-2">
          {/* Filters placeholder */}
          <select className="bg-surface border border-border text-sm rounded px-3 py-1.5 text-white">
            <option>All Severities</option>
            <option>High</option>
            <option>Critical</option>
          </select>
          <select className="bg-surface border border-border text-sm rounded px-3 py-1.5 text-white">
            <option>All Status</option>
            <option>New</option>
            <option>Investigating</option>
          </select>
        </div>
      </div>

      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-background border-b border-border text-slate-400">
            <tr>
              <th className="px-4 py-3 font-medium">Alert ID</th>
              <th className="px-4 py-3 font-medium">User</th>
              <th className="px-4 py-3 font-medium">Severity</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Reason</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {mockAlerts.map(alert => (
              <tr key={alert.id} className="hover:bg-background transition-colors">
                <td className="px-4 py-3 font-medium text-white">{alert.id}</td>
                <td className="px-4 py-3">{alert.user_name}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs uppercase font-medium ${alert.severity === 'critical' ? 'bg-red-500/20 text-red-500' : 'bg-orange-500/20 text-orange-500'}`}>
                    {alert.severity}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-1 rounded text-xs uppercase font-medium bg-blue-500/20 text-blue-500">
                    {alert.status}
                  </span>
                </td>
                <td className="px-4 py-3 truncate max-w-[200px]">{alert.main_reason}</td>
                <td className="px-4 py-3">
                  <button className="text-primary hover:underline text-sm font-medium">View Detail</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
