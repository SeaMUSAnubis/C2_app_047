# Engineering Journal

This is a running log of important engineering decisions, trade-offs, and
incidents. Newest at the top.

---

## 2026-06-22 — Phase 5 done (deployment + self-update)

### Decisions

- **Single-binary over per-OS installers for default**: per-OS installers
  (pip + systemd, pip + Task Scheduler, pip + launchd) are kept for IT
  teams that prefer source-level installs, but the curl-pipe pattern
  (`curl -sSL .../install.sh | sudo bash -s -- ...`) is the default
  for non-technical IT staff and for MDM push.
- **SHA256SUMS over GPG signatures**: GPG is the gold standard for
  binary distribution but adds a friction layer (need to publish a
  signing key, train users on `gpg --verify`). SHA256SUMS is good
  enough for a v0.1.0 — admin/IT can verify manually if they care.
  Future: add GPG signing in CI.
- **Self-update via in-process download** instead of a separate updater
  service. Simpler, but means the running binary needs network
  permissions. Acceptable for this threat model.
- **No HTTPS certificate pinning**: a future feature. For now, trust
  the OS's CA bundle (or pass `--ca-bundle` for internal CAs).

### Trade-offs

- **PyInstaller binary size = 60 MB**. The alternative (Nuitka) gives
  smaller binaries but is much harder to set up correctly across 3
  OSes. 60 MB is acceptable for a one-time download; the binary is
  reused for years.
- **Windows binary needs code-signing to avoid SmartScreen**. Out of
  scope for v0.1.0. Documented in `SECURITY.md` §6.3.

### Incidents

- None in this phase.

---

## 2026-06-22 — Phase 4 done (full collectors + UI)

### Decisions

- **5 new collectors are all "simplified" polling-based** (lsusb, /proc,
  /proc/net/tcp, etc.) rather than the real OS-level hooks (auditd,
  ReadDirectoryChangesW, ETW, inotify). Rationale: those require
  platform-specific setup that doesn't work in Docker for testing, and
  add significant complexity. The "simplified" versions are correct
  for the demo and good enough for many real deployments. Documented
  in `AGENT_DEPLOYMENT.md` and `ML_MODEL.md`.
- **`EmailCollector` is mostly programmatic, not auto-snooping
  `/var/log/mail.log`**. Reason: no portable way to do email monitoring
  on Windows without MAPI/Outlook integration (which requires COM).
  Programmatic API is the lowest common denominator.
- **Linux-only for most collectors**; Windows gets a stub that marks
  itself unhealthy. Reason: phase 4 was a demo milestone; full
  Windows support is v0.2.0 work.
- **Blocklist CRUD lives on the existing `/api/agents/blocklist`**
  (Phase 1) rather than a new admin route. The UI wraps it but the
  API is unchanged — Phase 1's REST contract held up.

### Trade-offs

- **Single `_run_lsusb` parser** (regex-like) is brittle to real-world
  variations. Mitigated with `: ID ` (colon-space) marker check.
- **Network collector reads /proc/net/tcp every 5s** — fine for
  < 100 connections, would need a conntrack listener for production
  scale. Out of scope for v0.1.0.

### Incidents

- **`_run_lsusb` test false positive**: parser matched "ID field"
  in a help-text line as a USB device. Fixed by requiring `: ID ` prefix.
