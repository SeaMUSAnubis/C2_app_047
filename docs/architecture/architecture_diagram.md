# Sơ Đồ Kiến Trúc

## Luồng dữ liệu chính

```text
┌─────────────────────────────────────────────────────────────────┐
│                    CERT r4.2 Dataset                            │
│  (logon.csv, device.csv, file.csv, http.csv, email.csv, LDAP)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Preprocessing & Feature Engineering
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              src/services/ueba_ml/pipelines/                     │
│  - preprocess.py: Import + Normalize + Feature Engineering      │
│  - train.py: Train OneClassSVM                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Model Artifact
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         weights/ocsvm_cert_r42_chunked.joblib                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Load & Inference
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ Auth (JWT)  │ │ User/Device │ │ ML Inference│               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ Log Ingest  │ │Risk Scoring │ │LLM Analysis │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ PostgreSQL
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Database                                   │
│  - app_accounts: Tài khoản đăng nhập                           │
│  - users: Người dùng được giám sát                             │
│  - devices: Thiết bị                                            │
│  - event_logs: Event logs đã normalize                         │
│  - raw_user_logs: Raw logs từ agents                           │
│  - alerts: Cảnh báo                                             │
│  - model_artifacts: Model metadata                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ REST API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                Frontend Dashboard (React + Vite)                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │   Login     │ │  Dashboard  │ │    Users    │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │   Devices   │ │    Logs     │ │   Alerts    │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

## Luồng inference tại runtime

```text
Client (Frontend/Agent)
        │
        │ POST /api/models/{version}/infer
        │ { features: { logon_count: 4, ... } }
        ▼
┌─────────────────────────────────────────────┐
│           API Route: infer_model            │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│     run_ocsvm_inference(features)           │
│  1. Load model từ weights/ (cached)         │
│  2. Tạo DataFrame từ features              │
│  3. Predict (normal/anomaly)                │
│  4. Tính anomaly_score, risk_score          │
│  5. Xác định severity                       │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│           ModelInferResponse                │
│  - prediction: "normal" | "anomaly"         │
│  - isAnomaly: boolean                       │
│  - riskScore: 0-100                         │
│  - severity: low/medium/high/critical       │
│  - missingFeatures, extraFeatures           │
└─────────────────────────────────────────────┘
```
