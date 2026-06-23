# UEBA Endpoint Monitoring

UEBA Endpoint Monitoring là web app phát hiện hành vi bất thường của user/device từ log endpoint theo hướng insider threat và account compromise. Hệ thống dùng CERT r4.2-style logs để preprocessing, train OCSVM (One-Class SVM) model, sinh anomaly score / risk context, kết hợp LLM giải thích alert và tích hợp dashboard + backend API + endpoint agent chạy trên máy nhân viên.

## Cấu trúc repo

```text
C2-App-047/
├── src/
│   ├── frontend/                 # React + Vite + TypeScript
│   ├── backend/                  # FastAPI app, backend tests, Dockerfile backend riêng
│   │   ├── app/
│   │   │   ├── main.py            # FastAPI entrypoint
│   │   │   ├── config.py          # App settings
│   │   │   ├── api/               # API routes
│   │   │   ├── core/              # Auth/security helpers
│   │   │   ├── db/                # Runtime DB helpers
│   │   │   ├── schemas/           # Pydantic schemas
│   │   │   ├── services/          # Backend business logic
│   │   │   └── agents/            # LLM alert-explanation graph
│   │   └── tests/                 # Backend pytest suite
│   ├── database/                 # PostgreSQL schema, seed, migration, data utilities
│   ├── ml/                       # ML services, weights, scripts
│   │   ├── services/ueba_ml/     # OCSVM inference và pipeline ML đã giữ lại
│   │   ├── weights/               # Model weight
│   │   └── legacy_review/         # File cần review thủ công
│   └── agent/                    # Endpoint agent (Phase 2 + 4) — chạy trên máy nhân viên
│       ├── collectors/            # 7 collector: logon, http, device, file, email, process, network
│       ├── buffer.py              # SQLite local queue (WAL, idempotent)
│       ├── transport.py           # HTTPS + X-API-Key auth + error classification
│       ├── config_client.py       # pull /api/agents/me/config mỗi 5 phút
│       ├── enroll.py              # enrollment CLI
│       ├── update.py              # self-update (Phase 5b)
│       ├── legal.py               # legal banner (Nghị định 13/2023 + GDPR Art. 88)
│       ├── state.py               # state file 0600
│       ├── cli.py                 # python -m agent {enroll,run,update}
│       └── service.py             # main loop
├── docs/                          # PRD, architecture, API/data contract, references, guide
├── scripts/                       # Docker entrypoint, AI logging helpers
├── data/                          # CERT r4.2 raw + sample
├── artifacts/                     # Model + feature matrix outputs
├── eval/                          # Evaluation evidence and reports
├── presentation/                  # Demo Day slides/assets
├── .github/                       # CI/CD workflows + AI logging hooks
├── docker-compose.yml             # Một container duy nhất (Postgres + API + frontend)
├── Dockerfile
├── Makefile
├── requirements.txt
├── .env.example
└── docs/PLAN.md                   # Bản kế hoạch triển khai 5 phase + 5b (tất cả đã done)
```

Chi tiết chuẩn thư mục nằm ở [docs/REPO_STRUCTURE_STANDARD.md](docs/REPO_STRUCTURE_STANDARD.md).

## Tính năng đã có (Phase 1 + Phase 2 + Phase 3 + Phase 4)

