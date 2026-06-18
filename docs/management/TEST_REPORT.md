# Backend & Database Test Report

**Project:** UEBA Endpoint Monitoring  
**Date:** 2026-06-17  
**Branch:** BuiHoangLinh_2A202600804  
**Environment:** Python 3.13.9, pytest 9.1.0, PostgreSQL 16  

---

## 1. Kết quả test

| Metric | Giá trị |
|--------|---------|
| **Tổng số test** | 118 |
| **Passed** | 118 |
| **Failed** | 0 |
| **Thời gian chạy** | ~12 giây |

---

## 2. Chi tiết test cases theo nhóm

### 2.1 Authentication Tests (`test_auth.py`) - 20 tests

| ID | Test Case | Status |
|----|-----------|--------|
| AUTH-01 | Login thành công với admin | PASS |
| AUTH-02 | Login thành công với analyst | PASS |
| AUTH-03 | Login thất bại - sai password | PASS |
| AUTH-04 | Login thất bại - email không tồn tại | PASS |
| AUTH-05 | Login thất bại - thiếu email | PASS |
| AUTH-06 | Login thất bại - thiếu password | PASS |
| AUTH-07 | Login thất bại - body rỗng | PASS |
| AUTH-08 | Response format đúng FE | PASS |
| AUTH-09 | Token hợp lệ truy cập protected | PASS |
| AUTH-10 | Token expired bị từ chối | PASS |
| AUTH-11 | Token giả mạo bị từ chối | PASS |
| AUTH-12 | Token thiếu claim `sub` | PASS |
| AUTH-14 | Header Authorization sai format | PASS |
| AUTH-15 | Header Authorization rỗng | PASS |
| AUTH-16 | Token rỗng | PASS |
| AUTH-17 | Password hash PBKDF2 | PASS |
| AUTH-18 | Salt khác nhau cho cùng password | PASS |
| AUTH-19 | Timing-safe comparison | PASS |
| AUTH-20 | Account deactivate không login | PASS |
| AUTH-21 | Token bị revoke khi deactivate | PASS |

### 2.2 Authorization Tests (`test_authorization.py`) - 26 tests

| ID | Test Case | Role | Status |
|----|-----------|------|--------|
| AUTHZ-01 | Admin tạo user | admin | PASS |
| AUTHZ-02 | Analyst bị từ chối tạo user | analyst | PASS |
| AUTHZ-03 | Không token bị từ chối | none | PASS |
| AUTHZ-04 | Admin sửa user | admin | PASS |
| AUTHZ-05 | Analyst bị từ chối sửa user | analyst | PASS |
| AUTHZ-06 | Admin tạo device | admin | PASS |
| AUTHZ-07 | Analyst bị từ chối tạo device | analyst | PASS |
| AUTHZ-08 | Admin sửa device | admin | PASS |
| AUTHZ-09 | Analyst bị từ chối sửa device | analyst | PASS |
| AUTHZ-10 | Admin ingest raw log | admin | PASS |
| AUTHZ-11 | Analyst ingest raw log | analyst | PASS |
| AUTHZ-12 | Không token bị từ chối | none | PASS |
| AUTHZ-13 | Admin batch ingest | admin | PASS |
| AUTHZ-14 | Analyst batch ingest | analyst | PASS |
| AUTHZ-15 | Admin list raw logs | admin | PASS |
| AUTHZ-16 | Analyst list raw logs | analyst | PASS |
| AUTHZ-17 | Admin model infer | admin | PASS |
| AUTHZ-18 | Analyst model infer | analyst | PASS |
| AUTHZ-19 | Admin xem profile | admin | PASS |
| AUTHZ-20 | Analyst xem profile | analyst | PASS |
| AUTHZ-21 | Admin xem dashboard | admin | PASS |
| AUTHZ-22 | Analyst xem dashboard | analyst | PASS |
| AUTHZ-23 | Admin list users | admin | PASS |
| AUTHZ-24 | Analyst list users | analyst | PASS |
| AUTHZ-25 | Health endpoint public | any | PASS |
| AUTHZ-26 | Root endpoint public | any | PASS |

### 2.3 API Endpoint Tests (`test_api_endpoints.py`) - 33 tests

| ID | Test Case | Status |
|----|-----------|--------|
| API-01 | Lấy danh sách users | PASS |
| API-02 | Lấy user theo ID | PASS |
| API-03 | Lấy user không tồn tại | PASS |
| API-04 | Tạo user mới | PASS |
| API-05 | Tạo user trùng ID | PASS |
| API-06 | Tạo user thiếu field | PASS |
| API-07 | Sửa user | PASS |
| API-08 | Sửa user không tồn tại | PASS |
| API-09 | Users response camelCase | PASS |
| API-10 | Lấy danh sách devices | PASS |
| API-11 | Lấy device theo ID | PASS |
| API-12 | Lấy device không tồn tại | PASS |
| API-13 | Tạo device mới | PASS |
| API-14 | Tạo device trùng ID | PASS |
| API-15 | Tạo device với user không tồn tại | PASS |
| API-16 | Sửa device | PASS |
| API-17 | Devices response camelCase | PASS |
| API-18 | Lấy danh sách logs | PASS |
| API-19 | Ingest log mới | PASS |
| API-20 | Ingest log idempotent | PASS |
| API-21 | Ingest log thiếu field | PASS |
| API-22 | Logs response camelCase | PASS |
| API-23 | Single ingest raw log | PASS |
| API-24 | Batch ingest raw logs | PASS |
| API-25 | Batch có record invalid | PASS |
| API-27 | Raw logs phân trang | PASS |
| API-28 | Raw logs filter theo type | PASS |
| API-29 | Lấy raw log theo ID | PASS |
| API-30 | Lấy raw log không tồn tại | PASS |
| API-31 | Invalid event type | PASS |
| API-32 | Model infer | PASS |
| API-33 | Model infer version sai | PASS |
| API-34 | Model metadata | PASS |
| API-35 | Model metrics | PASS |
| API-36 | Dashboard summary | PASS |
| API-37 | Dashboard camelCase | PASS |

