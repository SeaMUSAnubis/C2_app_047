# Kế hoạch triển khai Endpoint Agent & Real-time Log Collection

> Mục tiêu: xây dựng agent chạy ngầm trên máy công ty cấp cho nhân viên, tự động thu thập log (logon, USB, file, http, email, process, network) và gửi về server theo thời gian thực. Server đã có sẵn bảng `raw_user_logs`, endpoint `/api/raw-logs/batch`, field `collector_type: "endpoint_agent"` — cần lấp 3 khoảng trống: (1) auth/identity cho agent, (2) normalizer worker, (3) config/policy endpoint.

## Kiến trúc tổng thể

```
┌─────────────────────────────────────────┐         ┌──────────────────────────┐
│  Endpoint Agent (Python service)        │         │  Backend FastAPI (có sẵn) │
│                                         │         │                          │
│  ├─ logon_collector   (Event Log/utmp)  │  HTTPS  │  POST /api/raw-logs/batch│ ← đã có
│  ├─ device_collector  (USB udev/20001)  │ ──────► │  POST /api/raw-logs/ingest│ ← đã có
│  ├─ file_collector    (auditd/4663)     │         │                          │
│  ├─ http_collector    (local proxy+DNS) │         │  [MỚI] /api/agents/*      │
│  ├─ email_collector   (MAPI/IMAP log)   │         │  [MỚI] normalizer worker  │
│  ├─ process_collector (4688/auditd)     │         │                          │
│  ├─ network_collector (netstat/ETW)     │         │  raw_user_logs ──► event_logs
│  ├─ local SQLite buffer (offline-safe)  │         │   (normalized_event_id     │
│  ├─ policy/blocklist cache              │         │    đang luôn NULL)          │
│  └─ service wrapper (Win svc/systemd)   │         │                          │
└─────────────────────────────────────────┘         └──────────────────────────┘
```

## Mapping nguồn log theo OS

| `event_type` | Windows | Linux | macOS | `action` |
|---|---|---|---|---|
| `logon` | Security 4624/4634/4647 | `wtmp`/`utmp` | `last`, `utmpx` | `logon`/`logoff` |
| `device` | Event 20001/20003, WMI | `udev` + `lsusb` | `disk_arbitrationd` | `connect`/`disconnect` |
| `file` | Audit 4663 | `auditd` + `inotify` | `fs_usage` | `file_access` |
| `http` | Local proxy + DNS sinkhole | iptables DNAT + DNS | pf + DNS | `allowed`/`blocked` |
| `email` | Outlook MAPI / Exchange | Thunderbird / IMAP | Mail.log | `email_send`/`email_read` |
| `process` | Event 4688 | `auditd` exec | `eslogger` | `spawn`/`exit` |
| `network` | ETW Kernel-Network | `conntrack`/`ss` | `lsof -i` | `connection` |

## Website block — 3 lớp

- **Lớp 1 — DNS sinkhole**: agent ghi đè resolver → `0.0.0.0` cho domain trong blocklist (lấy từ server). Mỗi match tạo record `http` `action: blocked`. Không cần phá TLS.
- **Lớp 2 — Browser extension** (enterprise GPO/MDM): bắt full URL, trả block page có giải thích.
- **Lớp 3 — MITM HTTPS proxy** (tùy chọn, cần CA root qua MDM): chỉ dùng nếu công ty đã có hạ tầng PKI.

## Lưu ý pháp lý & đạo đức

- Legal banner + system tray icon bắt buộc (Nghị định 13/2023 PDPD, GDPR Art.88). Không giấu agent.
- Chỉ cài máy công ty, không cài máy cá nhân.
- Redact `content` email/http trước khi gửi (giữ hash + metadata).
- RBAC: chỉ security_manager/analyst xem log thu được.

---

## Các Phase

### Phase 1 — Server-side agent infrastructure (NỀN TẢNG)

**Mục tiêu**: agent có thể enroll, nhận API key, gửi log qua `/api/raw-logs/batch` bằng API key (không cần JWT con người), heartbeat, pull config.

