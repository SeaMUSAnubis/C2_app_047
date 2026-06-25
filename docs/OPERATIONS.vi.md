# Hướng Dẫn Vận Hành

Vận hành day-2 cho hệ thống UEBA Endpoint Monitoring. Bao gồm: chạy stack,
monitor health, scale, debug sự cố production.

> **Đối tượng**: SRE, DevOps, IT admin chạy UEBA backend trong production.
> Cài trên máy nhân viên xem [`AGENT_DEPLOYMENT.md`](AGENT_DEPLOYMENT.md).
> Security model xem [`SECURITY.md`](SECURITY.md).

---

## 1. Tổng quan kiến trúc (cái gì chạy ở đâu)

| Component | Ở đâu | Cái gì |
|---|---|---|
| **PostgreSQL** | 1 node (có thể HA) | Toàn bộ state (users, devices, alerts, raw + normalized logs, agent registry, blocklist) |
| **UEBA backend** (FastAPI) | 1+ node sau load balancer | API, ML scoring, normalizer worker (in-process) |
| **React frontend** | Static files serve bởi backend tại `/` | Single-page app, serve từ cùng container |
| **Endpoint agent** | 1 process trên mỗi máy nhân viên | Local SQLite buffer + 7 collector + HTTPS transport |

Single-node deploy (mọi thứ trong 1 container, xem `docker-compose.yml`)
chạy được cho ~10k events/min. Để scale hơn, tách database và scale
backend horizontal (normalizer thread-safe qua DB-level locks).

---

## 2. Health checks

### 2.1 — Endpoint

```
GET /health
```

Trả về `{"status": "ok"}` (HTTP 200) khi app process chạy. Không check
dependency (dùng `/api/admin/normalizer-stats` để sâu hơn).

### 2.2 — Chi tiết

```
GET /api/admin/normalizer-stats    (admin JWT)
```

Trả về:
```json
{
  "total_runs": 1234,
  "total_processed": 56789,
  "total_failed": 3,
  "last_run_at": "2026-06-22T12:34:56Z",
  "last_processed": 42,
  "last_failed": 0,
  "last_pending": 0,
  "pending_now": 0,
  "enabled": true
}
```

`pending_now > 100` trong vài phút → normalizer bị tụt hậu → xem §6.

### 2.3 — Liveness probe (cho k8s/Compose)

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 5173
  initialDelaySeconds: 30
  periodSeconds: 10
```

### 2.4 — Readiness probe (chờ DB)

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 5173
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 6
```

(`/health` được thiết kế cheap. Cho check DB sâu hơn, thêm endpoint
`/ready` chạy `SELECT 1` — chưa có.)

---

## 3. Triển khai

### 3.1 — Single-container (mặc định)

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f app
```

`docker-compose.yml` ở repo root chạy:
- PostgreSQL 16 (volume `pgdata` cho persistence).
- FastAPI app (port 5173 → container 5173 → uvicorn).
- Frontend bundle vào cùng container tại `/app/src/frontend/dist`.

`docker compose down` giữ DB volume. `docker compose down -v` xóa
(sạch sẽ).

### 3.2 — Production

Production: dùng external Postgres (managed như AWS RDS, Cloud SQL,
hoặc self-managed với replication) + stateless backend:

```yaml
# docker-compose.prod.yml
services:
  app:
    image: ghcr.io/vespionage/ueba-endpoint-monitoring:v0.1.0
    ports: ["5173:5173"]
    environment:
      DATABASE_URL: postgresql://user:pass@db.prod.internal:5432/ueba
      JWT_SECRET: ${JWT_SECRET}
      MISTRAL_API_KEY: ${MISTRAL_API_KEY}
      # xem .env.example để có đầy đủ
    depends_on: [db]
    restart: always
    deploy:
      replicas: 2   # 2 instance sau LB; normalizer idempotent
      resources:
        limits: {cpus: "1.0", memory: 1G}