### 2.4 Database Tests (`test_database.py`) - 29 tests

| ID | Test Case | Status |
|----|-----------|--------|
| DB-01 | app_accounts schema | PASS |
| DB-02 | users schema | PASS |
| DB-03 | devices schema | PASS |
| DB-04 | event_logs schema | PASS |
| DB-05 | raw_user_logs schema | PASS |
| DB-06 | alerts table exists | PASS |
| DB-07 | model_artifacts table exists | PASS |
| DB-08 | feature_windows table exists | PASS |
| DB-09 | accounts email UNIQUE | PASS |
| DB-10 | accounts role CHECK | PASS |
| DB-11 | users username UNIQUE | PASS |
| DB-12 | event_logs source_id UNIQUE | PASS |
| DB-13 | raw_logs source_id UNIQUE | PASS |
| DB-14 | raw_logs event_type CHECK | PASS |
| DB-15 | alerts severity CHECK | PASS |
| DB-16 | alerts status CHECK | PASS |
| DB-17 | devices FK constraint | PASS |
| DB-18 | event_logs FK constraint | PASS |
| DB-21 | Seed accounts | PASS |
| DB-22 | Seed users | PASS |
| DB-23 | Seed devices | PASS |
| DB-24 | Seed passwords hashed | PASS |
| DB-25 | Upsert event_logs | PASS |
| DB-26 | Upsert raw_user_logs | PASS |
| DB-27 | Batch savepoint | PASS |
| DB-28 | JSON fields decoded | PASS |
| DB-29 | Timestamp ISO format | PASS |

### 2.5 Security Tests (`test_security.py`) - 9 tests

| ID | Test Case | Status |
|----|-----------|--------|
| SEC-01 | SQL injection login email | PASS |
| SEC-02 | SQL injection path param | PASS |
| SEC-03 | SQL injection query param | PASS |
| SEC-04 | XSS trong user full_name | PASS |
| SEC-05 | Invalid email format | PASS |
| SEC-06 | Negative risk_score | PASS |
| SEC-07 | Extreme risk_score | PASS |
| SEC-08 | CORS cho phép origin đúng | PASS |
| SEC-09 | CORS từ chối origin lạ | PASS |

---

## 3. Authorization Coverage Matrix

| Endpoint | Admin | Analyst | No Auth |
|----------|-------|---------|---------|
| `GET /health` | PASS | PASS | PASS |
| `POST /auth/login` | PASS | PASS | PASS |
| `GET /auth/me` | PASS | PASS | BLOCKED |
| `GET /dashboard/summary` | PASS | PASS | BLOCKED |
| `GET /users` | PASS | PASS | BLOCKED |
| `POST /users` | PASS | BLOCKED | BLOCKED |
| `PATCH /users/{id}` | PASS | BLOCKED | BLOCKED |
| `GET /devices` | PASS | PASS | BLOCKED |
| `POST /devices` | PASS | BLOCKED | BLOCKED |
| `PATCH /devices/{id}` | PASS | BLOCKED | BLOCKED |
| `POST /logs/ingest` | PASS | PASS | BLOCKED |
| `GET /logs` | PASS | PASS | BLOCKED |
| `POST /raw-logs/ingest` | PASS | PASS | BLOCKED |
| `POST /raw-logs/batch` | PASS | PASS | BLOCKED |
| `GET /raw-logs` | PASS | PASS | BLOCKED |
| `POST /models/{v}/infer` | PASS | PASS | BLOCKED |
| `GET /models/{v}` | PASS | PASS | BLOCKED |

---

## 4. Database Constraint Coverage

| Constraint | Test | Status |
|------------|------|--------|
| `app_accounts.email` UNIQUE | DB-09 | PASS |
| `app_accounts.role` CHECK | DB-10 | PASS |
| `users.username` UNIQUE | DB-11 | PASS |
| `event_logs.source_id` UNIQUE | DB-12 | PASS |
| `raw_user_logs.source_id` UNIQUE | DB-13 | PASS |
| `raw_user_logs.event_type` CHECK | DB-14 | PASS |
| `alerts.severity` CHECK | DB-15 | PASS |
| `alerts.status` CHECK | DB-16 | PASS |
| `devices.assigned_user_id` FK | DB-17 | PASS |
| `event_logs.user_id` FK | DB-18 | PASS |

---

## 5. Cách chạy tests

```bash
docker compose up -d
source .venv/bin/activate
export TEST_DATABASE_URL="postgresql://ueba:ueba@localhost:5432/ueba"
pytest tests/ -v
```
