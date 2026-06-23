import { useState, type KeyboardEvent } from 'react';
import { useChatStore } from '../../store/chatStore';

interface Props {
  alertId: number;
}

export function ChatInput({ alertId }: Props) {
  const [value, setValue] = useState('');
  const isStreaming = useChatStore((s) => s.isStreaming);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const abortStream = useChatStore((s) => s.abortStream);
  const maxLen = 8000;

  const handleSend = async () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    setValue('');
    await sendMessage(alertId, trimmed);
  };

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="chat-input">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value.slice(0, maxLen))}
        onKeyDown={handleKey}
        placeholder="Hỏi AI về alert này… (Enter để gửi, Shift+Enter để xuống dòng)"
        disabled={isStreaming}
        rows={2}
        aria-label="Nhập câu hỏi"
      />
      <div className="chat-input-actions">
        <span className="chat-input-counter">{value.length}/{maxLen}</span>
        {isStreaming ? (
          <button type="button" className="primary-action primary-action--danger" onClick={abortStream}>
            Dừng
          </button>
        ) : (
          <button
            type="button"
            className="primary-action"
            onClick={handleSend}
            disabled={!value.trim()}
          >
            Gửi
          </button>
        )}
      </div>
    </div>
  );
}