```

Sau nginx (hoặc reverse proxy bất kỳ) cho TLS termination + rate limiting.

### 3.3 — Kubernetes

```bash
kubectl apply -f deploy/k8s/
```

(chưa có trong repo — generate qua `kompose convert` hoặc tương tự).
Cấu hình chính:
- 2+ replicas (normalizer safe khi chạy nhiều instance vì dùng
  `FOR UPDATE SKIP LOCKED`-style row locking — xem `list_pending_raw_logs`).
- `PodDisruptionBudget` với `minAvailable: 1` (không bao giờ hạ hết).
- `HorizontalPodAutoscaler` trên CPU > 70%.
- `readinessProbe` → `/health` (theo §2.4).

---

## 4. Cấu hình

Toàn bộ config qua environment variables (xem `.env.example`).

### 4.1 — Bắt buộc

| Var | Ví dụ | Ghi chú |
|---|---|---|
| `DATABASE_URL` | `postgresql://user:pass@db:5432/ueba` | psycopg format |
| `JWT_SECRET` | `<32-byte random hex>` | **PHẢI đổi trong prod** |
| `OCSVM_MODEL_PATH` | `src/ml/weights/ocsvm_cert_r42_chunked.joblib` | Mount as volume |
| `MISTRAL_API_KEY` | `<api-key>` | Cho LLM alert explanation; để trống dùng fallback |

### 4.2 — Tùy chọn (có default hợp lý)

| Var | Default | Ghi chú |
|---|---|---|
| `NORMALIZER_ENABLED` | `True` | Master switch cho normalizer |
| `NORMALIZER_POLL_INTERVAL_SECONDS` | `10` | Bao lâu normalizer poll một lần |
| `NORMALIZER_BATCH_SIZE` | `200` | Max raw logs / tick |
| `ML_SCORING_ENABLED` | `True` | Master switch cho ML scoring |
| `ML_SCORING_WINDOW_MINUTES` | `1440` (24h) | Bao nhiêu lịch sử event để xét |
| `ML_SCORING_ALERT_MIN_RISK` | `60` | Dưới ngưỡng này không tạo alert |
| `AGENT_HEARTBEAT_TIMEOUT_MINUTES` | `10` | Mark agents offline sau khoảng này |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated |
| `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR` |

### 4.3 — Tuning cho scale

| Triệu chứng | Setting | Giá trị mới |
|---|---|---|
| Normalizer tụt hậu (>100 pending) | `NORMALIZER_POLL_INTERVAL_SECONDS` | `5` |
| Normalizer tụt hậu dù ở 5s | `NORMALIZER_BATCH_SIZE` | `500` |
| ML scoring làm dashboard chậm | `ML_SCORING_WINDOW_MINUTES` | `360` (6h) |
| Quá nhiều low-risk alert | `ML_SCORING_ALERT_MIN_RISK` | `75` |
| Nhiều false stale-agent flag | `AGENT_HEARTBEAT_TIMEOUT_MINUTES` | `30` |

---

## 5. Monitoring

### 5.1 — Logs

```bash
# Docker:
docker compose logs -f app

# Bare metal (systemd):
journalctl -u ueba-backend -f
```

Backend dùng `logging.basicConfig` với format
`%(asctime)s %(levelname)s %(name)s: %(message)s`. Cho prod, ship đến
Loki / ELK / Datadog qua sidecar.

### 5.2 — Metrics (Prometheus)

Backend chưa expose Prometheus metrics. Để thêm:
1. `pip install prometheus-fastapi-instrumentator`.
2. Wire vào `main.py`:
   ```python
   from prometheus_fastapi_instrumentator import Instrumentator
   Instrumentator().instrument(app).expose(app)
   ```
3. Scrape `/metrics` từ Prometheus.

Metrics quan trọng để alert:
- `ueba_normalizer_pending` (gauge) — nên < 100.
- `ueba_normalizer_failed_total` (counter) — nên là 0.
- `ueba_alerts_created_total` (counter) — spike = sự cố thật.
- `ueba_agent_heartbeat_age_seconds` (gauge per agent) — > 600 = offline.

