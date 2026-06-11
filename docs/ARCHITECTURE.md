# Architecture

## Target MVP flow

```text
Endpoint Agent / Mock Agent
        |
        | REST events
        v
Backend API
        |
        | auth, user/device/log/alert services
        v
Database
        |
        | alert/risk context
        v
Frontend Dashboard

ML Pipeline
        |
        | feature matrix, model artifact, scores
        v
Artifacts + Backend integration
```

## Module boundaries

- `agent/`: produces endpoint events that match `docs/DATA_CONTRACT.md`.
- `backend/`: owns API, auth, database persistence, risk/alert workflow.
- `frontend/`: consumes backend API only; it does not read local CSV/model files.
- `ml/`: owns preprocessing, feature engineering, training and scoring code.
- `artifacts/`: stores generated ML outputs consumed by demo/integration code.
- `data/`: stores local raw/sample data and schema documentation.

## Current implementation status

- ML preprocessing and Isolation Forest training are implemented in `ml/ueba_ml/pipelines/`.
- Backend/frontend/agent are scaffolded for team work and still need implementation.
- Product requirements live in `docs/PRD.md` and `docs/UEBA_REQUIREMENTS.md`.
