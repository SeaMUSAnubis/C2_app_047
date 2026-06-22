# Kết quả refactor

## Thay đổi chính
- Đã tạo branch `refactor/src-only-fe-be-db-keep-ml` trước khi refactor.
- Đã gom source ứng dụng active vào `src/frontend`, `src/backend`, `src/database`, `src/ml`.
- Đã tạo `docs/refactor_inventory.md` trước khi di chuyển hoặc xóa file.
- Đã dựng lại package FastAPI backend trong `src/backend/app/` và vẫn giữ route cũ `/api/*` để frontend hiện tại không bị gãy.
- Đã thêm endpoint backend tối thiểu: `GET /health`, `POST /logs`, `GET /alerts`, `POST /ml/predict`.
- Đã thêm schema/seed PostgreSQL trong `src/database/`.
- Đã chuyển Docker sang mô hình một container: PostgreSQL, backend FastAPI và frontend static chạy trong cùng container.
- Đã cập nhật `.env.example`, `Dockerfile`, `docker-compose.yml`, `README.md` và `src/frontend/Dockerfile` theo layout mới.
- Đã giữ nguyên `artifacts/`, `data/`, `eval/` ở root.
- Không commit, không push.
- Không train lại model.

## Cấu trúc cuối
- `src/frontend/`: frontend React/Vite/TypeScript.
- `src/backend/`: backend FastAPI, Dockerfile backend riêng, requirements backend và test backend.
- `src/database/`: schema PostgreSQL, seed, thư mục migration và utility nạp dữ liệu đã giữ lại.
- `src/ml/`: ML service, weight, script ML và utility legacy cần review.
- `src/__init__.py`: giữ lại để import dạng `src.backend...` và `src.ml...` hoạt động.

## File ML đã bảo toàn
- `src/ml/weights/ocsvm_cert_r42_chunked.joblib`
- `src/ml/services/ueba_ml/inference.py`
- `src/ml/services/ueba_ml/pipelines/preprocess.py`
- `src/ml/services/ueba_ml/pipelines/train.py`
- `src/ml/services/ueba_ml/data/`
- `src/ml/services/ueba_ml/detectors/`
- `src/ml/services/ueba_ml/evaluation/`
- `src/ml/services/ueba_ml/explainers/`
- `src/ml/services/ueba_ml/features/`
- `src/ml/scripts/run_preprocessing.sh`
- `src/ml/scripts/train_model.sh`
- Root `artifacts/`, `data/`, `eval/` được giữ nguyên.

## File đã di chuyển
- `src/main.py` -> `src/backend/app/main.py`
- `src/config.py` -> `src/backend/app/config.py`
- `src/api/routes.py` -> `src/backend/app/api/routes.py`
- `src/models/schemas.py` -> `src/backend/app/schemas/schemas.py`
- `src/services/auth.py` -> `src/backend/app/core/security.py`
- `src/services/database.py` -> `src/backend/app/db/session.py`
- `src/services/demo_pipeline.py` -> `src/backend/app/services/demo_pipeline.py`
- `src/services/llm.py` -> `src/backend/app/services/llm.py`
- `src/agents/` -> `src/backend/app/agents/`
- `src/tests/` -> `src/backend/tests/`
- `src/services/ueba_ml/` -> `src/ml/services/ueba_ml/`
- `src/weights/ocsvm_cert_r42_chunked.joblib` -> `src/ml/weights/ocsvm_cert_r42_chunked.joblib`
- `src/scripts/run_preprocessing.sh` -> `src/ml/scripts/run_preprocessing.sh`
- `src/scripts/train_model.sh` -> `src/ml/scripts/train_model.sh`
- `src/scripts/seed_mock_data.py` -> `src/database/seed_mock_data.py`
- `src/scripts/load_cert_data.py` -> `src/database/load_cert_data.py`
- `src/README.md` -> `docs/legacy_src_readme_before_refactor.md`

