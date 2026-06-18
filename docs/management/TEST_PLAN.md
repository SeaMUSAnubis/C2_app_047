# Backend & Database Test Plan

**Project:** UEBA Endpoint Monitoring  
**Date:** 2026-06-17  
**Branch:** BuiHoangLinh_2A202600804  

---

## 1. Tổng quan hệ thống

### 1.1 Kiến trúc Backend
- **Framework:** FastAPI (Python 3.11)
- **Database:** PostgreSQL 16 (psycopg3, raw SQL, không dùng ORM)
- **Auth:** Custom JWT (HMAC-SHA256) + PBKDF2 password hashing
- **ML:** OneClassSVM anomaly detection (joblib artifact)

### 1.2 Accounts hiện có trong DB

| Email | Password | Role | Ghi chú |
|-------|----------|------|---------|
| `admin@demo.com` | `admin123` | admin | Seed data, toàn quyền |
| `analyst@demo.com` | `analyst123` | analyst | Seed data, quyền đọc + ingest |

### 1.3 Roles

| Role | Quyền hạn |
|------|-----------|
| `admin` | Toàn quyền: CRUD users, devices, ingest raw logs, models |
| `analyst` | Đọc + ingest raw logs + models, KHÔNG tạo/sửa user/device |

---

## 2. Test Cases - Authentication

### 2.1 Login (`POST /api/auth/login`)

| ID | Test Case | Input | Expected | Priority |
|----|-----------|-------|----------|----------|
| AUTH-01 | Login thành công với admin | `admin@demo.com` / `admin123` | 200, accessToken + user | HIGH |
| AUTH-02 | Login thành công với analyst | `analyst@demo.com` / `analyst123` | 200, accessToken + user | HIGH |
| AUTH-03 | Login thất bại - sai password | `admin@demo.com` / `wrong` | 401 | HIGH |
| AUTH-04 | Login thất bại - email không tồn tại | `notexist@test.com` | 401 | HIGH |
| AUTH-05 | Login thất bại - thiếu email | password only | 422 | MEDIUM |
| AUTH-06 | Login thất bại - thiếu password | email only | 422 | MEDIUM |
| AUTH-07 | Login thất bại - body rỗng | `{}` | 422 | MEDIUM |
| AUTH-08 | Response format đúng FE | Login admin | `accessToken` (camelCase), user object | HIGH |

### 2.2 Token JWT

| ID | Test Case | Expected | Priority |
|----|-----------|----------|----------|
| AUTH-09 | Token hợp lệ truy cập protected | 200 | HIGH |
| AUTH-10 | Token expired bị từ chối | 401 | HIGH |
| AUTH-11 | Token giả mạo bị từ chối | 401 | HIGH |
| AUTH-12 | Token thiếu claim `sub` | 401 | HIGH |
| AUTH-14 | Header Authorization sai format | 401/403 | MEDIUM |
| AUTH-15 | Header Authorization rỗng | 401/403 | HIGH |
| AUTH-16 | Token rỗng | 401/403 | MEDIUM |

### 2.3 Password Hashing

| ID | Test Case | Expected | Priority |
|----|-----------|----------|----------|
| AUTH-17 | Password hash PBKDF2 | Hash format đúng, verify chính xác | HIGH |
| AUTH-18 | Salt khác nhau cho cùng password | Mỗi lần hash ra salt khác | MEDIUM |
| AUTH-19 | Timing-safe comparison | Dùng `hmac.compare_digest` | HIGH |

### 2.4 Account Status

| ID | Test Case | Expected | Priority |
|----|-----------|----------|----------|
| AUTH-20 | Account deactivate không login được | 401 | HIGH |
| AUTH-21 | Token bị revoke khi deactivate | 401 | HIGH |

---

## 3. Test Cases - Authorization (RBAC)

### 3.1 Admin-only Endpoints