### 5.3 — Database health

```sql
-- Check bloat:
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

-- Long-running queries:
SELECT pid, state, query_start, left(query, 80)
FROM pg_stat_activity
WHERE state = 'active' AND query_start < NOW() - INTERVAL '30 seconds';

-- Index usage:
SELECT relname, idx_scan, seq_scan
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan AND n_live_tup > 1000
ORDER BY seq_scan DESC;
```

`raw_user_logs` và `event_logs` tăng nhanh nhất. Set up partitioning
theo tháng cho >10M events (xem §7).

---

## 6. Sự cố vận hành thường gặp

### 6.1 — Normalizer tụt hậu

**Triệu chứng**: `pending_now` tăng không giới hạn; agent buffer đầy.

**Nguyên nhân** (xếp theo xác suất):
1. **Single instance bottleneck**: normalizer xử lý tuần tự. Nếu có
   1 backend replica và 100k events/min đến, bạn đang CPU-bound trên
   DB writes.
2. **DB connection saturation**: mỗi `run_once` mở connection mới. Nếu
   pool max < 10, bạn đang queue.
3. **ML scoring chậm**: `run_ocsvm_inference` sync + CPU-bound (joblib
   load). Nếu `user_scoring.score_user` mất >100ms / call, và có
   100 user distinct, bạn burn 10s / tick.

**Fix**:
- Scale lên 2-3 backend replicas (normalizer idempotent).
- Set `NORMALIZER_POLL_INTERVAL_SECONDS=5` và `NORMALIZER_BATCH_SIZE=500`.
- Set `ML_SCORING_ENABLED=false` tạm thời để cô lập ML là nguyên nhân.
- Thêm partial index trên `raw_user_logs(normalized_event_id)` nếu chưa
  có (schema đã tạo — verify qua `\d+ raw_user_logs`).

### 6.2 — DB CPU cao

**Triệu chứng**: `pg_stat_activity` cho thấy query chạy lâu, dashboard chậm.

**Nguyên nhân**:
1. Missing indexes (verify theo §5.3).
2. Autovacuum không chạy (default OK, nhưng trên table ghi nhiều, tune
   `autovacuum_vacuum_scale_factor=0.05` cho `raw_user_logs`).
3. Connection storm (dùng `pgbouncer` phía trước).

### 6.3 — LLM rate limit hit

**Triệu chứng**: log cho thấy `Mistral rate limit`; alert được tạo
không có explanation (`explanation=None`).

**Fix**:
- Set `MISTRAL_MODEL=mistral-small-latest` (rẻ hơn `large`).
- Implement response caching cho duplicate alert (tương lai: cache
  theo `(user_id, top_factors_signature)`).
- Fall back về template-based explanation khi LLM fail (đã có trong
  `services/llm.py`).

### 6.4 — Agent offline liên tục

**Triệu chứng**: nhiều agent stuck ở trạng thái `offline`; dashboard
có gap.

**Nguyên nhân**:
1. **Network**: agent host không reach được server. Check bằng
   `curl -I https://ueba.corp.example/api/health` từ agent host.
2. **TLS**: cert hết hạn hoặc self-signed. Agent nhận
   `SSL: CERTIFICATE_VERIFY_FAILED`.
3. **Clock skew**: agent clock lệch >5 phút; heartbeat trả 401/403
   do `iat` claim validation (chỉ human JWT, không cho `X-API-Key`).
4. **Power saving**: laptop sleep → heartbeat dừng. Chấp nhận được;
   agent reconnect khi wake.

**Fix**:
- Mark-stale định kỳ: `POST /api/admin/agents/mark-stale`.
- Cho workstation luôn bật: config OS không bao giờ sleep.

### 6.5 — Buffer DB corruption

