# Chỉ Mục Tài Liệu

Đây là điểm vào cho tài liệu dự án. Bắt đầu với README để có quickstart,
sau đó nhảy đến chủ đề bạn cần.

> Tài liệu có 2 phiên bản: tiếng Anh (mặc định) và tiếng Việt (`.vi.md`).
> Nội dung giống nhau. Chọn phiên bản bạn đọc thoải mái hơn.

## Tài liệu dự án (root)

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [README.md](../../README.md) | Tổng quan dự án, quickstart, tài khoản demo | (giữ nguyên) |
| [PLAN.md](../PLAN.md) | Kế hoạch triển khai 4 phase + Phase 5 deployment | (giữ nguyên) |
| [PRD.md](../PRD.md) | Product requirements (cái gì + tại sao) | (giữ nguyên) |
| [BRIEF.md](../BRIEF.md) | Brief ngắn cho stakeholder | (giữ nguyên) |
| [UEBA_REQUIREMENTS.md](../UEBA_REQUIREMENTS.md) | Yêu cầu chi tiết (functional + non-functional) | (giữ nguyên) |

## Kiến trúc

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | Kiến trúc hệ thống (text) | (giữ nguyên) |
| [ARCHITECTURE_OVERVIEW.md](../ARCHITECTURE_OVERVIEW.md) | Tổng quan 1 trang | (giữ nguyên) |
| [architecture_diagram.md](../architecture_diagram.md) | Diagram source (mermaid) | (giữ nguyên) |
| [UI_FLOW.svg](../UI_FLOW.svg) | Luồng UI (visual) | (giữ nguyên) |

## Hợp đồng (Contracts)

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [API_CONTRACT.md](../API_CONTRACT.md) | Tham chiếu REST API (toàn bộ endpoint) | (giữ nguyên) |
| [DATA_CONTRACT.md](../DATA_CONTRACT.md) | DB schema + event payload formats | (giữ nguyên) |
| [REPO_STRUCTURE_STANDARD.md](../REPO_STRUCTURE_STANDARD.md) | Quy ước cấu trúc thư mục | (giữ nguyên) |

## Vận hành (Operations)

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [AGENT_DEPLOYMENT.md](../AGENT_DEPLOYMENT.md) | Cài agent lên máy nhân viên (curl, pip, binary) | (giữ nguyên) |
| [OPERATIONS.md](../OPERATIONS.md) | Day-2 ops: health, monitor, scale, backup | [OPERATIONS.vi.md](../OPERATIONS.vi.md) |
| [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) | Sự cố thường gặp + cách xử lý | [TROUBLESHOOTING.vi.md](../TROUBLESHOOTING.vi.md) |

## Phát triển (Development)

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Dev setup, code style, quy trình PR | [CONTRIBUTING.vi.md](../CONTRIBUTING.vi.md) |
| [ML_MODEL.md](../ML_MODEL.md) | OCSVM model: training, features, re-training, evaluation | [ML_MODEL.vi.md](../ML_MODEL.vi.md) |
| [SECURITY.md](../SECURITY.md) | Security model + threat model + compliance | [SECURITY.vi.md](../SECURITY.vi.md) |
| [CHANGELOG.md](../CHANGELOG.md) | Release notes | [CHANGELOG.vi.md](../CHANGELOG.vi.md) |

## Quản lý dự án (Project management)

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [MVP_PROGRESS.md](../management/MVP_PROGRESS.md) | Checklist MVP (100% done v0.1.0) | (giữ nguyên) |
| [TEST_PLAN.md](../management/TEST_PLAN.md) | Kế hoạch test gốc | (giữ nguyên) |
| [TEST_REPORT.md](../management/TEST_REPORT.md) | Báo cáo thực thi test | (giữ nguyên) |
| [FRONTEND_TEST_REPORT.md](../management/FRONTEND_TEST_REPORT.md) | Báo cáo test frontend | (giữ nguyên) |
| [WORKLOG.md](../management/WORKLOG.md) | Work log theo ngày | (giữ nguyên) |
| [JOURNAL.md](../management/JOURNAL.md) | Engineering journal (quyết định, trade-off, sự cố) | [JOURNAL.vi.md](../management/JOURNAL.vi.md) |

## Setup backend

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [BACKEND.md](BACKEND.md) | Cách chạy backend local + trong Docker | (giữ nguyên) |

## Lịch sử refactor

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [src_only_fe_be_db_keep_ml.md](../refactor/src_only_fe_be_db_keep_ml.md) | Refactor: chuyển backend+frontend+db vào `src/` | (giữ nguyên) |
| [inventory.md](../refactor/inventory.md) | Files đã move trong refactor | (giữ nguyên) |
| [result.md](../refactor/result.md) | Tóm tắt kết quả refactor | (giữ nguyên) |
| [legacy_src_readme_before_refactor.md](../refactor/legacy_src_readme_before_refactor.md) | README trước refactor | (giữ nguyên) |
| [ueba_ui_redesign_prompt.md](../refactor/ueba_ui_redesign_prompt.md) | Prompt redesign UI | (giữ nguyên) |

## Báo cáo

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [repo-review-2026-06-18.md](../reports/repo-review-2026-06-18.md) | Báo cáo review repo | (giữ nguyên) |
| [report_047_UEBA.md](../reports/report_047_UEBA.md) | Báo cáo dự án gốc (tóm tắt 047_UEBA.xlsx) | (giữ nguyên) |

## Tham khảo

| File | Mục đích | Tiếng Việt |
|---|---|---|
| [047_UEBA.xlsx](../047_UEBA.xlsx) | Bảng tính dự án gốc | (giữ nguyên) |
| [2506.23446v2.pdf](../references/2506.23446v2.pdf) | Paper tham khảo (OCSVM cho UEBA) | (giữ nguyên) |

---

## Thứ tự đọc

**Mới với dự án?** Đọc theo thứ tự:

1. [README.md](../../README.md) — 5 phút, chạy được
2. [ARCHITECTURE_OVERVIEW.md](../ARCHITECTURE_OVERVIEW.md) — 5 phút, bức tranh lớn
3. [API_CONTRACT.md](../API_CONTRACT.md) + [DATA_CONTRACT.md](../DATA_CONTRACT.md) — 15 phút, hợp đồng
4. [AGENT_DEPLOYMENT.md](../AGENT_DEPLOYMENT.md) — 10 phút, cách deploy
5. [OPERATIONS.md](../OPERATIONS.md) + [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) — 20 phút, day-2

**Muốn đóng góp?**

1. [CONTRIBUTING.md](../CONTRIBUTING.md) — 10 phút, dev setup
2. [SECURITY.md](../SECURITY.md) — 15 phút, security model
3. [ML_MODEL.md](../ML_MODEL.md) — 10 phút, mô hình OCSVM

**Sắp lên production?**

1. [SECURITY.md](../SECURITY.md) §6.3 — production checklist
2. [OPERATIONS.md](../OPERATIONS.md) §1+3+7 — deploy + scale
3. [AGENT_DEPLOYMENT.md](../AGENT_DEPLOYMENT.md) — fleet rollout
