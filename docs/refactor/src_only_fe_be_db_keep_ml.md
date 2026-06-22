# TASK: Rebuild project structure, all source code must stay inside `src/`, keep ML model parts

Bạn đang làm việc trong repo `C2-APP-047`.

## Mục tiêu

Refactor lại toàn bộ project theo hướng sạch, dễ demo, dễ chia việc FE/BE/DB/ML.

Yêu cầu quan trọng nhất:

> TẤT CẢ mã nguồn phải nằm trong thư mục `src/`.

Không được tạo `frontend/`, `backend/`, `database/`, `ml/` ở root dưới dạng source code.

Root chỉ được chứa các file/thư mục cấu hình, tài liệu, dữ liệu, artifact, script vận hành.

---

## Nên tạo branch trước khi làm

Trước khi refactor, hãy tạo branch mới tên:

```bash
git checkout -b refactor/src-only-fe-be-db-keep-ml
```

Chỉ làm việc trên branch này.

---

## Cấu trúc mong muốn sau refactor

```text
C2-APP-047/
├── src/
│   ├── frontend/
│   ├── backend/
│   ├── database/
│   └── ml/
├── docs/
├── scripts/
├── artifacts/
├── data/
├── eval/
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

Trong đó:

```text
src/
├── frontend/      # React/Vite/TypeScript source
├── backend/       # FastAPI source
├── database/      # DB schema, migrations, seed
└── ml/            # ML models, services, pipelines, inference
```

---

## Quy tắc cực kỳ quan trọng

KHÔNG được xóa hoặc làm mất phần ML/model hiện tại.

Cần giữ lại và migrate cẩn thận các phần sau nếu tồn tại:

```text
src/models/
src/weights/
src/services/ueba_ml/
artifacts/
data/
eval/
```

Mapping mong muốn:

```text
src/models              -> src/ml/models
src/weights             -> src/ml/weights
src/services/ueba_ml    -> src/ml/services/ueba_ml
src/scripts             -> src/ml/scripts hoặc scripts/
src/api                 -> src/backend/app/api nếu là backend API cũ
src/frontend            -> src/frontend nếu còn dùng được
data                    -> data hoặc src/ml/data nếu code cần import trực tiếp
eval                    -> eval hoặc src/ml/eval
artifacts               -> artifacts
```

Nếu không chắc một file có thuộc ML hay không, KHÔNG xóa. Hãy chuyển vào:

```text
src/ml/legacy_review/
```

và ghi lý do vào:

```text
docs/refactor_inventory.md
```

---

## Bước 1: Inventory trước khi sửa

Trước khi xóa hoặc di chuyển bất kỳ file nào, hãy tạo file:

```text
docs/refactor_inventory.md
```

Nội dung gồm:

```md
# Refactor Inventory

## Current frontend-related files
- ...

## Current backend-related files
- ...

## Current database-related files
- ...

## Current ML/model files to preserve
- ...

## Files safe to delete
- ...

## Files needing manual review
- ...
```

Không được xóa gì trước khi tạo inventory.

---

## Bước 2: Tạo lại cấu trúc trong `src`

Tạo cấu trúc:

```text
src/
├── frontend/
├── backend/
├── database/
└── ml/
```

Chi tiết:

```text
src/ml/
├── models/
├── weights/
├── services/
├── pipelines/
├── scripts/
├── data/
├── eval/
└── legacy_review/
```

Không tạo source code ở root.

Các thư mục ở root như `docs/`, `scripts/`, `artifacts/`, `data/`, `eval/` chỉ dùng cho tài liệu, dữ liệu, output, hoặc script vận hành.

---

## Bước 3: Rebuild backend mới trong `src/backend`

Backend dùng FastAPI.

Tạo cấu trúc:

```text
src/backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_health.py
│   │   ├── routes_logs.py
│   │   ├── routes_alerts.py
│   │   └── routes_ml.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── security.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py
│   │   └── models.py
│   └── schemas/
│       ├── __init__.py
│       ├── log.py
│       └── alert.py
├── tests/
├── requirements.txt
└── Dockerfile
```

Backend cần có tối thiểu:

```text
GET /health
POST /logs
GET /alerts
POST /ml/predict
```

Endpoint `/ml/predict` cần gọi wrapper từ `src/ml/`, ví dụ:

```python
from src.ml.services.ueba_ml import ...
```

Nếu chưa import được model thật, hãy tạo mock inference tạm thời nhưng vẫn giữ interface rõ ràng.

---

## Bước 4: Rebuild frontend mới trong `src/frontend`

Frontend dùng React + Vite + TypeScript.

Tạo cấu trúc:

```text
src/frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   ├── components/
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Logs.tsx
│   │   ├── Alerts.tsx
│   │   └── ModelTest.tsx
│   └── styles/
├── package.json
├── index.html
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

