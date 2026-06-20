import { mockBlockedWebsites } from '../mocks/mockData';
import { useAuth } from '../store/authStore';

export default function AdminBlockedWebsitesPage() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Blocked Websites</h1>
          <p className="text-sm text-slate-400 mt-1">Manage domains/URLs blocked based on UEBA alerts</p>
        </div>
        <button className="bg-primary hover:bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
          Add Blocked Website
        </button>
      </div>

      {user?.role !== 'admin' && (
        <div className="bg-red-500/10 border border-red-500/50 text-red-500 p-4 rounded-lg">
          Warning: This page is restricted to Admin users only.
        </div>
      )}

      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-background border-b border-border text-slate-400">
            <tr>
              <th className="px-4 py-3 font-medium">Domain / URL</th>
              <th className="px-4 py-3 font-medium">Reason</th>
              <th className="px-4 py-3 font-medium">Source Alert</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {mockBlockedWebsites.map(bw => (
              <tr key={bw.id} className="hover:bg-background transition-colors">
                <td className="px-4 py-3">
                  <div className="font-medium text-white">{bw.domain}</div>
                  <div className="text-xs text-slate-500">{bw.url}</div>
                </td>
                <td className="px-4 py-3">{bw.reason}</td>
                <td className="px-4 py-3 text-primary">{bw.source_alert_id}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-1 rounded text-xs uppercase font-medium bg-green-500/20 text-green-500">
                    {bw.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button className="text-slate-400 hover:text-white mr-3">Edit</button>
                  <button className="text-red-500 hover:text-red-400">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
