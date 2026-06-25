# Hướng Dẫn Xử Lý Sự Cố

Sự cố thường gặp + cách xử lý cho hệ thống UEBA Endpoint Monitoring. Phân
chia theo component: **agent** (trên máy nhân viên), **server** (FastAPI +
normalizer), **database**, **ML**, và **frontend**.

> Xem thêm: [`AGENT_DEPLOYMENT.md`](AGENT_DEPLOYMENT.md) (cài đặt),
> [`OPERATIONS.md`](OPERATIONS.md) (vận hành), [`SECURITY.md`](SECURITY.md)
> (security model).

---

## 1. Agent (trên máy nhân viên)

### 1.1 — Agent không xuất hiện trong admin UI sau khi cài

**Triệu chứng**: IT đã cài + chạy `agent enroll` + `systemctl start ueba-agent`,
nhưng Admin → Endpoint agents không hiển thị agent mới.

**Check**:
```bash
# 1. Service đang chạy?
sudo systemctl status ueba-agent
# Tìm "active (running)" và không có lỗi gần đây trong journal.

# 2. State file tồn tại?
sudo -u ueba-agent cat /var/lib/ueba-agent/state.json
# Phải chứa agent_id + api_key. Nếu rỗng/thiếu → enroll lại.

# 3. Agent có reach được server không?
sudo -u ueba-agent /opt/ueba-agent/venv/bin/agent run \
    --state-path /var/lib/ueba-agent/state.json \
    --log-level DEBUG
# Tìm lỗi heartbeat.

# 4. TLS cert trustable?
curl -vI https://ueba.corp.example/api/health
# Nếu lỗi cert, thêm --ca-bundle cho agent.
```

**Nguyên nhân thường gặp**:
- Sai server URL lúc enroll → enroll lại.
- TLS cert không tin cậy → thêm `--ca-bundle` hoặc dùng cert đúng.
- Firewall chặn 443/5173 từ agent host → nhờ IT mở port.
- Agent API key đã bị rotate (admin thu hồi) → enroll lại.

### 1.2 — `agent enroll` fail với `Invalid token` hoặc `Token not found`

**Nguyên nhân**: enrollment token hết hạn (mặc định 60 phút) hoặc đã được
dùng.

**Fix**: admin cấp token mới qua `POST /api/agents/enrollment-tokens` (hoặc
nút trên admin UI), sau đó chạy lại `agent enroll` trong TTL mới.

### 1.3 — `agent enroll` fail với `Foreign key violation: device_id`

**Nguyên nhân**: agent được start với `--device-id` cho một device chưa
tồn tại trong bảng `devices`.

**Fix**:
- Cách A: tạo device trước qua `POST /api/devices`.
- Cách B: bỏ `--device-id` lúc enroll (admin có thể patch sau).
- Cách C: bỏ luôn `--assigned-user-id` (cùng fix).

### 1.4 — `agent enroll` fail với `Network error: Connection refused`

**Nguyên nhân**: server URL sai hoặc server down.

**Check**:
```bash
curl -I https://ueba.corp.example/api/health
# Phải trả 200. Nếu refused → server down.
```

**Fix**:
- Verify URL (phải có `https://`).
- Verify server up: `docker compose ps` (trên server host).
- Check firewall / corporate proxy.

### 1.5 — Service start rồi stop ngay

**Triệu chứng**: `systemctl status ueba-agent` cho thấy `active (exited)`
sau 1-2 giây, không có lỗi.

**Nguyên nhân**: agent trong `crash loop` — exit vì lỗi fatal trước khi vào
main loop. Thường gặp nhất là **không có state file**.

**Fix**:
```bash
sudo journalctl -u ueba-agent -n 50
# Tìm "No state file at /var/lib/ueba-agent/state.json" hoặc tương tự.
# Sau đó: enroll lại.
```

### 1.6 — CPU cao trên agent host

**Triệu chứng**: `top` cho thấy process `agent` dùng >50% CPU.

**Nguyên nhân**: thường là `process` collector poll `/proc` mỗi 5s trên
máy có nhiều short-lived process. Hoặc wtmp reader hit file wtmp lớn
(hàng triệu record từ nhiều năm login history).

**Fix**:
- Cho process: không làm gì nhiều được; cân nhắc disable `process` collector
  qua policy:
  ```
  PATCH /api/agents/policy
  {"enabled_collectors": ["logon", "http", "device", "file", "email", "network"]}
  ```
  (bỏ "process")