**Việc cần làm**:
1. Bảng `endpoint_agents` (agent_id, hostname, device_id FK, api_key_hash, status, policy_version, last_heartbeat, enrolled_at, created_at, updated_at) trong `initialize_database()`.
2. Bảng `agent_blocklist` (id, pattern, category, reason, created_at) — blocklist domain/URL tải về agent.
3. Bảng `agent_enrollment_tokens` (token_hash, created_by_account_id, used_by_agent_id, expires_at, created_at) — one-time enrollment.
4. Pydantic schemas: `AgentEnrollRequest`, `AgentEnrollResponse`, `AgentRead`, `AgentHeartbeat`, `AgentConfig`, `AgentBlocklistEntry`, `AgentUpdate`.
5. DB helpers trong `session.py`: `create_enrollment_token`, `register_agent`, `get_agent_by_api_key`, `get_agent`, `list_agents`, `update_agent_heartbeat`, `get_agent_config`, `update_agent`, `revoke_agent`, `list_blocklist`.
6. `require_agent` dependency trong `core/security.py` — chấp nhận header `X-API-Key: <plaintext>`, tra hash, trả về agent dict.
7. Router mới `api/routes_agents.py`:
   - `POST /api/agents/enrollment-tokens` (admin) — tạo enrollment token.
   - `POST /api/agents/register` (public, dùng enrollment token) — enroll agent, trả `agent_id` + `api_key`.
   - `POST /api/agents/heartbeat` (agent auth) — update last_heartbeat, trả config_version.
   - `GET /api/agents/{agent_id}/config` (agent auth hoặc admin) — trả blocklist + sampling rate + enabled collectors.
   - `GET /api/agents` (admin) — list agents.
   - `GET /api/agents/{agent_id}` (admin) — detail.
   - `PATCH /api/agents/{agent_id}` (admin) — update status/policy_version.
   - `DELETE /api/agents/{agent_id}` (admin) — revoke (set status=revoked, invalidate api_key).
8. Sửa `/api/raw-logs/ingest` và `/api/raw-logs/batch` chấp nhận `require_agent` HOẶC `require_role(admin, security_manager, analyst)`.
9. Settings mới trong `config.py`: `agent_enrollment_token_ttl_minutes`, `agent_heartbeat_timeout_minutes`, `agent_default_sampling_rate`.
10. Wire router vào `main.py`.
11. Tests trong `src/backend/tests/`: enrollment flow, agent auth, raw-logs batch với agent key, heartbeat, config pull, revoke.
12. Cập nhật `.env.example`.

**Kết quả thực tế (điền sau khi hoàn thành)**: _xem Phase 1 Report dưới đây_

---

### Phase 2 — Agent core + logon + http (DNS sinkhole) collector

**Mục tiêu**: 1 agent chạy được trên Linux/Windows, thu thập logon + http (DNS block), gửi về server real-time, có offline buffer.

**Việc**:
1. Tạo `src/agent/` package Python.
2. `agent/core.py`: service wrapper (systemd unit + Windows service stub), main loop, graceful shutdown.
3. `agent/transport.py`: HTTP client với retry, exponential backoff, batch gửi `/api/raw-logs/batch`, auth bằng `X-API-Key`.
4. `agent/buffer.py`: SQLite local buffer (events table), flush theo thời gian hoặc kích thước, xóa sau khi ack.
5. `agent/config_client.py`: pull `GET /api/agents/{id}/config` mỗi 5 phút, cache blocklist.
6. `agent/collectors/base.py`: interface `Collector` với `start()`, `stop()`, `events()` queue.
7. `agent/collectors/logon.py`: Linux `wtmp`/`utmp` (struct) + Windows Event 4624/4634 (pywin32 optional).
8. `agent/collectors/http_dns.py`: hook DNS (Linux `/etc/hosts` ghi đè hoặc systemd-resolved, Windows `DnsQuery` API), match blocklist, emit `http` event `action: blocked`/`allowed`.
9. `agent/enroll.py`: CLI enroll dùng enrollment token, lưu `agent_id` + `api_key` vào `agent_state.json` (perm 0600).
10. `agent/policy_banner.py`: hiển thị legal banner ở startup (Linux notify, Windows msg).
11. Installer script: `scripts/install_agent.sh` (Linux), `scripts/install_agent.ps1` (Windows).
12. End-to-end test: agent giả lập gửi 100 event vào server đang chạy.

**Kết quả thực tế (điền sau khi hoàn thành)**: xem Phase 2 Report dưới đây

---

### Phase 3 — Normalizer worker + near-real-time ML scoring

**Mục tiêu**: raw logs từ agent được normalize sang `event_logs`, trigger ML scoring tự động, sinh alert.

**Việc**:
1. `src/backend/app/services/normalizer.py`: đọc `raw_user_logs` nơi `normalized_event_id IS NULL`, map `raw_payload` → `EventIngest` theo `event_type`, insert `event_logs`, update FK.
2. Trigger: chạy trong FastAPI `lifespan` background task (asyncio) hoặc cron endpoint `POST /api/admin/normalize` (admin only).
3. ML scoring hook: sau khi normalize, nếu 1 user có event mới trong window, enqueue `analyze_user(user_id)`.
4. Endpoint `POST /api/admin/run-normalizer` (admin) để trigger thủ công.
5. Metrics endpoint `GET /api/admin/normalizer-stats` (admin): pending count, processed, errors.
6. Tests: normalizer với mỗi event_type, idempotent, ML trigger.

