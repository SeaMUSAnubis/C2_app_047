# Nhật Ký Kỹ Thuật

Đây là log chạy về các quyết định kỹ thuật quan trọng, trade-off và sự cố.
Mới nhất ở trên cùng.

---

## 2026-06-22 — Phase 5 done (deployment + self-update)

### Quyết định

- **Single-binary thay vì per-OS installer làm default**: per-OS installer
  (pip + systemd, pip + Task Scheduler, pip + launchd) được giữ cho
  IT team thích source-level install, nhưng pattern curl-pipe
  (`curl -sSL .../install.sh | sudo bash -s -- ...`) là default cho
  IT staff không chuyên kỹ thuật và cho MDM push.
- **SHA256SUMS thay vì GPG signature**: GPG là tiêu chuẩn vàng cho binary
  distribution nhưng thêm friction (cần publish signing key, train user
  về `gpg --verify`). SHA256SUMS đủ tốt cho v0.1.0 — admin/IT có thể
  verify thủ công nếu muốn. Tương lai: thêm GPG signing trong CI.
- **Self-update qua in-process download** thay vì updater service riêng.
  Đơn giản hơn, nhưng binary đang chạy cần quyền network. Chấp nhận được
  cho threat model này.
- **Không HTTPS certificate pinning**: tính năng tương lai. Hiện tại, tin
  tưởng CA bundle của OS (hoặc truyền `--ca-bundle` cho internal CA).

### Trade-off

- **Kích thước PyInstaller binary = 60 MB**. Phương án thay thế (Nuitka)
  cho binary nhỏ hơn nhưng khó setup đúng qua 3 OS. 60 MB chấp nhận được
  cho download một lần; binary được dùng lại nhiều năm.
- **Windows binary cần code-signing để tránh SmartScreen**. Ngoài scope
  v0.1.0. Documented trong `SECURITY.md` §6.3.

### Sự cố

- Không có trong phase này.

---

## 2026-06-22 — Phase 4 done (full collectors + UI)

### Quyết định

- **5 collector mới đều là polling-based đơn giản hóa** (lsusb, /proc,
  /proc/net/tcp, v.v.) thay vì real OS-level hooks (auditd,
  ReadDirectoryChangesW, ETW, inotify). Lý do: những cái đó cần
  platform-specific setup không hoạt động trong Docker để test, và thêm
  complexity đáng kể. Phiên bản "đơn giản hóa" đúng cho demo và đủ
  tốt cho nhiều deployment thật. Documented trong `AGENT_DEPLOYMENT.md`
  và `ML_MODEL.md`.
- **`EmailCollector` chủ yếu là programmatic, không tự động snooping
  `/var/log/mail.log`**. Lý do: không có cách portable để monitor email
  trên Windows mà không có MAPI/Outlook integration (cần COM).
  Programmatic API là mẫu số chung thấp nhất.
- **Linux-only cho hầu hết collector**; Windows nhận stub mark
  unhealthy. Lý do: phase 4 là milestone demo; full Windows support là
  công việc v0.2.0.
- **Blocklist CRUD nằm trên `/api/agents/blocklist` hiện có** (Phase 1)
  thay vì admin route mới. UI wrap nó nhưng API không đổi — contract
  REST Phase 1 giữ vững.

### Trade-off

- **Single `_run_lsusb` parser** (kiểu regex) dễ vỡ với biến thể thật.
  Mitigated với marker check `: ID ` (colon-space).
- **Network collector đọc /proc/net/tcp mỗi 5s** — OK cho < 100
  connection, sẽ cần conntrack listener cho scale production. Ngoài
  scope v0.1.0.

### Sự cố

- **`_run_lsusb` test false positive**: parser match "ID field" trong
  help-text line như một USB device. Fix bằng cách yêu cầu prefix
  `: ID `.
- **IMAP poller `record_email` AttributeError**: refactor để dùng helper
  `_emit_read_event` gọi `self.emit` trực tiếp (đã gọi
  `self.record_email` không tồn tại trên poller class).
- **TypeScript `AlertItem.user_id` không tồn tại**: type dùng camelCase
  (`user`); code của tôi dùng snake_case. Fix bằng cách dùng `al.user`
  với fallback cho backend data.
- **Frontend lint `react-hooks/set-state-in-effect`**: rule bắn trên
  `useEffect` → useCallback → setState. Disabled inline (cùng pattern
  các trang hiện có dùng). Cân nhắc refactor sang in-line data fetch
  nhưng pattern hiện có tái sử dụng tốt hơn cho refresh logic.

---

## 2026-06-22 — Phase 3 done (normalizer + ML scoring)

### Quyết định

- **Normalizer chạy in-process** trong FastAPI `lifespan` (asyncio
  background task), không phải worker riêng. Deploy đơn giản hơn, nhưng
  normalizer giờ couple với API process. Cho HA, scale toàn bộ API
  lên 2+ replicas (normalizer idempotent — xem `OPERATIONS.md` §7.2).