- Cho wtmp: agent lưu offset, nên chỉ đọc record mới. Nếu vừa enroll,
  lần scan đầu đọc cả file → chậm lần đầu, nhanh sau đó. Chờ 5-10
  phút.

### 1.7 — Buffer DB quá lớn (nhiều GB)

**Triệu chứng**: `ls -lh /var/lib/ueba-agent/buffer.db` cho thấy >1 GB.

**Nguyên nhân**: server không reach được trong thời gian dài; events
chất đống local.

**Fix**:
- Verify network đã về: `journalctl -u ueba-agent` nên thấy
  `Flushed N events`.
- Nếu `BUFFER_MAX_EVENTS` ở default 100k, buffer không thể quá
  ~50 MB. Nếu lớn hơn, config sai:
  ```
  agent run --buffer-max-events 100000 ...
  ```
- Khẩn cấp: stop service, `rm buffer.db*`, restart (events chưa flush
  sẽ mất).

### 1.8 — Agent không gửi `http` events

**Triệu chứng**: agent enrolled + heartbeating, nhưng không có `http` events
trong dashboard. Events khác (logon, file) hoạt động.

**Nguyên nhân**: collector `http` cần URL được truyền vào explicit
(`DomainCheckCollector` — programmatic, không sniff). Trên hầu hết máy
nhân viên, browser extension hoặc IMAP/SMTP poller push event; không
có chúng thì không fire event `http`.

**Fix**: cài browser extension (Phase 4 tương lai) HOẶC push event từ
corporate HTTP proxy.

### 1.9 — Agent log cho thấy `Permission denied` cho `/var/log/wtmp`

**Nguyên nhân**: agent chạy user `ueba-agent` không đọc được wtmp.

**Fix**:
```bash
# Trên hầu hết distro, wtmp world-readable:
ls -l /var/log/wtmp
# -rw-rw-r-- ... → OK. Nếu mode 0600 owned by root, thì:
sudo chmod 644 /var/log/wtmp
# HOẶC (tốt hơn) thêm user ueba-agent vào group `adm`:
sudo usermod -aG adm ueba-agent
```

### 1.10 — `agent update` fail với "refusing to replace running binary"

**Nguyên nhân**: trên Windows, file `.exe` đang chạy bị OS giữ.

**Đây là expected** — xem `AGENT_DEPLOYMENT.md` §"Update the agent" cho
cơ chế deferred-swap. Binary mới được stage là `<bin>.new` và swap
khi service start lần tiếp theo. Nếu cần force swap:
```powershell
# Stop service:
Stop-ScheduledTask -TaskName "UEBA Agent"
# Manually swap:
Move-Item "C:\Program Files\UEBA Agent\agent.exe.new" "C:\Program Files\UEBA Agent\agent.exe" -Force
# Start lại:
Start-ScheduledTask -TaskName "UEBA Agent"
```

---

## 2. Server (FastAPI)

### 2.1 — Backend container không start

```bash
docker compose logs app
# Tìm stack trace trong 50 dòng cuối.
```

**Nguyên nhân thường gặp**:
- `DATABASE_URL` sai → không connect được DB.
- `JWT_SECRET` không set → uvicorn fail khi start (Pydantic validation).
- Port 5173 đã được dùng trên host → `lsof -i :5173`.
- Lỗi migration database (Phase 3) → `initialize_database()` raise
  trên check constraint; `CREATE TABLE IF NOT EXISTS` sẽ làm nó
  idempotent, nhưng nếu lần run trước fail để lại state, xem §3.3.

### 2.2 — 500 Internal Server Error trên /api/*

```bash
docker compose logs app | grep -E "ERROR|Traceback" | tail -30
```

Tìm exception thật. Thường gặp:
- `psycopg.OperationalError: connection refused` → DB down hoặc
  `DATABASE_URL` sai.
- `KeyError: 'user_id'` → request body thiếu field; check Pydantic
  schema của endpoint.
- `pydantic.ValidationError` → request body shape sai; check
  OpenAPI schema tại `/docs`.

### 2.3 — 422 Unprocessable Entity

**Nguyên nhân**: request body hoặc query params không khớp schema. Pydantic
trả về list validation error.

**Fix**: check response body cho `detail[].loc` và `msg` để tìm field
lỗi. Thường gặp:
- Thiếu field bắt buộc.
- Sai type (string vs int).
- String quá dài (ví dụ `name` có max_length=255).

### 2.4 — Normalizer không chạy