| ID | Test Case | Endpoint | Role | Expected | Priority |
|----|-----------|----------|------|----------|----------|
| AUTHZ-01 | Admin tạo user | `POST /users` | admin | 201 | HIGH |
| AUTHZ-02 | Analyst bị từ chối tạo user | `POST /users` | analyst | 403 | HIGH |
| AUTHZ-03 | Không token bị từ chối | `POST /users` | none | 401/403 | HIGH |
| AUTHZ-04 | Admin sửa user | `PATCH /users/{id}` | admin | 200 | HIGH |
| AUTHZ-05 | Analyst bị từ chối sửa user | `PATCH /users/{id}` | analyst | 403 | HIGH |
| AUTHZ-06 | Admin tạo device | `POST /devices` | admin | 201 | HIGH |
| AUTHZ-07 | Analyst bị từ chối tạo device | `POST /devices` | analyst | 403 | HIGH |
| AUTHZ-08 | Admin sửa device | `PATCH /devices/{id}` | admin | 200 | HIGH |
| AUTHZ-09 | Analyst bị từ chối sửa device | `PATCH /devices/{id}` | analyst | 403 | HIGH |

### 3.2 Admin/Analyst Endpoints

| ID | Test Case | Endpoint | Role | Expected | Priority |
|----|-----------|----------|------|----------|----------|
| AUTHZ-10 | Admin ingest raw log | `POST /raw-logs/ingest` | admin | 201 | HIGH |
| AUTHZ-11 | Analyst ingest raw log | `POST /raw-logs/ingest` | analyst | 201 | HIGH |
| AUTHZ-12 | Không token bị từ chối | `POST /raw-logs/ingest` | none | 401/403 | HIGH |
| AUTHZ-13 | Admin batch ingest | `POST /raw-logs/batch` | admin | 200 | HIGH |
| AUTHZ-14 | Analyst batch ingest | `POST /raw-logs/batch` | analyst | 200 | HIGH |
| AUTHZ-15 | Admin list raw logs | `GET /raw-logs` | admin | 200 | MEDIUM |
| AUTHZ-16 | Analyst list raw logs | `GET /raw-logs` | analyst | 200 | MEDIUM |
| AUTHZ-17 | Admin model infer | `POST /models/{v}/infer` | admin | 200/503 | HIGH |
| AUTHZ-18 | Analyst model infer | `POST /models/{v}/infer` | analyst | 200/503 | HIGH |

### 3.3 Any Authenticated Endpoints

| ID | Test Case | Endpoint | Role | Expected | Priority |
|----|-----------|----------|------|----------|----------|
| AUTHZ-19 | Admin xem profile | `GET /auth/me` | admin | 200 | HIGH |
| AUTHZ-20 | Analyst xem profile | `GET /auth/me` | analyst | 200 | HIGH |
| AUTHZ-21 | Admin xem dashboard | `GET /dashboard/summary` | admin | 200 | MEDIUM |
| AUTHZ-22 | Analyst xem dashboard | `GET /dashboard/summary` | analyst | 200 | MEDIUM |
| AUTHZ-23 | Admin list users | `GET /users` | admin | 200 | MEDIUM |
| AUTHZ-24 | Analyst list users | `GET /users` | analyst | 200 | MEDIUM |

### 3.4 Public Endpoints (không cần auth)

| ID | Test Case | Endpoint | Expected | Priority |
|----|-----------|----------|----------|----------|
| AUTHZ-25 | Health check | `GET /health` | 200 | MEDIUM |
| AUTHZ-26 | Root info | `GET /` | 200 | LOW |

---

## 4. Test Cases - API Endpoints

### 4.1 Users API

