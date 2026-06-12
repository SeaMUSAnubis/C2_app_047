# 1 - Research

## Nguồn tài liệu đã tổng hợp
- `docs/PRD.md`
- `docs/UEBA_REQUIREMENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_CONTRACT.md`
- `docs/API_CONTRACT.md`
- `docs/REPO_STRUCTURE_STANDARD.md`

## Phát hiện chính từ nghiên cứu

### 1) Nguồn dữ liệu và ánh xạ sự kiện
- Dataset chính của MVP: **CERT Insider Threat r4.2**.
- Các nguồn log trọng tâm: `logon.csv`, `device.csv`, `file.csv`, `http.csv`, `email.csv`, `LDAP/*.csv`, `psychometric.csv`.
- Mọi nguồn được map về schema event thống nhất để phục vụ cả dashboard và ML pipeline.

### 2) Kiến trúc triển khai đã chốt
- Source code chính đi theo template:
  - `src/api/` cho routes FastAPI.
  - `src/models/` cho schemas.
  - `src/services/` cho business logic + ML pipelines.
  - `src/agents/` cho agent workflow.
- Tách rõ dữ liệu local-only (`data/`, `artifacts/`) và tài liệu/đánh giá (`docs/`, `eval/`).

### 3) Hướng phát hiện bất thường
- MVP ưu tiên pipeline ML với **Isolation Forest** làm baseline chính.
- Có thể mở rộng bằng LOF / One-Class SVM / Autoencoder ở giai đoạn sau.
- Rule-based giữ vai trò baseline/guardrail/fallback, không phải hướng chính.

### 4) Risk scoring và explainability
- Risk score chuẩn hóa về thang **0-100**, phân mức: Low / Medium / High / Critical.
- Alert được tạo khi `risk_score >= 60`.
- Explanation ưu tiên LLM; khi thiếu API key hoặc lỗi provider thì fallback rule-based vẫn phải chạy được.

## Ràng buộc kỹ thuật và vận hành
- Sản phẩm bắt buộc là web/app hoàn chỉnh, không phải notebook/script-only.
- Dữ liệu CERT lớn, cần batch/chunk processing; không commit raw data và artifacts nặng vào git.
- Cần thể hiện rõ privacy-by-design: chỉ giám sát thiết bị công ty cấp, chỉ thu thập metadata phục vụ bảo mật.