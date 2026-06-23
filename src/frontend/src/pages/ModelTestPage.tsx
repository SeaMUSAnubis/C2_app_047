import { useMemo, useState } from 'react';
import { BrainCircuit, PlayCircle } from 'lucide-react';
import { PageHeader } from '../components/layout/PageHeader';
import { RiskScore } from '../components/security/RiskScore';
import { SeverityBadge } from '../components/security/SeverityBadge';
import type { Severity } from '../types/security';

export default function ModelTestPage() {
  const [form, setForm] = useState({ user_id: 'nguyenvana', device_id: 'HN-LAP-024', event_type: 'off_hours_login', hour: 2, source_ip: '203.113.45.21', resource: 'finance-share/contracts', action_count: 42 });
  const [submitted, setSubmitted] = useState(false);

  const result = useMemo(() => {
    const hourRisk = form.hour < 6 || form.hour > 21 ? 28 : 8;
    const eventRisk = form.event_type.includes('privilege') ? 32 : form.event_type.includes('bulk') ? 26 : form.event_type.includes('off_hours') ? 24 : 12;
    const actionRisk = Math.min(24, Math.round(form.action_count / 2));
    const riskScore = Math.min(99, hourRisk + eventRisk + actionRisk + 18);
    const severity: Severity = riskScore >= 85 ? 'critical' : riskScore >= 70 ? 'high' : riskScore >= 45 ? 'medium' : 'low';
    return { anomalyScore: Number((riskScore / 100).toFixed(2)), riskScore, severity };
  }, [form]);

  function updateField(name: string, value: string | number) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Kiểm thử mô hình" title="Thử suy luận điểm rủi ro" description="Nhập một sự kiện giả lập để kiểm tra giao diện kết quả điểm bất thường và điểm rủi ro. Phần này đang dùng bộ nối mô phỏng, tách riêng để nối API sau." />

      <section className="model-test-grid">
        <form className="panel-card model-form" onSubmit={(event) => { event.preventDefault(); setSubmitted(true); }}>
          <label>Mã người dùng<input value={form.user_id} onChange={(event) => updateField('user_id', event.target.value)} /></label>
          <label>Mã thiết bị<input value={form.device_id} onChange={(event) => updateField('device_id', event.target.value)} /></label>
          <label>Loại sự kiện<select value={form.event_type} onChange={(event) => updateField('event_type', event.target.value)}><option value="off_hours_login">Đăng nhập ngoài giờ</option><option value="bulk_download">Tải hàng loạt</option><option value="failed_login_spike">Đăng nhập lỗi tăng đột biến</option><option value="privilege_escalation">Leo thang đặc quyền</option><option value="impossible_travel">Di chuyển không khả thi</option></select></label>
          <label>Giờ trong ngày<input type="number" min="0" max="23" value={form.hour} onChange={(event) => updateField('hour', Number(event.target.value))} /></label>
          <label>IP nguồn<input value={form.source_ip} onChange={(event) => updateField('source_ip', event.target.value)} /></label>
          <label>Tài nguyên<input value={form.resource} onChange={(event) => updateField('resource', event.target.value)} /></label>
          <label>Số thao tác<input type="number" min="0" value={form.action_count} onChange={(event) => updateField('action_count', Number(event.target.value))} /></label>
          <button className="primary-action" type="submit"><PlayCircle size={17} /> Dự đoán rủi ro</button>
        </form>

        <aside className="detail-panel result-panel">
          <div className="detail-icon"><BrainCircuit size={24} /></div>
          <span className="eyebrow">Kết quả dự đoán</span>
          <h2>{submitted ? 'Sự kiện có dấu hiệu bất thường' : 'Sẵn sàng kiểm thử'}</h2>
          <div className="result-metrics">
            <div><span>Điểm bất thường</span><strong>{submitted ? result.anomalyScore : '--'}</strong></div>
            <div><span>Điểm rủi ro</span>{submitted ? <RiskScore value={result.riskScore} /> : <strong>--</strong>}</div>
            <div><span>Mức độ</span>{submitted ? <SeverityBadge severity={result.severity} /> : <strong>--</strong>}</div>
          </div>
          <h3>Giải thích</h3>
          <p>{submitted ? `Sự kiện ${form.event_type} từ ${form.source_ip} có điểm cao do thời gian, loại hành vi và số lượng thao tác lệch khỏi hồ sơ chuẩn.` : 'Nhấn “Dự đoán rủi ro” để tạo kết quả mô phỏng. Khi dịch vụ ML sẵn sàng, bộ nối trong API client có thể được nối vào đường dẫn /ml/predict.'}</p>
        </aside>
      </section>
    </div>
  );
}
