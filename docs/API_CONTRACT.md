# API Contract

Hợp đồng API giữa **backend FastAPI** và **frontend React** + **agent Python**.
Mọi endpoint shapes finalize ở đây trước khi integrate.

> **Status**: Updated to v0.1.0 (Phase 1 + 3 + 4 done). The full live
> reference is always at `GET /docs` (Swagger UI) on a running server.

## Cấu trúc response chuẩn

Tất cả response trả về JSON. Lỗi trả về:

```json
{
  "detail": "Human-readable error message"
}
```

Status code semantic:
- `200` — OK.
- `201` — Created.
- `204` — No content.
- `400` — Bad request (malformed).
- `401` — Not authenticated.
- `403` — Authenticated but lacking permission.
- `404` — Resource not found.
- `409` — Conflict (duplicate).
- `422` — Validation error.
- `500` — Internal error.

## Pagination

List endpoints dùng `limit` + `offset` query params. Response shape:

```json
{
  "items": [...],
  "total": 1234,
  "limit": 50,
  "offset": 0
}
```

Hoặc với header `X-Total-Count` (cho browser fetch).

## Auth

Mọi endpoint yêu cầu auth trừ `POST /api/auth/login`, `GET /api/health`,
`POST /api/agents/register` (cần enrollment token thay vì JWT).

Header: `Authorization: Bearer <jwt>` (human) hoặc `X-API-Key: o47ag_xxx`
(agent).

---

## Auth

```
POST /api/auth/login
```