### Backend (`src/backend/`)
- **REST API** FastAPI: `/api/auth/login`, `/api/users`, `/api/devices`, `/api/logs`, `/api/alerts`, `/api/dashboard/summary`, `/api/ml/*`, `/api/demo/*`, `/api/admin/*` (Phase 3).
- **Endpoint agent infrastructure** (Phase 1): admin cấp enrollment token → agent enroll → nhận `agent_id` + `api_key` → gửi raw-log bằng `X-API-Key`. Quản lý agent qua `/api/agents/*`, blocklist qua `/api/agents/blocklist/*`, policy qua `/api/agents/policy`.
- **OCSVM inference** (`src/ml/services/ueba_ml/inference.py`): load model `.joblib`, chạy `run_ocsvm_inference(features)` trả về `(anomaly_score, risk_score, factors)`.
- **Demo pipeline** (`src/backend/app/services/demo_pipeline.py`): trích feature từ events, gọi OCSVM, sinh alert.
- **LLM alert explanation** (`src/backend/app/agents/` + `src/backend/app/services/llm.py`): graph đơn giản gọi LLM giải thích alert.
- **LLM upgrade — multi-turn chat + long-term memory** (`docs/LLM.md`):
  - **Connection pool** max=20 (`src/backend/app/db/pool.py`) với statement timeout per checkout.
  - **4 bảng mới**: `llm_conversations`, `llm_messages`, `llm_feedback`, `llm_memories` + counter cache `llm_stats_cache` (real-time qua trigger).
  - **LLM service refactor** (`src/backend/app/services/llm/`): provider abstraction (Mistral + Protocol), retry, Pydantic schema validate, in-memory LRU cache, structured stats.
  - **Long-term memory v1**: tag-based retrieval (user / device / pattern / global) + auto-write từ analyst feedback.
  - **Multi-turn chat**: SSE streaming, history load, memory injection, abort support.
  - **10 endpoint mới**: chat, feedback, memory admin, LLM stats, pool stats.
  - **Polished UI**: `ChatPanel`, `AlertDetailModal`, `MemoryAdminPage`, dark mode, zustand store.
- **Auth + RBAC**: JWT (admin / security_manager / analyst / employee), bcrypt password hash, CORS configured.
- **Normalizer + ML scoring worker** (Phase 3): background `asyncio` loop trong `lifespan` poll `raw_user_logs` mỗi `NORMALIZER_POLL_INTERVAL_SECONDS` (default 10s), chuyển sang `event_logs` qua per-event-type mapping, gọi `user_scoring.score_user` cho từng user có event mới. Lưu `ml_anomaly_scores` (lịch sử score) + tạo `alerts` khi `risk_score >= ML_SCORING_ALERT_MIN_RISK`. Admin endpoint: `POST /api/admin/run-normalizer`, `GET /api/admin/normalizer-stats`, `POST /api/admin/score-user/{user_id}`, `GET /api/admin/scoring-stats`.

### Endpoint agent (`src/agent/`)
- **Enrollment CLI**: `python -m agent enroll --server-url ... --enrollment-token ... --state-path ...`.
- **Run CLI**: `python -m agent run --server-url ... --state-path ...` — chạy foreground với SIGINT/SIGTERM handling.
- **Local SQLite buffer** (WAL mode): durable, idempotent theo `source_id`, crash recovery qua `reset_in_flight()`, FIFO eviction khi vượt `max_events`.
- **HTTPS transport**: sync `httpx.Client`, classify lỗi (2xx/4xx/5xx/network) thành `TransientError` / `PermanentError` / `AuthRevokedError`.
- **Config client**: pull `/api/agents/me/config` mỗi 5 phút, cache blocklist + policy, exponential backoff.
- **7 collector** (Phase 2 + Phase 4): `logon` (Linux wtmp), `http` (DNS sinkhole + DomainCheck), `device` (USB), `file` (auditd/programmatic), `email` (programmatic + IMAP poller), `process` (/proc), `network` (/proc/net/tcp). Mỗi collector có Linux implementation + Windows stub. Collector name map đúng với policy `enabled_collectors`.
- **Legal banner** in lúc khởi động, state file mode 0600.

### Frontend (`src/frontend/`)
- React + Vite + TypeScript SPA.
- Trang: Dashboard, Users, Devices, Logs, Alerts, Models, Admin Blocked Websites, **Endpoint agents** (Phase 4), **Agent detail** (Phase 4), **Blocklist** (Phase 4), Login.
- **Legal banner** (Phase 4): component `LegalBanner` với 2 variant (compact cho login card, full cho login hero), trích dẫn Nghị định 13/2023/PDPD + GDPR Art. 88.
- Gọi `/api/*` qua `apiClient.ts`, JWT-based auth.

## Data

