import { useEffect, useMemo, useState } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { RiskScore } from '../components/common/RiskScore';
import { StatusBadge } from '../components/common/StatusBadge';
import { getDevices } from '../lib/apiClient';
import { formatDate } from '../lib/format';
import type { Device } from '../types/device';

export function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  useEffect(() => {
    getDevices()
      .then((data) => setDevices(data as Device[]))
      .finally(() => setLoading(false));
  }, []);

  const filteredDevices = useMemo(() => {
    const keyword = query.toLowerCase();
    return devices.filter((device) => {
      return (
        device.id.toLowerCase().includes(keyword) ||
        device.hostname.toLowerCase().includes(keyword) ||
        device.department?.toLowerCase().includes(keyword) ||
        device.assignedUser?.toLowerCase().includes(keyword)
      );
    });
  }, [devices, query]);

  if (loading) return <LoadingState message="Loading devices..." />;

  return (
    <section className="devices-page p-6 max-w-6xl mx-auto animated-bg min-h-[calc(100vh-64px)] rounded-xl">
      <PageHeader
        title="Devices"
        description="Monitor endpoint devices and their risk levels."
      />

      <div className="glass-panel hover-glow mt-6">
        <div className="filter-bar mb-6">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search hostname, department, user..."
            className="search-input bg-gray-900/50 border-gray-700/50 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 rounded-lg w-full max-w-md placeholder-gray-500 transition-all"
          />
        </div>

        {filteredDevices.length === 0 ? (
          <EmptyState title="No devices found" />
        ) : (
          <div className="table-container shadow-2xl">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Device ID</th>
                  <th>Hostname</th>
                  <th>Assigned User</th>
                  <th>Department</th>
                  <th>Status</th>
                  <th>Risk</th>
                  <th>Open Alerts</th>
                  <th>Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {filteredDevices.map((device) => (
                  <tr key={device.id}>
                    <td className="font-mono text-blue-300">{device.id}</td>
                    <td className="font-semibold text-white">{device.hostname}</td>
                    <td>{device.assignedUser ?? '-'}</td>
                    <td><span className="bg-gray-800/60 px-2 py-1 rounded text-gray-300">{device.department ?? '-'}</span></td>
                    <td><StatusBadge status={device.status} /></td>
                    <td><RiskScore value={device.riskScore ?? 0} /></td>
                    <td>
                      {device.openAlerts && device.openAlerts > 0 ? (
                        <span className="text-red-400 font-bold bg-red-900/30 px-2 py-1 rounded-full">{device.openAlerts}</span>
                      ) : (
                        <span className="text-gray-500">0</span>
                      )}
                    </td>
                    <td className="text-gray-400">{formatDate(device.lastSeen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
