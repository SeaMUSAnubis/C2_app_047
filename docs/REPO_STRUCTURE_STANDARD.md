# Chuẩn cấu trúc repo cho UEBA Endpoint Monitoring

**Mục tiêu:** chuẩn hóa thư mục để team dễ chia việc, giảm xung đột khi phát triển song song backend, frontend, agent, data pipeline, ML model và tài liệu.

**Phạm vi:** đây là cấu trúc đích cho repo dự án UEBA Endpoint Monitoring. Tài liệu này không yêu cầu di chuyển toàn bộ code ngay lập tức, nhưng nên dùng làm chuẩn khi thêm module mới hoặc refactor các script hiện có.

---

## 1. Kết quả nghiên cứu nhanh

Các nguồn đã đối chiếu:

| Nguồn | Link | Điểm rút ra |
|---|---|---|
| FastAPI Full Stack Template | https://github.com/fastapi/full-stack-fastapi-template | Dự án web app nên tách rõ `backend/`, `frontend/`, `scripts/`, compose/deployment và tài liệu vận hành. Template này dùng FastAPI, React, SQLModel/PostgreSQL, JWT, Docker Compose, tests và CI/CD. |
| Cookiecutter Data Science | https://cookiecutter-data-science.drivendata.org/ | Dự án data/ML nên tách `data/raw`, `data/interim`, `data/processed`, `models`, `notebooks`, `reports`, `references` và source code thành package riêng. |
| RobertoDure/Insider_Threat_Detection_with_CERT | https://github.com/RobertoDure/Insider_Threat_Detection_with_CERT | Repo CERT insider threat có luồng multi-modal: logon, device, file, email, HTTP, psychometric. Điểm yếu là notebook-heavy, chưa phù hợp để chia backend/frontend/agent. |
| iamAgbaCoder/UBA-Insider-Threat-Detection | https://github.com/iamAgbaCoder/UBA-Insider-Threat-Detection | Có tách `api/`, `src/`, `models/`, `data/`, `static/`, `templates/`, phù hợp hơn với app demo có API. Cần nâng cấp tiếp thành backend/frontend/ML module rõ ràng. |
| Elatchya/UEBA_Insider_Threat_Detection | https://github.com/Elatchya/UEBA_Insider_Threat_Detection | Có feature engineering, anomaly detection và dashboard, nhưng file script/data/plot nằm nhiều ở root. Đây là anti-pattern cần tránh khi team đông người. |
| AmmarAhmed1448/Insider-Threat-Detection-with-Unsupervised-Anomaly-Detection-and-UBA | https://github.com/AmmarAhmed1448/Insider-Threat-Detection-with-Unsupervised-Anomaly-Detection-and-UBA | Chủ yếu là notebook + paper. Hữu ích cho research, không đủ làm chuẩn repo sản phẩm. |

Kết luận: repo của mình nên dùng cấu trúc lai giữa **full-stack product repo** và **data science/ML repo**. Không nên chỉ theo kiểu notebook/script vì yêu cầu sản phẩm cuối có web app, API, auth, dashboard, agent, data pipeline, model inference và deploy.

---

## 2. Nguyên tắc tổ chức

1. **Tách source code và artifact sinh ra.** Code train/inference nằm trong `ml/`; model `.joblib`, CSV feature matrix, prediction output nằm trong `artifacts/`.
2. **Tách backend, frontend, agent và ML theo ownership.** Mỗi mảng có thư mục riêng, README riêng, test riêng.
3. **Root repo chỉ giữ file điều phối.** Không đặt script xử lý dữ liệu, notebook, dashboard hoặc model binary trực tiếp ở root.
4. **Dữ liệu gốc không commit.** `data/raw/` hoặc `dataset/` phải ignore. Chỉ commit sample nhỏ, schema, data dictionary và script tạo dữ liệu demo.
5. **Notebook chỉ dùng để khám phá.** Logic đã ổn định phải chuyển vào module Python trong `ml/` hoặc `backend/`.
6. **Mỗi thư mục lớn có contract rõ ràng.** Ví dụ backend publish OpenAPI, ML publish `model_metadata.json`, agent publish event schema, frontend consume API contract.
7. **Tên thư mục phản ánh trách nhiệm.** Tránh root `models/` vì dễ nhầm giữa ORM models của backend và ML model artifact.