**Kết quả**: _điền sau_

---

### Phase 4 — Collector còn lại + UI quản lý agent + legal banner

**Mục tiêu**: đầy đủ collector (device/file/email/process/network), UI admin quản lý agent & blocklist, legal banner hoàn chỉnh.

**Việc**:
1. `agent/collectors/device.py` (USB), `file.py` (auditd/4663), `email.py` (MAPI/IMAP log), `process.py` (4688/auditd), `network.py` (ETW/conntrack).
2. Frontend `src/frontend/src/pages/AgentsPage.tsx`: list agent, trạng thái online/offline, last_heartbeat, policy_version, nút revoke.
3. Frontend `BlocklistPage.tsx`: CRUD blocklist, category, preview match.
4. Frontend `AgentDetailPage.tsx`: timeline event của agent, config hiện tại, heartbeat history.
5. Frontend service `apiClient.ts`: `listAgents`, `enrollAgent`, `revokeAgent`, `getBlocklist`, `addBlocklistEntry`, `removeBlocklistEntry`.
6. Legal banner component trên login page + agent-side banner.
7. E2E test: enroll agent trên UI, xem log realtime, block 1 domain, verify event `http action: blocked` xuất hiện trên dashboard.

**Kết quả**: _điền sau_

---

## Tiến độ tổng quan

| Phase | Trạng thái | Bắt đầu | Hoàn thành |
|---|---|---|---|
| 1 — Server agent infra | **done** | 2026-06-22 | 2026-06-22 |
| 2 — Agent core + logon + http | **done** | 2026-06-22 | 2026-06-22 |
| 3 — Normalizer + ML scoring | _pending_ | — | — |
| 4 — Full collectors + UI | _pending_ | — | — |

---

## Phase 1 Report

**Trạng thái:** HOÀN THÀNH — server sẵn sàng cho agent enroll + gửi log.

### Việc đã làm

#### 1.1 Database schema (4 bảng mới)
File: `src/backend/app/db/session.py` (thêm vào `initialize_database()` + helper `_seed_agent_policy`)
- `endpoint_agents` (agent_id PK, hostname, os, os_version, device_id FK, assigned_user_id FK, api_key_hash, status CHECK('enrolled','active','offline','revoked'), policy_version, last_heartbeat, last_config_pull, enrolled_at, created_at, updated_at) + 3 index.
- `agent_enrollment_tokens` (token_hash PK SHA-256, created_by_account_id FK, used_by_agent_id FK, expires_at, created_at).
- `agent_blocklist` (id IDENTITY PK, pattern UNIQUE, pattern_type CHECK('domain','url','ip','regex'), category, reason, enabled, created_at, updated_at) + index trên enabled.
- `agent_policy` (id=1 PK singleton, policy_version, sampling_rate CHECK 1-100, enabled_collectors_json, updated_at). Seeded mặc định với 7 collector bật + sampling 100%.

#### 1.2 Pydantic schemas
File: `src/backend/app/schemas/schemas.py` (thêm 14 schema + 3 Literal)
- `AgentStatus`, `BlocklistPatternType`, `AgentCollectorName` Literal.
- `EnrollmentTokenCreate/Read`, `AgentEnrollRequest/Response`, `AgentHeartbeatRequest/Response`, `AgentConfigResponse`, `AgentRead`, `AgentUpdate`, `BlocklistEntryCreate/Update/Read`, `AgentPolicyUpdate`.

#### 1.3 DB helpers (module mới)
File: `src/backend/app/db/agents.py` (380 dòng, hoàn chỉnh)
- Token + API key generation: `_generate_api_key` (`o47ag_<32b>`), `_generate_enrollment_token` (`o47enr_<24b>`), `_generate_agent_id` (`agent-<16hex>`).
- `_hash_secret` SHA-256, `_constant_time_eq` hmac.compare_digest.
- `create_enrollment_token(account_id, ttl)` — tạo one-time token, lưu hash.
- `_consume_enrollment_token(conn, token)` — validate (tồn tại, chưa dùng, chưa hết hạn) trong cùng transaction.
- `register_agent(enrollment_token, hostname, os, ...)` — consume token + insert agent + mark token used. Atomic.
- `get_agent_by_api_key(api_key)` — lookup theo hash, constant-time verify, return None nếu revoked/invalid.
- `get_agent`, `list_agents`, `count_agents`, `update_agent_heartbeat` (status→active), `touch_config_pull`, `update_agent`, `revoke_agent` (status→revoked, giữ hash để identify).
- `mark_stale_agents_offline(timeout_minutes)` — flip agents quá timeout sang 'offline'.
- `get_agent_policy`, `update_agent_policy` (bump policy_version), `get_agent_config(agent_id)` (policy + blocklist + touch_config_pull).
- `list_blocklist`, `create_blocklist_entry` (upsert theo pattern), `update_blocklist_entry`, `delete_blocklist_entry`.

