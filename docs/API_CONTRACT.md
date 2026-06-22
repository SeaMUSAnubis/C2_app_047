# API Contract

File này là hợp đồng làm việc giữa backend và frontend. Các endpoint shapes được finalized ở đây trước khi tích hợp frontend.

## Nhóm endpoints

```text
POST /api/auth/login           # Đăng nhập
GET  /api/auth/me              # Lấy thông tin account hiện tại
GET  /api/dashboard/summary    # Tổng quan dashboard

GET  /api/users                # Danh sách users
GET  /api/users/{user_id}      # Chi tiết user
POST /api/users                # Tạo user (admin only)
PATCH /api/users/{user_id}     # Sửa user (admin only)

GET  /api/devices              # Danh sách devices
GET  /api/devices/{device_id}  # Chi tiết device
POST /api/devices              # Tạo device (admin only)
PATCH /api/devices/{device_id} # Sửa device (admin only)

POST /api/logs/ingest          # Ingest event log
GET  /api/logs                 # Danh sách event logs

POST /api/raw-logs/ingest      # Ingest raw log (admin/analyst)
POST /api/raw-logs/batch       # Batch ingest raw logs
GET  /api/raw-logs             # Danh sách raw logs (phân trang)
GET  /api/raw-logs/{log_id}    # Chi tiết raw log

GET  /api/models/{version}                # Model metadata
POST /api/models/{version}/infer          # Model inference
GET  /api/models/{version}/metrics        # Model metrics

POST /api/alerts               # Tạo alert (admin/analyst)
GET  /api/alerts               # Danh sách alerts (filter)
GET  /api/alerts/summary       # Tổng quan alerts
GET  /api/alerts/{id}          # Chi tiết alert
PATCH /api/alerts/{id}/status  # Cập nhật status (admin/analyst)

GET  /api/dashboard/alerts-over-time       # Alerts theo thời gian
GET  /api/dashboard/severity-distribution  # Phân bố severity
GET  /api/dashboard/top-risk-users         # Top users risk cao
GET  /api/dashboard/top-risk-devices       # Top devices risk cao
```

## Contract cho Frontend

Các shapes sau đây match với TypeScript types trong `frontend/src/types/*`.

### Auth

`POST /api/auth/login`

Request:

```json
{
  "email": "admin@demo.com",
  "password": "admin123"
}
```

Response (camelCase):

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

Tài khoản demo:

- `admin@demo.com / admin123` (role: admin)
- `analyst@demo.com / analyst123` (role: analyst)

`GET /api/auth/me` yêu cầu `Authorization: Bearer <jwt>` và trả về account hiện tại.

### Dashboard

`GET /api/dashboard/summary` yêu cầu token.

Response (camelCase):

```json
{
  "totalUsers": 3,
  "totalDevices": 3,
  "totalLogs": 0,
  "openAlerts": 0,
  "highCriticalAlerts": 0,
  "averageRiskScore": 22.3,
  "currentModelVersion": "ocsvm-cert-r42-chunked",
  "lastImportTime": null
}
```

### Users

`GET /api/users` yêu cầu token. Trả về mảng trực tiếp (không có pagination wrapper).

Response item (camelCase):

```json
{
  "id": "ACM0001",
  "account": "acm0001",
  "name": "Alice M. Carter",
  "department": "Finance",
  "role": "Accountant",
  "status": "active",
  "riskScore": 18,
  "assignedDevices": 1,
  "openAlerts": 0,
  "lastSeen": "2026-06-13T08:12:00Z"
}
```

### Devices

`GET /api/devices` yêu cầu token. Trả về mảng trực tiếp.

Response item (camelCase):

```json
{
  "id": "PC-1001",
  "hostname": "FIN-WS-1001",
  "assignedUser": "acm0001",
  "department": "Finance",
  "status": "active",
  "riskScore": 12,
  "openAlerts": 0,
  "lastSeen": "2026-06-13T08:12:00Z"
}
```

Giá trị status: `active` (DB: `online`) hoặc `inactive` (DB: `offline`, `retired`).

### Logs

