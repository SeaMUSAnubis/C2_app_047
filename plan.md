# Backend implementation plan for current frontend

## 1. Scope and assumptions

Goal: implement/adjust the backend so the already-merged frontend can run against real API data without changing frontend code unless absolutely necessary.

Assumptions:

- Frontend should remain the source of truth for the current UI contract because it has already been merged to `main`.
- `VITE_API_BASE_URL` will include the backend API prefix. Recommended local value: `http://localhost:8000/api`.
- The existing FastAPI backend under `src/` should be reused rather than replaced.
- Runtime database remains PostgreSQL via `DATABASE_URL`; no SQLite fallback is planned.
- Existing normalized backend schemas can stay available for internal/admin use, but the frontend-facing responses must match the TypeScript types in `frontend/src/types/*`.
- Current frontend pages are Overview, Users, Devices and Event Logs. Alerts, Data Import, ML Models and Settings are placeholder pages and do not need backend endpoints for this iteration.
- Demo credentials in the frontend are `admin@demo.com` and `analyst@demo.com`. Current backend requires passwords `admin123` and `analyst123`; this should be documented clearly because frontend mock mode accepts any password.

## 2. Repository findings

Frontend API calls are centralized in `frontend/src/lib/apiClient.ts`:

- `POST ${VITE_API_BASE_URL}/auth/login`
- `GET ${VITE_API_BASE_URL}/dashboard/summary`
- `GET ${VITE_API_BASE_URL}/users`
- `GET ${VITE_API_BASE_URL}/devices`
- `GET ${VITE_API_BASE_URL}/logs`

Frontend expected response types:

- `LoginResponse` uses camelCase `accessToken` and user `{ id, email, name, role }`.
- `DashboardSummary` uses camelCase KPI fields.
- `User[]`, `Device[]`, and `EventLog[]` are returned as direct arrays, not paginated wrappers.
- Frontend stores the token from `session.accessToken` and sends it as `Authorization: Bearer <token>`.

Backend current state:

- FastAPI app exists in `src/main.py`, mounted with `app.include_router(router, prefix="/api")`.
- Existing routes in `src/api/routes.py` include auth, users, devices, logs, raw-logs.
- PostgreSQL schema initialization exists in `src/services/database.py`.
- Existing tests cover health, auth, protected endpoints, users/devices seed reads, event ingest and raw-log ingest.

Main compatibility gaps:

- Login response currently returns `access_token`, while frontend expects `accessToken`.
- Backend `AccountPublic` returns `full_name`, while frontend expects `name`.
- Backend list endpoints return `{ items, total, limit, offset }`, while frontend expects arrays directly.
- Backend user fields are `username`, `full_name`, `job_role`, `risk_score`; frontend expects `account`, `name`, `role`, `riskScore`.
- Backend device status values are `online/offline/retired`; frontend expects `active/inactive`.
- Backend device assigned user field is `assigned_username`/`assigned_user_id`; frontend expects `assignedUser`.
- Backend log fields are `source_id`, `source_file`, `raw`/`metadata`; frontend expects `sourceId`, `sourceFile`, `rawDetail`.
- Backend does not currently expose `/api/dashboard/summary`.
- Backend currently lacks CORS middleware. Browser requests from Vite dev server `http://localhost:5173` may fail even if API routes work.

## 3. Frontend-facing API endpoints to implement

All endpoint paths below are relative to `/api` when backend runs from `src.main:app`.

### 3.1 `POST /auth/login`

Purpose: authenticate an admin or analyst and return a token in the shape the frontend persists.

Request:

```json
{
  "email": "admin@demo.com",
  "password": "admin123"
}
```

Response expected by frontend:

```json
{
  "accessToken": "<jwt>",
  "user": {
    "id": "1",
    "email": "admin@demo.com",
    "name": "Demo Admin",
    "role": "admin"
  }
}
```

Notes:

- Keep accepting the existing backend request body.
- Return `401` for invalid credentials.
- Prefer adding a frontend-compatible response schema instead of changing frontend storage.
- Consider whether to also keep the old `access_token`, `token_type`, `expires_in` fields for backward compatibility. If included, frontend will ignore them.

### 3.2 `GET /dashboard/summary`

Purpose: provide KPI cards for `DashboardPage`.

Headers:

```text
Authorization: Bearer <token>
```

Response:

```json
{
  "totalUsers": 128,
  "totalDevices": 96,
  "totalLogs": 54210,
  "openAlerts": 14,
  "highCriticalAlerts": 5,
  "averageRiskScore": 42,
  "currentModelVersion": "iForest-v0.1-demo",
  "lastImportTime": "2026-06-13T09:30:00+07:00"
}
```

Backend data source:

- `totalUsers`: count from `users`.
- `totalDevices`: count from `devices`.
- `totalLogs`: count from `event_logs`, optionally include `raw_user_logs` only if product decides raw logs should be visible in the event log count.
- `openAlerts`: count alerts where status is not `resolved` and not `false_positive`.
- `highCriticalAlerts`: count open alerts with severity `high` or `critical`.
- `averageRiskScore`: average user risk score, device risk score, or a documented combined metric. Recommended v1: average over `users.risk_score`.
- `currentModelVersion`: latest `model_artifacts.model_version` by `created_at`, nullable if none.
- `lastImportTime`: max timestamp from `event_logs` or `raw_user_logs`, nullable if none.

