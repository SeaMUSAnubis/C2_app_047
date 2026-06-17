# O47 Insider Threat Detection System

Hệ thống phân tích hành vi người dùng và phân tích rủi ro nội bộ (UEBA - User and Entity Behavior Analytics) kết hợp giữa Machine Learning (OCSVM) và Large Language Models (LLMs) để đưa ra giải thích thân thiện cho chuyên gia bảo mật.

## 1. Architecture Diagram
Xem sơ đồ kiến trúc tại file [Architecture Diagram](./artifacts/architecture_diagram.md).

## 2. Setup Instructions

### Yêu cầu hệ thống
- Python 3.10+
- Node.js 18+
- Dữ liệu CERT r4.2 đặt tại `d:\2 Code\TEAM_O47\Data`
- Model weight đặt tại `d:\2 Code\TEAM_O47\Weight`

### Cài đặt Backend
```bash
# 1. Chuyển vào thư mục dự án
cd "d:\2 Code\TEAM_O47\C2-App-047"

# 2. Tạo môi trường ảo (nếu chưa có) và cài đặt dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Khởi chạy FastAPI server
uvicorn src.main:app --reload --port 8000
```

### Cài đặt Frontend
```bash
# 1. Chuyển vào thư mục frontend
cd "d:\2 Code\TEAM_O47\C2-App-047\frontend"

# 2. Cài đặt các gói thư viện
npm install

# 3. Chạy Vite dev server
npm run dev
```

## 3. Environment Variables (Env Vars)

### Backend `.env`
Tạo file `.env` tại thư mục gốc backend:
```env
APP_NAME="O47 UEBA System"
APP_VERSION="1.0.0"
CORS_ORIGINS="http://localhost:5173"
JWT_SECRET="your-secret-key-here"
```

### Frontend `.env`
Tạo file `.env` tại thư mục `frontend`:
```env
VITE_API_BASE_URL=http://localhost:8000/api
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
```

## 4. Sample Queries
Ví dụ payload JSON gửi tới endpoint `/api/demo/analyze`:
```json
{
  "user_id": "HSB0196",
  "events": [
    {
      "event_type": "logon",
      "timestamp": "2010-01-02T09:00:00Z",
      "pc": "PC-8001"
    },
    {
      "event_type": "file",
      "timestamp": "2010-01-02T09:49:30Z",
      "filename": "RJGC8XX5.exe"
    }
  ]
}
```

## 5. Eval Evidences
Bạn có thể tham khảo kết quả phân tích 5 kịch bản thực tế (lấy từ log của tập CERT) tại báo cáo [Eval Evidences](./artifacts/eval_evidences.md).
Mọi cảnh báo đều được Model nhận diện dựa trên baseline của user, từ đó LLM sẽ tổng hợp ra một câu giải thích bằng ngôn ngữ tự nhiên.