UI tối thiểu cần có:

- Dashboard page
- Logs page
- Alerts page
- Model test page
- Sidebar layout đơn giản
- API client dùng biến môi trường:

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## Bước 5: Database nằm trong `src/database`

Tạo:

```text
src/database/
├── init.sql
├── migrations/
├── seed.sql
└── README.md
```

Database dùng PostgreSQL.

Schema tối thiểu cho UEBA gồm:

```sql
users
logs
alerts
model_predictions
```

Các bảng cần có field cơ bản:

- user id
- username
- role
- event type
- timestamp
- source ip
- device
- risk score
- anomaly score
- alert reason
- status

---

## Bước 6: ML nằm trong `src/ml`

Di chuyển phần ML hiện có vào:

```text
src/ml/
```

Cấu trúc mong muốn:

```text
src/ml/
├── models/
├── weights/
├── services/
│   └── ueba_ml/
├── pipelines/
├── scripts/
├── data/
├── eval/
├── legacy_review/
└── README.md
```

Yêu cầu:

- Không sửa logic ML nếu không cần thiết.
- Không train lại model.
- Không xóa model weights.
- Không xóa artifacts.
- Không đổi format model.
- Chỉ sửa import path nếu cần để backend gọi được ML inference.

---

## Bước 7: Docker compose ở root

Viết lại `docker-compose.yml` ở root để chạy:

- frontend từ `src/frontend`
- backend từ `src/backend`
- postgres dùng schema từ `src/database/init.sql`

Không cần chạy training ML trong Docker Compose.

Backend Dockerfile nằm tại:

```text
src/backend/Dockerfile
```

Frontend Dockerfile nằm tại:

```text
src/frontend/Dockerfile
```

---

## Bước 8: Env/config

Tạo hoặc cập nhật `.env.example` ở root:

```env
POSTGRES_USER=ueba_user
POSTGRES_PASSWORD=ueba_password
POSTGRES_DB=ueba_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

BACKEND_PORT=8000
FRONTEND_PORT=5173

VITE_API_BASE_URL=http://localhost:8000

ML_MODEL_PATH=src/ml/weights
ML_ARTIFACT_PATH=artifacts
```

Không commit file `.env` thật nếu có secret.

---

## Bước 9: README

Viết lại `README.md` ở root gồm:

```md
# C2-APP-047 UEBA

## Overview

## Folder Structure

## Backend

## Frontend

## Database

## ML Model

## Run Locally

## Run with Docker Compose

## API Endpoints

## Notes
```

README phải nói rõ:

> All application source code is inside `src/`.

---

## Bước 10: Dọn dẹp file cũ

Sau khi migrate xong:

Được xóa:

```text
__pycache__/
.pytest_cache/
.ruff_cache/
.mypy_cache/
node_modules/
dist/
build/
```

Không được xóa:

```text
.git/
.github/
.githooks/
.env.example
artifacts/
data/
eval/
src/ml/
src/ml/weights/
src/ml/models/
```

Nếu gặp file không chắc, chuyển vào:

```text
src/ml/legacy_review/
```

Không tự ý xóa.

---

## Bước 11: Cập nhật import path

Sau khi di chuyển file, kiểm tra và sửa các import bị lỗi.

Ưu tiên import theo hướng rõ ràng:

```python
from src.ml...
from src.backend...
```

Nếu cần, thêm `__init__.py` vào các package Python.

---

## Bước 12: Kiểm tra sau refactor

Chạy các lệnh phù hợp:

```bash
python -m compileall src/backend src/ml
```

Nếu backend có requirements:

```bash
pip install -r src/backend/requirements.txt
pytest src/backend/tests
```

Nếu frontend có package.json:

```bash
cd src/frontend
npm install
npm run build
```

Kiểm tra docker compose:

```bash
docker compose config
```

Ghi kết quả vào:

```text
docs/refactor_result.md
```

---

## Output cuối cùng cần báo lại

Sau khi làm xong, báo cáo theo format:

```md
# Refactor Summary

## Changed
- ...

## Final Structure
- ...

## Preserved ML files
- ...

## Moved files
- ...

## Deleted files
- ...

## Files needing manual review
- ...

## Import path updates
- ...

## Test results
- ...

## Next steps
- ...
```

---

## Ràng buộc

- Tất cả source code phải nằm trong `src/`.
- Không tạo `frontend/`, `backend/`, `database/`, `ml/` ở root.
- Không sửa logic ML nếu không cần.
- Không train lại model.
- Không xóa weights/model artifacts.
- Không xóa dữ liệu nếu chưa chắc.
- Không push lên GitHub.
- Không commit nếu chưa được yêu cầu.
- Ưu tiên cấu trúc sạch, dễ demo, dễ chia việc.
