# Mô Hình Bảo Mật

Tài liệu này mô tả kiến trúc bảo mật của hệ thống UEBA Endpoint Monitoring. Bao
gồm: authentication, authorization, định danh agent, quyền riêng tư dữ liệu, threat
model, và các biện pháp bảo vệ cho từng layer.

> **Đọc tài liệu này trước khi triển khai production.** Một hệ thống UEBA có
> quyền truy cập vào dữ liệu cực kỳ nhạy cảm (mọi login, mọi web request,
> mọi file access). Xử lý sai dữ liệu đó là vi phạm compliance ở hầu hết
> các quốc gia.

---

## 1. Mô hình tin cậy

```
                    ┌─────────────────────────────────┐
                    │  UEBA Backend (FastAPI :8000)   │
                    │  ─ Auth (JWT, X-API-Key)        │
                    │  ─ Normalizer (raw → events)    │
                    │  ─ ML scoring (OCSVM)           │
                    │  ─ Alert creation               │
                    └──────────┬──────────────────────┘
                               │ HTTPS
              ┌────────────────┼─────────────────┐
              │                │                 │
       ┌──────▼──────┐  ┌──────▼──────┐  ┌────────▼────────┐
       │ Employee    │  │ Employee    │  │  Admin browser  │
       │ machine 1   │  │ machine 2   │  │  (Chrome/Edge)  │
       │ (agent)     │  │ (agent)     │  │  (React SPA)    │
       └─────────────┘  └─────────────┘  └─────────────────┘
```

**Ba actor:**

1. **Human users** (admin, security_manager, analyst, employee) — truy cập
   qua browser, xác thực bằng JWT bearer token.
2. **Endpoint agents** — cài trên máy nhân viên, xác thực bằng header
   `X-API-Key` được cấp lúc enroll.
3. **External systems** (tương lai) — xác thực tương tự agent, qua
   `X-API-Key` được cấp qua admin API.

**Tin cậy ngầm**: database, model file, và host chạy backend là trusted.
Compromise bất kỳ thành phần nào trong 3 thứ này sẽ compromise toàn bộ hệ
thống.

---

## 2. Authentication

### 2.1 — Human users: JWT bearer

- **Algorithm**: HS256 (mặc định) với `JWT_SECRET` từ environment.
- **Token lifetime**: `JWT_EXPIRES_MINUTES` (mặc định 480 = 8 giờ).
- **Claims**: `sub` (account id), `role` (admin/security_manager/analyst/employee),
  `iat`, `exp`.
- **Storage trên client**: `localStorage` trong React app (production nên thay
  bằng `HttpOnly; Secure; SameSite=Strict` cookie — xem §8).
- **Password storage**: **bcrypt** qua `passlib`
  (`src/backend/app/core/security.py`). Plaintext không bao giờ được log
  hoặc lưu.
- `Authorization: Bearer <token>` trên mọi API call. Missing hoặc expired
  token → 401.

### 2.2 — Endpoint agents: X-API-Key

- Cấp lúc enroll: `o47ag_<32 ký tự base32>` (24 bytes entropy).
- Lưu trữ **đã hash** (SHA-256) trong cột `endpoint_agents.api_key_hash`.
- Plaintext key trả về **một lần** lúc enroll, không bao giờ lưu trên
  server.
- Trên agent: lưu trong `<state_path>/state.json` với file mode `0600`,
  owned bởi dedicated system user (`ueba-agent` / `_ueba-agent`).
- **Wire format**: `X-API-Key: o47ag_...` header trên mọi request.
- **Rotation**: `DELETE /api/agents/{id}` thu hồi agent (server đánh dấu
  `status='revoked'`). Hash được giữ lại cho audit, nhưng mọi request
  tiếp theo trả về 403.
- **Re-enrollment**: cần enrollment token mới (admin cấp qua
  `POST /api/agents/enrollment-tokens`); `X-API-Key` mới thay thế hash cũ.

### 2.3 — Enrollment tokens (one-time)

