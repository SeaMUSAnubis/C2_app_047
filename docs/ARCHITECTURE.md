# Kiến Trúc Hệ Thống

## Luồng MVP hiện tại

```text
Endpoint Agent / Mock Agent
        |
        | REST API (POST /api/raw-logs/ingest, /api/logs/ingest)
        v
Backend API (FastAPI)
        |
        |-- Auth & Phân quyền (JWT, admin/analyst)
        |-- Quản lý User/Device
        |-- Log Ingestion & Normalization
        |-- ML Inference (OneClassSVM)
        |-- Risk Scoring (0-100)
        |-- LLM Analysis (Mistral AI / Rule-based fallback)
        |
        v
Database (PostgreSQL)
        |
        v
Frontend Dashboard (React + Vite)
```

## Pipeline ML

```text
CERT r4.2 CSV Dataset
        |
        | Preprocessing & Feature Engineering
        v
Feature Matrix (user/day features)
        |
        | Train OneClassSVM
        v
Model Artifact (weights/ocsvm_cert_r42_chunked.joblib)
        |
        | Batch Inference
        v
Anomaly Score → Risk Score → Alert
```

## Ranh giới module

| Module | Đường dẫn | Trách nhiệm |
|--------|----------|-------------|
| API Routes | `src/api/routes.py` | Định nghĩa tất cả API endpoints |
| Models | `src/models/schemas.py` | Pydantic schemas cho request/response |
| Auth | `src/services/auth.py` | JWT authentication, password hashing |
| Database | `src/services/database.py` | PostgreSQL connection, CRUD operations |
| ML Inference | `src/services/ueba_ml/inference.py` | OCSVM model loading, inference |
| ML Pipelines | `src/services/ueba_ml/pipelines/` | Preprocessing, feature engineering, training |
| LLM Analysis | `src/services/llm.py` | Mistral AI integration, rule-based fallback |
| Agent | `src/agents/graph.py` | Alert explanation workflow |
| Config | `src/config.py` | App settings (pydantic-settings) |

## Trạng thái triển khai hiện tại

| Tính năng | Trạng thái | Ghi chú |
|-----------|------------|---------|
| FastAPI backend | ✅ Hoàn thành | `src/main.py`, `src/api/routes.py` |
| JWT Authentication | ✅ Hoàn thành | Custom JWT, PBKDF2 password hashing |
| RBAC (admin/analyst) | ✅ Hoàn thành | `require_role()` middleware |
| User CRUD | ✅ Hoàn thành | Create, Read, Update |
| Device CRUD | ✅ Hoàn thành | Create, Read, Update |
| Log Ingestion | ✅ Hoàn thành | Event logs + Raw logs |
| OCSVM Inference | ✅ Hoàn thành | Pre-trained model, batch inference |
| Risk Scoring | ✅ Hoàn thành | 0-100 scale, severity levels |
| LLM Analysis | ✅ Hoàn thành | Mistral AI + rule-based fallback |
| Dashboard API | ✅ Hoàn thành | Summary endpoint với KPIs |
| CERT r4.2 Import | ⚠️ Một phần | Script preprocessing, chưa có API import |
| Alert Management | ⚠️ Chưa hoàn thành | Database schema có, chưa có API endpoints |
| Frontend Dashboard | ✅ Hoàn thành | React + Vite, 5 pages |
| Docker | ✅ Hoàn thành | docker-compose.yml (FE + BE + DB) |
