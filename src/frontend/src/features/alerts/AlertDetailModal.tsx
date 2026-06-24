import { useState } from 'react';
import { ChatPanel } from '../chat/ChatPanel';
import { FeedbackModal } from '../chat/FeedbackModal';

interface AlertLike {
  id: number;
  title?: string;
  severity?: string;
  explanation?: string | null;
  user?: string;
  device?: string;
  risk_score?: number;
}

interface Props {
  alert: AlertLike | null;
  onClose: () => void;
}

export function AlertDetailModal({ alert, onClose }: Props) {
  const [chatOpen, setChatOpen] = useState(true);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  if (!alert) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="alert-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="alert-detail-header">
          <div>
            <h2>{alert.title ?? `Alert #${alert.id}`}</h2>
            <div className="alert-detail-meta">
              {alert.user && <span>Người dùng <strong>{alert.user}</strong></span>}
              {alert.device && <span>Thiết bị <strong>{alert.device}</strong></span>}
              {alert.risk_score != null && <span>Rủi ro <strong>{alert.risk_score}</strong></span>}
            </div>
          </div>
          <div className="alert-detail-actions">
            <button
              type="button"
              className="secondary-action"
              onClick={() => setChatOpen((v) => !v)}
            >
              {chatOpen ? 'Ẩn chat' : 'Mở chat'}
            </button>
            <button type="button" className="secondary-action" onClick={() => setFeedbackOpen(true)}>
              Gửi feedback
            </button>
            <button type="button" className="icon-button" onClick={onClose} aria-label="Đóng">×</button>
          </div>
        </div>
        <div className="alert-detail-body">
          {chatOpen && (
            <ChatPanel
              alertId={alert.id}
              alertTitle={alert.title ?? `Alert #${alert.id}`}
              severity={alert.severity}
              onClose={() => setChatOpen(false)}
              onOpenFeedback={() => setFeedbackOpen(true)}
            />
          )}
        </div>
        {feedbackOpen && (
          <FeedbackModal
            alertId={alert.id}
            onClose={() => setFeedbackOpen(false)}
            onSubmitted={() => {/* could show toast */}}
          />
        )}
      </div>
    </div>
  );
}