Repo tách dữ liệu theo vòng đời:

- `data/raw/cert-r4.2/`: raw CERT r4.2 dataset, local only, không commit.
- `data/sample/cert-r4.2-small/`: sample nhỏ để smoke test/demo nhanh, local only.
- `data/mock/`: **mock dataset có chủ đích** — 8 users, 5 ngày, có sẵn anomaly (wikileaks, USB + .exe, email lớn ra gmail). Xem [data/mock/README.md](data/mock/README.md) để import và test thủ công.
- `artifacts/`: feature matrix, model binary, scores, local/generated.
- Schema và data contract nằm trong [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md).

### Import mock data nhanh

```bash
# Generate (nếu chưa có data/mock/) + import vào DB
python scripts/generate_mock_data.py
python scripts/import_mock_data.py --direct

# Hoặc import qua HTTP API (mô phỏng agent):
python scripts/import_mock_data.py
```

Sau khi import, mở dashboard và tìm user `LRR0148` (Bob) để thấy anomaly wikileaks, `MOH0273` (Carol) để thấy USB + .exe, `LAP0338` (David) để thấy email lớn ra gmail.

### Import toàn bộ CERT r4.2 (dữ liệu gốc)

> ~32M dòng, ~16 GB CSV. PostgreSQL cần **30-50 GB trống** trên phân vùng chứa Docker volume.
> Import mất **15-30 phút** tuỳ máy.

Dataset CERT r4.2 gốc đặt ở `data/raw/cert-r4.2/` (local only, không commit). Đây là bộ dữ liệu đầy đủ từ cuộc thi [CERT Insider Threat v4.2](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=508099) của CMU SEI.

**Cách import:**

```bash
# 1) Khởi động Docker container (nếu chưa chạy)
docker compose up -d

# 2) Smoke test trước — 1000 dòng/file (~5 giây)
cat scripts/import_cert_full.py | docker compose exec -T app python3 - --limit-per-file 1000

# 3) Import toàn bộ
cat scripts/import_cert_full.py | docker compose exec -T app python3 -

# 4) (Tuỳ chọn) Xoá CERT cũ rồi import lại từ đầu
cat scripts/import_cert_full.py | docker compose exec -T app python3 - --reset-cert-events
```

**Tuỳ chọn dòng lệnh:**

| Flag | Mặc định | Mô tả |
|---|---|---|
| `--batch-size` | `5000` | Số dòng CSV mỗi batch INSERT. Giảm nếu disk yếu |
| `--limit-per-file` | _none_ | Giới hạn dòng/file để smoke test |
| `--reset-cert-events` | _false_ | Xoá toàn bộ event CERT cũ trong DB trước khi import |
| `--data-dir` | `data/raw/cert-r4.2` | Đường dẫn thư mục chứa CSV |

**Tối ưu đã tích hợp trong script:**

- Streaming CSV từng dòng — không load toàn bộ file vào RAM
- Batch 5000 dòng + `COMMIT` + `CHECKPOINT` sau mỗi file — giới hạn WAL size, tránh tràn disk
- `long_running` connection — không bị statement timeout 5s cắt ngang
- Hiển thị disk usage (`X.X/XX.X GB`) trong quá trình import
- Cảnh báo nếu disk trống < 10 GB trước khi chạy
- Vacuum nhẹ sau mỗi file để giữ kích thước DB gọn

**Sau khi import:**

```bash
# Kiểm tra dữ liệu
TOKEN=$(curl -s -X POST http://localhost:5173/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@demo.com","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

curl -s -H "Authorization: Bearer $TOKEN" http://localhost:5173/api/dashboard/overview \
  | python3 -m json.tool | head -30
```

## Chạy bằng Docker (khuyến nghị cho demo)

```bash
docker compose up --build -d
```

Sau khi build xong, mở:

| Thành phần | URL |
|---|---|
| Frontend (UI) | http://localhost:5173 |
| Health check | http://localhost:5173/health |
| API cho frontend | http://localhost:5173/api/* |
| Swagger / OpenAPI | http://localhost:5173/docs |

