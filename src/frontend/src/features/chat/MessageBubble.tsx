import { memo } from 'react';
import { clsx } from 'clsx';
import { useChatStore } from '../../store/chatStore';
import type { ChatMessage } from '../../lib/apiClient';

interface Props {
  message: ChatMessage;
}

/**
 * Static bubble — renders committed message content. Wrapped in React.memo so
 * it skips re-render when an SSE token updates `streamingContent` on a sibling
 * bubble. This is the hot path optimisation: 100 tokens = 100 streaming
 * bubble re-renders, NOT 100× full-list re-renders.
 */
export const MessageBubble = memo(function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';
  const streamingMessageId = useChatStore((s) => s.streamingMessageId);
  const streamingContent = useChatStore((s) => s.streamingContent);

  const isStreamingThis = isAssistant && message.id === streamingMessageId;
  const displayContent = isStreamingThis ? streamingContent : message.content;

  return (
    <div
      className={clsx('chat-bubble', {
        'chat-bubble--user': isUser,
        'chat-bubble--assistant': isAssistant,
        'chat-bubble--system': message.role === 'system',
      })}
    >
      <div className="chat-bubble-meta">
        {isUser ? 'Bạn' : isAssistant ? 'AI' : 'Hệ thống'}
        {message.model && isAssistant && !isStreamingThis && (
          <span className="chat-bubble-model">
            {message.model}
            {message.latency_ms != null && ` · ${(message.latency_ms / 1000).toFixed(1)}s`}
          </span>
        )}
      </div>
      <div className="chat-bubble-content">
        {displayContent}
        {isStreamingThis && <span className="chat-cursor" aria-hidden>|</span>}
      </div>
      {isAssistant && !isStreamingThis && message.memory_used_ids && message.memory_used_ids.length > 0 && (
        <div className="chat-bubble-memory">
          Đã dùng {message.memory_used_ids.length} memory
        </div>
      )}
    </div>
  );
});
