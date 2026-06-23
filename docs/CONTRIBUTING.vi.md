# Hướng Dẫn Đóng Góp

Cách develop, test và đóng góp cho codebase UEBA Endpoint Monitoring.

> **Lần đầu?** Bắt đầu bằng cách chạy hệ thống local theo §1 bên dưới.
> Dự án có 3 component (backend / frontend / agent) dùng chung một Python
> monorepo và một PostgreSQL database.

---

## 1. Local development setup

### 1.1 — Yêu cầu

- **Python 3.10+** (khuyến nghị 3.12).
- **Node.js 20+** + npm 10+.
- **PostgreSQL 14+** (hoặc dùng Docker).
- **Git**.
- Tùy chọn: PyInstaller (để build agent binary).

### 1.2 — Clone + venv

```bash
git clone https://github.com/vespionage/ueba-endpoint-monitoring.git
cd ueba-endpoint-monitoring
python3 -m venv .venv
source .venv/bin/activate   # hoặc .venv\Scripts\activate trên Windows
pip install -r requirements.txt
# (Cài thêm agent package ở editable mode để có sẵn `agent` CLI:)
pip install -e .
```

### 1.3 — Database

```bash
# Cách A: Docker (đơn giản nhất):
docker run -d --name ueba-postgres \
    -e POSTGRES_USER=ueba_user \
    -e POSTGRES_PASSWORD=ueba_password \
    -e POSTGRES_DB=ueba_db \
    -p 5432:5432 \
    postgres:16

# Cách B: native install (Ubuntu):
sudo apt install postgresql
sudo -u postgres createuser ueba_user --pwprompt  # password: ueba_password
sudo -u postgres createdb ueba_db -O ueba_user
```

### 1.4 — Environment

```bash
cp .env.example .env
# Edit .env: tối thiểu set DATABASE_URL.
# Cho local dev, default work:
#   DATABASE_URL=postgresql://ueba_user:ueba_password@localhost:5432/ueba_db
#   JWT_SECRET=test-secret  (OK cho local; PHẢI đổi cho prod)
#   MISTRAL_API_KEY=         (rỗng OK — fallback về template explanation)
```

### 1.5 — Khởi tạo database

`initialize_database()` chạy tự động khi backend start và là idempotent.
Để chạy tay:

```bash
python -c "from src.backend.app.db.session import initialize_database; initialize_database()"
```

Lệnh này tạo tất cả 9 bảng + seed 4 demo accounts (`admin@demo.com`,
`analyst@demo.com`, `security@demo.com`, `employee@demo.com` — với password
theo role).

### 1.6 — Chạy backend

```bash
uvicorn src.backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API tại `http://127.0.0.1:8000/api/*`
- Swagger tại `http://127.0.0.1:8000/docs`
- ReDoc tại `http://127.0.0.1:8000/redoc`
- SPA tại `http://127.0.0.1:8000/` (sau khi build frontend)

### 1.7 — Chạy frontend (dev mode)

```bash
cd src/frontend
npm install
npm run dev
# Vite serve tại http://localhost:5173 với HMR.
# Proxy /api đến http://localhost:8000 (config trong vite.config.ts).
```

Cho prod build:
```bash
npm run build
# Output ở dist/ — backend serve nó như static files.
```

### 1.8 — Chạy agent (với local backend)

```bash
# 1. Cấp enrollment token (admin JWT):
ADMIN_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@demo.com","password":"admin123"}' | jq -r .accessToken)

curl -X POST http://127.0.0.1:8000/api/agents/enrollment-tokens \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"expires_minutes": 30}'

# 2. Enroll agent:
agent enroll \
    --server-url http://127.0.0.1:8000 \
    --enrollment-token o47enr_xxx \
    --state-path /tmp/ueba-agent-state.json

# 3. Run:
agent run \
    --server-url http://127.0.0.1:8000 \
    --state-path /tmp/ueba-agent-state.json \
    --log-path /tmp/ueba-agent.log \
    --log-level DEBUG
```

---

## 2. Code layout

