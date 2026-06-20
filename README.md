# O47 Insider Threat Detection System

Hệ thống phân tích hành vi người dùng và phân tích rủi ro nội bộ (UEBA - User and Entity Behavior Analytics) kết hợp giữa Machine Learning (OCSVM) và Large Language Models (LLMs) để đưa ra giải thích thân thiện cho chuyên gia bảo mật.

## Cấu trúc repo

```text
C2-App-047/
├── src/                          # Backend + Frontend source code
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # App settings
│   ├── api/                      # FastAPI routes
│   │   └── routes.py             # All API endpoints
│   ├── models/                   # Pydantic schemas
│   │   └── schemas.py            # Request/response models
│   ├── services/                 # Business logic
│   │   ├── auth.py               # JWT auth
│   │   ├── database.py           # PostgreSQL CRUD
│   │   ├── llm.py                # LLM integration
│   │   └── ueba_ml/              # ML pipelines
│   │       ├── inference.py      # OCSVM inference
│   │       └── pipelines/        # Preprocessing, training
│   └── frontend/                 # React + Vite frontend
│       ├── src/                  # React source
│       ├── package.json          # Node dependencies
│       ├── Dockerfile            # Frontend Docker image
│       └── nginx.conf            # Nginx proxy config
│
├── tests/                        # pytest test suite
├── docs/                         # Documentation
├── scripts/                      # Helper scripts
├── weights/                      # ML model artifacts
├── data/                         # Local data (không commit)
├── artifacts/                    # ML outputs (không commit)
│
├── docker-compose.yml            # Docker services
├── Dockerfile                    # Backend Docker image
├── Makefile                      # Common commands
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment variables template
```

## Setup Instructions

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
cd "d:\2 Code\TEAM_O47\C2-App-047\src\frontend"

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
Tạo file `.env` tại thư mục `src/frontend`:
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
cd src/frontend

# Cài dependencies (lần đầu)
npm install

# Chạy dev server
npm run dev
```

Frontend chạy trên http://localhost:5173

## Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend (Vite/Nginx) | 5173 | http://localhost:5173 |
| Backend API (FastAPI) | 8000 | http://localhost:8000 |
| PostgreSQL | 5432 | localhost:5432 |

## Tài khoản mặc định

| Email | Password | Role |
|-------|----------|------|
| admin@demo.com | admin123 | admin |
| analyst@demo.com | analyst123 | analyst |

## Environment Variables

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
OCSVM_MODEL_PATH=weights/ocsvm_cert_r42_chunked.joblib
OCSVM_MODEL_VERSION=ocsvm-cert-r42-chunked

# LLM (optional)
MISTRAL_API_KEY=
MISTRAL_MODEL=mistral-small-latest
```

## ML Pipeline

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

## Load dữ liệu CERT r4.2

```bash
# Load sample data vào database
python scripts/load_cert_data.py
```

## Testing

### Backend Tests

```bash
# Bật Docker (PostgreSQL)
docker compose up -d

# Activate virtual environment
source .venv/bin/activate

# Chạy tất cả tests (cần PostgreSQL)
export TEST_DATABASE_URL="postgresql://ueba:ueba@localhost:5432/ueba"
pytest tests/ -v

# Chạy tests không cần DB
pytest tests/ -v -k "not postgres"
```

### Frontend Tests

```bash
cd src/frontend

# Chạy tất cả tests
npm run test

# Watch mode
npm run test:watch
```

## Tài liệu

- [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) - Kiến trúc hệ thống
- [docs/contracts/API_CONTRACT.md](docs/contracts/API_CONTRACT.md) - API Contract
- [docs/contracts/DATA_CONTRACT.md](docs/contracts/DATA_CONTRACT.md) - Data Contract
- [docs/planning/PRD.md](docs/planning/PRD.md) - Product Requirements Document
- [docs/management/MVP_PROGRESS.md](docs/management/MVP_PROGRESS.md) - Tiến độ MVP
