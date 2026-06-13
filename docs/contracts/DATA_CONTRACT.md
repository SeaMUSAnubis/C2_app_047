# Data Contract

This file is the working contract between agent, backend and ML pipeline.

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

## CERT r4.2 source mapping

| Source | Normalized event type | Notes |
|---|---|---|
| `logon.csv` | `logon` | Login/logout events. |
| `device.csv` | `device` | Removable device connect/disconnect events. |
| `file.csv` | `file` | File activity, especially removable-media copy indicators. |
| `http.csv` | `http` | Web access activity. |
| `email.csv` | `email` | Email activity, recipients, size, attachments. |
| `LDAP/*.csv` | user/device enrichment | Department, role, supervisor, org context. |
| `psychometric.csv` | user enrichment | Optional Big Five features for ML only. |

## ML feature matrix

Current preprocessing writes:

- `artifacts/preprocessing/user_day_features.csv`: readable `user + date` features.
- `artifacts/preprocessing/iforest_feature_matrix.csv`: numeric matrix for Isolation Forest.
- `artifacts/preprocessing/iforest_feature_columns.json`: ordered feature columns.

Rows are keyed by `user` and `date`.