- Admin cấp: `o47enr_<24 ký tự base32>`.
- Lifetime: `AGENT_ENROLLMENT_TOKEN_TTL_MINUTES` (mặc định 60).
- **One-shot**: cột `used_by_agent_id` được set khi dùng lần đầu; dùng lần 2
  trả về 400.
- Storage: SHA-256 hash trong `agent_enrollment_tokens.token_hash`.

### 2.4 — Password reset (humans)

Hiện ngoài scope (chưa có UI). Để thêm:
1. `POST /api/auth/forgot-password` gửi reset link qua email.
2. `POST /api/auth/reset-password?token=...` chấp nhận password mới và
   hash nó.
3. Reset token là JWT với `aud: "password-reset"`, single-use, lifetime 1h.

---

## 3. Authorization (RBAC)

Bốn role, định nghĩa trong `app_accounts.role CHECK`:

| Role | Có thể đọc | Có thể ghi | Ghi chú |
|---|---|---|---|
| `admin` | mọi thứ | mọi thứ (gồm blocklist, agents, accounts, policy) | Full access |
| `security_manager` | mọi thứ | alerts (status, investigation), blocklist, agents (read + revoke) | Không quản lý accounts |
| `analyst` | mọi thứ | alerts (status, investigation) | Read-only cho admin/agent data |
| `employee` | chỉ dữ liệu của mình | risk của mình | Chỉ thấy "My risk" |

Enforcement qua dependency `require_role(*roles)` trong
`src/backend/app/api/routes.py` và `routes_agents.py`:

```python
@router.get("/api/agents")
async def list_agents(
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
):
    ...
```

Frontend mirror điều này qua `RoleGuard` (React Router).

**Defense in depth**: ngay cả khi authenticated, mỗi query được filter theo
user scope khi thích hợp. Ví dụ: `GET /api/me/overview` luôn trả về
`current_account['id']` — không bao giờ nhận user_id từ client.

---

## 4. Định danh agent & bảo mật enrollment

### 4.1 — Enrollment flow

```
  Admin cấp token        Agent enroll
  ┌──────────┐            ┌──────────┐
  │  Admin   │            │  Agent   │
  │ browser  │            │ service  │
  └────┬─────┘            └────┬─────┘
       │                       │
       │ POST /api/agents/     │
       │ enrollment-tokens     │
       │ (admin JWT)           │
       │                       │
       │ ◄──── token: o47enr_xxx
       │                       │
       │        Hand token qua kênh bảo mật
       │        (1Password, Bitwarden Send, email mã hóa)
       │ ─────────────────────▶
       │                       │
       │              POST /api/agents/register
       │              {enrollment_token, hostname, os, ...}
       │                       │
       │                       │ ◄── {agent_id, api_key: o47ag_xxx}
       │                       │
       │              Save state.json (mode 0600)
       │              chứa agent_id + api_key
       │                       │
       │              Dùng api_key cho mọi request sau
```

Plaintext `api_key` trả về **một lần** và không recover được. Nếu mất, admin
phải thu hồi agent và cấp token mới.

### 4.2 — Vận chuyển token

- **Không bao giờ** gửi enrollment token qua HTTP thường, Slack, GitHub,
  v.v. Dùng password manager có mã hóa end-to-end, hoặc file share công ty
  có audit log.
- Production token TTL: giảm `AGENT_ENROLLMENT_TOKEN_TTL_MINUTES` xuống
  5–10 phút để bảo mật chặt nhất.

### 4.3 — Validation phía server

Mỗi request của agent validate:
1. Header `X-API-Key` có mặt → không thì 401.
2. SHA-256 hash khớp với agent active (`status != 'revoked'`) → không thì
   403.
3. Request cũng cần **host context** — agent phải gửi `agent_id` (ví dụ
   trong `agent_config_pull` body). Mismatch giữa `X-API-Key` và
   `agent_id` → 403 (defense chống confused-deputy).
4. `last_heartbeat` được update server-side trên mỗi request đã auth.

### 4.4 — Bảo vệ state file

