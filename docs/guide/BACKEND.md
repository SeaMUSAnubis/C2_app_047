# Backend Guide

Tài liệu này mô tả cách vận hành backend FastAPI của UEBA Endpoint Monitoring và cách kết nối với frontend hiện tại.

## Tổng quan

Backend nằm trong `src/`:

```text
src/
  main.py              FastAPI app entrypoint, CORS, lifespan init DB
  api/routes.py        API routes, auth dependency, RBAC
  config.py            Settings đọc từ .env
  models/schemas.py    Pydantic request/response models
  services/
    auth.py            Password hashing + JWT helper
    database.py        PostgreSQL schema, seed cơ bản, query helpers
    llm.py             Mistral explanation service + fallback
```

Runtime persistence dùng PostgreSQL qua `DATABASE_URL`. Backend không dùng SQLite.

## Yêu cầu

- Python 3.11+ khuyến nghị.
- PostgreSQL 16, có thể chạy bằng `docker compose`.
- Dependencies trong `requirements.txt`.
- Frontend dùng `VITE_API_BASE_URL` trỏ tới backend API prefix.

## Environment

Copy `.env.example` thành `.env` nếu chưa có:

```bash
cp .env.example .env
```

Các biến chính:

```text
DATABASE_URL=postgresql://ueba:ueba@localhost:5432/ueba
JWT_SECRET=replace-with-a-long-random-secret
JWT_EXPIRES_MINUTES=480
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

MISTRAL_API_KEY=
MISTRAL_MODEL=mistral-small-latest
MISTRAL_CHAT_COMPLETIONS_URL=https://api.mistral.ai/v1/chat/completions
```

Frontend local env:

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

Repo có `frontend/.env.example` với giá trị này.

## Cài dependencies

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Nếu không dùng venv:

```bash
pip install -r requirements.txt
```

## Chạy database

```bash
docker compose up -d db
```

Kiểm tra container:

```bash
docker compose ps
```

Service `db` phải ở trạng thái healthy trước khi chạy API hoặc seed data.

## Seed dữ liệu demo

Backend tự seed accounts/users/devices cơ bản khi app khởi động hoặc khi gọi `initialize_database()`.

Demo accounts:

- `admin@demo.com / admin123`
- `analyst@demo.com / analyst123`

Để seed thêm mock data cho test thủ công Dashboard/Logs:

```bash
.venv/bin/python scripts/seed_mock_data.py
```

Script này tạo hoặc cập nhật:

- 6 event logs demo
- 3 alerts demo
- 1 model artifact `iForest-v0.1-demo`

Script idempotent theo `event_logs.source_id`; chạy lại không nhân đôi event logs. Alert demo có title prefix `[demo]` sẽ được thay mới.

## Chạy backend local

```bash
.venv/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Hoặc:

```bash
make run
```

Health check:

```bash
curl http://localhost:8000/api/health
```

Expected:

```json
{"status":"ok"}
```

## Chạy full stack bằng Docker

```bash
docker compose up --build
```

API container expose port `8000`.

Lưu ý: khi chạy trong Docker Compose, `api` dùng:

```text
DATABASE_URL=postgresql://ueba:ueba@db:5432/ueba
```

## Frontend integration

Frontend hiện gọi API tại `frontend/src/lib/apiClient.ts`:

- `POST /auth/login`
- `GET /dashboard/summary`
- `GET /users`
- `GET /devices`
- `GET /logs`

Vì backend mount router tại `/api`, local frontend cần:

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

Chạy frontend:

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000/api npm run dev
```

## Frontend-facing API contract

Chi tiết contract nằm ở `docs/contracts/API_CONTRACT.md`.

Các response chính:

### Login

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
  "accessToken": "<jwt>",
  "user": {
    "id": "1",
    "email": "admin@demo.com",
    "name": "Demo Admin",
    "role": "admin"
  }
}
```

### Dashboard

`GET /api/dashboard/summary`

Requires:

```text
Authorization: Bearer <accessToken>
```

Response:

```json
{
  "totalUsers": 3,
  "totalDevices": 3,
  "totalLogs": 6,
  "openAlerts": 3,
  "highCriticalAlerts": 2,
  "averageRiskScore": 22.3,
  "currentModelVersion": "iForest-v0.1-demo",
  "lastImportTime": "2026-06-15T10:03:00Z"
}
```

### Lists

Frontend-facing list endpoints return direct arrays, not pagination wrappers:

```text
GET /api/users
GET /api/devices
GET /api/logs
```

Internal/admin endpoints such as raw-log management may still use `{ items, total, limit, offset }`.

## Auth and RBAC

- `GET /api/users`, `/api/devices`, `/api/logs`, `/api/dashboard/summary` require any valid account token.
- `POST /api/users`, `PATCH /api/users/{user_id}`, `POST /api/devices`, `PATCH /api/devices/{device_id}` require `admin`.
- Raw log ingest endpoints require `admin` or `analyst`.

JWT is signed with `JWT_SECRET` using HMAC SHA-256 helper in `src/services/auth.py`.

## Test and lint

Lint:

```bash
.venv/bin/ruff check src tests scripts/seed_mock_data.py
```

Tests without PostgreSQL integration:

```bash
.venv/bin/pytest -q
```

PostgreSQL integration tests:

```bash
export TEST_DATABASE_URL=postgresql://ueba:ueba@localhost:5432/ueba_test
.venv/bin/pytest -q
```

Nếu chưa có database `ueba_test`, tạo database trước trong PostgreSQL rồi chạy lại test.

## Manual smoke test

1. Start DB:

```bash
docker compose up -d db
```

2. Seed mock data:

```bash
.venv/bin/python scripts/seed_mock_data.py
```

3. Start backend:

```bash
.venv/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

4. Login:

```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@demo.com","password":"admin123"}'
```

5. Call protected endpoint with token:

```bash
TOKEN="<accessToken>"
curl -s http://localhost:8000/api/dashboard/summary \
  -H "Authorization: Bearer $TOKEN"
```

6. Start frontend:

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000/api npm run dev
```

Open `http://localhost:5173` or `http://127.0.0.1:5173`.

## Troubleshooting

### `ModuleNotFoundError: No module named 'psycopg'`

Install backend dependencies:

```bash
.venv/bin/pip install -r requirements.txt
```

### `psycopg.OperationalError` when connecting to DB

Check DB container:

```bash
docker compose ps
docker compose logs --tail=100 db
```

Confirm `.env` has:

```text
DATABASE_URL=postgresql://ueba:ueba@localhost:5432/ueba
```

### Browser requests fail with CORS

Confirm backend `CORS_ORIGINS` includes the frontend origin:

```text
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Restart backend after editing `.env`.

### Frontend shows mock data

Check `VITE_API_BASE_URL`. If it is missing, frontend intentionally falls back to mock data.

Use:

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

Then restart the Vite dev server.

### `/api/users` returns 403

The endpoint requires `Authorization: Bearer <token>`. Login first and pass the returned `accessToken`.

## Related docs

- `docs/contracts/API_CONTRACT.md`
- `docs/contracts/DATA_CONTRACT.md`
- `docs/architecture/ARCHITECTURE.md`
- `README.md`