- **ML scoring dùng `demo_pipeline.extract_features` (CERT pipeline
  đơn giản hóa)** thay vì full preprocessing (800 dòng và cần toàn bộ
  CERT dataset). 20 features giống nhau; sự đơn giản hóa nằm ở batch /
  multi-user compute. Production nên chuyển sang pipeline đầy đủ;
  tracked trong `ML_MODEL.md` §7.
- **Hai bảng riêng cho scores vs alerts**: `ml_anomaly_scores` ghi
  mọi score; `alerts` là subset (chỉ high-risk). Lý do: ML analysis
  cần full history; alert workflow chỉ cần high-risk. Giữ cả hai
  bảng nhỏ trong domain của chúng.
- **`agent update` mechanism qua in-place binary replacement** với
  SHA256 verify. Lý do: tránh updater service riêng; agent binary là
  thứ duy nhất biết version hiện tại của nó.

### Trade-off

- **OCSVM không có khái niệm "trust"**: user bị flag false_positive 100
  lần vẫn được score. Tương lai: duy trì per-user whitelist để skip
  scoring.
- **Không online learning**: model tĩnh. Pattern hành vi mới cần full
  re-train. Tương lai: incremental SVM (ví dụ LASVM).
- **`ML_SCORING_ALERT_MIN_RISK=60` default là tùy ý**. Các org khác
  nhau sẽ muốn threshold khác nhau. Documented; admin có thể tune.

### Sự cố

- **OCSVM inference fail trên events đầu tiên của user** (sparse feature
  vector). Mitigated: `_feature_frame` trong `inference.py` default
  missing features là 0.0 với WARNING log. Tunable trong production
  qua metadata của model.
- **`_top_factors_from_features` trả về "unusual_behavior_pattern"**
  ngay cả khi event có `filename=evil.exe` (executable copy). Root
  cause: `extract_features` nhìn top-level column `filename`, nhưng
  event đã normalize có nó trong `raw_json`. Fix: flatten dict `raw`
  và `metadata` trước khi extract features (giống
  `demo_pipeline.analyze` làm).

---

## 2026-06-22 — Phase 1+2 done (server agent infra + agent core)

### Quyết định

- **`endpoint_agents.api_key_hash` lưu SHA-256, không phải bcrypt**:
  bcrypt cho password user-chosen có entropy thấp; API key là 24 bytes
  CSPRNG, nên SHA-256 là hash đúng (và nhanh hơn nhiều). Attack model
  "second preimage" không áp dụng cho secret entropy cao.
- **Raw-logs dùng `INSERT ... ON CONFLICT(source_id) DO UPDATE`** cho
  idempotency. Agent gán `source_id` deterministic
  (collector + ms timestamp + namespace), nên gửi trùng an toàn để
  replay.
- **Agent buffer cap 100k events** (FIFO eviction). Ở ~1 KB / event →
  ~100 MB trên disk. Tunable qua `--buffer-max-events`.
- **Agent dùng httpx sync** trong worker thread, không async. Error
  handling đơn giản hơn; ta được 3-5x throughput / worker thread, đủ
  cho agent emit ~10 events/min.

### Trade-off

- **Per-host buffer DB là per-OS SQLite**, không phải format thống
  nhất. Chấp nhận được; SQLite là SQL engine được test nhiều nhất thế
  giới.
- **Không mã hóa state.json / buffer.db trên disk**. Mitigated bởi
  system user (`ueba-agent`) với mode 0600 trên state.json.
  Production: thêm LUKS/dm-crypt trên partition data của agent.

### Sự cố

- **`wtmp` struct format sai trong test**: agent code dùng
  `hi32s4s32s256s24xhh2xqqq` (392 bytes) thay vì
  `hi32s4s32s256s20xhh2xqqq` (384 bytes). Phát hiện khi struct.unpack
  trên file wtmp thật raise `struct.error`. Fix và thêm regression
  test.
- **Agent `attempts` counter không tăng**: UPDATE chạy trước SELECT, nên
  SELECT trả về count CŨ. Fix: SELECT sau UPDATE.
- **Source_id trùng giữa nhiều record**: code gốc dùng
  `self._offset - WTMP_RECORD_SIZE` cho mọi record, nên hai record
  trong cùng poll có cùng source_id. Fix: truyền rec_offset từ caller,
  include inode trong namespace.
- **Rotation detection miss `unlink + create`**: check chỉ size fail
  khi file bị rename. Fix: cũng check inode.
- **Linux file collector test `chmod 0o000` fail khi chạy root**:
  root bypass permission check. Fix: dùng `unlink + mkdir` thay vì chmod
  để deny access.
- **httpx sync Client không support ASGITransport** cho in-process
  e2e tests. Fix: chạy test với live container thay vì (e2e test setup
  spin up backend thật).

---

## Trước đó (trước Phase 1)

Xem `WORKLOG.md` và `MVP_PROGRESS.md` cho log phát triển theo thứ tự
thời gian dẫn đến v0.1.0.
