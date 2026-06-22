# Data Contract

File này là hợp đồng làm việc giữa agent, backend và ML pipeline.

## Normalized endpoint event

```json
{
  "source_id": "cert-r42:logon:123",
  "source_file": "logon.csv",
  "timestamp": "2010-01-04T08:15:00Z",
  "user_id": "ACM0001",
  "device_id": "PC-1234",
  "event_type": "logon",
  "action": "Logon",
  "resource": "PC-1234",
  "metadata": {},
  "raw": {}
}
```

## CERT r4.2 Source Mapping

| File | Event type normalized | Ghi chú |
|------|----------------------|---------|
| `logon.csv` | `logon` | Sự kiện login/logout |
| `device.csv` | `device` | Sự kiện connect/disconnect removable device |
| `file.csv` | `file` | Hoạt động file, đặc biệt copy to removable media |
| `http.csv` | `http` | Hoạt động web access |
| `email.csv` | `email` | Hoạt động email, recipients, size, attachments |
| `LDAP/*.csv` | user/device enrichment | Department, role, supervisor, org context |
| `psychometric.csv` | user enrichment | Optional Big Five features cho ML only |

## ML Feature Matrix

Preprocessing hiện tại tạo:

- `artifacts/preprocessing/user_day_features.csv`: Features readable theo `user + date`
- `artifacts/preprocessing/iforest_feature_matrix.csv`: Numeric matrix cho Isolation Forest
- `artifacts/preprocessing/iforest_feature_columns.json`: Ordered feature columns

Rows được key bởi `user` và `date`.

## Raw Log Schema

```json
{
  "source_id": "agent:PC-1001:logon:2026-06-15T08:15:00Z",
  "collector_type": "endpoint_agent",
  "event_type": "logon",
  "timestamp": "2026-06-15T08:15:00Z",
  "user_id": "ACM0001",
  "device_id": "PC-1001",
  "raw_payload": {
    "action": "Logon",
    "username": "acm0001",
    "pc": "PC-1001"
  },
  "ingest_metadata": {
    "agent_version": "0.1.0",
    "host_os": "Windows 11"
  }
}
```

### Event types hợp lệ

```
logon, device, file, http, email, process, network, ldap, psychometric, custom
```

## Database Tables

| Table | Mô tả |
|-------|-------|
| `app_accounts` | Tài khoản đăng nhập (admin/analyst) |
| `users` | Người dùng được giám sát |
| `devices` | Thiết bị được giám sát |
| `event_logs` | Event logs đã normalize |
| `raw_user_logs` | Raw logs từ agents |
| `alerts` | Cảnh báo |
| `feature_windows` | ML feature windows |
| `model_artifacts` | Model metadata |