`GET /api/logs` yêu cầu token. Trả về mảng trực tiếp, giới hạn 100 records.

Response item (camelCase):

```json
{
  "id": "1",
  "timestamp": "2026-06-13T16:10:00+07:00",
  "eventType": "logon",
  "userId": "ACM0001",
  "deviceId": "PC-1001",
  "action": "LOGIN_SUCCESS",
  "sourceFile": "logon.csv",
  "sourceId": "cert-r42:logon:123",
  "rawDetail": "Successful logon from FIN-WS-1001"
}
```

## Contract nội bộ/admin

Các endpoints sau giữ nguyên snake_case, paginated shapes cho internal/admin use:

- `POST /api/logs/ingest` - Event ingest (trả về full event record)
- `POST /api/users`, `PATCH /api/users/{user_id}`, `GET /api/users/{user_id}` - CRUD
- `POST /api/devices`, `PATCH /api/devices/{device_id}`, `GET /api/devices/{device_id}` - CRUD
- `POST /api/raw-logs/ingest`, `POST /api/raw-logs/batch`, `GET /api/raw-logs` - Raw log management

### Deployed OCSVM model

Backend không train model tại runtime. Nó load pre-trained OCSVM artifact từ `weights/ocsvm_cert_r42_chunked.joblib`.

`GET /api/models/ocsvm-cert-r42-chunked` yêu cầu token và trả về model metadata.

`POST /api/models/ocsvm-cert-r42-chunked/infer` yêu cầu token.

Request:

```json
{
  "features": {
    "logon_count": 4,
    "logon_after_hours_count": 1,
    "logon_activity_Logoff_count": 2,
    "logon_activity_Logon_count": 2,
    "device_count": 1,
    "device_after_hours_count": 0,
    "device_activity_Connect_count": 1,
    "device_activity_Disconnect_count": 0,
    "file_count": 12,
    "file_after_hours_count": 1,
    "email_count": 3,
    "email_after_hours_count": 0,
    "email_size_sum": 18400,
    "email_size_mean": 6133.33,
    "email_size_max": 12000,
    "email_attachments_sum": 1,
    "email_attachments_mean": 0.33,
    "email_attachments_max": 1,
    "http_count": 24,
    "http_after_hours_count": 2
  }
}
```

Response:

```json
{
  "modelVersion": "ocsvm-cert-r42-chunked",
  "prediction": "anomaly",
  "isAnomaly": true,
  "scoreSamples": 0.65,
  "decisionScore": -0.32,
  "anomalyScore": -0.65,
  "riskScore": 73,
  "severity": "high",
  "featureColumns": ["logon_count"],
  "missingFeatures": [],
  "extraFeatures": []
}
```

Features bị thiếu được điền bằng `0.0`; features thừa bị bỏ qua và được báo cáo.

## Quy ước response

- Sử dụng ISO 8601 cho timestamps.
- Sử dụng stable IDs từ backend/database, không dùng frontend-generated IDs.
- Frontend-facing list endpoints trả về mảng trực tiếp.
- Admin/internal endpoints có thể dùng pagination với `{ items, total, limit, offset }`.
- Trả về error codes machine-readable kèm messages human-readable.

## Environment variables

Backend:

```text
DATABASE_URL=postgresql://ueba:ueba@localhost:5432/ueba
JWT_SECRET=change-me-in-production
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
OCSVM_MODEL_PATH=weights/ocsvm_cert_r42_chunked.joblib
OCSVM_MODEL_VERSION=ocsvm-cert-r42-chunked
```

Frontend (`frontend/.env.local`):

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

## LLM Provider

Alert explanation sử dụng Mistral Chat Completions:

- Endpoint: `POST https://api.mistral.ai/v1/chat/completions`
- Auth header: `Authorization: Bearer <MISTRAL_API_KEY>`
- Model mặc định: `mistral-small-latest`
- Config variables:
  - `MISTRAL_API_KEY`
  - `MISTRAL_MODEL`
  - `MISTRAL_CHAT_COMPLETIONS_URL`

Nếu API key thiếu hoặc Mistral request fail, backend trả về rule-based fallback explanation.
