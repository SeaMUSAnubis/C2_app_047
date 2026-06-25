/**
 * Zustand store for the chat panel (Phase 4.4 of PLAN_LLM.md).
 *
 * Optimised: streaming content lives in its own state slice (`streamingContent`)
 * so that 100 SSE tokens don't cause 100 full-list re-renders. Only the
 * streaming bubble subscribes to it; the other bubbles are React.memo'd and
 * skip re-renders when their props don't change.
 */

import { create } from 'zustand';

import {
  deleteConversation as deleteConversationRequest,
  createConversation,
  getConversation,
  getConversationById,
  listConversations,
  resetConversation,
  streamChatMessage,
  updateConversationTitle,
  type ChatMessage,
  type ChatStreamEvent,
  type ConversationSummary,
} from '../lib/apiClient';

interface ChatStore {
  alertId: number | null;
  conversationId: number | null;
  messages: ChatMessage[];                 // committed messages (static)
  streamingMessageId: number | null;       // which message is currently streaming
  streamingContent: string;                // live content of streaming message
  isStreaming: boolean;
  isLoadingHistory: boolean;
  error: string | null;
  abortController: AbortController | null;
  usedMemoryIds: number[];
  title: string;
  conversations: ConversationSummary[];

  loadHistory: (alertId: number) => Promise<void>;
  loadConversation: (alertId: number, conversationId: number) => Promise<void>;
  createConversation: (alertId: number, title?: string) => Promise<void>;
  sendMessage: (alertId: number, content: string) => Promise<void>;
  updateTitle: (alertId: number, title: string) => Promise<void>;
  deleteConversation: (alertId: number) => Promise<void>;
  abortStream: () => void;
  resetConversation: (alertId: number) => Promise<void>;
  reset: () => void;
}

const initial: Pick<
  ChatStore,
  | 'alertId'
  | 'conversationId'
  | 'messages'
  | 'streamingMessageId'
  | 'streamingContent'
  | 'isStreaming'
  | 'isLoadingHistory'
  | 'error'
  | 'abortController'
  | 'usedMemoryIds'
  | 'title'
  | 'conversations'
> = {
  alertId: null,
  conversationId: null,
  messages: [],
  streamingMessageId: null,
  streamingContent: '',
  isStreaming: false,
  isLoadingHistory: false,
  error: null,
  abortController: null,
  usedMemoryIds: [],
  title: '',
  conversations: [],
};

