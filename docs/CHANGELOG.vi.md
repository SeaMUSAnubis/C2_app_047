# Lịch Sử Thay Đổi

Mọi thay đổi đáng chú ý của dự án được ghi lại ở đây. Format theo
[Keep a Changelog](https://keepachangelog.com/), version theo
[Semantic Versioning](https://semver.org/).

---

## [0.1.0] - 2026-06-22

Bản phát hành công khai đầu tiên. Hệ thống end-to-end đầu tiên bao gồm
agent + server + UI trong một repo.

### Đã thêm

#### Backend (Phase 1, 3)
- FastAPI app với 9 bảng, hơn 25 REST endpoint.
- JWT auth (human) + X-API-Key (agent) + bcrypt password hashing.
- 4-role RBAC: `admin`, `security_manager`, `analyst`, `employee`.
- Background normalizer (asyncio trong lifespan) poll `raw_user_logs`
  mỗi 10s, map sang `event_logs` qua per-event-type rules.
- ML scoring service: trích 20 features cho mỗi user, chạy OCSVM, lưu
  `ml_anomaly_scores`, tạo `alerts` khi `risk_score >= 60`.
- 4 admin endpoint: `POST /api/admin/run-normalizer`,
  `GET /api/admin/normalizer-stats`, `POST /api/admin/score-user/{id}`,
  `GET /api/admin/scoring-stats`.
- 19 agent endpoint: enroll, heartbeat, config pull, list/get/patch/
  delete agent, blocklist CRUD, policy read/patch, mark-stale.

#### Agent (Phase 2, 4, 5)
- Python 3.10+ service, `agent` CLI (enroll / run / version / update).
- Local SQLite buffer (WAL, 100k events FIFO eviction, idempotent trên
  `source_id`).
- HTTPS transport với retry + exponential backoff + error classification
  (Transient / Permanent / AuthRevoked).
- 7 collector: logon (Linux wtmp), http (DNS sinkhole + DomainCheck),
  device (USB / lsusb), file (poll + programmatic), email (programmatic
  + IMAP), process (/proc), network (/proc/net/tcp).
- Self-update qua subcommand `agent update`: tải binary mới từ release
  URL, verify SHA256, atomic replace, supervisor restart.
- Pkg qua `pyproject.toml` (`pip install -e .`).
- 3 OS installer script (systemd / Task Scheduler / launchd).
- 2 curl-pipe installer (`install_via_curl.sh` / `.ps1`).
- PyInstaller single-binary build (~58 MB, zero Python dep trên target).

#### Frontend (Phase 4)
- React 19 + Vite + TypeScript SPA.
- 3 trang mới: AgentsPage (list + revoke), AgentDetailPage,
  BlocklistPage (full CRUD).
- LegalBanner component (PDPD / GDPR notice) trên login + post-login.
- 13 method apiClient mới + 5 TypeScript type mới.

#### ML
- OCSVM model đã train sẵn trên CERT r4.2 (`ocsvm_cert_r42_chunked.joblib`).
- ~88 KB model, 20 features, nu=0.005, rbf kernel.
- LLM explanation qua Mistral (Vietnamese 3-line narrative + fallback).

#### Infrastructure
- Docker Compose single-container (Postgres + FastAPI + frontend).
- Dockerfile cho backend image.
- Health check tại `/health`.
- CORS, structured logging, env-based config.

### Tests
- 308 tests pass (208 agent + 100 backend), 4 pre-existing failures
  (DB constraint issues, đã verify không liên quan đến thay đổi).
- Frontend: tsc + eslint + Vite build sạch.
- 0 regression so với baseline.

### Tài liệu
- `README.md` — quickstart.
- `docs/PLAN.md` — 4-phase plan + Phase 5 deployment plan.
- `docs/PRD.md`, `docs/BRIEF.md`, `docs/UEBA_REQUIREMENTS.md` — tài liệu product gốc.
- `docs/ARCHITECTURE.md`, `docs/ARCHITECTURE_OVERVIEW.md`,
  `docs/architecture_diagram.md` — kiến trúc hệ thống.
- `docs/API_CONTRACT.md` — tham chiếu REST API.
- `docs/DATA_CONTRACT.md` — DB schema + event format.
- `docs/AGENT_DEPLOYMENT.md` — cách cài trên máy nhân viên.
- `docs/SECURITY.md` — security model + threat model.
- `docs/OPERATIONS.md` — hướng dẫn day-2 ops.
- `docs/TROUBLESHOOTING.md` — sự cố thường gặp + cách xử lý.
- `docs/CONTRIBUTING.md` — dev setup + quy trình PR.
- `docs/ML_MODEL.md` — tài liệu mô hình OCSVM.
- `docs/REPO_STRUCTURE_STANDARD.md` — quy ước cấu trúc thư mục.

### Bảo mật
- TLS bắt buộc cho production.
- Agent API keys lưu dưới dạng SHA-256 hash; plaintext trả về một lần lúc
  enrollment, không bao giờ lưu trữ.
- Enrollment tokens dùng một lần, có thời hạn.
- Email body không bao giờ được thu thập; subject được hash SHA-256.
- Xem `docs/SECURITY.md` để biết đầy đủ model.

---

## [Unreleased]

### Dự kiến cho 0.2.0
- Prometheus endpoint `/metrics`.
- MFA cho admin accounts.
- WebSocket để push alert real-time (không polling).
- Code-sign agent binary (Authenticode cho Windows, codesign cho macOS).
- Chuyển từ `localStorage` JWT sang `HttpOnly; Secure; SameSite=Strict` cookie.
- Chuyển từ scan event `O(n²)` sang materialized feature view.
- Per-user model fine-tuning (admin có thể flag user là "trusted",
  model học pattern của họ).
- Browser extension cho `DomainCheckCollector` (auto-push URL đến agent).
- Tablet / iOS agent variant (collector giới hạn).
- Audit log ALAE (ai truy cập data gì, khi nào).
