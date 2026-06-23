import { useEffect } from 'react';
import { useChatStore } from '../../store/chatStore';
import { ChatHeader } from './ChatHeader';
import { ChatInput } from './ChatInput';
import { MessageList } from './MessageList';

interface Props {
  alertId: number;
  alertTitle: string;
  severity?: string;
  onClose: () => void;
  onOpenFeedback: () => void;
}

export function ChatPanel({ alertId, alertTitle, severity, onClose, onOpenFeedback }: Props) {
  const loadHistory = useChatStore((s) => s.loadHistory);
  const loadConversation = useChatStore((s) => s.loadConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const reset = useChatStore((s) => s.reset);
  const error = useChatStore((s) => s.error);
  const conversations = useChatStore((s) => s.conversations);
  const conversationId = useChatStore((s) => s.conversationId);

  useEffect(() => {
    void loadHistory(alertId);
    return () => {
      reset();
    };
  }, [alertId, loadHistory, reset]);

  return (
    <aside className="chat-panel" role="complementary" aria-label="Chat với AI">
      <div className="chat-conversation-list">
        <div className="chat-conversation-head">
          <span>Đoạn chat</span>
          <button type="button" onClick={() => void createConversation(alertId, alertTitle)}>
            Mới
          </button>
        </div>
        <div className="chat-conversation-items">
          {conversations.length === 0 ? (
            <p>Chưa có đoạn chat.</p>
          ) : conversations.map((item) => (
            <button
              type="button"
              key={item.id}
              className={item.id === conversationId ? 'active' : ''}
              onClick={() => void loadConversation(alertId, item.id)}
            >
              <strong>{item.title}</strong>
              <span>{item.message_count} tin nhắn</span>
            </button>
          ))}
        </div>
      </div>
      <div className="chat-main-pane">
        <ChatHeader
          alertId={alertId}
          alertTitle={alertTitle}
          severity={severity}
          onClose={onClose}
          onOpenFeedback={onOpenFeedback}
        />
        {error && <div className="chat-error-banner">Lỗi: {error}</div>}
        <MessageList />
        <ChatInput alertId={alertId} />
      </div>
    </aside>
  );
}
