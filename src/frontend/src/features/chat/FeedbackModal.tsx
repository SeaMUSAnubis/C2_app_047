import { useState } from 'react';
import { submitFeedback, type FeedbackVerdict } from '../../lib/apiClient';

interface Props {
  alertId: number;
  onClose: () => void;
  onSubmitted?: () => void;
}

const VERDICTS: { value: FeedbackVerdict; label: string; tone: string }[] = [
  { value: 'true_positive', label: 'Đúng - Có bất thường', tone: 'danger' },
  { value: 'false_positive', label: 'Sai - Dương tính giả', tone: 'success' },
  { value: 'benign', label: 'Lành tính', tone: 'info' },
  { value: 'needs_investigation', label: 'Cần điều tra thêm', tone: 'warn' },
];

export function FeedbackModal({ alertId, onClose, onSubmitted }: Props) {
  const [verdict, setVerdict] = useState<FeedbackVerdict | null>(null);
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!verdict) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitFeedback(alertId, { verdict, note: note.trim() || undefined });
      onSubmitted?.();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Đánh giá alert #{alertId}</h3>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Đóng">×</button>
        </div>
        <p className="text-muted">
          Phản hồi này sẽ được dùng để cải thiện chất lượng giải thích cho các alert tương tự trong tương lai.
        </p>
        <div className="feedback-verdict-row">
          {VERDICTS.map((v) => (
            <button
              key={v.value}
              type="button"
              className={`status-pill status-pill--${v.tone} feedback-verdict ${verdict === v.value ? 'feedback-verdict--active' : ''}`}
              onClick={() => setVerdict(v.value)}
            >
              {v.label}
            </button>
          ))}
        </div>
        <label className="feedback-note">
          <span>Ghi chú (tuỳ chọn)</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder="Lý do phân loại, bằng chứng bổ sung, v.v."
            maxLength={2000}
          />
        </label>
        {error && <div className="state-error"><p>{error}</p></div>}
        <div className="modal-actions">
          <button type="button" className="secondary-action" onClick={onClose} disabled={submitting}>
            Hủy
          </button>
          <button
            type="button"
            className="primary-action"
            onClick={handleSubmit}
            disabled={!verdict || submitting}
          >
            {submitting ? 'Đang gửi…' : 'Gửi feedback'}
          </button>
        </div>
      </div>
    </div>
  );
}
