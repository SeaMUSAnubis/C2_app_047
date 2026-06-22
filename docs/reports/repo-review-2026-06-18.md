# Repo Review — C2-App-047 (UEBA)

> Ngày review: 2026-06-18 · Branch: `BuiHoangLinh_2A202600804`
> Phạm vi: backend FastAPI, ML pipeline, frontend React, tests, infra/CI, docs.
> Lưu ý: đây là danh sách phát hiện (chỉ liệt kê, **chưa sửa code**). Tick `[x]` khi xử lý xong.

---

## 🔴 Nhóm 1 — Repo đang di chuyển dở dang (vỡ runtime + CI ngay lúc này)

Branch có đợt tái cấu trúc chưa commit & chưa đồng bộ: `tests/` → `src/tests/`, `weights/` → `src/weights/`, đổi LLM OpenRouter → Mistral.

- [ ] **1. Test không chạy (CI `pytest` đỏ).** 6 file `src/tests/test_api/*.py` vẫn `import from tests.conftest` → `ModuleNotFoundError: No module named 'tests'`. Đã chạy thử: 6 lỗi collection, chỉ 24/~90 test thu thập được.
  - `src/tests/test_api/test_api_endpoints.py:7`, `test_auth.py:7`, `test_authorization.py:7`, `test_database.py:5`, `test_routes.py:3`, `test_security.py:7`
- [ ] **2. Model OCSVM không load với config mặc định.** `src/config.py:24` default `ocsvm_model_path="weights/..."` nhưng file đã chuyển sang `src/weights/...`. `inference.py:135-139` resolve theo `Path.cwd()` → chạy từ repo root tìm `./weights/...` (rỗng) → `503 ModelArtifactError`.
- [ ] **3. Docker đặt sai tên biến môi trường.** `docker-compose.yml` set `MODEL_PATH` & `DATA_DIR`, nhưng `config.py` đọc alias `OCSVM_MODEL_PATH` (pydantic `extra="ignore"` → biến bị bỏ qua) → trong Docker `/api/models/.../infer` & `/metrics` vẫn 503.
- [ ] **4. `Makefile:7` `ruff check src tests`** → `tests` không còn → lint fail (CI step `Lint` đỏ; `.github/workflows/ci.yml` chạy đúng lệnh này).
- [ ] **5. `Makefile:16,19`** `bash scripts/...sh` nhưng script ở `src/scripts/` → target `preprocess`/`train` hỏng.
- [ ] **6. README stale:** `tests/` (L29), `scripts/` (L31), `weights/` (L32), `OCSVM_MODEL_PATH=weights/...` (L153), `python scripts/load_cert_data.py` (L185), `pytest tests/ -v` (L201, L204).

---

## 🔴 Nhóm 2 — Bảo mật / secrets

- [ ] **7. Secret thật bị commit:** `.env.example:18` chứa `AI_LOG_API_KEY=f3p1dEOhD_...` (key thực, nên revoke + thay bằng placeholder).
- [ ] **8. `/demo/analyze` không có auth** (`routes.py:493-496`) trong khi mọi endpoint khác đều yêu cầu token. Endpoint còn **ghi DB** (`create_alert`), gọi **LLM trả phí**, **đọc CSV từ disk** — tất cả unauthenticated.
- [ ] **9. JWT secret mặc định công khai:** `config.py:15` default `"change-me-in-production"`. JWT tự viết tay (`auth.py`) — không set env thì token ký bằng secret công khai.
- [ ] **10. DB credential hardcode** trong `docker-compose.yml` (`POSTGRES_USER/PASSWORD = ueba/ueba`).
- [ ] **11. Dockerfile chạy root, base image không pin digest** (`Dockerfile:1`, `src/frontend/Dockerfile`). `Dockerfile.dev` `node:24` còn prod `node:20` (lệch dev/prod).
- [ ] **12. Frontend auth/lỗi:** token lưu `localStorage` (XSS) `authStore.ts:7`; `apiClient.ts:25-35` trả `mock-token` khi `API_BASE_URL` rỗng (login giả); `apiClient.ts:86-92` `getAlerts()` nuốt lỗi trả `[]`.

---

## 🟠 Nhóm 3 — Mâu thuẫn model / ML (provenance không khớp)