### 3.3 `GET /users`

Purpose: populate `UsersPage`.

Headers:

```text
Authorization: Bearer <token>
```

Frontend currently sends no query params. Backend may still support optional filters for future use.

Response:

```json
[
  {
    "id": "ACM0001",
    "account": "acm0001",
    "name": "Alice M. Carter",
    "department": "Finance",
    "role": "Accountant",
    "status": "active",
    "riskScore": 18,
    "assignedDevices": 1,
    "openAlerts": 0,
    "lastSeen": "2026-06-13T08:12:00Z"
  }
]
```

Mapping from current DB:

- `id` <- `users.id`
- `account` <- `users.username`
- `name` <- `users.full_name`
- `department` <- `users.department`
- `role` <- `users.job_role`
- `status` <- `users.status`
- `riskScore` <- `users.risk_score`
- `assignedDevices` <- count from `devices.assigned_user_id`
- `openAlerts` <- count from `alerts.user_id` where status is open
- `lastSeen` <- max `devices.last_seen` for assigned devices, or max `event_logs.timestamp` for user

### 3.4 `GET /devices`

Purpose: populate `DevicesPage`.

Headers:

```text
Authorization: Bearer <token>
```

Response:

```json
[
  {
    "id": "PC-1001",
    "hostname": "FIN-WS-1001",
    "assignedUser": "acm0001",
    "department": "Finance",
    "status": "active",
    "riskScore": 12,
    "openAlerts": 0,
    "lastSeen": "2026-06-13T08:12:00Z"
  }
]
```

Mapping from current DB:

- `id` <- `devices.id`
- `hostname` <- `devices.hostname`
- `assignedUser` <- joined `users.username`
- `department` <- joined `users.department`
- `status` <- map `online` to `active`; map `offline` and `retired` to `inactive`
- `riskScore` <- `devices.risk_score`
- `openAlerts` <- count from `alerts.device_id` where status is open
- `lastSeen` <- `devices.last_seen`

### 3.5 `GET /logs`

Purpose: populate `LogsPage`.

Headers:

```text
Authorization: Bearer <token>
```

Response:

```json
[
  {
    "id": "1",
    "timestamp": "2026-06-13T16:10:00+07:00",
    "eventType": "logon",
    "userId": "ACM0001",
    "deviceId": "PC-1001",
    "action": "LOGIN_SUCCESS",
    "sourceFile": "logon.csv",
    "sourceId": "cert-r42:logon:123",
    "rawDetail": "Successful logon from FIN-WS-1001"
  }
]
```

Mapping from current DB:

- `id` <- `event_logs.id` converted to string
- `timestamp` <- `event_logs.timestamp`
- `eventType` <- `event_logs.event_type`
- `userId` <- `event_logs.user_id`
- `deviceId` <- `event_logs.device_id`
- `action` <- `event_logs.action` or fallback `"UNKNOWN"`
- `sourceFile` <- `event_logs.source_file`
- `sourceId` <- `event_logs.source_id`
- `rawDetail` <- concise string derived from `resource`, `metadata`, or `raw`

Recommended default ordering and limit:

- Order by timestamp desc, id desc.
- Return first 50 or 100 records to avoid rendering very large tables. Because frontend currently does not send pagination params, choose a sensible backend default.

## 4. Database/model/schema plan

Existing tables to reuse:

- `app_accounts`
- `users`
- `devices`
- `event_logs`
- `raw_user_logs`
- `alerts`
- `model_artifacts`

No new table is strictly required for frontend compatibility.

Needed database service additions:

- `get_dashboard_summary()`
- `list_frontend_users(limit: int = 200)`
- `list_frontend_devices(limit: int = 200)`
- `list_frontend_logs(limit: int = 100)`

Needed query behavior:

- Aggregate counts for dashboard.
- Join users to devices for device owner and department.
- Aggregate open alert counts per user/device.
- Convert DB snake_case fields to frontend camelCase response models.

Optional but recommended indexes if data grows:

- `CREATE INDEX IF NOT EXISTS idx_devices_assigned_user ON devices(assigned_user_id)`
- `CREATE INDEX IF NOT EXISTS idx_alerts_user_status ON alerts(user_id, status)`
- `CREATE INDEX IF NOT EXISTS idx_alerts_device_status ON alerts(device_id, status)`
- Existing event log timestamp/user/device indexes are already present.

## 5. Files to create or modify

Modify:

- `src/models/schemas.py`
  - Add frontend-compatible Pydantic response models:
    - `FrontendAuthUser`
    - `FrontendLoginResponse`
    - `DashboardSummary`
    - `FrontendUser`
    - `FrontendDevice`
    - `FrontendEventLog`
  - Keep existing backend schemas unless intentionally deprecating them.

