# Module LLM & Long-term Memory (VI)

> Bản tiếng Việt — chi tiết kỹ thuật xem `docs/LLM.md`. Theo `docs/PLAN_LLM.md`.

## Tổng quan

Module LLM UEBA đã được nâng cấp từ **stateless 1-shot explainer** → **multi-turn chat với long-term memory**:

- **Provider**: Mistral AI (chat + embeddings) với abstraction `LLMProvider` Protocol — dễ đổi sang OpenAI/Ollama.
- **Streaming**: SSE qua FastAPI `StreamingResponse`, client nhận token từng cái một.
- **Long-term memory**: per-user / per-device / per-pattern, tag-based retrieval v1, có toggle `LLM_MEMORY_SEMANTIC_ENABLED` cho v2 (pgvector).
- **Auto-feedback**: analyst chấm điểm alert → tự động sinh `analyst_pattern` memory → inject vào explanation cho các alert tương lai cùng user/factor.
- **UI chỉnh chu**: dark mode (đã có sẵn), chat panel streaming, AlertDetailModal, MemoryAdminPage.

## 5 phase đã xong (xem `docs/LLM_PROGRESS.md`)

| Phase | Mô tả | Files chính |
|---|---|---|
| 1 | DB pool max=20 + statement timeout | `db/pool.py`, `db/session.py`, `main.py` |
| 2 | 4 schema mới + 10 indexes + 16 helpers + counter cache | `db/session.py`, `test_db/test_*.py` |
| 3 | LLM service refactor + memory v1 + chat + 10 endpoints | `services/llm/*.py`, `services/llm_chat.py`, `services/llm_memory.py`, `services/llm_feedback.py`, `api/routes_llm.py` |
| 4 | Frontend: chat panel + zustand + SSE + memory admin | `features/chat/*.tsx`, `features/alerts/AlertDetailModal.tsx`, `features/admin/MemoryAdminPage.tsx`, `store/chatStore.ts`, `lib/apiClient.ts` |
| 5 | Docs | `docs/LLM.md`, `docs/LLM.vi.md` |

## Settings mới (env vars)

```bash
# Pool
DB_POOL_MAX_SIZE=20                    # user quyết định
DB_POOL_ACQUIRE_TIMEOUT_SECONDS=5.0
DB_STATEMENT_TIMEOUT_READ_MS=5000
DB_STATEMENT_TIMEOUT_WRITE_MS=30000
DB_STATEMENT_TIMEOUT_STREAMING_MS=0    # tắt cho SSE

# LLM core
LLM_PROVIDER=mistral
LLM_CHAT_MODEL=mistral-small-latest
LLM_EMBEDDING_MODEL=mistral-embed
LLM_MAX_RETRIES=3
LLM_TIMEOUT_SECONDS=30
LLM_CHAT_ENABLED=true
LLM_DEFAULT_LANGUAGE=vi
LLM_CHAT_MAX_CONTEXT_MESSAGES=20

# Memory
LLM_MEMORY_ENABLED=true
LLM_MEMORY_SEMANTIC_ENABLED=false      # v2
LLM_MEMORY_MAX_RETRIEVE=5
LLM_MEMORY_DECAY_DAYS=90
LLM_MEMORY_AUTO_FEEDBACK=true
```

## Endpoints mới (10)

```
POST   /api/alerts/{id}/chat/message              # streaming SSE
GET    /api/alerts/{id}/conversation              # full thread
POST   /api/alerts/{id}/conversation/reset
POST   /api/alerts/{id}/feedback                  # tự sinh memory
GET    /api/alerts/{id}/feedback
GET    /api/admin/llm-memory                      # list + filter
DELETE /api/admin/llm-memory/{id}                 # forget
GET    /api/admin/llm-memory/stats                # counter cache
GET    /api/admin/llm-stats                       # provider call stats
GET    /api/admin/db-pool-stats                   # connection pool
```

## Cách dùng

### Frontend (chat với alert)

1. Vào `/alerts`, click 1 alert → `AlertDetailModal` mở với `ChatPanel` bên phải.
2. Gõ câu hỏi → Enter → AI trả lời streaming.
3. Bấm **Feedback** → chọn verdict (True/False positive, Benign, Cần điều tra) + ghi chú.
4. Bấm **Reset** để xoá thread.

### Frontend (admin memory)

1. Vào `/admin/llm-memory` (chỉ role admin).
2. Filter theo scope/kind/tag.
3. Bấm **Xóa** để forget memory.
4. Stats cards trên cùng: tổng memory, LLM call stats, DB pool stats.

### Backend (gọi explain_alert programmatically)

```python
from src.backend.app.services.llm import explain_alert

text = explain_alert({
    "alert_id": 42,
    "user_id": "U-1",
    "severity": "high",
    "risk_score": 88,
    "top_features": ["after_hours_logon", "usb_copy"],
})
# Trả 3 dòng tiếng Việt, hoặc fallback rule-based nếu no API key.
```

## Test

```bash
pytest src/backend/tests/test_db -v                          # 14 test
pytest src/backend/tests/test_services/test_llm_package.py   # 19 test
pytest src/backend/tests/test_services/test_llm_memory_feedback.py  # 16 test
pytest src/backend/tests/test_services/test_llm_chat.py      # 5 test
```

Kết quả: **136 pass, 4 fail (pre-existing baseline), 171 skip (cần TEST_DATABASE_URL)**.

## Tích hợp với các module hiện có

- `services/demo_pipeline.py` và `services/user_scoring.py` gọi `explain_alert` — backward compat 100%, không phải sửa dòng nào.
- 4 bảng mới + counter cache tạo idempotent trong `initialize_database()` — chạy an toàn trên DB cũ.

## Tương lai (v2)

- Embedding semantic search (toggle `LLM_MEMORY_SEMANTIC_ENABLED`).
- Partition `llm_messages` theo tháng (khi > 100K rows).
- `OpenAICompatibleProvider` concrete implementation.
- Frontend unit tests (vitest).
- Few-shot prompt examples.
