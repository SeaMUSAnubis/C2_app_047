# Tests

Integration và end-to-end tests cấp repo.

Unit tests nên nằm gần module owner:

- `backend/app/tests/`
- `ml/ueba_ml/tests/`
- `agent/tests/`
- `frontend/src/tests/`

Các luồng cross-module đặt trong `tests/integration/` hoặc `tests/e2e/`.
