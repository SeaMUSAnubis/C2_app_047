import { memo } from 'react';
import { clsx } from 'clsx';
import { useChatStore } from '../../store/chatStore';
import { formatMarkdown } from '../../lib/formatMarkdown';
import type { ChatMessage } from '../../lib/apiClient';

interface Props {
  message: ChatMessage;
}

export const MessageBubble = memo(function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';
  const streamingMessageId = useChatStore((s) => s.streamingMessageId);
  const streamingContent = useChatStore((s) => s.streamingContent);

  const isStreamingThis = isAssistant && message.id === streamingMessageId;
  const rawContent = isStreamingThis ? streamingContent : message.content;
  const displayContent = isAssistant && !isStreamingThis ? formatMarkdown(rawContent) : rawContent;

  return (
    <div
      className={clsx('chat-bubble', {
        'chat-bubble--user': isUser,
        'chat-bubble--assistant': isAssistant,
        'chat-bubble--system': message.role === 'system',
      })}
    >
      <div className="chat-bubble-meta">
        {isUser ? 'Bạn' : isAssistant ? 'AI · Vespionage' : 'Hệ thống'}
        {message.model && isAssistant && !isStreamingThis && (
          <span className="chat-bubble-model">
            {message.model}
            {message.latency_ms != null && ` · ${(message.latency_ms / 1000).toFixed(1)}s`}
          </span>
        )}
      </div>
      <div
        className="chat-bubble-content"
        dangerouslySetInnerHTML={
          isAssistant && !isStreamingThis ? { __html: displayContent } : undefined
        }
      >
        {isAssistant && !isStreamingThis ? null : displayContent}
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
