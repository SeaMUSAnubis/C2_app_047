# Backend review

## Final status: PASSED

Backend ready để commit/push/PR.

## Review result

Các lỗi đã ghi trong review trước đã được xử lý:

- `DashboardSummary`, `FrontendUser`, `FrontendDevice`, `FrontendEventLog`, `FrontendLoginResponse` hiện đã dùng `validation_alias=AliasChoices(...)` cùng `serialization_alias`, nên nhận được cả camelCase từ DB helpers và snake_case nội bộ, đồng thời serialize ra camelCase cho frontend.
- Các endpoint frontend-facing vẫn đúng với `frontend/src/lib/apiClient.ts`:
  - `POST /api/auth/login`
  - `GET /api/dashboard/summary`
  - `GET /api/users`
  - `GET /api/devices`
  - `GET /api/logs`
- Response contract khớp frontend:
  - Login trả `accessToken` và user `{ id, email, name, role }`.
  - Dashboard trả các KPI camelCase.
  - Users/devices/logs trả direct array, không còn paginated wrapper cho các route frontend đang gọi.
- Không thấy frontend source bị sửa không cần thiết. Các thay đổi backend tập trung ở schema/test; frontend API client hiện vẫn giữ contract ban đầu.

## Checks run

```bash
ruff check src tests
```

Result: passed.

```bash
pytest -q
```

Result: `26 passed, 19 skipped`.

Notes:

- PostgreSQL integration tests vẫn bị skip vì môi trường hiện tại chưa set `TEST_DATABASE_URL`.
- Nên chạy thêm trước khi merge nếu có database test:

```bash
export TEST_DATABASE_URL=postgresql://ueba:ueba@localhost:5432/ueba_test
pytest -q
```

## Manual smoke recommendation

Chạy backend với PostgreSQL:

```bash
docker compose up -d db
uvicorn src.main:app --reload --port 8000
```

Chạy frontend với:

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

Đăng nhập bằng:

- `admin@demo.com / admin123`
- `analyst@demo.com / analyst123`

Kiểm tra Dashboard, Users, Devices, Logs render dữ liệu thật và không fallback về mock data.
