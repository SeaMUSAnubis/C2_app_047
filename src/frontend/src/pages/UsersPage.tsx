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
    <section className="users-page p-6 max-w-6xl mx-auto animated-bg min-h-[calc(100vh-64px)] rounded-xl">
      <PageHeader
        title="Users"
        description="Monitor user accounts, departments, status and risk score."
      />

      <div className="glass-panel hover-glow mt-6">
        <div className="filter-bar mb-6">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search user, account, department..."
            className="search-input bg-gray-900/50 border-gray-700/50 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 rounded-lg w-full max-w-md placeholder-gray-500 transition-all"
          />
        </div>

        {filteredUsers.length === 0 ? (
          <EmptyState title="No users found" />
        ) : (
          <div className="table-container shadow-2xl">
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
                    <td className="font-mono text-purple-300 font-medium">{user.id}</td>
                    <td className="font-semibold text-white">{user.account}</td>
                    <td><span className="bg-gray-800/60 px-2 py-1 rounded text-gray-300">{user.department ?? '-'}</span></td>
                    <td><StatusBadge status={user.status} /></td>
                    <td><RiskScore value={user.riskScore ?? 0} /></td>
                    <td className="text-gray-300">{user.assignedDevices ?? 0}</td>
                    <td>
                      {user.openAlerts && user.openAlerts > 0 ? (
                        <span className="text-red-400 font-bold bg-red-900/30 px-2 py-1 rounded-full">{user.openAlerts}</span>
                      ) : (
                        <span className="text-gray-500">0</span>
                      )}
                    </td>
                    <td className="text-gray-400">{formatDate(user.lastSeen)}</td>
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