- [ ] **13. Script train KHÔNG tạo ra model đang deploy.** `train.py:382,436-442` train **IsolationForest** → lưu `iforest_model.joblib` (key `pipeline`/`feature_columns`). Production serve **OCSVM** `ocsvm_cert_r42_chunked.joblib` (key thực: `model`, `feature_cols`, `nu`, `kernel`, `gamma`, `max_benign_train`). `eval/results/` toàn *iforest*.
- [ ] **14. 3 quy ước key artifact khác nhau:** `train.py` (`pipeline`/`feature_columns`) ≠ `inference.py:116-117` (`model`/`feature_cols`) ≠ `demo_pipeline.py:31-32` (`pipeline`-or-`model`/`feature_columns`). File OCSVM thật chỉ khớp `inference.py`.
- [ ] **15. `demo_pipeline.extract_features` bịa feature hardcode** (`demo_pipeline.py:58-110`): `first_logon_hour=8`, `last_logon_hour=20`, `n_logon_afterhours=len(logons)`, Big Five `O/C/E/A/N=3.0`... → vector feature lệch so với lúc train → kết quả demo gần như vô nghĩa.
- [ ] **16. Hai cách tính risk_score/severity không nhất quán:** `inference._risk_score()` (thang liên tục) vs `demo_pipeline.py:151` (cứng `85`/`20`) vs `routes.py:531` (`high` nếu `>70`); context demo còn gán `severity="critical"` (`demo_pipeline.py:187`).
- [ ] **17. `demo_pipeline.py:239` load model ngay lúc import** (`demo_pipeline = DemoPipeline()` module level) — side-effect nặng, chỉ in warning nếu thiếu model.
- [ ] **18. *(cần xem lại)* z-score leakage:** `preprocess.py` (~L424-428) tính z-score per-user bằng groupby trên toàn dataset (gồm ngày test) → có thể rò rỉ train/test; xác nhận theo thiết kế eval.

---

## 🟠 Nhóm 4 — Đường dẫn Windows hardcode (không chạy ngoài máy gốc)

- [ ] **19. `r"d:\2 Code\TEAM_O47\..."`** ở 4 chỗ làm default:
  - `demo_pipeline.py:15` (MODEL_PATH), `demo_pipeline.py:208` (DATA_DIR)
  - `seed_mock_data.py:23` (DATA_DIR), `seed_mock_data.py:155` (MODEL_PATH)

---

## 🟡 Nhóm 5 — Chất lượng code / dead code

- [ ] **20. `print()` thay logging — 66 chỗ trong `src/`** (llm.py, demo_pipeline.py, routes.py, scripts, train/preprocess); `inference.py` & `database.py` lại dùng `logging` → không nhất quán.
- [ ] **21. `routes.py:493-556`** lệch style: `bare except` + `print` khi create_alert fail (L536-537), import trong thân hàm (L497,502,515,548), trailing whitespace (L513). Endpoint `/datasets/cert-r42/import` thực chất gọi `seed_mock_data` (seed dữ liệu giả, không phải import CERT).
- [ ] **22. `src/agents/*` là scaffold chết:** `run_explanation_graph` chỉ test gọi, app thật bỏ qua (demo_pipeline gọi thẳng `llm.explain_alert`). `alert_tools.summarize_alert_context` không nơi nào dùng.
- [ ] **23. 5 package rỗng** `src/services/ueba_ml/{data,detectors,evaluation,explainers,features}/__init__.py` — không được import ở đâu.
- [ ] **24. `llm.py:110-114`** check label bằng `in` nhưng pick bằng `startswith` → có thể `StopIteration` (crash) nếu label nằm giữa dòng.
- [ ] **25. `demo_pipeline.py:205-207`** `import os` / `import pandas` lặp trong thân hàm (đã import đầu file).
- [ ] **26. Frontend (chất lượng):** nhiều `any` (`apiClient.ts:67,88`, `DataImportPage.tsx:8,18,32`), `as Type[]` không validate (`Alerts/Users/Devices/LogsPage`), `console.error` để lại, ô search `Topbar` không có handler, badge "mock/API" hardcode, trộn Việt/Anh trong code.
- [ ] **27. `requirements.txt`** dùng `>=` toàn bộ (không khóa version), trộn dev-deps (`pytest`, `pytest-asyncio`, `ruff`) vào file runtime.

---

## 🟡 Nhóm 6 — Rác / cấu trúc thư mục

- [ ] **28. `frontend/` ở root** là rác (chỉ có `.vite` owned by `root`) — frontend thật ở `src/frontend/`. `.gitignore` đang ignore `frontend/`.
- [ ] **29. `weights/` ở root** rỗng, owned by `root` — nhầm với `src/weights/`.
- [ ] **30. Binary trong git:** `.joblib` 88KB + 3 PNG (`eval/results/figures/iforest/*`). Nhỏ nên chấp nhận, cân nhắc Git LFS / artifact store.

---

## ✅ Các điểm xác nhận là ổn
- `database.py`: query tham số hóa (`%s`) + whitelist cột/bảng khi build WHERE/UPDATE động → **không có SQL injection**.
- `auth.py`: PBKDF2 120k vòng + `hmac.compare_digest` → hợp lý (chỉ tự viết tay thay vì PyJWT).
- node_modules / `.env` thật **không** bị track (gitignore đúng).