---

## 3. Cấu trúc chuẩn đề xuất

```text
.
├── README.md
├── .env.example
├── .gitignore
├── pyproject.toml / requirements.txt
├── package.json
├── docker-compose.yml
├── JOURNAL.md
├── WORKLOG.md
│
├── backend/
│   ├── README.md
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── routers/
│   │   │       └── deps.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── seed.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   ├── device_service.py
│   │   │   ├── log_ingestion_service.py
│   │   │   ├── risk_scoring_service.py
│   │   │   ├── anomaly_service.py
│   │   │   └── llm_explanation_service.py
│   │   └── tests/
│   ├── migrations/
│   └── scripts/
│
├── frontend/
│   ├── README.md
│   ├── src/
│   │   ├── app/ or pages/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── dashboard/
│   │   │   ├── users/
│   │   │   ├── devices/
│   │   │   ├── logs/
│   │   │   └── alerts/
│   │   ├── lib/
│   │   │   ├── api/
│   │   │   └── utils/
│   │   ├── routes/
│   │   ├── styles/
│   │   └── tests/
│   └── e2e/
│
├── agent/
│   ├── README.md
│   ├── ueba_agent/
│   │   ├── main.py
│   │   ├── collectors/
│   │   ├── transport/
│   │   └── config.py
│   ├── simulators/
│   │   ├── normal_behavior.py
│   │   └── anomaly_behavior.py
│   └── tests/
│
├── ml/
│   ├── README.md
│   ├── ueba_ml/
│   │   ├── config.py
│   │   ├── data/
│   │   │   ├── loaders.py
│   │   │   └── validators.py
│   │   ├── features/
│   │   │   ├── cert_r42_features.py
│   │   │   └── feature_schema.py
│   │   ├── pipelines/
│   │   │   ├── preprocess.py
│   │   │   ├── train.py
│   │   │   └── score.py
│   │   ├── detectors/
│   │   │   ├── isolation_forest.py
│   │   │   └── rule_based.py
│   │   ├── explainers/
│   │   │   └── feature_drivers.py
│   │   ├── evaluation/
│   │   └── tests/
│   └── notebooks/
│       └── README.md
│
├── data/
│   ├── README.md
│   ├── raw/
│   │   └── cert-r4.2/          # ignored, local only
│   ├── sample/
│   │   └── cert-r4.2-small/    # commit được nếu đủ nhỏ
│   ├── interim/                # ignored/generated
│   ├── processed/              # ignored/generated unless tiny contract files
│   └── schemas/
│       ├── cert_event_schema.md
│       └── normalized_event_schema.md
│
├── artifacts/
│   ├── README.md
│   ├── preprocessing/
│   ├── models/
│   ├── predictions/
│   └── evaluation/
│
├── reports/
│   ├── README.md
│   ├── figures/
│   ├── preprocessing_report.md
│   └── model_training_report.md
│
├── docs/
│   ├── BRIEF.md
│   ├── PRD.md
│   ├── REPO_STRUCTURE_STANDARD.md
│   ├── ARCHITECTURE.md
│   ├── API_CONTRACT.md
│   ├── DATA_CONTRACT.md
│   ├── UI_FLOW.svg
│   ├── decisions/
│   └── references/
│
├── scripts/
│   ├── setup_hooks.sh
│   ├── setup_hooks.ps1
│   ├── dev_backend.sh
│   ├── dev_frontend.sh
│   ├── run_preprocessing.sh
│   └── train_model.sh
│
├── infra/
│   ├── docker/
│   ├── compose/
│   ├── deploy/
│   └── nginx/
│
├── tests/
│   ├── integration/
│   └── e2e/
│
└── .github/
    ├── workflows/
    └── CODEOWNERS
```