| ID | Test Case | Endpoint | Expected | Priority |
|----|-----------|----------|----------|----------|
| API-01 | Lấy danh sách users | `GET /users` | 200, array >= 3 | HIGH |
| API-02 | Lấy user theo ID | `GET /users/ACM0001` | 200, user object | HIGH |
| API-03 | Lấy user không tồn tại | `GET /users/NOTEXIST` | 404 | HIGH |
| API-04 | Tạo user mới | `POST /users` | 201 | HIGH |
| API-05 | Tạo user trùng ID | `POST /users` | 409 | HIGH |
| API-06 | Tạo user thiếu field | `POST /users` | 422 | MEDIUM |
| API-07 | Sửa user | `PATCH /users/{id}` | 200 | HIGH |
| API-08 | Sửa user không tồn tại | `PATCH /users/{id}` | 404 | HIGH |
| API-09 | Response camelCase | `GET /users` | `riskScore`, `openAlerts` | HIGH |

### 4.2 Devices API

| ID | Test Case | Endpoint | Expected | Priority |
|----|-----------|----------|----------|----------|
| API-10 | Lấy danh sách devices | `GET /devices` | 200, array >= 3 | HIGH |
| API-11 | Lấy device theo ID | `GET /devices/PC-1001` | 200 | HIGH |
| API-12 | Lấy device không tồn tại | `GET /devices/NOTEXIST` | 404 | HIGH |
| API-13 | Tạo device mới | `POST /devices` | 201 | HIGH |
| API-14 | Tạo device trùng ID | `POST /devices` | 409 | HIGH |
| API-15 | Tạo device với user không tồn tại | `POST /devices` | 422 | HIGH |
| API-16 | Sửa device | `PATCH /devices/{id}` | 200 | HIGH |
| API-17 | Response camelCase | `GET /devices` | `riskScore`, `openAlerts` | HIGH |

### 4.3 Event Logs API

| ID | Test Case | Endpoint | Expected | Priority |
|----|-----------|----------|----------|----------|
| API-18 | Lấy danh sách logs | `GET /logs` | 200 | HIGH |
| API-19 | Ingest log mới | `POST /logs/ingest` | 201 | HIGH |
| API-20 | Ingest log trùng source_id | `POST /logs/ingest` | Cùng id (idempotent) | HIGH |
| API-21 | Ingest log thiếu field | `POST /logs/ingest` | 422 | MEDIUM |
| API-22 | Response camelCase | `GET /logs` | `eventType`, `userId` | HIGH |

### 4.4 Raw Logs API

| ID | Test Case | Endpoint | Expected | Priority |
|----|-----------|----------|----------|----------|
| API-23 | Single ingest raw log | `POST /raw-logs/ingest` | 201 | HIGH |
| API-24 | Batch ingest raw logs | `POST /raw-logs/batch` | 200 | HIGH |
| API-25 | Batch có record invalid | `POST /raw-logs/batch` | Partial success | HIGH |
| API-27 | Raw logs phân trang | `GET /raw-logs` | `items`, `total`, `limit` | MEDIUM |
| API-28 | Raw logs filter theo type | `GET /raw-logs?event_type=logon` | Filtered results | MEDIUM |
| API-29 | Lấy raw log theo ID | `GET /raw-logs/{id}` | 200 | MEDIUM |
| API-30 | Lấy raw log không tồn tại | `GET /raw-logs/{id}` | 404 | MEDIUM |
| API-31 | Invalid event type | `POST /raw-logs/ingest` | 422 | HIGH |

### 4.5 Model Inference API

| ID | Test Case | Endpoint | Expected | Priority |
|----|-----------|----------|----------|----------|
| API-32 | Model infer | `POST /models/{v}/infer` | 200/503 | HIGH |
| API-33 | Model infer version sai | `POST /models/{v}/infer` | 404 | HIGH |
| API-34 | Model metadata | `GET /models/{v}` | 200/503 | MEDIUM |
| API-35 | Model metrics | `GET /models/{v}/metrics` | 200/503 | MEDIUM |

### 4.6 Dashboard API