```
.
├── pyproject.toml                   # pip package config (agent only)
├── requirements.txt                 # backend deps
├── requirements-agent.txt           # agent-only deps (minimal)
├── docker-compose.yml               # single-container deploy (db + app + frontend)
├── Dockerfile                       # backend image
├── src/
│   ├── backend/                     # FastAPI app
│   │   ├── app/
│   │   │   ├── main.py              # entry point + lifespan
│   │   │   ├── config.py            # Settings (env vars)
│   │   │   ├── api/                 # routers
│   │   │   │   ├── routes.py        # /api/auth, /api/users, /api/devices, /api/logs, /api/alerts, /api/raw-logs, /api/dashboard
│   │   │   │   ├── routes_admin.py   # /api/admin/* (Phase 3: normalizer + scoring)
│   │   │   │   ├── routes_agents.py # /api/agents/* (Phase 1)
│   │   │   │   ├── routes_alerts.py # /api/alerts
│   │   │   │   ├── routes_health.py # /health
│   │   │   │   ├── routes_logs.py   # /api/logs
│   │   │   │   └── routes_ml.py    # /api/ml, /api/models, /api/analysis
│   │   │   ├── core/                # auth, security
│   │   │   │   └── security.py      # JWT, bcrypt, agent auth
│   │   │   ├── db/                  # database layer
│   │   │   │   ├── session.py       # connection, schema, helpers
│   │   │   │   └── agents.py        # agent-specific DB helpers
│   │   │   ├── schemas/             # Pydantic
│   │   │   │   └── schemas.py
│   │   │   └── services/            # business logic
│   │   │       ├── normalizer.py    # raw → event (Phase 3)
│   │   │       ├── user_scoring.py  # OCSVM + alert (Phase 3)
│   │   │       ├── demo_pipeline.py # CSV-based analysis
│   │   │       └── llm.py           # Mistral explanation
│   │   └── tests/                   # pytest
│   ├── frontend/                    # React + Vite + TypeScript
│   │   ├── src/
│   │   │   ├── pages/               # một file mỗi route
│   │   │   ├── components/          # layout, security (reusable UI)
│   │   │   ├── lib/                 # apiClient, authStore, labels
│   │   │   ├── types/               # TypeScript types
│   │   │   ├── store/               # React contexts
│   │   │   ├── App.tsx              # router
│   │   │   └── main.tsx             # entry
│   │   └── package.json
│   ├── ml/                          # ML pipeline
│   │   ├── services/ueba_ml/        # OCSVM inference (production)
│   │   ├── weights/                 # joblib artifacts
│   │   └── scripts/                 # train/preprocess shell scripts
│   ├── database/                    # legacy data utilities
│   └── agent/                       # Endpoint agent (Phase 2 + 4)
│       ├── cli.py                   # `agent` command
│       ├── service.py               # main loop
│       ├── collectors/              # 7 collector implementations
│       │   ├── base.py
│       │   ├── logon.py             # Linux wtmp + Windows stub
│       │   ├── http_dns.py          # DNS sinkhole + DomainCheck
│       │   ├── device.py            # USB (Phase 4)
│       │   ├── file.py              # poll + programmatic (Phase 4)
│       │   ├── email.py             # programmatic + IMAP (Phase 4)
│       │   ├── process.py           # /proc + programmatic (Phase 4)
│       │   └── network.py           # /proc/net/tcp + programmatic (Phase 4)
│       ├── transport.py             # httpx + error classification
│       ├── buffer.py                # SQLite local queue
│       ├── config_client.py         # pulls server config
│       ├── enroll.py                # `agent enroll` subcommand
│       ├── update.py                # `agent update` subcommand (Phase 5b)
│       └── tests/                   # pytest
├── scripts/                         # installer + build scripts
│   ├── install_agent.sh             # Linux systemd installer
│   ├── install_agent.ps1            # Windows installer
│   ├── install_agent_macos.sh       # macOS installer
│   ├── install_via_curl.sh          # curl-pipe installer (Phase 5b)
│   ├── install_via_curl.ps1         # PowerShell installer
│   ├── build_agent_binary.sh       # PyInstaller (Phase 5)
│   ├── generate_mock_data.py       # demo dataset
│   └── import_mock_data.py          # demo dataset importer
├── docs/                            # all documentation
└── eval/                            # evaluation scripts (CERT r4.2 replay)
```

---

## 3. Quy ước code

### 3.1 — Python

- **Style**: enforced bởi `ruff` (config trong `pyproject.toml`).
- **Type hints**: bắt buộc cho mọi code mới.
- **Docstrings**: Google style, cho mọi public function và class.
- **Imports**: standard library → 3rd party → local. Dùng
  `from __future__ import annotations` cho forward references.
- **Line length**: 100 (mặc định của ruff; không bắt buộc cho code cũ).
- **Format**: `ruff format` (hoặc `black` với line-length=100).

```bash
# Trước khi commit:
ruff check src/          # lint
ruff format src/         # format (tùy chọn — CI không enforce)
```

### 3.2 — TypeScript / React

- **Style**: enforced bởi `eslint` (config trong
  `src/frontend/eslint.config.js`).
- **Components**: chỉ dùng functional (không class component).
- **Hooks**: tuân theo rules of hooks. Wrap state update phụ thuộc vào
  previous state trong `useCallback` để tránh warning
  `react-hooks/set-state-in-effect`.
