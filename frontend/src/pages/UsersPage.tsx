import { useEffect, useMemo, useState } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { RiskScore } from '../components/common/RiskScore';
import { StatusBadge } from '../components/common/StatusBadge';
import { getUsers } from '../lib/apiClient';
import { formatDate } from '../lib/format';
import type { User } from '../types/user';

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  useEffect(() => {
    getUsers()
      .then((data) => setUsers(data as User[]))
      .finally(() => setLoading(false));
  }, []);

  const filteredUsers = useMemo(() => {
    const keyword = query.toLowerCase();
    return users.filter((user) => {
      return (
        user.id.toLowerCase().includes(keyword) ||
        user.account.toLowerCase().includes(keyword) ||
        user.department?.toLowerCase().includes(keyword)
      );
    });
  }, [users, query]);

  if (loading) return <LoadingState message="Loading users..." />;

  return (
    <section>
      <PageHeader
        title="Users"
        description="Monitor user accounts, departments, status and risk score."
      />

      <div className="filter-bar">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search user, account, department..."
          className="search-input"
        />
      </div>

      {filteredUsers.length === 0 ? (
        <EmptyState title="No users found" />
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Account</th>
                <th>Department</th>
                <th>Status</th>
                <th>Risk</th>
                <th>Devices</th>
                <th>Open Alerts</th>
                <th>Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>{user.account}</td>
                  <td>{user.department ?? '-'}</td>
                  <td><StatusBadge status={user.status} /></td>
                  <td><RiskScore value={user.riskScore ?? 0} /></td>
                  <td>{user.assignedDevices ?? 0}</td>
                  <td>{user.openAlerts ?? 0}</td>
                  <td>{formatDate(user.lastSeen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
