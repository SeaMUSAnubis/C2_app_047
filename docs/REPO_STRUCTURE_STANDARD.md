# Chuẩn cấu trúc repo theo AI20K starter-code-template

Repo này follow cấu trúc của `AI20K-Build-Cohort-2/starter-code-template`:

```text
.
├── src/
│   ├── agents/
│   │   ├── nodes/
│   │   ├── tools/
│   │   ├── graph.py
│   │   └── state.py
│   ├── api/
│   │   └── routes.py
│   ├── models/
│   │   └── schemas.py
│   ├── services/
│   │   ├── llm.py
│   │   └── ueba_ml/
│   │       └── pipelines/
│   ├── config.py
│   └── main.py
├── tests/
│   ├── test_agents/
│   └── test_api/
├── docs/
│   ├── guide/
│   ├── references/
│   ├── architecture/
│   ├── assets/
│   ├── contracts/
│   ├── management/
│   ├── planning/
│   ├── reports/
│   ├── standards/
│   ├── guide/
│   └── references/
├── eval/
│   └── results/
├── presentation/
├── scripts/
├── .github/
│   ├── hooks/
│   └── workflows/
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── ruff.toml
└── README.md
```

## Quy tắc chính

1. Source code chính nằm trong `src/`, không tạo top-level `backend/`, `frontend/`, `agent/`, `ml/` làm source root.
2. API nằm trong `src/api/`; entrypoint FastAPI nằm ở `src/main.py`.
3. Pydantic/domain schemas nằm trong `src/models/`.
4. Business logic nằm trong `src/services/`.
5. UEBA preprocessing/training pipeline nằm trong `src/services/ueba_ml/`.
6. Agent/LLM workflow nằm trong `src/agents/`.
7. Tests follow template: `tests/test_api/`, `tests/test_agents/`.
8. Evaluation evidence và report nằm trong `eval/results/`.
9. Raw/sample data và generated artifacts là local-only: `data/`, `artifacts/`.
10. AI logging hooks giữ nguyên trong `scripts/`, `.agents/`, `.claude/`, `.codex/`, `.cursor/`, `.gemini/`, `.github/hooks/`.

## Mapping từ cấu trúc cũ sang cấu trúc template

| Cấu trúc cũ | Cấu trúc template hiện tại |
|---|---|
| `backend/app/...` | `src/api/`, `src/models/`, `src/services/`, `src/main.py` |
| `agent/...` | `src/agents/` |
| `ml/ueba_ml/...` | `src/services/ueba_ml/...` |
| `reports/...` | `eval/results/...` |
| `infra/...` | `Dockerfile`, `docker-compose.yml`, `.github/workflows/` |
| `data/schemas/...` | `docs/DATA_CONTRACT.md` |
| `data/raw`, `data/sample` | local-only `data/`, ignored by git |
| `artifacts/...` | local-only `artifacts/`, ignored by git |

## Ownership để chia việc

| Role | Thư mục chính | Deliverable |
|---|---|---|
| API/backend | `src/api/`, `src/models/`, `src/main.py` | FastAPI endpoints, schemas, app wiring |
| Data/ML | `src/services/ueba_ml/`, `eval/results/` | Feature pipeline, iForest training, metrics/report |
| Agent/LLM | `src/agents/`, `src/services/llm.py` | Alert explanation workflow |
| Product/docs | `docs/`, `README.md`, `docs/management/JOURNAL.md`, `docs/management/WORKLOG.md` | PRD, architecture, contracts, worklog |
| QA/DevOps | `tests/`, `.github/workflows/`, `Dockerfile`, `Makefile` | CI, tests, container/deploy commands |

## Commit hygiene

- Commit source, docs, config, tests and evaluation reports.
- Do not commit raw CERT data, generated CSV matrices, model binaries or AI log JSONL files.
- Use explicit staging paths when worktree is mixed.