Request:
```json
{ "email": "admin@demo.com", "password": "admin123" }
```
Response 200:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": "1", "email": "admin@demo.com", "name": "Demo Admin", "role": "admin" }
}
```

```
GET /api/auth/me
```
Response 200: user object.

---

## Dashboard

```
GET /api/dashboard/summary
```
Response 200:
```json
{
  "total_users": 100,
  "total_devices": 95,
  "total_logs": 1234567,
  "active_alerts": 23,
  "high_risk_users": 5,
  "critical_alerts": 2,
  "blocked_websites": 12
}
```

```
GET /api/dashboard/overview
```
Response 200: full dashboard payload (KPIs, risk trend, severity
volume, risk distribution, alerts, risky entities, timeline).

---

## Users (CRUD)

```
GET    /api/users?limit=&offset=    (admin, security_manager, analyst)
GET    /api/users/{user_id}         (admin, security_manager, analyst)
POST   /api/users                   (admin)
PATCH  /api/users/{user_id}         (admin)
```

User object:
```json
{
  "id": "ACM0001",
  "username": "alice",
  "full_name": "Alice Johnson",
  "email": "alice@corp.com",
  "department": "Engineering",
  "job_role": "Senior Engineer",
  "status": "active",
  "risk_score": 42,
  "app_account_id": 12,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-06-22T10:00:00Z"
}
```

---

## Devices (CRUD)

```
GET    /api/devices?limit=&offset=
GET    /api/devices/{device_id}
POST   /api/devices                 (admin)
PATCH  /api/devices/{device_id}     (admin)
```

Device object:
```json
{
  "id": "PC-1234",
  "hostname": "alice-laptop",
  "os": "macos",
  "ip_address": "10.0.0.42",
  "assigned_user_id": "ACM0001",
  "status": "active",
  "risk_score": 35,
  "last_seen": "2026-06-22T10:00:00Z",
  "created_at": "...",
  "updated_at": "..."
}
```

---

## Event logs

```
POST /api/logs/ingest
```
Request: `EventIngest` schema (see `DATA_CONTRACT.md`).
Response 201: created event_log.

```
GET /api/logs?user_id=&device_id=&from=&to=&limit=&offset=
```
Response 200: paginated list of `EventRead`.

---

## Alerts

```
GET /api/alerts?status=&severity=&user_id=&device_id=&limit=&offset=
```
Response 200: paginated list of `FrontendAlert` (id, title, severity,
status, riskScore, time, etc.).

```
PATCH /api/alerts/{alert_id}/status
```
Request: `{ "status": "investigating" | "resolved" | "false_positive" }`.
Response 200: updated alert.

---

## Raw logs (agent ingest)

```
POST /api/raw-logs/ingest
POST /api/raw-logs/batch
```
Auth: agent X-API-Key HOẶC admin/analyst JWT.
Request: `RawLogIngest` (see `DATA_CONTRACT.md`).
Response 201 / 200: created raw_log.

```
GET /api/raw-logs?user_id=&device_id=&event_type=&limit=&offset=
GET /api/raw-logs/{log_id}
```
Response: paginated `RawLogRead`.

---

## ML / Models

```
POST /api/models/{model_version}/infer
```
Request: `{ "features": {"n_logon": 5, ...}, "user_id": "ACM0001" }`.
Response: `ModelInferResponse` (prediction, scores, risk_score, severity).

```
GET /api/models/{model_version}
GET /api/models/{model_version}/metrics
```

---

## Demo analysis (CSV-based, single shot)

```
POST /api/demo/analyze
POST /api/analysis/analyze
```
Request: `{ "user_id": "ACM0001", "events": [...] }`.
Response: `AnalyzeResponse` (is_anomaly, scores, explanation).

```
POST /api/demo/analyze-all         (admin or security_manager)
POST /api/analysis/analyze-all
```
Analyzes all users end-to-end.

---

## My risk (employee self-service)

```
GET /api/me/overview
```
Returns the current user's own data (risk score, recent alerts, devices,
logs). Used by `/my-risk` page.

---

## Admin accounts (admin only)

```
GET    /api/admin/accounts
POST   /api/admin/accounts
PATCH  /api/admin/accounts/{account_id}
```

---

## Agents (Phase 1)

```
POST /api/agents/enrollment-tokens                (admin)
```
Request: `{ "expires_minutes": 60 }`.
Response 201: `{ "token": "o47enr_xxx", "token_id": "...", "expires_at": "...", "created_at": "..." }`.

```
POST /api/agents/register                        (public, enrollment token in body)
```
Request: `{ "enrollment_token": "o47enr_xxx", "hostname": "alice-laptop", "os": "linux", "os_version": "5.15" }`.
Response 201: `{ "agent_id": "agent-abc123", "api_key": "o47ag_xxx" }`. **The api_key is shown once.**

```
POST /api/agents/heartbeat                       (agent X-API-Key)
```
Request: `{ "agent_id": "agent-abc123", "status": "active" }`.
Response 200: `{ "status": "active", "policy_version": 10, "config_version": 5 }`.

```
GET  /api/agents/me/config                       (agent X-API-Key)
```
Response 200:
```json
{
  "agent_id": "agent-abc123",
  "policy": { "policy_version": 10, "sampling_rate": 100, "enabled_collectors": ["logon", "http", ...] },
  "blocklist": [{ "id": 1, "pattern": "evil.com", "pattern_type": "domain", "enabled": true, ... }],
  "config_version": 5,
  "fetched_at": "..."
}
```

```
GET    /api/agents?limit=&offset=                (admin, security_manager, analyst)
GET    /api/agents/{agent_id}
PATCH  /api/agents/{agent_id}                     (admin)
DELETE /api/agents/{agent_id}                     (admin)
```
PATCH body: `{ "status": "active"|"offline"|"revoked", "policy_version": 11, "device_id": "PC-1234", "assigned_user_id": "ACM0001" }`.
DELETE response: revoked agent object.

```
POST /api/admin/agents/mark-stale                (admin)
```
Optional `?timeout_minutes=15`. Returns `{ "flipped_to_offline": 3 }`.

---

## Blocklist (Phase 1)

```
GET    /api/agents/blocklist?enabled_only=true
POST   /api/agents/blocklist                      (admin)
PATCH  /api/agents/blocklist/{entry_id}           (admin)
DELETE /api/agents/blocklist/{entry_id}           (admin)
```
Entry body:
```json
{ "pattern": "evil.com", "pattern_type": "domain", "category": "malware", "reason": "...", "enabled": true }
```
Entry object: `{ "id": 1, "pattern": "evil.com", "pattern_type": "domain", "category": "...", "reason": "...", "enabled": true, "created_at": "...", "updated_at": "..." }`.

---

## Policy (Phase 1)

```
GET   /api/agents/policy                          (admin, security_manager, analyst)
PATCH /api/agents/policy                          (admin)
```
Response / body:
```json
{
  "policy_version": 10,
  "sampling_rate": 100,
  "enabled_collectors": ["logon", "http", "device", "file", "email", "process", "network"],
  "updated_at": "..."
}
```

---

## Admin — Normalizer + Scoring (Phase 3)

```
POST /api/admin/run-normalizer
```
Optional params: `batch_size`, `trigger_scoring` (default true).
Response 200:
```json
{
  "started_at": "...",
  "duration_ms": 45.2,
  "processed": 42,
  "failed": 0,
  "pending_before": 0,
  "users_with_new_events": ["ACM0001", "BTR0002"],
  "errors": []
}
```

```
GET /api/admin/normalizer-stats
```
Response 200: stats dict (see `services/normalizer.py:NormalizerStats`).

```
POST /api/admin/score-user/{user_id}
```
Optional `?lookback_minutes=1440`.
Response 200: outcome `{ user_id, is_anomaly, risk_score, alert_created, alert_id, ... }`.

```
GET /api/admin/scoring-stats
```
Response 200: `ScoringStats` dict.

---

## OpenAPI

The full schema (with request/response examples) is at:

- `http://localhost:8000/docs` (Swagger UI)
- `http://localhost:8000/redoc` (ReDoc)
- `http://localhost:8000/openapi.json` (raw OpenAPI 3)

When integrating a new client, prefer to **generate** types from the
OpenAPI spec (e.g. `openapi-typescript` for TS clients) rather than
hand-write them.

---

## Changelog

- **v0.1.0** (2026-06-22): Initial release with Phase 1+3+4 endpoints.
- Phase 2 (agent core) doesn't expose new HTTP endpoints (uses the
  ones above with X-API-Key).
- Phase 5b (self-update) doesn't add new HTTP endpoints (uses
  `agent update` CLI subcommand).