#### 1.4 Auth dependency
File: `src/backend/app/core/security.py` (thêm `get_agent_from_request`, `require_agent`)
- `get_agent_from_request(request)` — đọc `X-API-Key` header, lookup agent, raise 401 nếu header có nhưng invalid, raise 403 nếu revoked, return None nếu header thiếu.
- `require_agent` — dependency bắt buộc agent (cho heartbeat, me/config).

#### 1.5 Router mới (15 endpoints)
File: `src/backend/app/api/routes_agents.py` (315 dòng)
- `POST /api/agents/enrollment-tokens` (admin JWT) — issue token.
- `POST /api/agents/register` (public, enrollment token trong body) — enroll, return api_key 1 lần.
- `POST /api/agents/heartbeat` (X-API-Key) — update last_heartbeat, flip status→active.
- `GET /api/agents/me/config` (X-API-Key) — pull policy + blocklist.
- `GET /api/agents` (admin/analyst JWT) — list + pagination.
- `GET /api/agents/{agent_id}` (admin/analyst) — detail.
- `PATCH /api/agents/{agent_id}` (admin) — update status/device/user/policy_version.
- `DELETE /api/agents/{agent_id}` (admin) — revoke.
- `GET /api/agents/blocklist` (admin/analyst) — list, hỗ trợ `enabled_only`.
- `POST /api/agents/blocklist` (admin) — create/upsert.
- `PATCH /api/agents/blocklist/{entry_id}` (admin) — update.
- `DELETE /api/agents/blocklist/{entry_id}` (admin) — delete.
- `GET /api/agents/policy` (admin/analyst) — read singleton policy.
- `PATCH /api/agents/policy` (admin) — update + bump version.
- `POST /api/admin/agents/mark-stale` (admin) — flip stale agents sang offline.
- Route ordering: static paths (`/agents/blocklist`, `/agents/policy`) đặt TRƯỚC `/agents/{agent_id}` để tránh path param nuốt.

#### 1.6 Raw-logs endpoints chấp nhận agent auth
File: `src/backend/app/api/routes.py`
- Thêm `require_role_or_agent` dependency: chấp nhận `X-API-Key` (agent) HOẶC Bearer JWT (human). Return `{auth_kind: 'agent'|'account', ...}`.
- `POST /api/raw-logs/ingest` và `POST /api/raw-logs/batch` đổi sang dep mới.
- Khi agent gửi raw-log mà thiếu `user_id`/`device_id`, tự fill từ `assigned_user_id`/`device_id` của agent (gán agent cho 1 user/device cố định).
- Human account vẫn phải có role admin/security_manager/analyst.
- Status code khi chưa auth: 401 (trước là 403 — đúng ngữ nghĩa hơn: 401=unauthenticated, 403=forbidden).

#### 1.7 Settings
File: `src/backend/app/config.py` + `README.md`
- `AGENT_ENROLLMENT_TOKEN_TTL_MINUTES` (default 60).
- `AGENT_HEARTBEAT_TIMEOUT_MINUTES` (default 10).
- `AGENT_DEFAULT_SAMPLING_RATE` (default 100).

#### 1.8 Wire router
File: `src/backend/app/main.py` — `app.include_router(agents_router, prefix="/api")`.

#### 1.9 Tests
File: `src/backend/tests/test_api/test_agents_enrollment.py` (14 test, 290 dòng)
- 9 non-Postgres test (monkeypatch DB helpers, chạy mọi môi trường):
  - `test_create_enrollment_token_returns_plaintext` — admin issue token.
  - `test_register_agent_returns_api_key` — enroll flow.
  - `test_register_agent_rejects_invalid_token` — 400 trên token sai.
  - `test_heartbeat_requires_api_key` — 401 khi thiếu X-API-Key.
  - `test_heartbeat_with_valid_agent_key` — 200, status=active.
  - `test_revoked_agent_cannot_heartbeat` — 403.
  - `test_agent_config_endpoint` — GET /me/config trả policy + blocklist.
  - `test_admin_list_agents` — paginated list.
  - `test_blocklist_crud` — POST tạo entry.
- 5 Postgres integration test (chạy khi có `TEST_DATABASE_URL`):
  - `test_full_enroll_and_raw_log_with_agent_key` — E2E: issue token → enroll → raw-log ingest bằng X-API-Key → heartbeat → pull config → admin list → revoke → revoked không gửi được log.
  - `test_batch_ingest_with_agent_key_inherits_user_device` — agent gán user/device, batch 2 raw-log không cần user_id/device_id, verify auto-fill.
  - `test_enrollment_token_single_use` — token dùng 2 lần → lần 2 lỗi 400.
  - `test_blocklist_full_crud` — create/list/patch/delete.
  - `test_policy_update_bumps_version` — PATCH policy tăng version.

