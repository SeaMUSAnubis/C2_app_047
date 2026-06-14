import { useEffect, useMemo, useState } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { getLogs } from '../lib/apiClient';
import { formatDate } from '../lib/format';
import type { EventLog } from '../types/log';

export function LogsPage() {
  const [logs, setLogs] = useState<EventLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  useEffect(() => {
    getLogs()
      .then((data) => setLogs(data as EventLog[]))
      .finally(() => setLoading(false));
  }, []);

  const filteredLogs = useMemo(() => {
    const keyword = query.toLowerCase();
    return logs.filter((log) => {
      return (
        log.eventType.toLowerCase().includes(keyword) ||
        log.action.toLowerCase().includes(keyword) ||
        log.userId?.toLowerCase().includes(keyword) ||
        log.deviceId?.toLowerCase().includes(keyword)
      );
    });
  }, [logs, query]);

  if (loading) return <LoadingState message="Loading logs..." />;

  return (
    <section>
      <PageHeader
        title="Event Logs"
        description="Raw system and endpoint event logs."
      />

      <div className="filter-bar">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search user, device, action, type..."
          className="search-input"
        />
      </div>

      {filteredLogs.length === 0 ? (
        <EmptyState title="No logs found" />
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Event Type</th>
                <th>User</th>
                <th>Device</th>
                <th>Action</th>
                <th>Source File</th>
                <th>Raw Detail</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((log) => (
                <tr key={log.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{formatDate(log.timestamp)}</td>
                  <td><span className="event-type-badge">{log.eventType}</span></td>
                  <td>{log.userId ?? '-'}</td>
                  <td>{log.deviceId ?? '-'}</td>
                  <td>{log.action}</td>
                  <td>{log.sourceFile ?? '-'}</td>
                  <td className="log-detail-cell" title={log.rawDetail}>{log.rawDetail ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
