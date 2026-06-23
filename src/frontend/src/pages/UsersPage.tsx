import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, UserRoundCheck } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { DataTable } from '../components/security/DataTable';
import { RiskScore } from '../components/security/RiskScore';
import { StatusBadge } from '../components/security/SeverityBadge';
import { getUsers } from '../lib/apiClient';
import { formatDateTime, riskLevelOptions, shortText } from '../lib/labels';
import type { UserEntity } from '../types/security';

const PAGE_SIZE = 25;

export function UsersPage() {
  const [users, setUsers] = useState<UserEntity[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [departments, setDepartments] = useState<string[]>([]);
  const [selected, setSelected] = useState<UserEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [department, setDepartment] = useState('all');
  const [riskLevel, setRiskLevel] = useState('all');
  const [page, setPage] = useState(1);

  const loadPage = useCallback(async (targetPage: number) => {
    setLoading(true);
    setError('');
    try {
      const { rows, total } = await getUsers({ limit: PAGE_SIZE, offset: (targetPage - 1) * PAGE_SIZE });
      setUsers(rows);
      setTotalCount(total);
      if (targetPage === 1) {
        const depts = Array.from(new Set(rows.map((u) => u.department).filter((d): d is string => Boolean(d)))).sort();
        setDepartments(depts);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể tải người dùng');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    (async () => {
      setLoading(true);
      try {
        const { rows, total } = await getUsers({ limit: PAGE_SIZE, offset: 0 });
        if (ignore) return;
        setUsers(rows);
        setTotalCount(total);
        setSelected(rows[0] ?? null);
        setDepartments(Array.from(new Set(rows.map((u) => u.department).filter((d): d is string => Boolean(d)))).sort());
      } catch (err: unknown) {
        if (!ignore) setError(err instanceof Error ? err.message : 'Không thể tải người dùng');
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => { ignore = true; };
  }, []);

  const filteredUsers = useMemo(() => {
    const term = search.trim().toLowerCase();
    return users.filter((user) => {
      const score = user.riskScore ?? 0;
      const matchesSearch = !term || [user.name, user.account, user.department, user.role]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
      const matchesDepartment = department === 'all' || user.department === department;
      const matchesRisk = riskLevel === 'all'
        || (riskLevel === 'high' && score >= 70)
        || (riskLevel === 'medium' && score >= 45 && score < 70)
        || (riskLevel === 'low' && score < 45);
      return matchesSearch && matchesDepartment && matchesRisk;
    });
  }, [department, riskLevel, search, users]);

  const activeSelected = selected && filteredUsers.some((user) => user.account === selected.account)
    ? selected
    : filteredUsers[0] ?? null;

  function resetFilters() {
    setSearch('');
    setDepartment('all');
    setRiskLevel('all');
  }

  function handlePageChange(next: number) {
    setPage(next);
    loadPage(next);
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Thực thể người dùng" title="Hồ sơ rủi ro người dùng" description="Theo dõi hồ sơ chuẩn, thiết bị thường dùng, số bất thường và giải thích rủi ro." />

      <section className="filter-panel narrow">
        <label><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Tìm người dùng, phòng ban, vai trò..." /></label>
        <select value={department} onChange={(event) => setDepartment(event.target.value)}><option value="all">Tất cả phòng ban</option>{departments.map((item) => <option key={item} value={item}>{item}</option>)}</select>
        <select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)}><option value="all">Tất cả mức rủi ro</option>{riskLevelOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
      </section>

      <section className="filter-summary"><span>Đang hiển thị {filteredUsers.length} / {totalCount} người dùng</span><button className="table-action" onClick={resetFilters}>Xóa lọc</button></section>

      <section className="entity-layout">
        <div className="panel-card">
          {loading && <p>Đang tải người dùng...</p>}
          {error && <p className="error-message">{error}</p>}
          {!loading && !error && users.length === 0 && <p>Chưa có người dùng. Hãy nạp dữ liệu vào cơ sở dữ liệu.</p>}
          {!loading && !error && users.length > 0 && filteredUsers.length === 0 && <p>Không có người dùng khớp bộ lọc.</p>}
          <DataTable<UserEntity>
            columns={[
              { key: 'name', header: 'Người dùng', width: '24%', render: (u) => (<div className="cell-main" title={`${u.name} ${u.account}`}><strong>{u.name}</strong><span className="muted-line">{u.account}</span></div>) },
              { key: 'role', header: 'Vai trò', width: '12%', className: 'col-secondary', render: (u) => shortText(u.role, 'Không xác định') },
              { key: 'department', header: 'Phòng ban', width: '12%', className: 'col-secondary', render: (u) => shortText(u.department, 'Không xác định') },
              { key: 'devices', header: 'Thiết bị', align: 'center', width: '8%' },
              { key: 'lastSeen', header: 'Hoạt động cuối', width: '16%', className: 'cell-nowrap col-optional', render: (u) => formatDateTime(u.lastSeen) },
              { key: 'baseline', header: 'Hồ sơ chuẩn', width: '12%', className: 'col-optional', render: (u) => <StatusBadge value={u.baseline} /> },
              { key: 'anomalies', header: 'Bất thường', align: 'center', width: '7%', sortable: true, value: (u) => u.anomalies ?? 0 },
              { key: 'riskScore', header: 'Rủi ro', align: 'center', width: '8%', className: 'cell-risk', sortable: true, value: (u) => u.riskScore ?? 0, render: (u) => <RiskScore value={u.riskScore ?? 0} size="sm" /> },
            ]}
            rows={filteredUsers}
            rowKey={(u) => u.account}
            onRowClick={(u) => setSelected(u)}
            selectedKey={activeSelected?.account}
            pageSize={PAGE_SIZE}
            total={totalCount}
            currentPage={page}
            onPageChange={handlePageChange}
            emptyText="Không có người dùng khớp bộ lọc"
          />
        </div>

        {activeSelected && <aside className={`detail-panel profile-panel ${(activeSelected.riskScore ?? 0) >= 70 ? 'detail-risk-high' : ''}`}>
          <div className="detail-icon"><UserRoundCheck size={24} /></div>
          <span className="eyebrow">Hồ sơ chuẩn</span>
          <div className="detail-heading-row">
            <div>
              <h2>{activeSelected.name}</h2>
              <p>{activeSelected.account}</p>
            </div>
            <RiskScore value={activeSelected.riskScore ?? 0} size="md" />
          </div>
          <p>{shortText(activeSelected.explanation, 'Chưa có giải thích hồ sơ chuẩn.')}</p>
          <div className="profile-grid">
            <div><span>Giờ đăng nhập thường lệ</span><strong>{shortText(activeSelected.loginHours)}</strong></div>
            <div><span>Thiết bị phổ biến</span><strong>{shortText(activeSelected.commonDevices)}</strong></div>
            <div><span>Số bất thường</span><strong>{activeSelected.anomalies}</strong></div>
            <div><span>Trạng thái hồ sơ chuẩn</span><StatusBadge value={activeSelected.baseline} /></div>
          </div>
        </aside>}
      </section>
    </div>
  );
}