- **IMAP poller `record_email` AttributeError**: refactored to use
  `_emit_read_event` helper that calls `self.emit` directly (was
  calling `self.record_email` which doesn't exist on the poller class).
- **TypeScript `AlertItem.user_id` doesn't exist**: the type uses
  camelCase (`user`); my code used snake_case. Fixed by using
  `al.user` with a fallback for backend data.
- **Frontend lint `react-hooks/set-state-in-effect`**: rule fires on
  `useEffect` → useCallback → setState. Disabled inline (same pattern
  as existing pages). Considered refactoring to in-line data fetch
  but the existing pattern is more reusable for refresh logic.

---

## 2026-06-22 — Phase 3 done (normalizer + ML scoring)

### Decisions

- **Normalizer runs in-process** in the FastAPI `lifespan` (asyncio
  background task), not as a separate worker. Simpler deployment, but
  the normalizer is now coupled to the API process. For HA, scale the
  whole API to 2+ replicas (normalizer is idempotent — see
  `OPERATIONS.md` §7.2).
- **ML scoring uses `demo_pipeline.extract_features` (simplified
  CERT pipeline) instead of the full preprocessing** (which is 800
  lines and requires the full CERT dataset). The 20 features are
  identical; the simplification is in batch / multi-user compute.
  Production should switch to the full pipeline; tracked in
  `ML_MODEL.md` §7.
- **Two separate tables for scores vs alerts**: `ml_anomaly_scores`
  records every score; `alerts` is a subset (only the high-risk ones).
  Rationale: ML analysis needs the full history; alert workflow only
  needs the high-risk ones. Keeps both tables small in their domain.
- **`agent update` mechanism via in-place binary replacement** with
  SHA256 verify. Rationale: avoids a separate updater service; the
  agent binary is the only thing that knows its current version.

### Trade-offs

- **OCSVM has no concept of "trust"**: a user who's been flagged
  false_positive 100 times still gets scored. Future: maintain a
  per-user whitelist to skip scoring.
- **No online learning**: model is static. New behavior patterns
  require full re-train. Future: incremental SVM (e.g. LASVM).
- **`ML_SCORING_ALERT_MIN_RISK=60` default is arbitrary**. Different
  orgs will want different thresholds. Documented; admin can tune.

### Incidents

- **OCSVM inference fails on first events for a user** (sparse feature
  vector). Mitigated: `_feature_frame` in `inference.py` defaults
  missing features to 0.0 with a WARNING log. Tunable in production
  via the model's metadata.
- **`_top_factors_from_features` returned "unusual_behavior_pattern"**
  even when an event had `filename=evil.exe` (executable copy). Root
  cause: `extract_features` looks at top-level `filename` column, but
  the normalized event had it in `raw_json`. Fix: flatten `raw` and
  `metadata` dicts before extracting features (same as
  `demo_pipeline.analyze` does).

---

## 2026-06-22 — Phase 1+2 done (server agent infra + agent core)

### Decisions

- **`endpoint_agents.api_key_hash` stores SHA-256, not bcrypt**: bcrypt
  is for low-entropy user-chosen passwords; the API key is 24 bytes
  of CSPRNG, so SHA-256 is the right hash (and is much faster). The
  "second preimage" attack model doesn't apply to high-entropy secrets.
- **Raw-logs use `INSERT ... ON CONFLICT(source_id) DO UPDATE`** for
  idempotency. The agent assigns `source_id` deterministically
  (collector + ms timestamp + namespace), so duplicate sends are
  safe to replay.
- **Agent buffer caps at 100k events** (FIFO eviction). At ~1 KB per
  event → ~100 MB on disk. Tunable via `--buffer-max-events`.
- **Agent uses httpx sync** in worker threads, not async. Simpler
  error handling; we get 3-5x throughput per worker thread, which is
  plenty for an agent emitting ~10 events/min.

### Trade-offs

- **Per-host buffer DB is per-OS SQLite**, not a unified format.
  Acceptable; SQLite is the most-tested SQL engine in the world.
- **No encryption of state.json / buffer.db on disk**. Mitigated by
  the system user (`ueba-agent`) with mode 0600 on state.json.
  Production: add LUKS/dm-crypt on the agent's data partition.

### Incidents

- **`wtmp` struct format wrong in test**: agent code used
  `hi32s4s32s256s24xhh2xqqq` (392 bytes) instead of
  `hi32s4s32s256s20xhh2xqqq` (384 bytes). Discovered when
  struct.unpack on a real wtmp file raised `struct.error`. Fixed and
  regression test added.
- **Agent `attempts` counter didn't increment**: UPDATE ran before
  SELECT, so SELECT returned the OLD count. Fix: SELECT after UPDATE.
- **Source_id duplicates across multiple records**: original code
  used `self._offset - WTMP_RECORD_SIZE` for every record, so two
  records in the same poll got the same source_id. Fix: pass
  rec_offset from caller, include inode in namespace.
- **Rotation detection missed `unlink + create`**: size-only check
  fails when the file is renamed. Fix: also check inode.
- **Linux file collector `chmod 0o000` test failed when running as
  root**: root bypasses permission checks. Fix: use `unlink + mkdir`
  instead of chmod to deny access.
- **httpx sync Client doesn't support ASGITransport** for in-process
  e2e tests. Fix: run tests against the live container instead
  (e2e test setup spins up a real backend).

---

## Earlier (pre-Phase 1)

See `WORKLOG.md` and `MVP_PROGRESS.md` for the chronological development
log leading up to v0.1.0.