**Triệu chứng**: agent log `sqlite3.DatabaseError: database disk image is malformed`.

**Fix**:
1. Stop service.
2. `sqlite3 /var/lib/ueba-agent/buffer.db "PRAGMA integrity_check"`
3. Nếu corrupt, xóa file (`rm buffer.db buffer.db-wal buffer.db-shm`)
   — events chưa flush sẽ mất. Start service; nó tạo DB mới.

Để phòng: schedule `sqlite3 ... "VACUUM"` định kỳ qua cron
(hàng tuần đủ cho 100k events).

### 6.6 — Hết disk trên agent host

**Triệu chứng**: agent dừng gửi event; log cho thấy `No space left on device`.

**Fix**:
- `BUFFER_MAX_EVENTS=100000` cap buffer DB (FIFO eviction).
- `LOG_LEVEL=WARNING` giảm log volume.
- Thêm disk space monitor (Prometheus node_exporter + alert ở <10%
  free).

---

## 7. Scale

### 7.1 — Khi nào scale

| Metric | Ngưỡng | Hành động |
|---|---|---|
| Events/min | > 50k | Thêm backend replicas |
| DB CPU | > 70% sustained | Thêm read replica; optimize queries |
| Disk usage | > 80% | Thêm retention cleanup (§5.6 trong SECURITY) |
| Normalizer pending | > 1000 sustained | Scale backend, sau đó DB |

### 7.2 — Scale backend

Stateless sau load balancer. Khuyến nghị: 2-3 instance.
Normalizer safe khi chạy nhiều (dùng DB row-level locks qua
`FOR UPDATE SKIP LOCKED`-equivalent — xem `list_pending_raw_logs`).

### 7.3 — Scale database

Cho >10M events, partition `raw_user_logs` và `event_logs` theo tháng:

```sql
CREATE TABLE raw_user_logs_2026_06 PARTITION OF raw_user_logs
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
-- repeat cho mỗi tháng
```

(Xem PostgreSQL docs cho declarative partitioning.)

Cho analytics, set up read replica (postgres logical replication) và
point dashboard vào đó. Alerts vẫn ghi vào primary.

### 7.4 — Scale agent fleet

Backend được thiết kế để xử lý 10k+ agent không cần thay đổi. Mỗi
agent gửi ~10 events/min (user idle) đến ~100 events/min (user active).
Cho 10k agent, peak ~17k events/sec sustained → cần
~3 backend replicas + 1 DB mạnh.

Cho >50k agent, cân nhắc:
- Kafka / RabbitMQ giữa agent và normalizer (ngoài scope hiện tại).
- Shard theo `device_id` hoặc `user_id`.

---

## 8. Backup & restore

### 8.1 — Backup PostgreSQL

```bash
# Daily:
pg_dump -Fc -d ueba -f /backup/ueba-$(date +%Y%m%d).dump

# Hoặc qua WAL archiving (point-in-time recovery):
# postgresql.conf:
#   wal_level = replica
#   archive_mode = on
#   archive_command = 'cp %p /backup/wal/%f'
```

### 8.2 — Restore

```bash
# Stop backend (để không có write trong lúc restore).
docker compose stop app
# HOẶC: kubectl scale deployment ueba --replicas=0

# Restore:
pg_restore -d ueba --clean --if-exists /backup/ueba-20260620.dump

# Start backend.
```

### 8.3 — Disaster recovery

RPO/RTO targets (tune theo business):
- **RPO 1 giờ**: WAL archive mỗi phút + daily full dump.
- **RTO 15 phút**: warm standby với `pg_basebackup`; promote + DNS
  failover.

Cho multi-region: dùng managed Postgres (RDS Multi-AZ, Cloud SQL HA,
Aurora) — chúng handle failover tự động.

---

## 9. Maintenance windows

### 9.1 — Rotate JWT_SECRET