```bash
GET /api/admin/normalizer-stats
# Check "enabled": true và "total_runs" > 0.
```

Nếu `total_runs == 0`:
- Check `NORMALIZER_ENABLED=true` trong env.
- Check log lỗi lúc lifespan startup.

Nếu `total_runs` tăng nhưng `processed` là 0:
- Bảng `raw_user_logs` rỗng (chưa có event từ agent).

### 2.5 — Normalizer lỗi `insert_ml_anomaly_score failed`

**Nguyên nhân**: bảng `ml_anomaly_scores` thiếu hoặc schema mismatch.

**Fix**:
```sql
\d ml_anomaly_scores
-- Nếu bảng không tồn tại:
-- Migration tạo nó khi startup. Restart server.
docker compose restart app
```

Nếu tồn tại, check `feature_summary_json` constraint — phải là TEXT, không
VARCHAR(N).

### 2.6 — Latency cao trên /api/alerts

**Nguyên nhân**: query full-table-scan `alerts`.

**Fix**: verify index tồn tại:
```sql
\d alerts
-- Tìm idx_alerts_status, idx_alerts_severity, idx_alerts_user_status.
-- Nếu thiếu, chạy:
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
```

---

## 3. Database (PostgreSQL)

### 3.1 — `connection refused` từ backend

**Nguyên nhân**: PostgreSQL không chạy, hoặc sai port / host / creds.

**Check**:
```bash
docker compose ps
# db container Up chưa?

docker compose exec db psql -U ueba_user -d ueba_db -c "SELECT 1;"
# Connect được không?
```

**Fix**:
- Nếu `db` Exited: check `docker compose logs db` xem lý do crash.
- Nếu connect OK nhưng app không reach: check `DATABASE_URL` trong
  `.env` (hostname `db` là service name trong docker-compose).
- Nếu đổi password: update cả `POSTGRES_PASSWORD` trong docker-compose
  lẫn `DATABASE_URL` trong `.env`.

### 3.2 — Migration error: `constraint "..." already exists`

**Nguyên nhân**: migration chạy nhiều lần (ví dụ 2 backend replicas
cùng chạy `initialize_database()` đồng thời).

**Fix**: `initialize_database()` được thiết kế idempotent qua
`CREATE TABLE IF NOT EXISTS` và `CREATE INDEX IF NOT EXISTS`. Nếu
bạn gặp migration concurrent thật, cách đơn giản nhất là chạy 1
instance tại 1 thời điểm:
```bash
docker compose scale app=0
docker compose run --rm app python -c "from src.backend.app.db.session import initialize_database; initialize_database()"
docker compose scale app=1
```

Tương lai: dùng `pg_advisory_lock` quanh `initialize_database()` để
serialize. (Chưa implement.)

### 3.3 — Migration error: `column "X" already exists` (duplicate migration)

**Nguyên nhân**: migration apply nửa vời. `initialize_database()` có guard
nhưng nếu Phase 1 + Phase 3 chạy trên DB nửa build, có thể conflict.

**Fix**: kiểm tra schema, drop duplicate, restart:
```sql
-- Tìm column:
SELECT column_name FROM information_schema.columns
WHERE table_name = 'ml_anomaly_scores';
-- Nếu tồn tại 2 lần (không nên, nhưng nếu có):
-- (Manual fix — cẩn thận, phá hủy)
ALTER TABLE ml_anomaly_scores DROP COLUMN IF EXISTS duplicate_col;
```

### 3.4 — Hết disk

**Nguyên nhân**: `raw_user_logs` và `event_logs` tăng nhanh.

**Fix**:
1. Chạy retention cleanup từ `SECURITY.md §5.6`.
2. Hoặc: thêm disk. Hoặc: enable table partitioning (§7.3 của OPERATIONS).

### 3.5 — Query chậm

```sql
SELECT pid, state, query_start, left(query, 100)
FROM pg_stat_activity
WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 seconds'
ORDER BY query_start;
```

Nếu query bị stuck, kill nó:
```sql
SELECT pg_cancel_backend(pid);
-- hoặc cho connection treo:
SELECT pg_terminate_backend(pid);
```

Fix vĩnh viễn, xem §5.3 của OPERATIONS cho check index.

---

## 4. ML (OCSVM scoring)

### 4.1 — `run_ocsvm_inference` raise `ModelArtifactError`

**Nguyên nhân**: file model thiếu, hỏng, hoặc version mismatch.

