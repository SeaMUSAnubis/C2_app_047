import { useChatStore } from '../../store/chatStore';

interface Props {
  alertId: number;
  alertTitle: string;
  severity?: string;
  onClose: () => void;
  onOpenFeedback: () => void;
}

export function ChatHeader({ alertId, alertTitle, severity, onClose, onOpenFeedback }: Props) {
  const resetConversation = useChatStore((s) => s.resetConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const updateTitle = useChatStore((s) => s.updateTitle);
  const messages = useChatStore((s) => s.messages);
  const usedMemoryIds = useChatStore((s) => s.usedMemoryIds);
  const title = useChatStore((s) => s.title);
  const displayTitle = title || alertTitle;

  return (
    <div className="chat-header">
      <div className="chat-header-info">
        <button type="button" className="icon-button" onClick={onClose} aria-label="Đóng chat">
          ×
        </button>
        <div>
          <h3>Thảo luận với AI</h3>
          <p className="chat-header-subtitle">
            {displayTitle}
            {severity && <span className={`severity-pill severity-pill--${severity}`}>{severity}</span>}
          </p>
        </div>
      </div>
      <div className="chat-header-actions">
        {usedMemoryIds.length > 0 && (
          <span className="chat-memory-badge" title="Tin nhắn gần nhất đã dùng memory">
            🧠 {usedMemoryIds.length}
          </span>
        )}
        <button type="button" className="secondary-action" onClick={onOpenFeedback}>
          Gửi feedback
        </button>
        <button
          type="button"
          className="secondary-action"
          onClick={() => {
            const next = prompt('Đổi tiêu đề hội thoại', displayTitle);
            if (next && next.trim() && next.trim() !== displayTitle) {
              void updateTitle(alertId, next.trim());
            }
          }}
          disabled={messages.length === 0}
        >
          Đổi tên
        </button>
        <button
          type="button"
          className="secondary-action"
          onClick={() => {
            if (confirm('Xóa toàn bộ lịch sử hội thoại?')) {
              void resetConversation(alertId);
            }
          }}
          disabled={messages.length === 0}
        >
          Reset
        </button>
        <button
          type="button"
          className="secondary-action table-action--danger"
          onClick={() => {
            if (confirm('Xóa hẳn hội thoại này?')) {
              void deleteConversation(alertId);
            }
          }}
          disabled={messages.length === 0}
        >
          Xóa
        </button>
      </div>
    </div>
  );
}