```bash
# 1. Generate secret mới:
NEW_SECRET=$(openssl rand -hex 32)

# 2. Update env, restart:
docker compose down
# edit .env
docker compose up -d

# 3. Tất cả human session bị invalidate; users phải login lại.
# 4. Agent key KHÔNG bị ảnh hưởng (X-API-Key độc lập).
```

### 9.2 — Rotate agent API keys

Hệ thống chưa support "rotate without re-enroll". Để rotate:

```bash
# Per-agent:
curl -X DELETE https://ueba.corp.example/api/agents/agent-abc123 \
    -H "Authorization: Bearer $ADMIN_TOKEN"

# Sau đó IT staff phải re-enroll trên host (xem AGENT_DEPLOYMENT.md).
```

Cho fleet-wide rotation, chạy vòng lặp này và dùng MDM để push script
enroll + start mới.

### 9.3 — Upgrade backend

```bash
# Pull image mới:
docker compose pull

# Stop, migrate, start:
docker compose down
docker compose up -d   # chạy migration qua initialize_database()
```

`initialize_database()` idempotent (`CREATE TABLE IF NOT EXISTS`,
`CREATE INDEX IF NOT EXISTS`). Không cần bước migration riêng.

Cho breaking schema change, xem `docs/management/MIGRATIONS.md`
(chưa viết; dùng `pg_dump` + manual review tạm thời).

---

## 10. Tối ưu chi phí

Cho 1k-agent deploy, chi phí hàng tháng ước tính (cloud):

| Resource | Size | $/tháng |
|---|---|---|
| Backend (2x) | 1 vCPU, 1 GB RAM mỗi cái | $30 |
| PostgreSQL (1x) | 2 vCPU, 4 GB RAM, 50 GB SSD | $80 |
| Object storage (backups) | 100 GB | $3 |
| Egress (agent uploads) | 50 GB | $5 |
| Mistral API (LLM) | 1M tokens | $2 |
| **Tổng** | | **~$120/tháng** |

Cho 10k agents, nhân backend 3-4 và DB 2.

Để giảm chi phí:
- Self-host LLM (ví dụ Llama 3 trên single GPU) — loại bỏ Mistral
  API cost. Sửa `services/llm.py` để gọi local server.
- Tăng `ML_SCORING_ALERT_MIN_RISK` để giảm LLM calls.
- Aggressive log retention (§5.6 trong SECURITY).

---

## 11. Query hữu ích

### 11.1 — Top risky users tuần này

```sql
SELECT u.id, u.username, u.full_name, u.department,
       COUNT(a.id) AS alert_count,
       MAX(a.risk_score) AS max_risk
FROM users u
JOIN alerts a ON a.user_id = u.id
WHERE a.detected_at > NOW() - INTERVAL '7 days'
  AND a.status != 'false_positive'
GROUP BY u.id, u.username, u.full_name, u.department
ORDER BY max_risk DESC, alert_count DESC
LIMIT 20;
```

### 11.2 — Domain bị block nhiều nhất hôm nay

```sql
SELECT raw_payload->>'block_pattern' AS pattern,
       COUNT(*) AS blocked_count,
       COUNT(DISTINCT user_id) AS affected_users
FROM raw_user_logs
WHERE event_type = 'http'
  AND created_at > CURRENT_DATE
  AND raw_payload->>'action' = 'blocked'
GROUP BY pattern
ORDER BY blocked_count DESC
LIMIT 20;
```

### 11.3 — Stale agents

```sql
SELECT agent_id, hostname, last_heartbeat, NOW() - last_heartbeat AS age
FROM endpoint_agents
WHERE status != 'revoked'
  AND (last_heartbeat IS NULL OR last_heartbeat < NOW() - INTERVAL '10 minutes')
ORDER BY last_heartbeat NULLS FIRST;
```

### 11.4 — Admin actions gần đây

```sql
-- Cần wire access log vào DB (future). Tạm thời grep application log:
-- docker compose logs app | grep -E '"POST /api/admin|"DELETE /api/admin|"PATCH /api/agents'
```
