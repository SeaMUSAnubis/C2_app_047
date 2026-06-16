# API Contract

This file is the working contract between backend and frontend. Endpoint shapes should be finalized here before frontend integration.

## Endpoint groups

```text
POST /api/auth/login
GET  /api/auth/me
GET  /api/dashboard/summary

GET  /api/users
GET  /api/users/{user_id}
POST /api/users
PATCH /api/users/{user_id}

GET  /api/devices
GET  /api/devices/{device_id}
POST /api/devices
PATCH /api/devices/{device_id}

POST /api/logs/ingest
GET  /api/logs
GET  /api/logs/timeline

GET  /api/alerts
GET  /api/alerts/{alert_id}
PATCH /api/alerts/{alert_id}

POST /api/models/train
POST /api/models/{model_version}/infer
GET  /api/models/{model_version}/metrics
```

## Frontend-compatible contract

The following shapes match the TypeScript types in `frontend/src/types/*`.

### Auth

`POST /api/auth/login`

Request:

```json
{
  "email": "admin@demo.com",
  "password": "admin123"
}
```

Response (camelCase):

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

Demo accounts:

- `admin@demo.com / admin123`
- `analyst@demo.com / analyst123`

`GET /api/auth/me` requires `Authorization: Bearer <jwt>` and returns the current account.

### Dashboard

`GET /api/dashboard/summary` requires a token.

Response (camelCase):

```json
{
  "totalUsers": 3,
  "totalDevices": 3,
  "totalLogs": 0,
  "openAlerts": 0,
  "highCriticalAlerts": 0,
  "averageRiskScore": 22.3,
  "currentModelVersion": null,
  "lastImportTime": null
}
```

### Users

`GET /api/users` requires a token. Returns a direct array (no pagination wrapper).

Response item (camelCase):

```json
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
```

### Devices

`GET /api/devices` requires a token. Returns a direct array (no pagination wrapper).

Response item (camelCase):

```json
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
```

Status values: `active` (DB: `online`) or `inactive` (DB: `offline`, `retired`).

### Logs

`GET /api/logs` requires a token. Returns a direct array (no pagination wrapper), ordered by timestamp desc, limited to 100 records.

Response item (camelCase):

```json
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
```

## Internal/admin contract

The following endpoints retain the original snake_case, paginated shapes for internal/admin use:

- `POST /api/logs/ingest` - event ingest (returns full event record)
- `POST /api/users`, `PATCH /api/users/{user_id}`, `GET /api/users/{user_id}` - CRUD
- `POST /api/devices`, `PATCH /api/devices/{device_id}`, `GET /api/devices/{device_id}` - CRUD
- `POST /api/raw-logs/ingest`, `POST /api/raw-logs/batch`, `GET /api/raw-logs` - raw log management

## Response conventions

- Use ISO 8601 timestamps.
- Use stable IDs from backend/database, not frontend-generated IDs.
- Frontend-facing list endpoints return direct arrays.
- Admin/internal endpoints may use pagination with `{ items, total, limit, offset }`.
- Return machine-readable error codes with human-readable messages.

## Environment variables

Backend:

```text
DATABASE_URL=postgresql://ueba:ueba@localhost:5432/ueba
JWT_SECRET=change-me-in-production
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Frontend (`frontend/.env.local`):

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

## LLM Provider

Alert explanation uses Mistral Chat Completions:

- Endpoint: `POST https://api.mistral.ai/v1/chat/completions`
- Auth header: `Authorization: Bearer <MISTRAL_API_KEY>`
- Default model: `mistral-small-latest`
- Config variables:
  - `MISTRAL_API_KEY`
  - `MISTRAL_MODEL`
  - `MISTRAL_CHAT_COMPLETIONS_URL`

If the API key is missing or the Mistral request fails, the backend returns a deterministic rule-based fallback explanation.