---

## 4. Trách nhiệm từng thư mục

### `backend/`

Nơi đặt FastAPI app, auth, database, API, service layer và integration với ML/LLM.

Người phụ trách chính: backend engineer.

Nên có:

- `app/api/v1/routers/`: route theo domain, ví dụ `auth.py`, `users.py`, `devices.py`, `logs.py`, `alerts.py`.
- `app/models/`: ORM/database model, không đặt ML model ở đây.
- `app/schemas/`: Pydantic request/response schema.
- `app/services/`: nghiệp vụ như risk scoring, alert creation, LLM explanation.
- `migrations/`: migration database nếu dùng Alembic.
- `app/tests/`: unit test và API test cho backend.

Không nên có:

- Notebook.
- CSV raw dataset.
- File model binary lớn.
- React component.

### `frontend/`

Nơi đặt dashboard React/Next.js: login, overview, users, devices, logs, alerts, alert detail, timeline.

Người phụ trách chính: frontend engineer.

Nên chia theo feature:

- `features/auth/`
- `features/dashboard/`
- `features/users/`
- `features/devices/`
- `features/logs/`
- `features/alerts/`

Quy tắc: frontend không tự định nghĩa logic anomaly/risk. Frontend chỉ gọi API và render dữ liệu theo contract trong `docs/API_CONTRACT.md`.

### `agent/`

Nơi đặt endpoint agent thật hoặc mock agent/simulator.

Người phụ trách chính: agent/integration engineer.

Nên có:

- `collectors/`: đọc log hệ thống hoặc sinh event demo.
- `transport/`: gửi event về backend qua REST API.
- `simulators/`: sinh normal/anomaly behavior để demo.
- `tests/`: test format event và retry behavior.

Output của agent phải tuân theo `docs/DATA_CONTRACT.md` hoặc `data/schemas/normalized_event_schema.md`.

### `ml/`

Nơi đặt source code data preprocessing, feature engineering, training, scoring và explainability.

Người phụ trách chính: data/ML engineer.

Nên có:

- `data/loaders.py`: đọc CERT r4.2 hoặc sample data.
- `data/validators.py`: kiểm tra cột bắt buộc, date format, user/device missing.
- `features/`: logic feature engineering theo user/device/time window.
- `pipelines/preprocess.py`: tạo feature matrix.
- `pipelines/train.py`: train model và ghi artifact.
- `pipelines/score.py`: inference anomaly score/risk input.
- `detectors/`: Isolation Forest, rule-based, hoặc detector khác.
- `explainers/`: feature drivers dùng cho LLM/rule-based explanation.

Không nên đặt output `.joblib`, `.csv`, `.png` trực tiếp trong `ml/`; output phải vào `artifacts/` hoặc `reports/`.

### `data/`

Nơi quản lý dữ liệu theo vòng đời.

- `data/raw/`: dữ liệu gốc CERT r4.2, không sửa, không commit.
- `data/sample/`: sample nhỏ để test/demo nhanh, có thể commit nếu không chứa dữ liệu nhạy cảm và kích thước nhỏ.
- `data/interim/`: dữ liệu trung gian, generated, thường ignore.
- `data/processed/`: dữ liệu cuối cho modeling, generated, thường ignore.
- `data/schemas/`: schema và data dictionary, nên commit.

### `artifacts/`

Nơi lưu output máy sinh ra:

- feature matrix.
- model binary.
- score/prediction.
- metadata.
- evaluation output.

Quy tắc: artifact lớn nên ignore. Chỉ commit artifact nhỏ cần cho demo hoặc kiểm thử, ví dụ `model_metadata.json`, `feature_columns.json`, sample prediction.

### `reports/`

Nơi lưu báo cáo phân tích, training report, hình ảnh đã chọn để trình bày.

Khác với `artifacts/`: `reports/` dành cho người đọc; `artifacts/` dành cho pipeline.

### `docs/`

Nơi đặt tài liệu sản phẩm và kỹ thuật:

- `BRIEF.md`: bối cảnh và mục tiêu.
- `PRD.md`: yêu cầu sản phẩm.
- `ARCHITECTURE.md`: kiến trúc hệ thống.
- `API_CONTRACT.md`: contract API backend/frontend.
- `DATA_CONTRACT.md`: schema event, feature, alert.
- `decisions/`: ADR, quyết định kỹ thuật.
- `references/`: paper, hình tham khảo, dataset manual.

### `scripts/`

Chỉ chứa lệnh tiện ích mỏng để gọi module chính:

- setup hooks.
- chạy dev server.
- chạy preprocessing.
- train model.
- seed database.

Không nên nhét business logic dài vào `scripts/`. Logic dài phải nằm trong `backend/`, `ml/` hoặc `agent/`.

### `infra/`

Nơi đặt Docker, compose, deployment, reverse proxy, cloud config.

Người phụ trách chính: DevOps/backend.

---

## 5. Ánh xạ từ repo hiện tại sang cấu trúc đích

| Hiện tại | Chuẩn đích | Ghi chú |
|---|---|---|
| `preprocessing/ueba_preprocess.py` | `ml/ueba_ml/pipelines/preprocess.py` | Giữ `preprocessing/` tạm thời được, nhưng code mới nên vào `ml/`. |
| `preprocessing/README.md` | `ml/README.md` hoặc `ml/notebooks/README.md` | Gộp hướng dẫn pipeline ML vào một nơi. |
| `models/train_iforest.py` | `ml/ueba_ml/pipelines/train.py` | `models/` ở root nên dành cho artifact hoặc bỏ hẳn để tránh nhầm. |
| `models/iforest_model.joblib` | `artifacts/models/iforest_model.joblib` | Model binary là artifact, không phải source code. |
| `models/iforest_*.csv/json` | `artifacts/models/` hoặc `artifacts/evaluation/` | Tùy loại output. |
| `models/figures/` | `reports/figures/` hoặc `artifacts/evaluation/figures/` | Hình cho người đọc để `reports`; hình pipeline để `artifacts`. |
| `artifacts/preprocessing/` | `artifacts/preprocessing/` | Đang đúng hướng. |
| `dataset/` | `data/raw/cert-r4.2/` | Nên ignore. |
| `data-template/` | `data/sample/cert-r4.2-small/` | Nên đổi tên để rõ là sample data. |
| `reports/` | `reports/` | Đang đúng hướng. |
| `docs/2506.23446v2.pdf` | `docs/references/2506.23446v2.pdf` | Paper/reference nên gom vào `docs/references/`. |
| `docs/PRD.md`, `docs/BRIEF.md` | `docs/PRD.md`, `docs/BRIEF.md` | Đang đúng hướng. |

---

## 6. Mapping để chia việc trong team

| Role | Thư mục chính | Deliverable rõ ràng |
|---|---|---|
| Product/PM | `docs/`, `JOURNAL.md`, `WORKLOG.md` | PRD, user story, acceptance criteria, task assignment, quyết định scope. |
| Backend engineer | `backend/`, `infra/`, `.env.example` | API, auth, DB schema, service layer, seed data, OpenAPI docs. |
| Frontend engineer | `frontend/`, `docs/UI_FLOW.svg` | Dashboard, login, user/device/log/alert views, API client integration. |
| Data/ML engineer | `ml/`, `data/schemas/`, `artifacts/`, `reports/` | Preprocessing, feature engineering, training, scoring, model report. |
| Agent/integration engineer | `agent/`, `docs/DATA_CONTRACT.md` | Mock/real agent, event format, REST transport, normal/anomaly simulator. |
| QA/test owner | `tests/`, `backend/app/tests/`, `frontend/e2e/`, `ml/ueba_ml/tests/` | Test plan, integration tests, e2e happy path, regression checks. |
| DevOps | `infra/`, `.github/workflows/`, `scripts/` | Docker Compose, deploy config, CI, environment setup. |

Khi tạo issue/task, nên gắn rõ thư mục owner. Ví dụ:

- `[backend] POST /api/logs/ingest`
- `[ml] Feature matrix for user-day behavior`
- `[frontend] Alert detail timeline`
- `[agent] Simulate USB copy anomaly`
- `[infra] Docker compose for backend/frontend/db`

---

## 7. Quy tắc commit và ignore

Nên commit:

- Source code trong `backend/`, `frontend/`, `agent/`, `ml/`.
- Schema/data contract trong `data/schemas/` và `docs/`.
- Sample data nhỏ trong `data/sample/`.
- Report markdown và hình đã chọn trong `reports/`.
- Config mẫu: `.env.example`, compose file, CI workflow.

Không nên commit:

- `.env` và secret.
- Raw CERT dataset đầy đủ.
- File CSV/generated lớn.
- Model binary lớn nếu chưa cần cho demo.
- Cache: `__pycache__/`, `.pytest_cache/`, build output, frontend dist.
- Notebook output quá lớn.

Gợi ý `.gitignore` khi chuyển sang cấu trúc mới:

```gitignore
.env
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
node_modules/
dist/
build/

data/raw/
data/interim/
data/processed/
artifacts/**/*.csv
artifacts/**/*.joblib
artifacts/**/*.pkl
artifacts/**/*.parquet

!artifacts/**/README.md
!artifacts/**/metadata.json
!artifacts/**/feature_columns.json
```

---

## 8. Checklist khi thêm module mới

Trước khi merge một module mới, cần có:

- `README.md` trong thư mục module nếu module có cách chạy riêng.
- Cấu hình qua `.env` hoặc config file, không hard-code secret.
- Test tối thiểu cho logic chính.
- Input/output contract được ghi trong `docs/` hoặc `data/schemas/`.
- Không tạo file generated lớn ngoài `artifacts/`, `reports/`, `data/interim/`, `data/processed/`.
- Không đặt file app/script mới ở root nếu đã có thư mục owner phù hợp.

---

## 9. Kế hoạch refactor đề xuất

### Phase 1: Chuẩn hóa không phá vỡ code hiện tại

1. Tạo `data/README.md`, `artifacts/README.md`, `reports/README.md`.
2. Thêm `docs/API_CONTRACT.md`, `docs/DATA_CONTRACT.md`, `docs/ARCHITECTURE.md`.
3. Giữ `preprocessing/` và `models/` tạm thời, nhưng ghi rõ deprecated trong README.
4. Bổ sung `.gitignore` cho raw data và artifact lớn.

### Phase 2: Tách module theo ownership

1. Di chuyển preprocessing/training source sang `ml/ueba_ml/pipelines/`.
2. Di chuyển ML artifact sang `artifacts/models/`.
3. Tạo skeleton `backend/`, `frontend/`, `agent/`.
4. Tạo test smoke cho pipeline: sample data -> feature matrix -> train -> score.

### Phase 3: Chuẩn hóa product repo

1. Backend expose API contract cho logs, users, devices, alerts, explanations.
2. Frontend consume API contract thay vì đọc file local.
3. Agent gửi event qua backend thay vì chỉ sinh file.
4. CI chạy backend tests, ML smoke tests và frontend build.
5. Docker Compose chạy được full loop demo.

---

## 10. Chuẩn tối thiểu cho MVP

Nếu không đủ thời gian làm đầy đủ cấu trúc trên, tối thiểu repo nên có các thư mục sau:

```text
backend/
frontend/
agent/
ml/
data/
artifacts/
reports/
docs/
scripts/
tests/
infra/
```

Trong đó bắt buộc ưu tiên:

1. `backend/`: API, auth, DB, alert/risk service.
2. `frontend/`: dashboard và alert detail.
3. `agent/`: mock agent gửi log.
4. `ml/`: preprocessing, training, scoring.
5. `data/`: raw/sample/schema tách rõ.
6. `artifacts/`: output pipeline.
7. `docs/`: PRD, architecture, API/data contract.

Đây là ranh giới đủ rõ để chia việc theo người mà không phải sửa chung một file hoặc để mọi thứ ở root.
