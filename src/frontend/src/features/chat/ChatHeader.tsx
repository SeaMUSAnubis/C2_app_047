import { useChatStore } from '../../store/chatStore';
import { severityLabel } from '../../lib/labels';
import type { Severity } from '../../types/security';

interface Props {
  alertId: number;
  alertTitle: string;
  severity?: string;
  onClose: () => void;
  onOpenFeedback: () => void;
}

export function ChatHeader({ alertId, alertTitle, severity, onOpenFeedback }: Props) {
  const resetConversation = useChatStore((s) => s.resetConversation);
  const messages = useChatStore((s) => s.messages);
  const usedMemoryIds = useChatStore((s) => s.usedMemoryIds);
  const title = useChatStore((s) => s.title);
  const displayTitle = title || alertTitle;

  return (
    <div className="chat-header">
      <div className="chat-header-info">
        <div>
          <h3>AI Phân tích</h3>
          <p className="chat-header-subtitle">
            {displayTitle}
            {severity && (
              <span className={`severity-pill severity-pill--${severity}`}>
                {severityLabel(severity as Severity)}
              </span>
            )}
          </p>
        </div>
      </div>
      <div className="chat-header-actions">
        {usedMemoryIds.length > 0 && (
          <span className="chat-memory-badge" title="Tin nhắn gần nhất đã dùng memory">
            🧠 {usedMemoryIds.length}
          </span>
        )}
        {messages.length > 0 && (
          <button
            type="button"
            className="secondary-action"
            onClick={() => {
              if (confirm('Xóa toàn bộ lịch sử hội thoại?')) {
                void resetConversation(alertId);
              }
            }}
          >
            Xoá lịch sử
          </button>
        )}
        <button type="button" className="secondary-action" onClick={onOpenFeedback}>
          Gửi phản hồi
        </button>
      </div>
    </div>
  );
}