**Check**:
```bash
ls -lh src/ml/weights/
# Phải có ocsvm_cert_r42_chunked.joblib (~88 KB).
```

**Fix**:
1. Nếu thiếu: re-download từ artifact store, hoặc re-train:
   ```bash
   bash src/ml/scripts/train_model.sh
   ```
2. Nếu hỏng: re-download.
3. Nếu version mismatch (sklearn version): re-train với sklearn hiện tại.

### 4.2 — Mọi user đều `is_anomaly: true`

**Nguyên nhân**: model over-fitting hoặc threshold (`ML_SCORING_ALERT_MIN_RISK`)
quá thấp.

**Fix**:
- Tăng `ML_SCORING_ALERT_MIN_RISK` lên 80 hoặc 90.
- Verify model load đúng:
  ```python
  from src.ml.services.ueba_ml.inference import get_deployed_ocsvm_model
  m = get_deployed_ocsvm_model()
  print(m.feature_columns)
  print(m.pipeline)
  ```
- Nếu vừa deploy, đợi 24h cho normalizer catch up — feature vector ban
  đầu có thể thưa.

### 4.3 — Không có alert nào được tạo

**Nguyên nhân**: `ML_SCORING_ALERT_MIN_RISK` quá cao, HOẶC ML không tìm
thấy anomaly (model quá nhạy thấp).

**Check**:
```sql
SELECT user_id, is_anomaly, risk_score, severity, created_alert_id
FROM ml_anomaly_scores
ORDER BY scored_at DESC LIMIT 20;
```

Nếu `is_anomaly: false` everywhere → model quá lenient. Re-train với
feature engineering tốt hơn, hoặc giảm `nu` (nhạy hơn).

Nếu `is_anomaly: true` nhưng không có `created_alert_id` → risk_score <
threshold. Hạ `ML_SCORING_ALERT_MIN_RISK` (mặc định 60) xuống 40 hoặc 50.

### 4.4 — LLM explanation rỗng

**Nguyên nhân**: `MISTRAL_API_KEY` rỗng hoặc invalid.

**Check**:
```bash
docker compose exec app env | grep MISTRAL
# MISTRAL_API_KEY phải được set.
```

**Fix**:
- Set key thật.
- Restart.
- Note: code có fallback về template-based explanation
  (`_fallback_explanation` trong `services/llm.py`) khi LLM fail, nên
  alert vẫn được tạo — chỉ là explanation generic.

### 4.5 — LLM rate limit hit

**Triệu chứng**: log cho thấy `Mistral rate limit exceeded` hoặc
`429 Too Many Requests`.

**Fix**:
- Giảm `ML_SCORING_ALERT_MIN_RISK` (ít LLM call hơn).
- Implement response caching (tương lai).
- Upgrade Mistral plan.

---

## 5. Frontend (React SPA)

### 5.1 — Trang trắng sau login

**Nguyên nhân**: API base URL sai, hoặc SPA không được serve tại root.

**Check**:
- Browser DevTools → Network tab → tìm request fail.
- Check `VITE_API_BASE_URL` lúc build (trong `.env` cho frontend).

**Fix**:
- Build frontend với base URL đúng:
  ```bash
  cd src/frontend
  VITE_API_BASE_URL=https://ueba.corp.example/api npm run build
  ```
- Verify backend serve SPA tại `/` (default trong
  `src/backend/app/main.py:frontend_spa`).

### 5.2 — Lỗi CORS trong browser console

**Triệu chứng**: `Access to XMLHttpRequest at 'https://...' from origin
'https://...' has been blocked by CORS policy`.

**Fix**: thêm frontend origin vào `CORS_ORIGINS` trong backend env:
```
CORS_ORIGINS=https://app.corp.example,https://localhost:5173
```
Restart backend.

### 5.3 — Stuck ở login sau khi nhập credentials

**Nguyên nhân**: API không reach được hoặc trả 5xx.

**Check**: tương tự §2.1 + §2.2.

### 5.4 — Dashboard hiển thị "0 alerts" nhưng DB có alerts

**Nguyên nhân**: frontend date filter quá hẹp, hoặc `list_alerts` đang
filter `status` ngoài ý muốn.

**Fix**: check URL trang — tìm `?status=...&from=...&to=...`.
Clear filter, refresh.

### 5.5 — Agent detail page không có data

**Nguyên nhân**: agent chưa có `assigned_user_id`, HOẶC agent gán cho user
chưa có alert nào.

**Fix**: sửa agent qua `PATCH /api/agents/{id}` để set `assigned_user_id`
(sau khi tạo user record nếu cần).