Agent lưu `agent_id + api_key` trong `state.json` với:
- File mode `0600` (chỉ owner read/write).
- Owned bởi system user (`ueba-agent` / `_ueba-agent`).
- Lưu trên path chỉ system user đó đọc được (default
  `/var/lib/ueba-agent/`).
- **Không bao giờ** log plaintext.

---

## 5. Quyền riêng tư dữ liệu

### 5.1 — Cái gì được thu thập

Agent emit events cho:

| Type | Dữ liệu | Rủi ro PII |
|---|---|---|
| `logon` | username, host, timestamp | Username = PII |
| `device` | USB descriptor (vendor:product) | Thấp |
| `file` | file path, op (copy/write/delete) | Path có thể leak tên dự án |
| `http` | URL, domain, action (allowed/blocked), block_pattern/category/reason | URL có thể chứa token / query secret |
| `email` | from, to, subject (hash), size, attachments, op (send/read/forward) | Subject + recipients là PII |
| `process` | pid, process_name, cmdline | Cmdline có thể chứa password/key |
| `network` | src_ip, src_port, dst_ip, dst_port, protocol | IP là PII |

### 5.2 — Cái gì KHÔNG thu thập (và không bao giờ nên)

- **Email body** — chỉ metadata (size, attachment count, hash của subject).
  Xem `EmailCollector._redact_subject` (sha256[:16]).
- **File content** — chỉ path + op.
- **Web request/response body** — chỉ URL + domain.
- **Keystrokes** — không bao giờ.
- **Screenshots** — không bao giờ.
- **Webcam / microphone** — không bao giờ.

### 5.3 — Giảm thiểu dữ liệu khi truyền

Agent **không** gửi email body hoặc file content. Nếu tích hợp của bạn
thêm custom field, hãy **strip PII** trước khi thêm vào `raw_payload`.

### 5.4 — Mã hóa khi truyền

- **Bắt buộc**: production deploy PHẢI dùng HTTPS. Flag `--no-verify-tls`
  của agent chỉ dành cho development.
- **CA bundle**: truyền `--ca-bundle /etc/ssl/certs/corp-ca.pem` nếu server
  dùng internal CA. Không disable cert verification.
- **TLS minimum**: TLS 1.2. Server dùng uvicorn + httpx, cả hai default
  TLS 1.2+.

### 5.5 — Mã hóa khi lưu

- **Database**: PostgreSQL với disk-level encryption (LUKS, AWS EBS
  encryption, v.v.) được khuyến nghị. Column-level encryption chưa
  implement.
- **Agent state + buffer**: lưu trong SQLite trên disk. State file mode
  0600; buffer DB mode 0644 (collectors cần write event từ worker thread).
  Cả hai chỉ agent system user đọc được.
- **Log files** (`/var/log/ueba-agent/agent.log`): không mã hóa khi lưu.
  Dùng log forwarder (Fluent Bit, Vector) để ship đến SIEM với retention
  policy phù hợp.

### 5.6 — Retention

Default: vô hạn. Khuyến nghị:
- `raw_user_logs`: 30 ngày (debug-grade, có thể replay qua re-normalize).
- `event_logs`: 1 năm.
- `alerts`: 1 năm cho resolved, vô hạn cho new.
- `ml_anomaly_scores`: 90 ngày.
- Agent local buffer: 100k events (FIFO eviction, xem `BUFFER_MAX_EVENTS`).

Set up periodic cleanup job (cron / pg_cron):

```sql
DELETE FROM raw_user_logs
WHERE created_at < NOW() - INTERVAL '30 days';

DELETE FROM ml_anomaly_scores
WHERE scored_at < NOW() - INTERVAL '90 days';
```

---

## 6. Threat model

### 6.1 — Các threat trong scope