- **Types**: define interface cho mọi props và API response.
- **Không `any`**: dùng `unknown` + type guards, hoặc define proper
  interface.

```bash
# Trước khi commit:
cd src/frontend
npx eslint src
npx tsc -b
```

### 3.3 — SQL

- Tên bảng: `snake_case`, số nhiều (`users`, `event_logs`).
- Tên column: `snake_case`, số ít.
- Index: `idx_<table>_<columns>`.
- Constraint: dùng `CHECK` cho enum-like value, `FOREIGN KEY ... ON DELETE`
  rõ ràng.
- Luôn dùng `CREATE INDEX IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS`
  cho idempotency.

### 3.4 — Git

- Tên branch: `feature/...`, `fix/...`, `docs/...`, `refactor/...`.
- Commit message: thì hiện tại, 50 char subject, dòng trống, 72 char body.
  Ví dụ: `fix(agent): handle LinuxNetworkCollector ESTABLISHED state filter`
- Squash trước khi merge.

---

## 4. Test

### 4.1 — Backend tests (pytest)

```bash
pytest src/backend/tests

# Với DB integration tests:
TEST_DATABASE_URL=postgresql://test_user:test_pass@localhost:5432/test_db \
    pytest src/backend/tests
```

Hai layer:
- **Pure unit tests** (không DB): mock DB helpers. Chạy ở bất kỳ đâu.
- **PostgreSQL integration tests** (gated bởi `@requires_postgres`): cần
  DB thật. Dùng `TEST_DATABASE_URL` env var để enable.

Quy ước: mỗi helper mới trong `db/session.py` nên có test non-Postgres
(mocked) VÀ test Postgres (thật).

### 4.2 — Agent tests (pytest)

```bash
pytest src/agent/tests
```

Chủ yếu pure unit tests. Agent có SQLite buffer riêng; test bằng
cách dùng tempdir fixture.

Một vài `test_e2e.py` cần backend thật đang chạy — những cái đó dùng
`TEST_DATABASE_URL` và skip khi không có.

### 4.3 — Frontend

Chưa có automated test. Manual test checklist:
- Login với từng role → thấy đúng menu items.
- Admin → Agents → cấp token → verify agent mới xuất hiện sau khi enroll.
- Admin → Blocklist → thêm entry → check nó xuất hiện trong lần
  config pull tiếp theo của agent (trong 5 phút).
- Admin → trigger normalizer → verify ml_anomaly_scores row count > 0.

### 4.4 — ML evaluation

```bash
bash src/ml/scripts/run_preprocessing.sh
bash src/ml/scripts/train_model.sh
# Outputs:
#   artifacts/feature_matrix.parquet
#   artifacts/iforest_anomaly_scores.csv
#   artifacts/ocsvm_anomaly_scores.csv
#   eval/report.md
```

So sánh với baseline trong `docs/ML_MODEL.md` (TBD).

---

## 5. Pull request process

1. **Branch từ `main`**:
   ```bash
   git checkout main
   git pull
   git checkout -b feature/my-change
   ```

2. **Code + commit thường xuyên**. Pre-commit checklist:
   ```bash
   # Backend
   ruff check src/backend
   pytest src/backend/tests

   # Agent
   ruff check src/agent
   pytest src/agent/tests

   # Frontend
   cd src/frontend
   npx tsc -b
   npx eslint src
   ```

3. **Push + mở PR**:
   ```bash
   git push -u origin feature/my-change
   # Mở PR trên GitHub.
   ```

4. **Mô tả PR** phải có:
   - Thay đổi làm gì (1-2 câu).
   - Cách test (commands reviewer có thể chạy).
   - Screenshot cho UI changes.
   - Linked issue (nếu có).

5. **CI checks** (khi set up) sẽ chạy:
   - `ruff check src/`
   - `pytest src/backend/tests src/agent/tests`
   - `npm run build` (frontend)

6. **Review**: cần ít nhất 1 approval trước khi merge. Maintainer sẽ
   check:
   - Tests pass.
   - Lint clean.
   - Docs updated (nếu user-facing).
   - Không có lint error mới.

7. **Squash merge** để giữ history `main` sạch.

---

## 6. Thêm endpoint mới

Ví dụ: thêm `GET /api/things/{id}`:

1. **Schema** trong `src/backend/app/schemas/schemas.py`:
   ```python
   class ThingRead(BaseModel):
       id: int
       name: str
       created_at: str
   ```

2. **DB helper** trong `src/backend/app/db/session.py`:
   ```python
   def get_thing(thing_id: int) -> dict[str, Any] | None:
       with get_connection() as conn:
           row = conn.execute("SELECT * FROM things WHERE id = %s", (thing_id,)).fetchone()
           return _row_to_dict(row) if row else None
   ```

