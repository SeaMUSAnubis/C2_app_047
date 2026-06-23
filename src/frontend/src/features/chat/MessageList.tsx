import { useEffect, useRef } from 'react';
import { useChatStore } from '../../store/chatStore';
import { MessageBubble } from './MessageBubble';

export function MessageList() {
  const messages = useChatStore((s) => s.messages);
  const isLoadingHistory = useChatStore((s) => s.isLoadingHistory);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const error = useChatStore((s) => s.error);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, isStreaming]);

  if (isLoadingHistory) {
    return <div className="chat-state">Đang tải hội thoại…</div>;
  }
  if (error && messages.length === 0) {
    return <div className="chat-state chat-state--error">Lỗi: {error}</div>;
  }
  if (messages.length === 0) {
    return (
      <div className="chat-state">
        <p>Chưa có tin nhắn nào. Hãy bắt đầu bằng một câu hỏi cho AI về alert này.</p>
        <p className="chat-hint">Gợi ý: "Tại sao risk score của user này cao?"</p>
      </div>
    );
  }

  return (
    <div className="chat-message-list" role="log" aria-live="polite">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      {isStreaming && messages[messages.length - 1]?.content === '' && (
        <div className="chat-typing" aria-label="AI đang trả lời">
          <span /><span /><span />
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
