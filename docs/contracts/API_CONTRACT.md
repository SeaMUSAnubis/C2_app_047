# API Contract

This file is the working contract between backend and frontend. Endpoint shapes should be finalized here before frontend integration.

## Endpoint groups

```text
POST /api/auth/login
GET  /api/auth/me

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

## Implemented in Sprint 3 backend

Runtime persistence uses PostgreSQL through `DATABASE_URL`; SQLite is not used.

### Auth

`POST /api/auth/login`

Request:

```json
{
  "email": "admin@demo.com",
  "password": "admin123"
}
```

Response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "id": 1,
    "email": "admin@demo.com",
    "full_name": "Demo Admin",
    "role": "admin"
  }
}
```

Demo accounts:

- `admin@demo.com / admin123`
- `analyst@demo.com / analyst123`

`GET /api/auth/me` requires `Authorization: Bearer <jwt>` and returns the current account.

### Users

`GET /api/users` requires a token. Query filters:

- `department`
- `job_role`
- `status`
- `search`
- `limit`
- `offset`

`POST /api/users` and `PATCH /api/users/{user_id}` require role `admin`.

User shape:

```json
{
  "id": "ACM0001",
  "username": "acm0001",
  "full_name": "Alice M. Carter",
  "email": "alice.carter@example.com",
  "department": "Finance",
  "job_role": "Accountant",
  "status": "active",
  "risk_score": 18,
  "created_at": "2026-06-13T08:00:00Z",
  "updated_at": "2026-06-13T08:00:00Z"
}
```

### Devices

`GET /api/devices` requires a token. Query filters:

- `status`
- `os`
- `assigned_user_id`
- `limit`
- `offset`

`POST /api/devices` and `PATCH /api/devices/{device_id}` require role `admin`.

Device shape:

```json
{
  "id": "PC-1001",
  "hostname": "FIN-WS-1001",
  "os": "Windows 11",
  "ip_address": "10.10.1.21",
  "assigned_user_id": "ACM0001",
  "assigned_username": "acm0001",
  "assigned_user_name": "Alice M. Carter",
  "status": "online",
  "risk_score": 12,
  "last_seen": "2026-06-13T08:12:00Z",
  "created_at": "2026-06-13T08:00:00Z",
  "updated_at": "2026-06-13T08:00:00Z"
}
```

### Logs

`POST /api/logs/ingest` requires a token and upserts by `source_id` to avoid duplicate imports.

Request:

```json
{
  "source_id": "cert-r42:logon:123",
  "source_file": "logon.csv",
  "timestamp": "2010-01-04T08:15:00Z",
  "user_id": "ACM0001",
  "device_id": "PC-1001",
  "event_type": "logon",
  "action": "Logon",
  "resource": "PC-1001",
  "metadata": {},
  "raw": {}
}
```

`GET /api/logs` requires a token. Query filters:

- `user_id`
- `device_id`
- `event_type`
- `limit`
- `offset`

## Response conventions

- Use ISO 8601 timestamps.
- Use stable IDs from backend/database, not frontend-generated IDs.
- Return pagination metadata for list endpoints.
- Return machine-readable error codes with human-readable messages.

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
