# UEBA Endpoint Monitoring

UEBA Endpoint Monitoring là web app phát hiện hành vi bất thường của user/device từ log endpoint theo hướng insider threat và account compromise. MVP dùng CERT r4.2-style logs để preprocessing, train Isolation Forest, sinh anomaly score/risk context và chuẩn bị tích hợp dashboard + backend API + endpoint agent.

## Cấu trúc repo

```text
src/
  agents/       Agent graph, nodes, tools, state theo starter template
  api/          FastAPI routes
  models/       Pydantic schemas
  services/     Business logic và UEBA ML pipelines
tests/          pytest suite
docs/           PRD, architecture, API/data contract, references, guide
eval/           Evaluation evidence và reports
presentation/   Demo Day slides/assets
scripts/        AI logging hooks và helper scripts
.github/        CI/CD workflows + Copilot hook config
Dockerfile      API container
docker-compose.yml
Makefile
```

Chi tiết chuẩn thư mục nằm ở [docs/standards/REPO_STRUCTURE_STANDARD.md](docs/standards/REPO_STRUCTURE_STANDARD.md).

## Data

Repo tách dữ liệu theo vòng đời:

- `data/raw/cert-r4.2/`: raw CERT dataset, local only, không commit.
- `data/sample/cert-r4.2-small/`: sample nhỏ để smoke test/demo nhanh, local only.
- `artifacts/`: feature matrix, model binary, scores, local/generated.
- Schema và data contract nằm trong `docs/contracts/DATA_CONTRACT.md`.

## ML pipeline hiện có

Chạy preprocessing trên sample:

```bash
python src/services/ueba_ml/pipelines/preprocess.py --input-dir data/sample/cert-r4.2-small
```

Chạy preprocessing trên raw dataset:

```bash
python src/services/ueba_ml/pipelines/preprocess.py --input-dir data/raw/cert-r4.2 --chunksize 250000
```

Train Isolation Forest từ feature matrix:

```bash
python src/services/ueba_ml/pipelines/train.py
```

Output chính:

- `artifacts/preprocessing/iforest_feature_matrix.csv`
- `artifacts/preprocessing/iforest_feature_columns.json`
- `artifacts/models/iforest_model.joblib`
- `artifacts/models/iforest_metadata.json`
- `artifacts/models/iforest_anomaly_scores.csv`
- `artifacts/evaluation/iforest_feature_lift.csv`
- `eval/results/preprocessing_report.md`
- `eval/results/iforest_training_report.md`

## Chạy project

### Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend (Vite) | 5173 | http://localhost:5173 |
| Backend API (FastAPI) | 8000 | http://localhost:8000 |
| PostgreSQL | 5432 | localhost:5432 |

### Cách 1: Chạy bằng Docker (Khuyến nghị)

Docker sẽ khởi động cả Frontend + Backend API + PostgreSQL cùng lúc.

```bash
# Khởi động tất cả services
docker compose up -d

# Xem logs
docker compose logs -f

# Dừng services
docker compose down

# Rebuild sau khi sửa code
docker compose up -d --build
```

Truy cập ứng dụng tại http://localhost:5173

### Cách 2: Chạy tách riêng từng service

#### 1. Database (PostgreSQL)

```bash
# Khởi động PostgreSQL bằng Docker
docker compose up -d db

# Verify database đang chạy
docker compose ps
```

#### 2. Backend API (FastAPI)

```bash
# Tạo virtual environment (lần đầu)
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# Cài dependencies (lần đầu)
pip install -r requirements.txt

# Tạo file .env từ template (lần đầu)
cp .env.example .env

# Chạy Backend API
uvicorn src.main:app --reload --port 8000

# Hoặc dùng Makefile
make run
```

Backend API chạy trên http://localhost:8000

API docs (Swagger): http://localhost:8000/docs

#### 3. Frontend (React + Vite)

```bash
# Vào thư mục frontend
cd frontend

# Cài dependencies (lần đầu)
npm install

# Chạy dev server
npm run dev
```

Frontend chạy trên http://localhost:5173

### Tài khoản mặc định

| Email | Password | Role |
|-------|----------|------|
| admin@demo.com | admin123 | admin |
| analyst@demo.com | analyst123 | analyst |

### Environment Variables

Xem `.env.example` để biết các biến môi trường cần thiết:

```bash
# Database
DATABASE_URL=postgresql://ueba:ueba@localhost:5432/ueba

# JWT
JWT_SECRET=change-me-in-production
JWT_EXPIRES_MINUTES=480

# CORS (Frontend URL)
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# ML Model
OCSVM_MODEL_PATH=src/models/ocsvm_cert_r42_chunked.joblib
OCSVM_MODEL_VERSION=ocsvm-cert-r42-chunked

# LLM (optional)
MISTRAL_API_KEY=
MISTRAL_MODEL=mistral-small-latest
```

## Module ownership

| Mảng | Thư mục | Deliverable |
|---|---|---|
| Product/PM | `docs/`, `docs/management/JOURNAL.md`, `docs/management/WORKLOG.md` | PRD, user story, task assignment |
| API/backend | `src/api/`, `src/models/`, `src/main.py` | FastAPI app, schemas, service API |
| Data/ML | `src/services/ueba_ml/`, `data/`, `artifacts/`, `eval/` | Feature pipeline, model training, scoring, reports |
| Agent/LLM workflow | `src/agents/`, `src/services/` | Alert explanation workflow and services |
| QA/DevOps | `tests/`, `.github/`, `Dockerfile`, `Makefile` | CI, tests, deploy config |

## AI logging hooks

Repo vẫn giữ hook logging của AI20K Build Cohort 2 trong `scripts/` và các thư mục `.agents/`, `.claude/`, `.codex/`, `.cursor/`, `.gemini/`, `.github/hooks/`.

Cài pre-push hook một lần:

```bash
bash scripts/setup_hooks.sh
```

Hoặc trên Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```

Với ChatGPT/web tools, log thủ công:

```bash
bash scripts/_pyrun.sh scripts/log_manual.py --tool chatgpt --prompt "<what you did>"
```

## Tài liệu

- [docs/planning/BRIEF.md](docs/planning/BRIEF.md)
- [docs/planning/PRD.md](docs/planning/PRD.md)
- [docs/planning/UEBA_REQUIREMENTS.md](docs/planning/UEBA_REQUIREMENTS.md)
- [docs/standards/REPO_STRUCTURE_STANDARD.md](docs/standards/REPO_STRUCTURE_STANDARD.md)
- [docs/assets/UI_FLOW.svg](docs/assets/UI_FLOW.svg)
