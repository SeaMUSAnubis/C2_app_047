# Tổng Quan Kiến Trúc

Source code chính theo cấu trúc:

```text
src/
  __init__.py
  main.py           # FastAPI app entry point
  config.py         # App settings (pydantic-settings)
  agents/           # Agent graph, nodes, tools, state
    graph.py        # Alert explanation workflow
  api/              # FastAPI routes
    routes.py       # Tất cả API endpoints
  models/           # Pydantic schemas + ML artifacts
    schemas.py      # Request/response models
    ocsvm_cert_r42_chunked.joblib  # OCSVM model artifact
  services/         # Business logic
    auth.py         # JWT auth, password hashing
    database.py     # PostgreSQL connection, CRUD
    llm.py          # Mistral AI integration
    ueba_ml/        # ML pipelines
      inference.py  # OCSVM inference
      pipelines/    # Preprocessing, training

tests/              # pytest suite
  conftest.py       # Test config, helpers
  test_api/         # API integration tests
  test_services/    # Service unit tests
  test_agents/      # Agent tests

frontend/           # React + Vite frontend
  src/
    components/     # UI components
    pages/          # Page components
    lib/            # Utilities, API client
    types/          # TypeScript types

docs/               # Tài liệu
  architecture/     # Kiến trúc hệ thống
  contracts/        # API, data contracts
  management/       # Test reports, worklog
  planning/         # PRD, requirements

weights/            # ML model artifacts
data/               # Local data (không commit)
artifacts/          # ML outputs (không commit)
```

Chi tiết kiến trúc nằm trong `docs/architecture/ARCHITECTURE.md`.