- `src/api/routes.py`
  - Adjust `POST /auth/login` response model or add serialization aliases so response includes `accessToken` and user `name`.
  - Add `GET /dashboard/summary`.
  - Decide whether existing `/users`, `/devices`, `/logs` should become frontend-compatible arrays, or whether to introduce separate adapter routes.
  - Recommended for zero frontend changes: make existing `GET /users`, `GET /devices`, `GET /logs` return frontend-compatible arrays by default.

- `src/services/database.py`
  - Add dashboard aggregate queries.
  - Add frontend list query functions and field mapping.
  - Add missing indexes if chosen.

- `src/main.py`
  - Add CORS middleware for local frontend dev.
  - Recommended env-driven origins with default including `http://localhost:5173`.

- `src/config.py`
  - Add `cors_origins` setting, for example `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`.

- `.env.example`
  - Document `CORS_ORIGINS`.
  - Document local frontend value `VITE_API_BASE_URL=http://localhost:8000/api` for `frontend/.env.local`.

- `docs/contracts/API_CONTRACT.md`
  - Update or add a section for current frontend-facing contract.
  - Note any backward-compatible internal response shape if retained.

- `tests/test_api/test_routes.py`
  - Add tests for frontend-compatible login, dashboard summary, users, devices and logs response shape.

Potentially create:

- `frontend/.env.example`
  - `VITE_API_BASE_URL=http://localhost:8000/api`
  - This is documentation-only and does not change frontend runtime behavior.

## 6. Compatibility decision points

Recommended approach:

- Keep frontend unchanged.
- Make the backend endpoints already called by frontend return the frontend-compatible contract.
- If older paginated/admin contracts are still needed, add versioned/internal endpoints later, for example `/api/admin/users` or `/api/v1/users`.

Alternative approach:

- Keep backend paginated contracts and modify frontend `apiClient.ts` to unwrap `items` and map snake_case to camelCase.
- This is not recommended for this task because frontend has already been merged and the assignment says not to modify frontend unless necessary.

## 7. How to run backend

Install dependencies:

```bash
pip install -r requirements.txt
```

Start PostgreSQL:

```bash
docker compose up -d db
```

Run API locally:

```bash
uvicorn src.main:app --reload --port 8000
```

Or:

```bash
make run
```

Run full stack with Docker:

```bash
docker compose up --build
```

Frontend local env expected:

```bash
VITE_API_BASE_URL=http://localhost:8000/api
```

Then run frontend from `frontend/`:

```bash
npm install
npm run dev
```

## 8. How to test backend

Static/lint:

```bash
ruff check src tests
```

Unit/API tests:

```bash
pytest -q
```

PostgreSQL integration tests:

```bash
export TEST_DATABASE_URL=postgresql://ueba:ueba@localhost:5432/ueba_test
pytest -q
```

Manual smoke test:

```bash
curl -s http://localhost:8000/api/health
curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@demo.com","password":"admin123"}'
```

Browser integration smoke:

- Start backend on `http://localhost:8000`.
- Start frontend on `http://localhost:5173`.
- Set frontend `VITE_API_BASE_URL=http://localhost:8000/api`.
- Login as `admin@demo.com / admin123`.
- Verify Dashboard, Users, Devices and Logs render without falling back to mock data.

## 9. Step-by-step implementation plan

1. Add frontend-compatible response schemas in `src/models/schemas.py`.
2. Add CORS settings in `src/config.py` and CORS middleware in `src/main.py`.
3. Add database service functions for dashboard aggregates and frontend-shaped list data.
4. Update `POST /auth/login` to emit `accessToken` and `user.name`.
5. Implement `GET /dashboard/summary`.
6. Update `GET /users`, `GET /devices`, `GET /logs` to return direct arrays in the current frontend contract.
7. Update `docs/contracts/API_CONTRACT.md` with the frontend-facing contract and local env setup.
8. Add/adjust API tests for each frontend-called endpoint.
9. Run lint and tests.
10. Run manual smoke with backend and frontend together.

## 10. Completion checklist

- [ ] `POST /api/auth/login` returns `accessToken` and user `{ id, email, name, role }`.
- [ ] Frontend can store token and send `Authorization: Bearer <token>`.
- [ ] `GET /api/dashboard/summary` exists and returns all KPI fields in camelCase.
- [ ] `GET /api/users` returns a direct `User[]` with `account`, `riskScore`, `assignedDevices`, `openAlerts`, `lastSeen`.
- [ ] `GET /api/devices` returns a direct `Device[]` with `assignedUser`, `status` as `active`/`inactive`, `riskScore`, `openAlerts`.
- [ ] `GET /api/logs` returns a direct `EventLog[]` with `eventType`, `sourceFile`, `sourceId`, `rawDetail`.
- [ ] CORS allows the Vite dev origin.
- [ ] `.env.example` documents backend and frontend env expectations.
- [ ] API contract docs match implemented behavior.
- [ ] `ruff check src tests` passes.
- [ ] `pytest -q` passes.
- [ ] PostgreSQL integration tests pass with `TEST_DATABASE_URL`.
- [ ] Manual frontend smoke test passes without editing frontend source.