File: `src/backend/tests/test_api/test_routes.py` — update 1 test:
- `test_unauthorized_raw_log_ingest_returns_auth_error` — expected 403 → 401 (do tôi đổi auth semantic).

### Kết quả kiểm thử

| Môi trường | Pass | Fail | Skip | Ghi chú |
|---|---|---|---|---|
| Host (không PostgreSQL) | 9 | 0 | 5 | 5 integration test skip |
| Docker container (có PostgreSQL) | **14/14** agent test | 0 | 0 | Tất cả agent test pass |
| Full suite (container) | 182 | 12 | 17 | 12 fail đều là baseline có sẵn, 0 regression |

Baseline so sánh:
- Trước Phase 1: 181 pass / 13 fail
- Sau Phase 1: 182 pass / 12 fail ( thêm 14 test mới, sửa 1 test cũ, giảm 1 fail)

### Lint

| File | Lỗi |
|---|---|
| Tất cả file mới/sửa | **0 lỗi** |
| `session.py` F811 (x2) | có sẵn từ trước, không do Phase 1 |
| `test_database.py` I001 | có sẵn từ trước, không do Phase 1 |

### Files thêm/sửa

| File | Loại | Số dòng |
|---|---|---|
| `src/backend/app/db/agents.py` | **MỚI** | 380 |
| `src/backend/app/api/routes_agents.py` | **MỚI** | 315 |
| `src/backend/tests/test_api/test_agents_enrollment.py` | **MỚI** | 290 |
| `src/backend/app/db/session.py` | sửa | +65 dòng (4 bảng + seed helper) |
| `src/backend/app/core/security.py` | sửa | +36 dòng (agent auth) |
| `src/backend/app/api/routes.py` | sửa | +44 dòng (require_role_or_agent + sửa 2 endpoint) |
| `src/backend/app/schemas/schemas.py` | sửa | +120 dòng (14 schema + 3 Literal) |
| `src/backend/app/config.py` | sửa | +9 dòng (3 settings) |
| `src/backend/app/main.py` | sửa | +2 dòng (wire router) |
| `src/backend/tests/test_api/test_routes.py` | sửa | 1 dòng (403→401) |
| `README.md` | sửa | +4 dòng (env vars) |

### Endpoint sẵn sàng dùng

```
POST   /api/agents/enrollment-tokens          (admin JWT)
POST   /api/agents/register                   (enrollment token)
POST   /api/agents/heartbeat                  (X-API-Key)
GET    /api/agents/me/config                  (X-API-Key)
GET    /api/agents                            (admin/analyst JWT)
GET    /api/agents/{agent_id}                 (admin/analyst JWT)
PATCH  /api/agents/{agent_id}                 (admin JWT)
DELETE /api/agents/{agent_id}                 (admin JWT)
GET    /api/agents/blocklist                  (admin/analyst JWT)
POST   /api/agents/blocklist                  (admin JWT)
PATCH  /api/agents/blocklist/{entry_id}       (admin JWT)
DELETE /api/agents/blocklist/{entry_id}       (admin JWT)
GET    /api/agents/policy                     (admin/analyst JWT)
PATCH  /api/agents/policy                     (admin JWT)
POST   /api/admin/agents/mark-stale           (admin JWT)
POST   /api/raw-logs/ingest                   (X-API-Key HOẶC JWT)  ← sửa
POST   /api/raw-logs/batch                    (X-API-Key HOẶC JWT)  ← sửa
```

### Bước tiếp theo (Phase 2)

Server đã sẵn sàng cho agent enroll + gửi log. Phase 2 sẽ viết agent Python chạy trên máy nhân viên:
1. `src/agent/` package với service wrapper + SQLite buffer + HTTP transport.
2. `enroll.py` CLI dùng enrollment token.
3. Collectors: `logon` (Linux utmp + Windows Event 4624) + `http` (DNS sinkhole + blocklist cache).
4. Legal banner + system tray icon.

---

## Phase 2 Report

**Trạng thái:** HOÀN THÀNH — agent Python chạy ngầm với SQLite buffer + HTTPS transport + 2 collector (logon + http) đã hoạt động đầu cuối với Phase 1 server.

### 2.1 — Kiến trúc package

Tạo `src/agent/` (sibling của `src/backend/`) — 14 file code (~2400 dòng) + 8 file test (~1700 dòng).