### 5.6 — Blocklist page không thêm được entry

**Nguyên nhân**: backend trả 403 (không phải admin) hoặc 400 (validation).

**Check**: Browser DevTools → Network → click POST fail → Response body
cho `detail`.

---

## 6. End-to-end flow

### 6.1 — Event từ agent không hiện trong dashboard

Checklist chẩn đoán (chạy từ trên xuống, dừng ở lỗi đầu tiên):

```bash
# 1. Agent có gửi không?
sudo journalctl -u ueba-agent -n 100 | grep "Flushed"

# 2. Server có nhận không?
docker compose logs app | grep -E "POST /api/raw-logs/batch"

# 3. Normalizer có chạy không?
curl -H "Authorization: Bearer $TOKEN" \
     https://ueba.corp.example/api/admin/normalizer-stats
# Tìm total_runs > 0 và last_processed > 0.

# 4. Raw log đã được normalize chưa?
PGPASSWORD=... psql -c "SELECT id, source_id, normalized_event_id FROM raw_user_logs WHERE created_at > NOW() - INTERVAL '10 minutes' ORDER BY id DESC LIMIT 10;"
# normalized_event_id phải non-null.

# 5. event_log đã được tạo chưa?
PGPASSWORD=... psql -c "SELECT id, event_type, action, user_id FROM event_logs WHERE created_at > NOW() - INTERVAL '10 minutes' ORDER BY id DESC LIMIT 10;"

# 6. Scoring đã chạy chưa?
PGPASSWORD=... psql -c "SELECT user_id, is_anomaly, risk_score, severity FROM ml_anomaly_scores WHERE scored_at > NOW() - INTERVAL '10 minutes' ORDER BY scored_at DESC LIMIT 10;"

# 7. Alert đã được tạo chưa?
PGPASSWORD=... psql -c "SELECT id, user_id, title, severity, risk_score, status FROM alerts WHERE detected_at > NOW() - INTERVAL '10 minutes' ORDER BY detected_at DESC LIMIT 10;"

# 8. Check dashboard's API call:
# Mở DevTools → Network → /api/alerts → check request URL + response.
```

Nếu tìm thấy gap, nhảy đến section tương ứng ở trên.

### 6.2 — Tất cả event tạo alert, nhưng đều `severity: low`

**Nguyên nhân**: model quá bảo thủ, hoặc threshold quá cao (không bao giờ
fire high/critical alert).

**Fix**:
- Hạ `ML_SCORING_ALERT_MIN_RISK` để cho medium severity đi qua.
- Verify model cho risk_score cao với anomaly đã biết (ví dụ user copy
  `evil.exe` nên có risk_score > 90).
- Nếu không, model under-trained → re-train với data nhiều hơn, hoặc
  tune tham số OCSVM `nu`.

### 6.3 — Cùng user bị hàng trăm alert mỗi ngày

**Nguyên nhân**: user "noisy" (ví dụ người làm nhiều USB file copy hợp
pháp) đụng anomaly threshold mỗi event.

**Fix**:
- Đánh alert là `false_positive` từ admin UI → cải thiện training tương
  lai.
- Tăng `ML_SCORING_ALERT_MIN_RISK` lên 80.
- Configure alert dedup (tương lai): nếu cùng user cùng alert type
  trong 1h, suppress.

---

## 7. Nhờ trợ giúp

Nếu đã đọc qua guide này mà vẫn chưa giải quyết:

1. **Check log** (luôn là bước đầu):
   - Agent: `journalctl -u ueba-agent -n 200` hoặc `tail -f agent.log`
   - Server: `docker compose logs app`
   - DB: `docker compose logs db`

2. **Search existing issues**:
   - GitHub issues (search error message)
   - Wiki nội bộ / Slack #ueba-ops

3. **Thu thập debug info trước khi ticket**:
   ```bash
   # Server info:
   docker compose version
   docker compose ps
   curl -H "Authorization: Bearer $ADMIN_TOKEN" \
        https://ueba.corp.example/api/admin/normalizer-stats | jq

   # DB info:
   PGPASSWORD=... psql -c "SELECT version();"
   PGPASSWORD=... psql -c "SELECT pg_size_pretty(pg_database_size('ueba_db'));"
   ```

4. **File bug** với:
   - Reproduction steps.
   - Server version (git SHA).
   - Agent version (`agent version`).
   - Log từ cả 3 component.
   - Expected vs actual behavior.
