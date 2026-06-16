# 2 - Scope

## Mục tiêu MVP (2 tuần)
Xây được một luồng demo end-to-end: import dữ liệu CERT r4.2, phát hiện bất thường bằng ML, tạo alert có risk score và explanation, hiển thị/điều phối xử lý trên dashboard.

## In Scope

### P0 (bắt buộc)
- Authentication cơ bản (admin/analyst) bằng JWT.
- Import + normalize CERT r4.2 (logon/device/file/http/email/LDAP/psychometric).
- Feature engineering theo user/device/time window.
- Train + inference anomaly detection (ưu tiên Isolation Forest).
- Risk scoring 0-100 và tạo alert theo ngưỡng.
- Alert detail có: anomaly score, top features, timeline, explanation.
- Dashboard có overview + danh sách user/device/log/alert.

### P1 (nên có nếu kịp)
- API giữ sẵn cho phase endpoint agent thật: `POST /api/logs/ingest`.
- Deploy online có URL demo.

## Out of Scope (MVP này chưa làm)
- BYOD monitoring (thiết bị cá nhân).
- Tự động response kiểu SOAR/kill process/quarantine.
- SIEM/SOAR integration, multi-tenant, mobile agent.
- Rule-only engine thay thế hoàn toàn ML.

## Definition of Done
- Chạy được API và dashboard với tài khoản demo.
- Chạy được pipeline import -> feature -> train -> inference.
- Có alert được tạo từ risk scoring và hiển thị trên dashboard.
- Alert detail có explanation (LLM hoặc fallback) + timeline.
- Có tài liệu hướng dẫn run cơ bản và cấu trúc repo đồng nhất với template.

## Mapping phạm vi theo folder
- `src/api/`, `src/models/`, `src/main.py`: API + schema + app wiring.
- `src/services/ueba_ml/`: preprocessing, feature pipeline, training, scoring.
- `src/agents/`: workflow agent và mở rộng ingest phase sau.
- `docs/`: PRD, requirements, contracts, architecture.
- `eval/results/`: báo cáo/evidence đánh giá pipeline.
- `tests/`: kiểm thử API/agent theo template.