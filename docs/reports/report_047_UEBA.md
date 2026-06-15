# Report 047 UEBA - Backend Sprint 3

Date: 2026-06-13

## Source Reviewed

- Read `docs/planning/047_UEBA.xlsx`.
- Relevant assigned owner: Bui Hoang Linh - Backend/DevOps Engineer.
- Current Sprint 3 assigned tasks:
  - `T-007`: DB schema + migration/seed.
  - `T-008`: Auth JWT + RBAC middleware.

## Completed Work

- Added PostgreSQL-backed backend storage in `src/services/database.py`.
- Created schema initialization for:
  - `app_accounts`
  - `users`
  - `devices`
  - `event_logs`
  - `feature_windows`
  - `model_artifacts`
  - `alerts`
- Seeded demo accounts:
  - `admin@demo.com / admin123`
  - `analyst@demo.com / analyst123`
- Seeded demo users/devices for dashboard integration.
- Added JWT HS256 auth and PBKDF2 password hashing in `src/services/auth.py`.
- Added protected API endpoints:
  - `POST /api/auth/login`
  - `GET /api/auth/me`
  - `GET/POST/PATCH /api/users`
  - `GET/POST/PATCH /api/devices`
  - `POST /api/logs/ingest`
  - `GET /api/logs`
- Added admin-only RBAC for user/device create and update.
- Added normalized log ingest upsert by `source_id` to reduce duplicate import risk.
- Updated `docs/contracts/API_CONTRACT.md` with implemented request/response examples.
- Added backend env settings to `.env.example`.
- Added API tests for health, login, auth protection, RBAC, seed reads, and idempotent log ingest.
- Migrated runtime persistence away from SQLite to PostgreSQL using `DATABASE_URL`.
- Added docker-compose PostgreSQL service for local development.
- Added Mistral Chat Completions integration for alert explanations:
  - endpoint: `https://api.mistral.ai/v1/chat/completions`
  - auth: `Authorization: Bearer <MISTRAL_API_KEY>`
  - default model: `mistral-small-latest`
  - rule-based fallback remains available when the key is missing or the API errors.
- Added service-level test cases for:
  - Mistral request URL, bearer header, model, messages, temperature, max tokens, and text response parsing.
  - Mistral HTTP error fallback to rule-based explanation.
  - Missing `MISTRAL_API_KEY` fallback behavior.
  - PostgreSQL schema initialization using identity columns, references, indexes, and `ON CONFLICT`.
  - PostgreSQL log ingest upsert using `%s` placeholders, `ON CONFLICT(source_id)`, and `RETURNING *`.
  - PostgreSQL filter builders using `%s` placeholders.

## Verification

- `ruff check src tests`: passed.
- `timeout 60s pytest -q`: passed with `10 passed, 5 skipped`.
- Skipped tests are PostgreSQL integration tests because this local environment does not currently have `psycopg` installed and no `TEST_DATABASE_URL` was provided.
- `python - <<'PY' ... from src.main import app ... PY`: app imports successfully without initializing a SQLite database.

## Notes

- The workbook filename in the request was `047_UEBA.xlxs`, but the actual file is `docs/planning/047_UEBA.xlsx`.
- The workbook itself was not modified.
- SQLite is no longer used by backend runtime or tests.

## Remaining Assigned Work From Workbook

- Later backend tasks still open by sprint:
  - `T-015`: Alert service + API filter/status.
  - `T-016`: Dashboard summary endpoints.
  - `T-021`: API/integration tests expansion.
  - `T-023`: Docker/deploy staging.
  - `T-026`: Production URL + demo data.