Lệnh hữu ích:

```bash
docker compose logs -f app       # xem log
docker compose ps                # trạng thái container
docker compose down              # dừng (giữ volume DB)
docker compose down -v           # dừng + xóa volume DB
```

## Chạy tách riêng khi development

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Sửa DATABASE_URL trong .env trỏ tới PostgreSQL local
uvicorn src.backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend
cd src/frontend
npm install
npm run dev     # http://localhost:5173
```

## Test

```bash
# Backend (cần PostgreSQL nếu chạy integration test)
pytest src/backend/tests -q

# Agent
pytest src/agent/tests -q
```

## Tài khoản demo

| Email | Password | Role |
|---|---|---|
| admin@demo.com | admin123 | admin |
| security@demo.com | security123 | security_manager |
| analyst@demo.com | analyst123 | analyst |
| employee@demo.com | employee123 | employee |

## Tài liệu

> Mỗi tài liệu có 2 phiên bản: **tiếng Anh** (file gốc) và **tiếng Việt**
> (`.vi.md`). Nội dung giống nhau. Xem [docs/guide/README.md](docs/guide/README.md)
> hoặc [docs/guide/README.vi.md](docs/guide/README.vi.md) cho reading order.

### Quick links (đọc trước)
- [docs/guide/README.md](docs/guide/README.md) — Documentation index ([VI](docs/guide/README.vi.md))
- [docs/AGENT_DEPLOYMENT.md](docs/AGENT_DEPLOYMENT.md) — Cài agent lên máy nhân viên (curl, pip, binary)
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — Day-2 ops ([VI](docs/OPERATIONS.vi.md))
- [docs/SECURITY.md](docs/SECURITY.md) — Security model + threat model ([VI](docs/SECURITY.vi.md))
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — Common issues + fixes ([VI](docs/TROUBLESHOOTING.vi.md))

### Product & Planning
- [docs/PRD.md](docs/PRD.md) — Product Requirements (VI)
- [docs/BRIEF.md](docs/BRIEF.md) — Brief (VI)
- [docs/UEBA_REQUIREMENTS.md](docs/UEBA_REQUIREMENTS.md) — Yêu cầu chi tiết (VI)
- [docs/PLAN.md](docs/PLAN.md) — Kế hoạch triển khai 5 phase + Phase 5b (VI)
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — Release notes ([VI](docs/CHANGELOG.vi.md))

### Architecture & Contracts
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Kiến trúc hệ thống (VI)
- [docs/ARCHITECTURE_OVERVIEW.md](docs/ARCHITECTURE_OVERVIEW.md) — Tổng quan kiến trúc (VI)
- [docs/architecture_diagram.md](docs/architecture_diagram.md) — Sơ đồ (mermaid) (VI)
- [docs/API_CONTRACT.md](docs/API_CONTRACT.md) — Hợp đồng API (25+ endpoints) (VI)
- [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md) — Hợp đồng dữ liệu (13 bảng) (VI)
- [docs/UI_FLOW.svg](docs/UI_FLOW.svg) — Sơ đồ luồng UI
- [docs/REPO_STRUCTURE_STANDARD.md](docs/REPO_STRUCTURE_STANDARD.md) — Chuẩn cấu trúc repo (VI)
- [docs/ML_MODEL.md](docs/ML_MODEL.md) — OCSVM model documentation ([VI](docs/ML_MODEL.vi.md))
- [docs/LLM.md](docs/LLM.md) — LLM service + long-term memory ([VI](docs/LLM.vi.md))
- [docs/PLAN_LLM.md](docs/PLAN_LLM.md) — LLM upgrade plan
- [docs/LLM_PROGRESS.md](docs/LLM_PROGRESS.md) — LLM upgrade progress log

### Development
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — Dev setup, code style, PR process ([VI](docs/CONTRIBUTING.vi.md))
- [docs/guide/BACKEND.md](docs/guide/BACKEND.md) — Backend setup
- [docs/guide/README.md](docs/guide/README.md) — Full doc index ([VI](docs/guide/README.vi.md))

### Project management
- [docs/management/MVP_PROGRESS.md](docs/management/MVP_PROGRESS.md) — 16/16 MVP features done
- [docs/management/WORKLOG.md](docs/management/WORKLOG.md) — Per-day work log
- [docs/management/JOURNAL.md](docs/management/JOURNAL.md) — Engineering journal ([VI](docs/management/JOURNAL.vi.md))
- [docs/management/TEST_PLAN.md](docs/management/TEST_PLAN.md) — Test plan
- [docs/management/TEST_REPORT.md](docs/management/TEST_REPORT.md) — Test execution report
- [docs/management/FRONTEND_TEST_REPORT.md](docs/management/FRONTEND_TEST_REPORT.md) — Frontend test report

### Refactor & history
- [docs/refactor/](docs/refactor/) — Refactor notes (Phase 0, 2026-06-21)
- [docs/reports/](docs/reports/) — Repo review + 047_UEBA summary
- [docs/management/](docs/management/) — Worklog, journal, test plan/report, MVP progress
- [docs/references/2506.23446v2.pdf](docs/references/2506.23446v2.pdf) — Paper reference
- [docs/047_UEBA.xlsx](docs/047_UEBA.xlsx) — Original project spreadsheet

## ML pipeline

OCSVM đã train sẵn ở `src/ml/weights/ocsvm_cert_r42_chunked.joblib`. Backend tự load khi khởi động. Nếu muốn train lại (không khuyến nghị cho demo):

```bash
bash src/ml/scripts/run_preprocessing.sh
bash src/ml/scripts/train_model.sh
```

## Module ownership

| Mảng | Thư mục | Deliverable |
|---|---|---|
| Product/PM | `docs/`, `docs/management/` | PRD, user story, worklog, journal |
| Backend API | `src/backend/`, `src/database/` | FastAPI app, schemas, DB helpers, agent endpoints |
| Data/ML | `src/ml/`, `data/`, `artifacts/`, `eval/` | OCSVM pipeline, training, scoring, reports |
| Endpoint agent | `src/agent/` | Collector (logon/http), buffer, transport, service |
| Frontend | `src/frontend/` | React + Vite UI |
| QA/DevOps | `src/backend/tests/`, `src/agent/tests/`, `.github/`, `Dockerfile` | Tests, CI, container config |

## AI logging hooks

Repo giữ hook logging của AI20K Build Cohort 2 trong `scripts/` và các thư mục `.agents/`, `.claude/`, `.codex/`, `.cursor/`, `.gemini/`, `.github/hooks/`.

Cài pre-push hook một lần:

```bash
bash scripts/setup_hooks.sh
```

Hoặc trên Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```

