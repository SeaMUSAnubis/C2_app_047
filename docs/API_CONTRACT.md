# API Contract

This file is the working contract between backend and frontend. Endpoint shapes should be finalized here before frontend integration.

## Planned endpoint groups

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

## Response conventions

- Use ISO 8601 timestamps.
- Use stable IDs from backend/database, not frontend-generated IDs.
- Return pagination metadata for list endpoints.
- Return machine-readable error codes with human-readable messages.

Detailed request/response schemas should be added as backend routes are implemented.