| ID | Test Case | Endpoint | Expected | Priority |
|----|-----------|----------|----------|----------|
| API-36 | Dashboard summary | `GET /dashboard/summary` | 200, đầy đủ KPIs | HIGH |
| API-37 | Dashboard camelCase | `GET /dashboard/summary` | `totalUsers`, `openAlerts` | MEDIUM |

---

## 5. Test Cases - Database

### 5.1 Schema Verification

| ID | Test Case | Expected | Priority |
|----|-----------|----------|----------|
| DB-01 | app_accounts schema | Columns tồn tại | HIGH |
| DB-02 | users schema | Columns tồn tại | HIGH |
| DB-03 | devices schema | Columns tồn tại | HIGH |
| DB-04 | event_logs schema | Columns tồn tại | HIGH |
| DB-05 | raw_user_logs schema | Columns tồn tại | HIGH |
| DB-06 | alerts table exists | Table tồn tại | MEDIUM |
| DB-07 | model_artifacts table exists | Table tồn tại | MEDIUM |
| DB-08 | feature_windows table exists | Table tồn tại | LOW |

### 5.2 Constraints

| ID | Test Case | Expected | Priority |
|----|-----------|----------|----------|
| DB-09 | accounts email UNIQUE | Constraint tồn tại | HIGH |
| DB-10 | accounts role CHECK | Constraint tồn tại | HIGH |
| DB-11 | users username UNIQUE | Constraint tồn tại | HIGH |
| DB-12 | event_logs source_id UNIQUE | Upsert behavior | HIGH |
| DB-13 | raw_logs source_id UNIQUE | Upsert behavior | HIGH |
| DB-14 | raw_logs event_type CHECK | Invalid bị reject | HIGH |
| DB-15 | alerts severity CHECK | Enum verified | MEDIUM |
| DB-16 | alerts status CHECK | Enum verified | MEDIUM |
| DB-17 | devices FK constraint | Invalid user bị reject | HIGH |
| DB-18 | event_logs FK constraint | Invalid user bị reject | HIGH |

### 5.3 Seed Data

| ID | Test Case | Expected | Priority |
|----|-----------|----------|----------|
| DB-21 | Seed accounts | admin + analyst tồn tại | HIGH |
| DB-22 | Seed users | 3 users tồn tại | HIGH |
| DB-23 | Seed devices | 3 devices tồn tại | HIGH |
| DB-24 | Seed passwords hashed | Không lưu plaintext | HIGH |

### 5.4 Data Operations

| ID | Test Case | Expected | Priority |
|----|-----------|----------|----------|
| DB-25 | Upsert event_logs | Idempotent | HIGH |
| DB-26 | Upsert raw_user_logs | Idempotent | HIGH |
| DB-27 | Batch savepoint | Xử lý partial failure | HIGH |
| DB-28 | JSON fields decoded | Trả về dict | MEDIUM |
| DB-29 | Timestamp ISO format | Lưu ISO 8601 | MEDIUM |

---

## 6. Test Cases - Security

| ID | Test Case | Expected | Priority |
|----|-----------|----------|----------|
| SEC-01 | SQL injection login email | Không crash, 401 | HIGH |
| SEC-02 | SQL injection path param | Không crash, 404 | HIGH |
| SEC-03 | SQL injection query param | Không crash | HIGH |
| SEC-04 | XSS trong user full_name | Lưu nguyên dạng | MEDIUM |
| SEC-05 | Invalid email format | 401/422 | MEDIUM |
| SEC-06 | Negative risk_score | 201/422 | MEDIUM |
| SEC-07 | Extreme risk_score | 201/422 | MEDIUM |
| SEC-08 | CORS cho phép origin đúng | Header present | HIGH |
| SEC-09 | CORS từ chối origin lạ | Không có header | HIGH |

---

## 7. Cách chạy tests

```bash
# Backend tests
docker compose up -d
source .venv/bin/activate
export TEST_DATABASE_URL="postgresql://ueba:ueba@localhost:5432/ueba"
pytest tests/ -v
```
