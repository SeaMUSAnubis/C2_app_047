# Report 047 UEBA - Backend Sprint 3

Date: 2026-06-13

## Source Reviewed

- Read `docs/047_UEBA.xlsx`.
- Relevant assigned owner: Bui Hoang Linh - Backend/DevOps Engineer.
- Current Sprint 3 assigned tasks:
  - `T-007`: DB schema + migration/seed.
  - `T-008`: Auth JWT + RBAC middleware.

## Completed Work

- Added SQLite-backed backend storage in `src/services/database.py`.
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
- Updated `docs/API_CONTRACT.md` with implemented request/response examples.
- Added backend env settings to `.env.example`.
- Added API tests for health, login, auth protection, RBAC, seed reads, and idempotent log ingest.

## Verification

- `ruff check src tests`: passed.
- `timeout 60s pytest -q`: passed, `7 passed in 0.48s`.

## Notes

- The workbook filename in the request was `047_UEBA.xlxs`, but the actual file is `docs/047_UEBA.xlsx`.
- The workbook itself was not modified.
- Runtime SQLite files are ignored by `.gitignore`.

## Remaining Assigned Work From Workbook

- Later backend tasks still open by sprint:
  - `T-015`: Alert service + API filter/status.
  - `T-016`: Dashboard summary endpoints.
  - `T-021`: API/integration tests expansion.
  - `T-023`: Docker/deploy staging.
  - `T-026`: Production URL + demo data.