```
src/agent/
├── __init__.py / __main__.py    # version + python -m agent
├── config.py                    # AgentConfig: env + CLI args (120 dòng)
├── state.py                     # AgentState JSON, atomic write, mode 0600 (130 dòng)
├── legal.py                     # banner khởi động (30 dòng)
├── enroll.py                    # CLI: enroll --server-url ... --enrollment-token ... (200 dòng)
├── service.py                   # AgentService: main loop, collectors + flusher + heartbeat + config-pull (446 dòng)
├── buffer.py                    # EventBuffer: SQLite local queue (WAL, claim/ack/nack) (280 dòng)
├── transport.py                 # Transport: httpx sync client, error classification (240 dòng)
├── config_client.py             # ConfigClient: pull /me/config, cache blocklist, sampling (220 dòng)
├── cli.py                       # agent {enroll|run|version} (120 dòng)
└── collectors/
    ├── base.py                  # Collector ABC + emit() với sampling + is_enabled (130 dòng)
    ├── logon.py                 # LinuxLogonCollector (wtmp 384 bytes), WindowsLogonCollector (stub) (257 dòng)
    └── http_dns.py              # DomainCheckCollector + DnsSniffCollector (root required) (342 dòng)
```

### 2.2 — State file (perm 0600, atomic write)
- `save_state` dùng temp file + `os.replace` để đảm bảo atomic (không partial write khi process chết giữa chừng).
- File mode 0o600; `load_state` từ chối nếu mode có bit group/world (`PermissionError`).
- `AgentState` dataclass: `agent_id, api_key, server_url, enrolled_at, hostname, last_heartbeat_at, last_config_pull_at, last_policy_version, extra`.

### 2.3 — SQLite buffer (`buffer.py`, 280 dòng)
- Schema: `events(id PK, source_id UNIQUE, payload_json, state 0=ready 1=in_flight, attempts, last_attempt_at, created_at)` + index `(state, id)`.
- **Idempotent**: `INSERT OR IGNORE` theo `source_id` — collector retry không tạo duplicate. Server cũng idempotent (Phase 1 ON CONFLICT) → defense in depth.
- **FIFO claim**: `UPDATE ... SET state=1, attempts=attempts+1` rồi `SELECT` post-UPDATE → BufferedEvent phản ánh attempts mới nhất.
- **Crash recovery**: `reset_in_flight()` đánh dấu các event state=1 về 0 — events đang claim dở khi process chết được phục hồi.
- **Eviction**: khi `count > max_events` xoá các row cũ nhất (FIFO).
- **WAL mode**: `PRAGMA journal_mode=WAL` cho phép reader/writer đồng thời.
- Thread-safe với `threading.Lock` + autocommit + `BEGIN IMMEDIATE` transaction.

### 2.4 — Transport (`transport.py`, 240 dòng)
- 5 method: `send_batch`, `send_single`, `heartbeat`, `get_config`, `register`.
- **Error classification** (4 loại exception):
  - 2xx (200/201) → success
  - 401/403 → `AuthRevokedError` (subclass của PermanentError) → stop sending
  - 429 + 5xx → `TransientError` → caller retry với backoff
  - 4xx khác → `PermanentError` → caller drop batch (không retry)
  - Network error (ConnectError, ReadTimeout) → `TransientError`
  - JSON decode error trên 2xx → `PermanentError` (server trả response lạ)
- Headers explicit qua từng call (không rely on default) — để test được và override được cho `register` (clear X-API-Key).

### 2.5 — ConfigClient (`config_client.py`, 220 dòng)
- Thread-safe cache bằng swap-toàn-dict.
- `pull()` lấy policy + blocklist từ server; detect `policy_version` change → log + emit callback.
- `pull_with_retry(max_attempts)` với exponential backoff + jitter.
- `is_blocked(value)` check 4 loại pattern:
  - `domain`: exact + suffix match (e.g. pattern "evil.com" match "api.evil.com", không match "evil.company.com")
  - `url`/`ip`: case-insensitive substring
  - `regex`: full regex (catch malformed regex)
  - unknown: fallback substring (conservative)
- `should_sample()` dùng `random.randint(1, 100) <= sampling_rate` để giảm tải khi admin giảm rate.

### 2.6 — LogonCollector (`collectors/logon.py`, 257 dòng)
- Parse `/var/log/wtmp` (binary, 384 bytes/record trên Linux x86_64 glibc).
- **Struct format** khám phá thực nghiệm: `hi32s4s32s256s20xhh2xqqq` (20-byte pad giữa ut_host và exit_status).
- Detect record type: USER_PROCESS (7) → `action: logon`; DEAD_PROCESS (8) → `action: logoff`; skip system events (BOOT/RUN_LVL/LOGIN_PROCESS).
- Skip `user == "reboot"` và `user == "LOGIN"` (system events).
- **Inode tracking** (`_last_inode`) + size check → detect rotation (file bị rename, inode đổi hoặc size shrink).
- **Persistence**: wtmp offset + inode lưu vào `state.wtmp_offset` file riêng (mode 0600) → restart không re-emit.
- Backoff exponential khi lỗi liên tiếp (cap 60s).
- Windows: stub `WindowsLogonCollector` mark unhealthy (Phase 4 sẽ dùng `pywin32` + WMI).