| Threat | Mitigation |
|---|---|
| Nhân viên cố gỡ cài agent | Service chạy dưới separate user; `dpkg`/`rpm` integration (tương lai) ngăn remove không cần root. Heartbeat dừng trong 60s → admin thấy agent offline. |
| Nhân viên cố sửa binary agent | Agent chạy user `ueba-agent` với `ProtectSystem=strict`; không write được `/usr/local/bin/agent`. Dù có thể, lần `agent update` tiếp theo sẽ thay bất kỳ binary nào bị tamper (SHA256 verify). |
| Nhân viên cố exfiltrate API key | `state.json` mode 0600; chỉ agent process đọc được. Key vô dụng nếu không có binary của agent. |
| Attacker trên network giả mạo server | TLS + cert verification. Với `--no-verify-tls`, agent sẽ trust BẤT KỲ cert nào (chỉ dev). |
| Attacker giả mạo agent | `X-API-Key` bắt buộc + SHA-256 hash server-side. Brute-force: 24 bytes entropy = 2^192 tổ hợp → không khả thi. |
| Attacker replay request cũ | Hầu hết endpoint idempotent (`ON CONFLICT(source_id) DO UPDATE`). `agent_id` mismatch giữa body và key bị reject. |
| Attacker DoS server bằng fake agent | Mỗi enrollment token one-time. Rate limiting (tương lai, qua nginx): max 10 enrollments / IP / giờ. |
| Attacker DoS server bằng log spam | Agent local buffer cap 100k events (FIFO eviction). Server normalizer xử lý batch size cố định. |
| Attacker compromise backend | JWT secret + DB credentials trong env vars / secrets manager (không trong code). Hạn chế truy cập host. Enable audit logging. Rotate secrets mỗi quý. |
| Compromised admin account | RBAC: chỉ `admin` quản lý accounts; `security_manager` có thể thu hồi agents nhưng không tạo account. Alert trên event `POST /api/admin/accounts`. |
| Compromised LLM API key | Mistral key đọc từ env, không bao giờ log. Restrict ở provider. Nếu nghi compromise: rotate ngay. |
| ML model bị poison | Model lưu trong `model_artifacts`, serve từ disk. Re-train chỉ từ pipeline trusted (CERT r4.2 sample + dữ liệu labeled của bạn). Verify model hash trước khi deploy. |

### 6.2 — Threat ngoài scope (cố ý, document nếu bạn có)

- **Insider với admin role**: governance / least-privilege controls.
- **Compromise host chạy backend**: assume-root-if-compromised.
- **Compromise database**: mã hóa khi lưu + access control + audit logging.
  Cân nhắc read replica cho analytics.
- **Network-level DDoS**: bảo vệ bằng CDN / WAF (Cloudflare, v.v.).
- **Side-channel attacks trên agent** (cache timing, v.v.): không trong scope.

### 6.3 — Checklist bảo mật trước khi lên production

