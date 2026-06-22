import { useCallback, useEffect, useMemo, useState } from 'react';
import { HardDrive, Search } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { DataTable } from '../components/security/DataTable';
import { RiskScore } from '../components/security/RiskScore';
import { getDevices } from '../lib/apiClient';
import type { DeviceEntity } from '../types/security';

const PAGE_SIZE = 25;

export function DevicesPage() {
  const [devices, setDevices] = useState<DeviceEntity[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [osOptions, setOsOptions] = useState<string[]>([]);
  const [postureOptions, setPostureOptions] = useState<string[]>([]);
  const [selected, setSelected] = useState<DeviceEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [posture, setPosture] = useState('all');
  const [os, setOs] = useState('all');
  const [page, setPage] = useState(1);

  const loadPage = useCallback(async (targetPage: number) => {
    setLoading(true);
    setError('');
    try {
      const { rows, total } = await getDevices({ limit: PAGE_SIZE, offset: (targetPage - 1) * PAGE_SIZE });
      setDevices(rows);
      setTotalCount(total);
      if (targetPage === 1) {
        setOsOptions(Array.from(new Set(rows.map((d) => d.os).filter((v): v is string => Boolean(v)))).sort());
        setPostureOptions(Array.from(new Set(rows.map((d) => d.posture ?? d.status).filter((v): v is string => Boolean(v)))).sort());
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể tải thiết bị');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    (async () => {
      setLoading(true);
      try {
        const { rows, total } = await getDevices({ limit: PAGE_SIZE, offset: 0 });
        if (ignore) return;
        setDevices(rows);
        setTotalCount(total);
        setSelected(rows[0] ?? null);
        setOsOptions(Array.from(new Set(rows.map((d) => d.os).filter((v): v is string => Boolean(v)))).sort());
        setPostureOptions(Array.from(new Set(rows.map((d) => d.posture ?? d.status).filter((v): v is string => Boolean(v)))).sort());
      } catch (err: unknown) {
        if (!ignore) setError(err instanceof Error ? err.message : 'Không thể tải thiết bị');
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => { ignore = true; };
  }, []);

  const filteredDevices = useMemo(() => {
    const term = search.trim().toLowerCase();
    return devices.filter((device) => {
      const matchesSearch = !term || [device.id, device.hostname, device.owner, device.assignedUser, device.ip, device.os]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
      const matchesPosture = posture === 'all' || device.posture === posture || device.status === posture;
      const matchesOs = os === 'all' || device.os === os;
      return matchesSearch && matchesPosture && matchesOs;
    });
  }, [devices, os, posture, search]);

  const activeSelected = selected && filteredDevices.some((device) => device.id === selected.id)
    ? selected
    : filteredDevices[0] ?? null;

  function resetFilters() {
    setSearch('');
    setPosture('all');
    setOs('all');
  }

  function handlePageChange(next: number) {
    setPage(next);
    loadPage(next);
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Kiểm kê thiết bị" title="Thiết bị và tình trạng rủi ro" description="Theo dõi chủ sở hữu, hệ điều hành, IP, tình trạng bảo mật và số sự kiện đáng ngờ." />

      <section className="filter-panel narrow">
        <label><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Tìm tên máy, chủ sở hữu, IP..." /></label>
        <select value={posture} onChange={(event) => setPosture(event.target.value)}><option value="all">Tất cả tình trạng</option>{postureOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select>
        <select value={os} onChange={(event) => setOs(event.target.value)}><option value="all">Tất cả hệ điều hành</option>{osOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select>
      </section>

      <section className="filter-summary"><span>Đang hiển thị {filteredDevices.length} / {totalCount} thiết bị</span><button className="table-action" onClick={resetFilters}>Xóa lọc</button></section>

      <section className="entity-layout">
        <div className="panel-card">
          {loading && <p>Đang tải thiết bị...</p>}
          {error && <p className="error-message">{error}</p>}
          {!loading && !error && devices.length === 0 && <p>Chưa có thiết bị. Hãy nạp dữ liệu vào cơ sở dữ liệu.</p>}
          {!loading && !error && devices.length > 0 && filteredDevices.length === 0 && <p>Không có thiết bị khớp bộ lọc.</p>}

          <DataTable<DeviceEntity>
            columns={[
              { key: 'id', header: 'Thiết bị', render: (d) => <code>{d.id}</code> },
              { key: 'owner', header: 'Chủ sở hữu', render: (d) => d.owner ?? d.assignedUser ?? 'Chưa gán' },
              { key: 'os', header: 'Hệ điều hành', render: (d) => d.os ?? 'Không rõ' },
              { key: 'ip', header: 'IP', render: (d) => d.ip ?? '-' },
              { key: 'lastSeen', header: 'Hoạt động cuối' },
              { key: 'suspiciousEvents', header: 'Sự kiện đáng ngờ', align: 'right', sortable: true, value: (d) => d.suspiciousEvents ?? 0 },
              { key: 'posture', header: 'Tình trạng', render: (d) => <span className="status-pill">{d.posture ?? d.status}</span> },
              { key: 'riskScore', header: 'Rủi ro', align: 'right', sortable: true, value: (d) => d.riskScore ?? 0, render: (d) => <RiskScore value={d.riskScore ?? 0} size="sm" /> },
            ]}
            rows={filteredDevices}
            rowKey={(d) => d.id}
            onRowClick={(d) => setSelected(d)}
            selectedKey={activeSelected?.id}
            pageSize={PAGE_SIZE}
            total={totalCount}
            currentPage={page}
            onPageChange={handlePageChange}
            emptyText="Không có thiết bị khớp bộ lọc"
          />
        </div>

        {activeSelected && <aside className="detail-panel profile-panel">
          <div className="detail-icon"><HardDrive size={24} /></div>
          <span className="eyebrow">Chi tiết thiết bị</span>
          <h2>{activeSelected.hostname ?? activeSelected.id}</h2>
          <p>{activeSelected.id} thuộc {activeSelected.owner ?? activeSelected.assignedUser ?? 'người dùng chưa xác định'} với tình trạng {activeSelected.posture ?? activeSelected.status ?? 'chưa rõ'}.</p>
          <div className="profile-grid">
            <div><span>Hệ điều hành</span><strong>{activeSelected.os ?? 'Không rõ'}</strong></div>
            <div><span>IP</span><strong>{activeSelected.ip ?? '-'}</strong></div>
            <div><span>Hoạt động cuối</span><strong>{activeSelected.lastSeen ?? '-'}</strong></div>
            <div><span>Sự kiện đáng ngờ</span><strong>{activeSelected.suspiciousEvents ?? 0}</strong></div>
          </div>
          <h3>Đánh giá tình trạng</h3>
          <p>Thiết bị này đang được ưu tiên theo điểm rủi ro và số sự kiện bất thường lấy trực tiếp từ cơ sở dữ liệu.</p>
          <h3>Hành động gợi ý <span className="hint-tag">(chung)</span></h3>
          <ul>
            <li>Kiểm tra phiên đăng nhập gần nhất và IP nguồn.</li>
            <li>Đối chiếu chủ sở hữu với hồ sơ chuẩn của người dùng.</li>
            <li>Ưu tiên cô lập nếu điểm rủi ro vượt mức cao.</li>
          </ul>
        </aside>}
      </section>
    </div>
  );
}
