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
│   └── agent/                    # Endpoint agent (Phase 2) — chạy trên máy nhân viên
│       ├── collectors/            # logon (wtmp) + http (blocklist)
│       ├── buffer.py              # SQLite local queue
│       ├── transport.py           # HTTPS + X-API-Key auth
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
└── docs/PLAN.md                   # Bản kế hoạch triển khai 4 phase (Phase 1, 2 done; 3, 4 pending)
```

Chi tiết chuẩn thư mục nằm ở [docs/REPO_STRUCTURE_STANDARD.md](docs/REPO_STRUCTURE_STANDARD.md).

## Tính năng đã có (Phase 1 + Phase 2)

### Backend (`src/backend/`)
- **REST API** FastAPI: `/api/auth/login`, `/api/users`, `/api/devices`, `/api/logs`, `/api/alerts`, `/api/dashboard/summary`, `/api/ml/*`, `/api/demo/*`.
- **Endpoint agent infrastructure** (Phase 1): admin cấp enrollment token → agent enroll → nhận `agent_id` + `api_key` → gửi raw-log bằng `X-API-Key`. Quản lý agent qua `/api/agents/*`, blocklist qua `/api/agents/blocklist/*`, policy qua `/api/agents/policy`.
- **OCSVM inference** (`src/ml/services/ueba_ml/inference.py`): load model `.joblib`, chạy `run_ocsvm_inference(features)` trả về `(anomaly_score, risk_score, factors)`.
- **Demo pipeline** (`src/backend/app/services/demo_pipeline.py`): trích feature từ events, gọi OCSVM, sinh alert.
- **LLM alert explanation** (`src/backend/app/agents/` + `src/backend/app/services/llm.py`): graph đơn giản gọi LLM giải thích alert.
- **Auth + RBAC**: JWT (admin / security_manager / analyst / employee), bcrypt password hash, CORS configured.

### Endpoint agent (`src/agent/`)
- **Enrollment CLI**: `python -m agent enroll --server-url ... --enrollment-token ... --state-path ...`.
- **Run CLI**: `python -m agent run --server-url ... --state-path ...` — chạy foreground với SIGINT/SIGTERM handling.
- **Local SQLite buffer** (WAL mode): durable, idempotent theo `source_id`, crash recovery qua `reset_in_flight()`, FIFO eviction khi vượt `max_events`.
- **HTTPS transport**: sync `httpx.Client`, classify lỗi (2xx/4xx/5xx/network) thành `TransientError` / `PermanentError` / `AuthRevokedError`.
- **Config client**: pull `/api/agents/me/config` mỗi 5 phút, cache blocklist + policy, exponential backoff.
- **Collector logon (Linux)**: poll `/var/log/wtmp` (384 bytes/record), phát hiện logon/logoff, skip system events, xử lý rotation (inode change), persist offset qua restart.
- **Collector http (DomainCheck)**: thread-safe queue, mỗi domain/URL được check qua blocklist, domain extraction cho URL, DNS query parser với defensive cap.
- **Collector http (DnsSniff, root required)**: bind UDP/53, parse DNS query thủ công, emit event mỗi query.
- **Legal banner** in lúc khởi động, state file mode 0600.

### Frontend (`src/frontend/`)
- React + Vite + TypeScript SPA.
- Trang: Dashboard, Users, Devices, Logs, Alerts, Models, Admin Blocked Websites, Login.
- Gọi `/api/*` qua `apiClient.ts`, JWT-based auth.

## Data

Repo tách dữ liệu theo vòng đời:

- `data/raw/cert-r4.2/`: raw CERT r4.2 dataset, local only, không commit.
- `data/sample/cert-r4.2-small/`: sample nhỏ để smoke test/demo nhanh, local only.
- `artifacts/`: feature matrix, model binary, scores, local/generated.
- Schema và data contract nằm trong [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md).

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

- [docs/PRD.md](docs/PRD.md) — Product Requirements
- [docs/BRIEF.md](docs/BRIEF.md) — Brief
- [docs/UEBA_REQUIREMENTS.md](docs/UEBA_REQUIREMENTS.md) — Yêu cầu chi tiết
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Kiến trúc hệ thống
- [docs/ARCHITECTURE_OVERVIEW.md](docs/ARCHITECTURE_OVERVIEW.md) — Tổng quan kiến trúc
- [docs/architecture_diagram.md](docs/architecture_diagram.md) — Sơ đồ
- [docs/API_CONTRACT.md](docs/API_CONTRACT.md) — Hợp đồng API
- [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md) — Hợp đồng dữ liệu
- [docs/REPO_STRUCTURE_STANDARD.md](docs/REPO_STRUCTURE_STANDARD.md) — Chuẩn cấu trúc repo
- [docs/UI_FLOW.svg](docs/UI_FLOW.svg) — Sơ đồ luồng UI
- [docs/PLAN.md](docs/PLAN.md) — Kế hoạch triển khai 4 phase
- [docs/guide/](docs/guide/) — Hướng dẫn (backend setup, v.v.)
- [docs/references/](docs/references/) — Tài liệu tham khảo (paper, v.v.)
- [docs/reports/](docs/reports/) — Báo cáo review, v.v.
- [docs/management/](docs/management/) — Worklog, journal, test plan/report, MVP progress
- [docs/refactor/](docs/refactor/) — Tài liệu refactor repo (2026-06)
- [docs/047_UEBA.xlsx](docs/047_UEBA.xlsx) — Bảng tính dự án

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
| 3 — Normalizer + ML scoring | ⏳ pending | Worker chuyển `raw_user_logs` → `event_logs`, near-real-time ML scoring |
| 4 — Full collectors + UI | ⏳ pending | USB/file/email/process/network collector, UI quản lý agent, legal banner UI |

Xem chi tiết: [docs/PLAN.md](docs/PLAN.md).