export const useChatStore = create<ChatStore>((set, get) => ({
  ...initial,

  loadHistory: async (alertId: number) => {
    set({ alertId, isLoadingHistory: true, error: null });
    try {
      const [conversations, conv] = await Promise.all([
        listConversations(alertId).catch(() => []),
        getConversation(alertId),
      ]);
      set({
        conversationId: conv.id || null,
        title: conv.title ?? '',
        messages: conv.messages ?? [],
        conversations,
        isLoadingHistory: false,
      });
    } catch (err) {
      set({ isLoadingHistory: false, error: (err as Error).message });
    }
  },

  loadConversation: async (alertId: number, conversationId: number) => {
    set({ alertId, isLoadingHistory: true, error: null });
    try {
      const conv = await getConversationById(alertId, conversationId);
      set({
        conversationId: conv.id || null,
        title: conv.title ?? '',
        messages: conv.messages ?? [],
        isLoadingHistory: false,
      });
    } catch (err) {
      set({ isLoadingHistory: false, error: (err as Error).message });
    }
  },

  createConversation: async (alertId: number, title?: string) => {
    try {
      const conv = await createConversation(alertId, title);
      const conversations = await listConversations(alertId).catch(() => []);
      set({
        conversationId: conv.id || null,
        title: conv.title ?? '',
        messages: conv.messages ?? [],
        conversations,
        error: null,
      });
    } catch (err) {
      set({ error: (err as Error).message });
    }
  },

  sendMessage: async (alertId: number, content: string) => {
    if (!content.trim()) return;
    if (get().isStreaming) return;
    if (!get().conversationId) {
      try {
        const conv = await createConversation(alertId);
        const conversations = await listConversations(alertId).catch(() => []);
        set({
          conversationId: conv.id || null,
          title: conv.title ?? '',
          messages: conv.messages ?? [],
          conversations,
        });
      } catch (err) {
        set({ error: (err as Error).message });
        return;
      }
    }

    const assistantId = Date.now() + 1;
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: content.trim(),
      model: null,
      latency_ms: null,
      memory_used_ids: null,
      created_at: new Date().toISOString(),
    };
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      model: null,
      latency_ms: null,
      memory_used_ids: null,
      created_at: new Date().toISOString(),
    };
    set({
      messages: [...get().messages, userMsg, assistantMsg],
      streamingMessageId: assistantId,
      streamingContent: '',
      isStreaming: true,
      error: null,
    });

    const controller = new AbortController();
    set({ abortController: controller });

    return new Promise<void>((resolve) => {
      let memoryIds: number[] = [];

      streamChatMessage(alertId, content, get().conversationId, {
        signal: controller.signal,
        onEvent: (ev: ChatStreamEvent) => {
          if (ev.type === 'token' && ev.text) {
            // Update ONLY the streaming slice — doesn't change `messages` ref.
            set((s) => ({ streamingContent: s.streamingContent + ev.text! }));
          } else if (ev.type === 'memory_used' && ev.ids) {
            memoryIds = ev.ids;
            set({ usedMemoryIds: memoryIds });
          } else if (ev.type === 'error') {
            set({ error: ev.message ?? 'lỗi không xác định' });
          } else if (ev.type === 'done') {
            set((s) => ({
              messages: s.messages.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content: s.streamingContent,
                      latency_ms: ev.latency_ms ?? null,
                      model: ev.model ?? null,
                      memory_used_ids: memoryIds.length ? memoryIds : null,
                    }
                  : m,
              ),
              streamingMessageId: null,
              streamingContent: '',
              isStreaming: false,
              abortController: null,
            }));
            void listConversations(alertId)
              .then((conversations) => set({ conversations }))
              .catch(() => undefined);
            resolve();
          }
        },
        onError: (err) => {
          set((s) => ({
            isStreaming: false,
            abortController: null,
            error: err.message,
            messages: s.messages.map((m) =>
              m.id === assistantId
                ? { ...m, content: s.streamingContent || `**[lỗi]** ${err.message}` }
                : m,
            ),
            streamingMessageId: null,
            streamingContent: '',
          }));
          resolve();
        },
        onDone: () => {
          if (get().isStreaming) {
            set({ isStreaming: false, abortController: null });
          }
          resolve();
        },
      });
    });
  },

  updateTitle: async (alertId: number, title: string) => {
    try {
      const conv = await updateConversationTitle(alertId, title, get().conversationId ?? undefined);
      const conversations = await listConversations(alertId).catch(() => get().conversations);
      set({ title: conv.title, conversationId: conv.id || null, messages: conv.messages ?? [], conversations });
    } catch (err) {
      set({ error: (err as Error).message });
    }
  },

  deleteConversation: async (alertId: number) => {
    try {
      const currentId = get().conversationId ?? undefined;
      await deleteConversationRequest(alertId, currentId);
      const conversations = await listConversations(alertId).catch(() => []);
      if (conversations[0]) {
        const conv = await getConversationById(alertId, conversations[0].id);
        set({ messages: conv.messages ?? [], conversationId: conv.id || null, title: conv.title ?? '', usedMemoryIds: [], conversations });
      } else {
        set({ messages: [], conversationId: null, title: '', usedMemoryIds: [], conversations });
      }
    } catch (err) {
      set({ error: (err as Error).message });
    }
  },

  abortStream: () => {
    const ctrl = get().abortController;
    if (ctrl) {
      ctrl.abort();
      set({ isStreaming: false, abortController: null });
    }
  },

  resetConversation: async (alertId: number) => {
    try {
      await resetConversation(alertId);
      set({ messages: [], conversationId: null, usedMemoryIds: [], streamingContent: '', streamingMessageId: null });
    } catch (err) {
      set({ error: (err as Error).message });
    }
  },

  reset: () => set({ ...initial }),
}));
