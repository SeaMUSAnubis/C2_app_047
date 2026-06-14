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
    <section>
      <PageHeader
        title="Devices"
        description="Monitor endpoint devices and their risk levels."
      />

      <div className="filter-bar">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search hostname, department, user..."
          className="search-input"
        />
      </div>

      {filteredDevices.length === 0 ? (
        <EmptyState title="No devices found" />
      ) : (
        <div className="table-container">
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
                  <td>{device.id}</td>
                  <td>{device.hostname}</td>
                  <td>{device.assignedUser ?? '-'}</td>
                  <td>{device.department ?? '-'}</td>
                  <td><StatusBadge status={device.status} /></td>
                  <td><RiskScore value={device.riskScore ?? 0} /></td>
                  <td>{device.openAlerts ?? 0}</td>
                  <td>{formatDate(device.lastSeen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
