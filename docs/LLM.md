# LLM Service & Long-term Memory

> Module LLM cho UEBA Endpoint Monitoring — multi-turn chat, long-term memory, polished UI. Theo `docs/PLAN_LLM.md` (Phase 0–4 đã xong; Phase 5 polish).

## Tổng quan

- **Provider**: Mistral AI (chat + embeddings) với abstraction `LLMProvider` Protocol, dễ swap sang OpenAI/Ollama.
- **Streaming**: SSE qua FastAPI `StreamingResponse`, token-by-token về client.
- **Long-term memory**: per-user / per-device / per-pattern, tag-based retrieval v1, có thể bật embedding semantic search v2.
- **Auto-feedback**: analyst verdict → tự động tạo `analyst_pattern` memory → inject vào explanation các alert tương lai cùng user/factor.
- **Polished UI**: dark mode, chat panel streaming, AlertDetailModal, MemoryAdminPage.

## Kiến trúc

```
[Frontend]                  [Backend]                      [Postgres]
ChatPanel.tsx        ──►   routes_llm.py          ──►   llm_conversations
zustand store               llm_chat.py (multi-turn)      llm_messages
apiClient.ts                llm_memory.py (v1 tag)        llm_feedback
                            llm_feedback.py               llm_memories
                            llm.py (provider+retry)       llm_stats_cache
                            db/pool.py (max=20)
                            db/session.py (16 helpers)
```

## Settings (env vars)

```bash
# Pool (Phase 1)
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=20
DB_POOL_ACQUIRE_TIMEOUT_SECONDS=5.0
DB_STATEMENT_TIMEOUT_READ_MS=5000
DB_STATEMENT_TIMEOUT_WRITE_MS=30000
DB_STATEMENT_TIMEOUT_STREAMING_MS=0        # disabled
DB_IDLE_IN_TRANSACTION_TIMEOUT_MS=10000

# LLM core (Phase 3)
LLM_PROVIDER=mistral
LLM_CHAT_MODEL=mistral-small-latest
LLM_EMBEDDING_MODEL=mistral-embed
LLM_MAX_RETRIES=3
LLM_TIMEOUT_SECONDS=30
LLM_CHAT_ENABLED=true
LLM_DEFAULT_LANGUAGE=vi
LLM_CHAT_MAX_CONTEXT_MESSAGES=20
LLM_OPENAI_API_KEY=                          # chỉ cần nếu LLM_PROVIDER=openai_compatible
LLM_OPENAI_BASE_URL=

# Memory
LLM_MEMORY_ENABLED=true
LLM_MEMORY_SEMANTIC_ENABLED=false            # v2 pgvector
LLM_MEMORY_MAX_RETRIEVE=5
LLM_MEMORY_DECAY_DAYS=90
LLM_MEMORY_AUTO_FEEDBACK=true
```

## Endpoints mới

| Method | Path | Auth | Mục đích |
|---|---|---|---|
| POST | `/api/alerts/{id}/chat/message` | analyst+ | Gửi message, trả SSE stream |
| GET | `/api/alerts/{id}/conversation` | analyst+ | Lấy full thread |
| POST | `/api/alerts/{id}/conversation/reset` | analyst+ | Xoá messages |
| POST | `/api/alerts/{id}/feedback` | analyst+ | Verdict + note, tự động tạo memory |
| GET | `/api/alerts/{id}/feedback` | analyst+ | List feedback của alert |
| GET | `/api/admin/llm-memory` | admin | List memories, filter scope/kind/tag |
| DELETE | `/api/admin/llm-memory/{id}` | admin | Forget memory |
| GET | `/api/admin/llm-memory/stats` | admin | Counter cache (real-time) |
| GET | `/api/admin/llm-stats` | admin | Provider call stats |
| GET | `/api/admin/db-pool-stats` | admin | Connection pool stats |

## DB schema (Phase 2)

4 bảng mới + 1 counter cache:

- **`llm_conversations`** — 1 thread / alert (UNIQUE alert_id)
- **`llm_messages`** — every turn, high-write, autovacuum tuned
- **`llm_feedback`** — analyst verdicts, UNIQUE (alert_id, analyst_id)
- **`llm_memories`** — long-term memory, UNIQUE (scope, scope_id, kind, content_hash)
- **`llm_stats_cache`** — counter cache maintained by trigger on `llm_memories`

Indexes (10 cái): composite cho thread load, GIN cho tag search, partial cho hot memories.

Trigger `llm_memories_stats_sync` giữ `llm_stats_cache` real-time khi insert/update/delete memories.

## Cách dùng

### Frontend (chat với alert)

1. Vào `/alerts`, click 1 alert.
2. Panel chat mở tự động (mặc định) bên phải.
3. Gõ câu hỏi → Enter → AI trả lời streaming.
4. Bấm "Feedback" → chọn verdict (TP/FP/Benign/Investigate) + ghi chú.
5. Bấm "Reset" để xoá thread.

### Frontend (admin memory)

1. Vào `/admin/llm-memory` (chỉ admin).
2. Filter theo scope / kind / tag.
3. Click "Xóa" để forget memory.
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
# Returns Vietnamese 3-line explanation, hoặc fallback rule-based nếu no key.
```

### Backend (submit feedback programmatically)

```python
from src.backend.app.services.llm_feedback import get_feedback_service

# Auto-creates analyst_pattern memory if LLM_MEMORY_AUTO_FEEDBACK=true
get_feedback_service().submit(
    alert_id=42, analyst_id="A-1", verdict="false_positive", note="đã verify"
)
```

## Cache & fallback

- **`LLMCache`** (in-memory, LRU 1000 + TTL 1h): cache `(alert_id, severity, risk, factors)` → explanation. Hit khi analyst mở lại alert page.
- **Fallback rule-based**: nếu `MISTRAL_API_KEY` rỗng, hoặc call fail sau 3 retry, hoặc parse fail → trả explanation mặc định từ context.

## Troubleshooting

| Vấn đề | Nguyên nhân | Fix |
|---|---|---|
| Chat không phản hồi | `LLM_CHAT_ENABLED=false` hoặc no API key | Set `MISTRAL_API_KEY` + `LLM_CHAT_ENABLED=true` |
| Memory table empty | `LLM_MEMORY_ENABLED=false` | Bật trong `.env` |
| SSE bị buffer qua nginx | Proxy buffer | Thêm header `X-Accel-Buffering: no` (đã có) |
| `QueryCanceled` exception | Statement timeout (5s read) | Tăng `DB_STATEMENT_TIMEOUT_READ_MS` |
| Pool exhausted | Quá nhiều concurrent SSE | Tăng `DB_POOL_MAX_SIZE` (currently 20) hoặc giảm số stream đồng thời |

## Test

```bash
# Backend (cần PostgreSQL cho 5 integration test)
pytest src/backend/tests/test_db -v
pytest src/backend/tests/test_services/test_llm_package.py -v
pytest src/backend/tests/test_services/test_llm_memory_feedback.py -v
pytest src/backend/tests/test_services/test_llm_chat.py -v
```

## Files thêm/sửa

Xem `docs/LLM_PROGRESS.md` để biết chi tiết từng phase.

## Future work (v2)

- Embedding semantic search (`LLM_MEMORY_SEMANTIC_ENABLED=true` + pgvector)
- Partition `llm_messages` by `created_at` monthly (when > 100K rows)
- `OpenAICompatibleProvider` concrete implementation
- Few-shot examples in prompt
- Frontend unit tests (vitest)
- Suggested follow-up questions
- LangGraph multi-node explanation pipeline