3. **Route** trong `src/backend/app/api/routes.py`:
   ```python
   @router.get("/things/{thing_id}", response_model=ThingRead)
   async def get_thing_endpoint(
       thing_id: int,
       current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
   ) -> dict:
       _ = current_account
       thing = database.get_thing(thing_id)
       if not thing:
           raise HTTPException(status_code=404, detail="Thing not found")
       return thing
   ```

4. **Test** trong `src/backend/tests/test_api/test_routes.py` (hoặc file mới):
   ```python
   @pytest.mark.asyncio
   async def test_get_thing_returns_200():
       async with get_test_client() as client:
           response = await client.get("/api/things/1", headers=auth_header)
           assert response.status_code == 200
   ```

5. **Frontend** — thêm vào `apiClient.ts`:
   ```typescript
   export async function getThing(thingId: number) {
       return await request<ThingRead>(`/things/${thingId}`);
   }
   ```

6. **API contract** — thêm vào `docs/API_CONTRACT.md`.

---

## 7. Thêm collector mới

Ví dụ: thêm collector `printer`:

1. **File**: `src/agent/collectors/printer.py`:
   ```python
   class LinuxPrinterCollector(Collector):
       name = "printer"

       def __init__(self, config_client, poll_interval=30.0):
           super().__init__(config_client)
           ...

       def start(self) -> None:
           ...

       def stop(self) -> None:
           ...
   ```

2. **Policy name**: `printer` (thêm vào `agent_policy` default
   `enabled_collectors_json` trong `db/session.py`).

3. **Wire trong `service.py`**:
   ```python
   candidates.append(LinuxPrinterCollector(config_client))
   ```

4. **Test**: `src/agent/tests/test_printer_collector.py`.

5. **Thêm vào `agent.update`'s PyInstaller excludes** nếu nó kéo theo
   dependency nặng (hiếm; hầu hết collector chỉ dùng stdlib).

6. **Docs**: cập nhật `AGENT_DEPLOYMENT.md` collector list + `DATA_CONTRACT.md`.

---

## 8. Thêm schema migration

Codebase hiện dùng `initialize_database()` với idempotent
`CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`. Không có
versioned migrations. **Đây là cố ý** — cho project nhỏ, simplicity
thắng. Nếu cần migration phá hủy (drop column, change type, rename),
làm thủ công:

1. **Viết migration dưới dạng one-off script** trong
   `src/database/migrations/<date>_<description>.py`.
2. **Document** trong `docs/management/MIGRATIONS.md` (TODO).
3. **Test** trên bản copy của production data trước.
4. **Chạy** trong maintenance window.
5. **Cập nhật `initialize_database()`** nếu thay đổi nên permanent
   (để deploy mới bắt đầu với schema đúng).

Cho greenfield deploy, `initialize_database()` là đủ.

Khi project lớn lên, chuyển sang Alembic:

```bash
alembic init src/database/migrations
alembic revision --autogenerate -m "add ml_anomaly_scores"
alembic upgrade head
```

---

## 9. Thêm dependency mới

1. Thêm vào `requirements.txt` (backend) hoặc `requirements-agent.txt` (agent).
2. Pin minimum version. Tránh pin exact version (để `pip install` tự
   resolve version tương thích).
3. Cho agent: cũng thêm vào `pyproject.toml` `dependencies =`.
4. Cho agent: rebuild binary (`./scripts/build_agent_binary.sh`).
5. Test rằng dep mới không phình binary quá (list `exclude-module` trong
   `build_agent_binary.sh` quan trọng ở đây).
6. Cập nhật docs liên quan.

---

## 10. Release process

1. **Bump version** trong `pyproject.toml`.
2. **Cập nhật `docs/CHANGELOG.md`** với changes.
3. **Build binaries**:
   ```bash
   ./scripts/build_agent_binary.sh --target all
   ```
4. **Tag + release**:
   ```bash
   git tag v0.1.0
   git push --tags
   gh release create v0.1.0 \
       dist/agent-linux-x86_64 \
       dist/agent-darwin-x86_64 dist/agent-darwin-arm64 \
       dist/agent-windows-x86_64.exe \
       dist/SHA256SUMS \
       --title "v0.1.0" --notes-file CHANGELOG.md
   ```
5. **Cập nhật README + PLAN** với version mới.

---

## 11. Quy tắc ứng xử

Hãy tử tế. Bất đồng về mặt kỹ thuật, không bao giờ cá nhân. Mặc định
thiện ý. Giúp đỡ người mới. Đừng làm kẻ cứng đầu.

Vi phạm: liên hệ conduct@vespionage.com.
