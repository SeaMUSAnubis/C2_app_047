# Normalized Event Schema

Canonical event fields for agent/backend/ML integration.

| Field | Type | Required | Description |
|---|---|---:|---|
| `source_id` | string | yes | Stable source row/event identifier. |
| `source_file` | string | yes | Origin file or collector name. |
| `timestamp` | string | yes | ISO 8601 event timestamp. |
| `user_id` | string | yes | User/account identifier. |
| `device_id` | string | no | Device/PC identifier. |
| `event_type` | string | yes | `logon`, `device`, `file`, `http`, `email`, etc. |
| `action` | string | no | Source action/activity. |
| `resource` | string | no | URL, filename, device, host, or other target. |
| `metadata` | object | no | Normalized optional fields. |
| `raw` | object | no | Raw source row for traceability. |
