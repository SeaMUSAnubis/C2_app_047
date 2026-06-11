# Backend

FastAPI backend cho UEBA Endpoint Monitoring.

## Trách nhiệm

- Authentication/JWT và role admin/analyst.
- API quản lý users, devices, logs, alerts.
- Ingestion endpoint cho agent/mock agent.
- Risk scoring, anomaly service và LLM/rule-based explanation service.
- Database models, schemas, repositories và migrations.

## Cấu trúc dự kiến

```text
app/
  api/v1/routers/
  core/
  db/
  models/
  schemas/
  repositories/
  services/
  tests/
migrations/
scripts/
```

Backend không lưu raw dataset, notebook hoặc ML model binary. Các artifact ML nằm trong `artifacts/`.