- [ ] TLS cert từ trusted CA (Let's Encrypt hoặc corp CA).
- [ ] `JWT_SECRET` là random value 32+ bytes (KHÔNG dùng default
      `change-me-in-production`).
- [ ] `MISTRAL_API_KEY` được set với key thật, có rate limit.
- [ ] `DATABASE_URL` dùng password mạnh, không dùng default
      `ueba_password`.
- [ ] PostgreSQL listen trên `127.0.0.1` hoặc private subnet, không
      `0.0.0.0`.
- [ ] Firewall cho phép port 5173 (hoặc 443 sau reverse proxy) từ mạng
      nội bộ công ty — không public internet.
- [ ] `agent --no-verify-tls` không bao giờ dùng trong production.
- [ ] Agent binary được ký số (Windows Authenticode, macOS codesign,
      Linux sigstore/GPG) để nhân viên không bị SmartScreen / Gatekeeper
      warning.
- [ ] Log retention policy đã config (xem §5.6).
- [ ] Backup strategy cho PostgreSQL (pg_dump, WAL archiving).
- [ ] Incident response runbook cover: agent revoke flow, secret
      rotation, server rollback, data export cho forensic.

---

## 7. Compliance

### 7.1 — Việt Nam (PDPD — Nghị định 13/2023)

- **Cơ sở pháp lý**: lợi ích chính đáng (bảo mật hệ thống thông tin của
  công ty, lợi ích chính đáng của người sử dụng lao động trong việc giám
  sát tài sản của mình). Document điều này trong chính sách nội bộ về quyền
  riêng tư.
- **Quyền của chủ thể dữ liệu**: nhân viên có thể yêu cầu dữ liệu của họ
  qua admin (export từ `event_logs` và `alerts` filter theo `user_id`).
- **Chuyển dữ liệu xuyên biên giới**: nếu server host ngoài Việt Nam,
  đảm bảo dữ liệu ở quốc gia có bảo vệ đầy đủ (EU/US thường được
  chấp nhận cho B2B monitoring). Legal banner trên login page
  (`src/frontend/src/components/security/LegalBanner.tsx`) đã disclose
  điều này.

### 7.2 — EU (GDPR — cho bất kỳ nhân viên EU nào)

- **Article 88**: collective agreements cho monitoring tại nơi làm việc.
  Phối hợp với HR / legal.
- **DPIA (Data Protection Impact Assessment)**: bắt buộc cho systematic
  monitoring. Dùng tài liệu này làm input.
- **Storage limitation**: xem §5.6.

### 7.3 — Audit trail

Mọi API call log `user_id` (hoặc `agent_id`) + timestamp + IP. Bảng
`alerts` ghi `detected_at` và `updated_at` (gồm status transitions). Cho
forensic:
```sql
SELECT a.id, a.user_id, a.title, a.severity, a.status, a.detected_at, a.updated_at
FROM alerts a
WHERE a.user_id = 'ACM0001'
ORDER BY a.detected_at DESC;
```

---

## 8. Hạn chế đã biết & công việc tương lai

- [ ] JWT trong `localStorage` — chuyển sang `HttpOnly; Secure; SameSite=Strict` cookie.
- [ ] Không rate limiting trên login (brute force có thể). Thêm `slowapi` hoặc nginx `limit_req`.
- [ ] Không anomaly detection trên admin actions (ví dụ ai đó grant `admin` role).
- [ ] Không MFA cho admin accounts.
- [ ] Chưa code-signing cho agent binary (SmartScreen / Gatekeeper sẽ warn).
- [ ] LLM API key trong env (chuyển sang secret manager: AWS Secrets Manager,
  HashiCorp Vault).
- [ ] Agent không integrity-check binary của chính nó khi startup (có thể
  thêm `assert __file__ == /usr/local/bin/agent` để bắt tamper).
- [ ] Không auto-rotate secrets (admin phải tự rotate `JWT_SECRET` mỗi quý,
  sẽ invalidate mọi session).

---

## 9. Ứng phó sự cố

### 9.1 — Compromised agent host

```bash
# Trên server, thu hồi agent:
curl -X DELETE https://ueba.corp.example/api/agents/agent-abc123 \
    -H "Authorization: Bearer $ADMIN_TOKEN"

# Agent request tiếp theo sẽ trả 403. Để cũng stop local process:
ssh user@infected-host
sudo systemctl stop ueba-agent

# Audit xem gì đã gửi trong 24h qua:
SELECT timestamp, event_type, action, resource
FROM event_logs
WHERE device_id = (SELECT device_id FROM endpoint_agents WHERE agent_id = 'agent-abc123')
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

### 9.2 — Compromised admin account

```bash
# 1. Disable account (DB-level — nhanh nhất):
psql -c "UPDATE app_accounts SET is_active = FALSE WHERE email = 'admin@corp';"

# 2. Force logout (invalidate tất cả JWT): rotate JWT_SECRET và restart.
#    Mọi session hiện tại trở nên invalid.
kubectl set env deployment/ueba JWT_SECRET=<new-secret>   # hoặc tương đương

# 3. Audit recent admin actions (check application logs cho IP đó).
# 4. Tạo admin mới với MFA (khi đã implement).
```

### 9.3 — Compromised DB

- Rotate tất cả secrets (JWT, DB password, LLM key).
- Restore từ backup đã biết tốt.
- Audit `alerts` và `event_logs` mới nhất cho bất kỳ data exfiltration
  nào (ví dụ ai đó query all users' data qua API).

---
