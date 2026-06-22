# Kiểm kê trước refactor

File này được tạo trước khi thực hiện bất kỳ thao tác di chuyển hoặc xóa file nào.

Branch làm việc: `refactor/src-only-fe-be-db-keep-ml`

## File liên quan frontend hiện có
- `src/frontend/` là ứng dụng React/Vite/TypeScript hiện tại.
- Source frontend nằm dưới `src/frontend/src/`, gồm page, component, layout, style, store, API client và type.
- File cấu hình/build frontend gồm `src/frontend/package.json`, `src/frontend/package-lock.json`, `src/frontend/vite.config.ts`, `src/frontend/tsconfig*.json`, `src/frontend/eslint.config.js`, `src/frontend/index.html`, `src/frontend/Dockerfile`, `src/frontend/Dockerfile.dev`, `src/frontend/nginx.conf`.
- Output/cache sinh ra trước refactor gồm `src/frontend/dist/` và `src/frontend/node_modules/`.

## File liên quan backend hiện có
- Source backend cũ nằm rải rác trong `src/main.py`, `src/config.py`, `src/api/`, `src/models/`, `src/services/`, `src/agents/`, `src/tests/`.
- Entrypoint FastAPI cũ: `src/main.py`.
- Route cũ: `src/api/routes.py`.
- Config cũ: `src/config.py`.
- Schema cũ: `src/models/schemas.py`.
- Service backend cũ: `src/services/auth.py`, `src/services/database.py`, `src/services/demo_pipeline.py`, `src/services/llm.py`.
- Code agent/giải thích cảnh báo cũ: `src/agents/`.
- Test cũ: `src/tests/`.

## File liên quan database hiện có
- SQLite demo/runtime tồn tại tại `data/ueba_demo.sqlite3`; giữ lại như dữ liệu, không xem là source.
- Logic database cũ nằm tại `src/services/database.py` và cần chuyển vào `src/backend/app/db/`.
- Script seed/import cũ nằm tại `src/scripts/seed_mock_data.py` và `src/scripts/load_cert_data.py`.
- Trước refactor chưa có thư mục riêng `src/database/`.

## File ML/model cần giữ lại
- `src/weights/ocsvm_cert_r42_chunked.joblib` phải giữ lại và chuyển vào `src/ml/weights/`.
- `src/services/ueba_ml/` phải giữ lại và chuyển vào `src/ml/services/ueba_ml/`.
- `src/services/ueba_ml/inference.py` là wrapper inference hiện tại; chỉ sửa import path nếu cần.
- `artifacts/` chứa artifact model/preprocessing/evaluation, phải giữ nguyên ở root.
- `data/` chứa dữ liệu demo/raw/sample/schema, phải giữ nguyên ở root trừ khi code bắt buộc import trực tiếp.
- `eval/` chứa report/hình đánh giá, phải giữ nguyên ở root.
- `src/scripts/run_preprocessing.sh` và `src/scripts/train_model.sh` là script liên quan ML; chuyển vào `src/ml/scripts/` và không chạy training.

## File an toàn để xóa
- Cache Python: `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` và các `*/__pycache__/` lồng bên trong.
- Output/dependency frontend sinh ra: `src/frontend/node_modules/`, `src/frontend/dist/`.
- Chỉ xóa file build/cache sinh ra tự động. Không xóa source, dữ liệu, artifact, weight model hoặc output đánh giá.

## File cần review thủ công
- `src/agents/`: code backend/AI orchestration dùng cho test giải thích cảnh báo; nếu giữ active thì chuyển vào `src/backend/app/agents/`.
- `src/services/demo_pipeline.py`: trộn workflow demo backend và risk scoring kiểu ML; tạm chuyển vào backend service, có thể tách sau.
- `src/services/llm.py`: phục vụ giải thích cảnh báo; tạm chuyển vào backend service, có thể tách sau.
- `src/scripts/auto_commit_push.sh`: script tự động VCS, không phải source app; chuyển vào `src/ml/legacy_review/` thay vì xóa.
- `src/scripts/log_antigravity.py`, `src/scripts/log_hook.py`, `src/scripts/log_manual.py`, `src/scripts/setup_hooks.*`, `src/scripts/submit_log.py`: utility workflow/logging, không rõ thuộc FE/BE/DB/ML; chuyển vào `src/ml/legacy_review/` thay vì xóa.
- `src/scripts/_pyrun.cmd` và `src/scripts/_pyrun.sh`: helper chạy lệnh; chuyển vào `src/ml/legacy_review/` nếu không chắc backend mới cần dùng.
- `src/README.md` và các thư mục tài liệu/presentation như `flow/`, `presentation/`: giữ lại hoặc chuyển sang docs nếu cần, không xóa tùy tiện.