### 2.7 — HTTP/DNS collector (`collectors/http_dns.py`, 342 dòng)
- **`DomainCheckCollector`** (collector chính): thread-safe queue, các domain/URL được push vào queue qua `check_domain()`, worker thread drain mỗi 0.5s, phân loại allowed/blocked, emit event.
- **`_HttpBlockMixin._classify`**: trích domain từ URL (bỏ `http(s)://`, `www.`, path) trước khi match blocklist domain — fix bug ban đầu khi URL `https://wikileaks.org/path` không match `pattern=wikileaks.org, type=domain`.
- **`_emit_http`**: build payload với `url, domain, action, block_pattern, block_category, block_reason` (nếu bị chặn).
- **`DnsSniffCollector`** (advanced, cần root): bind UDP/53, parse DNS query thủ công (header 12 bytes + length-prefixed labels), emit event cho mỗi query. Tự mark unhealthy nếu không phải root.
- DNS parser có defensive cap (128 labels) chống malformed input.

### 2.8 — Main service + enroll (`service.py` 446 dòng, `enroll.py` 200 dòng)
- `AgentService.run()`:
  1. Load state + in legal banner.
  2. `EventBuffer.reset_in_flight()` recover events từ crash.
  3. `Transport` + `ConfigClient` + `pull_with_retry`.
  4. Build collectors theo policy, restore wtmp offset.
  5. Start collectors (threads).
  6. Start 3 asyncio tasks: flusher, heartbeat, config-puller.
  7. `wait` cho SIGINT/SIGTERM.
  8. Graceful shutdown: stop collectors, save wtmp offset, final flush, close transport/buffer.
- 3 loops với backoff exponential + jitter (1s → 60s cap).
- `enroll` flow: check existing state → resolve hostname/OS → `Transport.register` → save state. Refuse nếu device_id/assigned_user_id sẽ trigger FK violation (chỉ set khi caller truyền explicit).

### 2.9 — Tests (8 file, 148 test pass + 1 skip)

| File | Số test | Phủ |
|---|---|---|
| `test_buffer.py` | 24 | enqueue, dedup, FIFO claim, ack/nack, in_flight recovery, max_events eviction, concurrent threads, Unicode, persistence across close-reopen, WAL mode |
| `test_transport.py` | 29 | request shape, headers, error classification (2xx/4xx/5xx/401/403/429), network errors, JSON decode errors, register public endpoint |
| `test_config_client.py` | 29 | blocklist matching (domain/url/ip/regex), sampling rate, is_collector_enabled, thread-safe reads, parse resilience, pull_with_retry backoff |
| `test_state.py` | 15 | mode 0600, atomic write (failure leaves original), JSON round-trip, parent dir creation, optional fields |
| `test_logon_collector.py` | 16 | USER_PROCESS → logon, DEAD_PROCESS → logoff, skip system events, skip reboot/LOGIN users, new record pickup, rotation (inode change + size shrink), wtmp missing → unhealthy, read error recovery, unique source_id, offset persistence |
| `test_http_dns_collector.py` | 17 | classify block/not-block, URL domain extraction, disabled collector, sampling drops, queue overflow, DNS query parsing (exact/subdomain/uppercase/malformed/pointer), root-required DnsSniff |
| `test_enroll.py` | 15 | state file creation, refile/overwrite, no auto-set device_id/assigned_user_id (FK safety), proper error propagation (Permanent/Transient/FileExists), transport cleanup |
| `test_e2e.py` | 4 | **E2E với running server** (Phase 1 + Phase 2 đầu cuối): enroll → batch send → query verify; flusher_loop drains buffer; revoke stops sends; blocklist visible via config |

### 2.10 — Kết quả kiểm thử

| Môi trường | Pass | Fail | Skip | Ghi chú |
|---|---|---|---|---|
| Host (không PostgreSQL) | 145 | 0 | 4 | 4 e2e skip (cần TEST_DATABASE_URL) |
| Container (có PostgreSQL + server đang chạy) | **148** | 0 | 1 | 1 skip (test cần non-root, container chạy root) |
| **Full suite (Phase 1 + Phase 2)** | **330** | **12** | 1 | 12 fail = baseline có sẵn, **0 regression** |