## Phase triển khai

| Phase | Trạng thái | Mô tả |
|---|---|---|
| 1 — Server agent infrastructure | ✅ done | 4 bảng DB mới, 15 endpoint `/api/agents/*`, auth `X-API-Key`, raw-logs chấp nhận agent key |
| 2 — Endpoint agent | ✅ done | `src/agent/` package: SQLite buffer + HTTPS transport + 2 collector (logon + http), 148 test pass |
| 3 — Normalizer + ML scoring | ✅ done | Background worker `raw_user_logs → event_logs → OCSVM → alerts`, bảng `ml_anomaly_scores`, 4 admin endpoint, 38 test mới |
| 4 — Full collectors + UI | ✅ done | 5 collector mới (device/file/email/process/network), UI Agents/AgentDetail/Blocklist, LegalBanner component, E2E test enroll→score→alert, 66 test mới |
| 5 — Deployment pipeline | ✅ done | `pyproject.toml` (pip install), 3 OS installer (systemd/Task Scheduler/launchd), PyInstaller single-binary, deployment guide |
| 5b — Curl install + self-update | ✅ done | 1-line `curl \| sudo bash` install, `agent update` subcommand, GitHub Releases flow, 15 test mới |

Xem chi tiết: [docs/PLAN.md](docs/PLAN.md).
