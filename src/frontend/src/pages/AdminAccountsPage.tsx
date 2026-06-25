import { useEffect, useState } from 'react';
import { Lock, Save, UserCog, X } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { DataTable } from '../components/security/DataTable';
import type { Column } from '../components/security/DataTable';
import { StateMessage } from '../components/security/StateMessage';
import { listAccounts, createAccount, updateAccount } from '../lib/apiClient';
import type { AccountRow } from '../lib/apiClient';
import { roleLabel, roleOptions } from '../lib/labels';
import { useAuth } from '../store/useAuth';

interface AccountFormState {
  email: string;
  full_name: string;
  role: string;
  password: string;
}

const emptyForm: AccountFormState = { email: '', full_name: '', role: 'analyst', password: '' };

export default function AdminAccountsPage() {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<AccountFormState>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let ignore = false;
    listAccounts()
      .then((rows) => { if (!ignore) setAccounts(rows); })
      .catch((err: unknown) => { if (!ignore) setError(err instanceof Error ? err.message : 'Không thể tải danh sách tài khoản'); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, []);

  function openCreate() {
    setForm(emptyForm);
    setEditingId(null);
    setFormError('');
    setShowForm(true);
  }

  function openEdit(account: AccountRow) {
    setForm({ email: account.email, full_name: account.full_name, role: account.role, password: '' });
    setEditingId(account.id);
    setFormError('');
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setForm(emptyForm);
    setEditingId(null);
    setFormError('');
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError('');
    setSaving(true);
    try {
      if (editingId) {
        const payload: Partial<{ full_name: string; role: string; is_active: boolean; password: string }> = {
          full_name: form.full_name,
          role: form.role,
        };
        if (form.password) payload.password = form.password;
        await updateAccount(editingId, payload);
      } else {
        await createAccount(form);
      }
      const rows = await listAccounts();
      setAccounts(rows);
      closeForm();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Không thể lưu tài khoản');
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(account: AccountRow) {
    try {
      await updateAccount(account.id, { is_active: !account.is_active });
      const rows = await listAccounts();
      setAccounts(rows);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể đổi trạng thái tài khoản');
    }
  }

  const columns: Column<AccountRow>[] = [
    { key: 'email', header: 'Email', render: (a) => <strong>{a.email}</strong> },
    { key: 'full_name', header: 'Tên' },
    { key: 'role', header: 'Vai trò', render: (a) => <span className="status-pill">{roleLabel(a.role)}</span> },
    { key: 'is_active', header: 'Trạng thái', render: (a) => <span className={a.is_active ? 'status-pill status-active' : 'status-pill status-locked'}>{a.is_active ? 'Hoạt động' : 'Đã khóa'}</span> },
    { key: 'created_at', header: 'Ngày tạo' },
    { key: 'actions', header: 'Thao tác', align: 'center', render: (a) => (
      <div className="row-actions">
        <button className="table-action" onClick={() => openEdit(a)}>Sửa</button>
        {a.id !== Number(user?.id) && (
          <button className="table-action" onClick={() => toggleActive(a)}>{a.is_active ? 'Khóa' : 'Kích hoạt'}</button>
        )}
      </div>
    ) },
  ];

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Quản trị hệ thống" title="Tài khoản hệ thống" description="Tạo, sửa và khóa tài khoản đăng nhập. Không thể xóa tài khoản, chỉ khóa." actions={<button className="secondary-action" onClick={openCreate}><UserCog size={17} /> Thêm tài khoản</button>} />

      <section className="panel-card">
        {loading && <StateMessage variant="loading" title="Đang tải tài khoản..." />}
        {error && <StateMessage variant="error" title="Lỗi tải dữ liệu">{error}</StateMessage>}
        {!loading && !error && accounts.length === 0 && <StateMessage variant="empty">Chưa có tài khoản nào.</StateMessage>}
        <DataTable<AccountRow>
          columns={columns}
          rows={accounts}
          rowKey={(a) => String(a.id)}
          emptyText="Chưa có tài khoản"
        />
      </section>

      {showForm && (
        <div className="modal-overlay" onClick={closeForm}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div className="detail-icon"><Lock size={20} /></div>
              <div>
                <span className="eyebrow">{editingId ? 'Sửa tài khoản' : 'Thêm tài khoản'}</span>
                <h2>{editingId ? form.email : 'Tài khoản mới'}</h2>
              </div>
              <button className="icon-button" aria-label="Đóng" onClick={closeForm}><X size={18} /></button>
            </div>
            <form className="account-form" onSubmit={handleSubmit}>
              <label>Email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required disabled={!!editingId} /></label>
              <label>Tên hiển thị<input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required /></label>
              <label>Vai trò
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  {roleOptions.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </label>
              <label>{editingId ? 'Mật khẩu mới (để trống nếu không đổi)' : 'Mật khẩu'}<input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required={!editingId} minLength={editingId ? 0 : 6} /></label>
              {formError && <div className="form-error">{formError}</div>}
              <div className="modal-actions">
                <button type="button" className="secondary-action" onClick={closeForm}>Hủy</button>
                <button type="submit" className="primary-action" disabled={saving}><Save size={17} /> {saving ? 'Đang lưu...' : 'Lưu'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