**Smoke test thủ công (chạy trong container)**:
```
1. Admin issues enrollment token
2. Agent enrolls → agent_id=agent-309770b39399876e, hostname=...
3. Send raw log: created=1, failed=0
4. Heartbeat: status=active, policy_version=1
5. Config: policy_version=10, sampling=75%, collectors=3, blocklist=7
SMOKE TEST PASSED
```

### 2.11 — Lint

- Tất cả file mới: 0 lỗi ruff
- Không tạo lỗi mới ở file có sẵn

### 2.12 — Bugs tìm thấy và fix trong quá trình test (kỹ lưỡi)

1. **wtmp struct format sai**: lúc đầu dùng `hi32s4s32s256s24xhh2xqqq` (392 bytes) — sai. Format đúng `hi32s4s32s256s20xhh2xqqq` (384 bytes) khớp với file wtmp thật. Phát hiện qua test với record giả + verify trên `/var/log/wtmp` thật.
2. **attempts không tăng**: SELECT trước UPDATE trả về attempts cũ. Fix: UPDATE trước (bump attempts), rồi SELECT post-UPDATE.
3. **Source_id duplicate**: tính `self._offset - WTMP_RECORD_SIZE` cho cả 2 record trong cùng loop → cùng source_id. Fix: truyền `rec_offset` từ caller, dùng inode làm namespace.
4. **Rotation detection sai**: chỉ check `size < offset` không bắt được trường hợp unlink+create. Thêm inode tracking.
5. **URL không match blocklist domain**: `https://wikileaks.org/path` không suffix-match `wikileaks.org`. Fix: extract domain trước khi classify.
6. **chmod 0o000 bypass khi root**: test fail trong container chạy root. Fix: dùng `wtmp.unlink() + wtmp.mkdir()` thay vì chmod.
7. **FK violation khi enroll với device_id/assigned_user_id auto-set**: rows chưa tồn tại trong users/devices khi agent enroll trước khi admin chạy data import. Fix: mặc định None, caller truyền explicit.
8. **httpx sync Client không support ASGITransport**: e2e test fail. Fix: dùng container host IP (172.17.0.1:5173) thay vì in-process.
9. **Route ordering**: agent/{agent_id} nuốt /agents/blocklist và /agents/policy (đã fix ở Phase 1, Phase 2 phát hiện lại trong test setup).
10. **Datetime.utcnow() deprecated**: dùng `datetime.now(timezone.utc)` thay thế.

### 2.13 — Files

| File | Loại | Số dòng |
|---|---|---|
| `src/agent/__init__.py` | MỚI | 15 |
| `src/agent/__main__.py` | MỚI | 3 |
| `src/agent/config.py` | MỚI | 120 |
| `src/agent/state.py` | MỚI | 130 |
| `src/agent/buffer.py` | MỚI | 280 |
| `src/agent/transport.py` | MỚI | 240 |
| `src/agent/config_client.py` | MỚI | 220 |
| `src/agent/legal.py` | MỚI | 30 |
| `src/agent/enroll.py` | MỚI | 200 |
| `src/agent/service.py` | MỚI | 446 |
| `src/agent/cli.py` | MỚI | 120 |
| `src/agent/collectors/base.py` | MỚI | 130 |
| `src/agent/collectors/logon.py` | MỚI | 257 |
| `src/agent/collectors/http_dns.py` | MỚI | 342 |
| `src/agent/tests/test_buffer.py` | MỚI | 240 |
| `src/agent/tests/test_transport.py` | MỚI | 280 |
| `src/agent/tests/test_config_client.py` | MỚI | 250 |
| `src/agent/tests/test_state.py` | MỚI | 150 |
| `src/agent/tests/test_logon_collector.py` | MỚI | 290 |
| `src/agent/tests/test_http_dns_collector.py` | MỚI | 200 |
| `src/agent/tests/test_enroll.py` | MỚI | 200 |
| `src/agent/tests/test_e2e.py` | MỚI | 280 |

**Tổng Phase 2**: ~4000 dòng code + test, 0 regression, 148 test mới pass.

### 2.14 — Bước tiếp theo (Phase 3)

Phase 3: viết normalizer worker (raw_user_logs → event_logs) + near-real-time ML scoring hook.
- Service `src/backend/app/services/normalizer.py` đọc raw logs nơi `normalized_event_id IS NULL`, map theo `event_type`, insert vào `event_logs`, update FK.
- Trigger bằng background task trong FastAPI `lifespan` hoặc endpoint `POST /api/admin/run-normalizer` (admin only).
- Sau normalize, nếu user có event mới, enqueue `analyze_user(user_id)` → chạy OCSVM scoring → tạo alert nếu anomaly.
- Khi đó dashboard sẽ tự động thấy event mới từ agent real-time mà không cần bấm "Import data".

---

## Phase 3 Report

_(chưa bắt đầu)_

---

## Phase 4 Report

_(chưa bắt đầu)_
