# UEBA Endpoint Monitoring

UEBA Endpoint Monitoring là web app phát hiện hành vi bất thường của user/device từ log endpoint theo hướng insider threat và account compromise. MVP dùng CERT r4.2-style logs để preprocessing, train Isolation Forest, sinh anomaly score/risk context và chuẩn bị tích hợp dashboard + backend API + endpoint agent.

## Cấu trúc repo

```text
backend/        FastAPI app, API, auth, database, service layer
frontend/       React/Next.js dashboard
agent/          Endpoint agent hoặc mock agent gửi log
ml/             Preprocessing, feature engineering, training, scoring
data/           Raw/sample/interim/processed data và schema
artifacts/      Output pipeline: feature matrix, model, predictions, metadata
reports/        Báo cáo phân tích, training report, figures
docs/           PRD, architecture, API/data contract, references
scripts/        Hook scripts và lệnh tiện ích mỏng
infra/          Docker/deploy/reverse proxy config
tests/          Integration và e2e tests cấp repo
```

Chi tiết chuẩn thư mục nằm ở [docs/REPO_STRUCTURE_STANDARD.md](docs/REPO_STRUCTURE_STANDARD.md).

## Data

Repo tách dữ liệu theo vòng đời:

- `data/raw/cert-r4.2/`: raw CERT dataset, local only, không commit.
- `data/sample/cert-r4.2-small/`: sample nhỏ để smoke test/demo nhanh.
- `data/interim/` và `data/processed/`: dữ liệu trung gian/generated, không commit.
- `data/schemas/`: schema/data contract nên commit.

## ML pipeline hiện có

Chạy preprocessing trên sample:

```bash
python ml/ueba_ml/pipelines/preprocess.py --input-dir data/sample/cert-r4.2-small
```

Chạy preprocessing trên raw dataset:

```bash
python ml/ueba_ml/pipelines/preprocess.py --input-dir data/raw/cert-r4.2 --chunksize 250000
```

Train Isolation Forest từ feature matrix:

```bash
python ml/ueba_ml/pipelines/train.py
```

Output chính:

- `artifacts/preprocessing/iforest_feature_matrix.csv`
- `artifacts/preprocessing/iforest_feature_columns.json`
- `artifacts/models/iforest_model.joblib`
- `artifacts/models/iforest_metadata.json`
- `artifacts/models/iforest_anomaly_scores.csv`
- `artifacts/evaluation/iforest_feature_lift.csv`
- `reports/preprocessing_report.md`
- `reports/iforest_training_report.md`

## Module ownership

| Mảng | Thư mục | Deliverable |
|---|---|---|
| Product/PM | `docs/`, `JOURNAL.md`, `WORKLOG.md` | PRD, user story, task assignment |
| Backend | `backend/`, `infra/` | API, auth, DB, services |
| Frontend | `frontend/` | Dashboard, login, alert/user/device/log views |
| Data/ML | `ml/`, `data/`, `artifacts/`, `reports/` | Feature pipeline, model training, scoring, reports |
| Agent | `agent/` | Mock/real endpoint agent, normal/anomaly simulator |
| QA/DevOps | `tests/`, `.github/`, `infra/` | CI, integration/e2e tests, deploy config |

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

- [docs/BRIEF.md](docs/BRIEF.md)
- [docs/PRD.md](docs/PRD.md)
- [docs/UEBA_REQUIREMENTS.md](docs/UEBA_REQUIREMENTS.md)
- [docs/REPO_STRUCTURE_STANDARD.md](docs/REPO_STRUCTURE_STANDARD.md)
- [docs/UI_FLOW.svg](docs/UI_FLOW.svg)
