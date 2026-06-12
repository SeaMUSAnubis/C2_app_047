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

- `src/agents/`: produces or orchestrates endpoint/alert workflows.
- `src/api/`: owns API routes.
- `src/models/`: owns Pydantic schemas.
- `src/services/`: owns business logic, LLM explanation, preprocessing and model training services.
- `artifacts/`: stores generated ML outputs consumed by demo/integration code.
- `data/`: stores local raw/sample data and schema documentation.

## Current implementation status

- ML preprocessing and Isolation Forest training are implemented in `src/services/ueba_ml/pipelines/`.
- FastAPI scaffold is implemented in `src/main.py` and `src/api/routes.py`.
- Product requirements live in `docs/PRD.md` and `docs/UEBA_REQUIREMENTS.md`.