## File đã xóa
- Chỉ xóa cache/build/dependency sinh ra tự động:
  - `.pytest_cache/`
  - `.ruff_cache/`
  - toàn bộ `__pycache__/`
  - `src/frontend/node_modules/`
  - `src/frontend/dist/`
- Đã xóa thư mục layout cũ sau khi migrate xong:
  - `src/api/`
  - `src/models/`
  - `src/scripts/`
  - `src/services/`
  - `src/weights/`
- Không xóa weight ML, artifact model, dữ liệu root hoặc output eval.

## File cần review thủ công
Đã chuyển vào `src/ml/legacy_review/` thay vì xóa:

- `_pyrun.cmd`
- `_pyrun.sh`
- `auto_commit_push.sh`
- `log_antigravity.py`
- `log_hook.py`
- `log_manual.py`
- `setup_hooks.ps1`
- `setup_hooks.sh`
- `submit_log.py`

Lý do: đây là script workflow/logging/VCS của project, không rõ thuộc FE/BE/DB/ML source active. Theo yêu cầu, các file không chắc chắn được giữ lại để review.

## Cập nhật import path
- `src.config` -> `src.backend.app.config`
- `src.api.routes` -> `src.backend.app.api.routes`
- `src.models.schemas` -> `src.backend.app.schemas.schemas`
- `src.services.auth` -> `src.backend.app.core.security`
- `src.services.database` -> `src.backend.app.db.session`
- `src.services.demo_pipeline` -> `src.backend.app.services.demo_pipeline`
- `src.services.llm` -> `src.backend.app.services.llm`
- `src.services.ueba_ml` -> `src.ml.services.ueba_ml`
- `src.agents` -> `src.backend.app.agents`
- `src.scripts.seed_mock_data` -> `src.database.seed_mock_data`
- Đã cập nhật default path OCSVM thành `src/ml/weights/ocsvm_cert_r42_chunked.joblib`.

## Cập nhật Docker một container
- Root `Dockerfile` hiện là multi-stage build:
  - Stage Node build frontend từ `src/frontend`.
  - Stage Python cài PostgreSQL, dependencies backend, copy source và frontend `dist` vào image.
- `docker-compose.yml` chỉ còn một service `app`.
- Container `app` chạy PostgreSQL nội bộ, khởi tạo schema từ `src/database/init.sql`, seed từ `src/database/seed.sql`, sau đó chạy `uvicorn src.backend.app.main:app`.
- FastAPI phục vụ frontend static nếu `FRONTEND_DIST_DIR` tồn tại.
- Truy cập frontend qua `http://localhost:5173`.
- API và health cũng đi qua cùng port: `http://localhost:5173/api/*`, `http://localhost:5173/health`.
- PostgreSQL không publish ra host mặc định để tránh đụng port `5432` với PostgreSQL hoặc container cũ đang chạy.

## Kết quả test
- `python -m compileall src/backend src/ml`: pass, 58 package đã compile.
- `cd src/frontend && npm install`: pass. Môi trường có in cảnh báo `Failed to create stream fd: Operation not permitted`, nhưng npm hoàn tất.
- `cd src/frontend && npm run build`: pass. Vite build production thành công.
- `pytest src/backend/tests -q`: pass với `42 passed, 127 skipped, 12 warnings`.
  - Các test skip là test integration PostgreSQL cần `TEST_DATABASE_URL`.
  - Warning gồm deprecation của `pytest-asyncio` và cảnh báo version khi unpickle model scikit-learn.
- `bash -n scripts/docker/all_in_one_entrypoint.sh`: pass.
- `docker compose config`: pass. Không copy output đầy đủ vào docs vì lệnh này expand giá trị `.env` thật, có thể chứa secret.

## Việc tiếp theo
- Review `src/ml/legacy_review/` để quyết định file nào giữ, xóa hoặc chuyển sang root `scripts/` dạng script vận hành.
- Nếu cần full DB test, chạy lại test với `TEST_DATABASE_URL`.
- Nếu muốn kiểm tra image thật, chạy `docker compose up --build` sau khi xác nhận `.env` local không chứa secret ngoài ý muốn.
