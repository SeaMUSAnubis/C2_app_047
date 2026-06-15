# Backend review

## Summary

Not OK for manual test / PR yet.

The implementation follows the direction of `plan.md` and does not unnecessarily modify frontend source files. However, the frontend-facing response models and database helper return shapes are inconsistent. This can make `/api/dashboard/summary` fail response validation, make `/api/logs` fail once log rows exist, and silently return `null` for several user/device fields.

## Findings

### Critical - Frontend response models do not validate camelCase data returned by the service

Files:

- `src/models/schemas.py:184`
- `src/models/schemas.py:197`
- `src/models/schemas.py:210`
- `src/models/schemas.py:221`
- `src/services/database.py:555`
- `src/services/database.py:576`
- `src/services/database.py:603`
- `src/services/database.py:627`
- `src/api/routes.py:93`
- `src/api/routes.py:101`
- `src/api/routes.py:143`
- `src/api/routes.py:211`

Problem:

- The Pydantic models use `serialization_alias`, but the database helpers return dictionaries that already use camelCase keys such as `totalUsers`, `riskScore`, `assignedUser`, and `eventType`.
- `serialization_alias` controls output serialization only. It does not make Pydantic accept those camelCase keys as input during response validation.
- `DashboardSummary` has required snake_case fields, so `GET /api/dashboard/summary` will fail validation when the service returns `totalUsers`, `totalDevices`, etc.
- `FrontendEventLog.event_type` is required, so `GET /api/logs` will fail validation when there is at least one row because the service returns `eventType`.
- `FrontendUser` and `FrontendDevice` have optional snake_case fields, so their camelCase DB values are ignored and serialized back as `null` for fields like `riskScore`, `assignedDevices`, `openAlerts`, `assignedUser`, and `lastSeen`.

Evidence:

- `ruff check src tests` passed.
- `pytest -q` passed with `22 passed, 19 skipped`, but PostgreSQL integration tests were skipped.
- Direct schema validation shows:
  - `DashboardSummary.model_validate({"totalUsers": ...})` fails required-field validation.
  - `FrontendEventLog.model_validate({"eventType": ...})` fails required-field validation.
  - `FrontendUser.model_validate({"riskScore": 1, ...})` succeeds but serializes `riskScore` as `null`.
  - `FrontendDevice.model_validate({"assignedUser": "u", ...})` succeeds but serializes `assignedUser` as `null`.

Suggested fix:

- Pick one consistent shape at the service/model boundary.
- Option A: make database helpers return snake_case keys matching model fields, then let `response_model_by_alias=True` serialize camelCase to frontend.
- Option B: keep camelCase service keys, but change fields to use `validation_alias` as well as `serialization_alias`, or use `alias`/`AliasChoices` and set model config intentionally.
- Add focused tests that assert actual values, not just key presence:
  - `averageRiskScore` is not lost.
  - `riskScore`, `assignedDevices`, `openAlerts`, `lastSeen` have expected values.
  - `assignedUser` has the expected username.
  - `/api/logs` returns a populated item after ingest without response validation error.

### Major - Current tests do not exercise the implemented frontend contract in this environment

Files:

- `tests/test_api/test_routes.py:100`
- `tests/test_api/test_routes.py:119`
- `tests/test_api/test_routes.py:141`
- `tests/test_api/test_routes.py:154`

Problem:

- The frontend-compatible API tests are all guarded by `requires_postgres`.
- In the current run, PostgreSQL integration tests were skipped because `TEST_DATABASE_URL` is not set.
- The remaining unit tests do not catch the response-model alias issue above.
- Some tests only assert key presence and type, so they would not catch fields being serialized as `null`.

Suggested fix:

- Add non-PostgreSQL tests for response serialization by monkeypatching database service functions used by the routes.
- Strengthen PostgreSQL tests to assert field values, not just field names.
- Run the integration suite with:

```bash
export TEST_DATABASE_URL=postgresql://ueba:ueba@localhost:5432/ueba_test
pytest -q
```

### Minor - `/api/users`, `/api/devices`, and `/api/logs` dropped existing query filters from the original backend

Files:

- `src/api/routes.py:101`
- `src/api/routes.py:143`
- `src/api/routes.py:211`

Problem:

- The previous backend supported filters and pagination for users/devices/logs.
- The plan prioritizes frontend compatibility and says optional filters may remain for future use, so this is not a blocker for current frontend.
- It is still a contract regression for any caller using the prior documented filters.

Suggested fix:

- Either document these routes as frontend-only direct-array endpoints, or preserve query params and apply them in the frontend helper queries where practical.
- If internal paginated endpoints are needed, introduce separate paths such as `/api/admin/users`, `/api/admin/devices`, and `/api/admin/logs`.

## Checks run

```bash
ruff check src tests
```

Result: passed.

```bash
pytest -q
```

Result: `22 passed, 19 skipped`. PostgreSQL integration coverage was skipped in this environment.

Additional local schema check:

- Confirmed Pydantic response models do not accept the camelCase dictionaries returned by the database helpers as intended.

## Other review notes

- Frontend source files were not modified. Only `frontend/.env.example` was added, which matches `plan.md`.
- CORS settings were added in `src/config.py` and `src/main.py`.
- Dependencies remain compatible with existing `requirements.txt`; no new package appears required.
- `docs/contracts/API_CONTRACT.md` was updated to describe the frontend-compatible contract, but implementation currently does not reliably satisfy that contract because of the response validation issue.
