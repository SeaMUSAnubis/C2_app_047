# UEBA Endpoint Agent — Deployment Guide

This guide covers installing the agent on employee machines so it can collect
logon, file, USB, HTTP, email, process, and network events and stream them to
your central UEBA backend.

The agent is distributed as a **single binary** (PyInstaller, ~30-60 MB) that
has **no Python dependency on the target machine**. One binary per OS
(Linux, macOS, Windows) — install with a single `curl | bash` or
`iwr | iex` command.

## TL;DR — choose your path

| Path | One-liner | Best for |
|---|---|---|
| **[A. curl | bash](#a-install-via-curlrecommended)** | `curl -sSL .../install.sh \| sudo bash -s -- --server-url ... --enrollment-token ...` | **Default. Linux, macOS. No Python, no pip.** |
| **[B. iwr | iex](#b-install-via-powershell-windows)** | `iwr .../install.ps1 -useb \| iex` | Windows. No Python, no MSI. |
| **[C. pip install + systemd](#c-pip-install--systemd-linux)** | `sudo ./scripts/install_agent.sh` | Linux fleet where Python 3.10+ is managed by IT |
| **[D. pip install + Task Scheduler](#d-pip-install--task-scheduler-windows)** | `.\scripts\install_agent.ps1` | Windows fleet where Python is on the golden image |
| **[E. pip install + launchd](#e-pip-install--launchd-macos)** | `sudo ./scripts/install_agent_macos.sh` | macOS fleet where Python is on the golden image |

For most enterprise deployments: **A on Linux + macOS**, **B on Windows**.

---

---

## 1. Prepare the backend

Before installing on any employee machine, your UEBA backend must be running
and the admin must issue an enrollment token for that machine.

### 1.1 — Make sure the backend is reachable

The agent posts to `<server-url>/api/raw-logs/batch` over HTTPS. The URL must
be reachable from the employee machine.

- **Production**: `https://ueba.corp.example` (use a real cert).
- **Demo / internal**: `https://10.0.0.5:5173` (self-signed; pass `--no-verify-tls` to the agent).

### 1.2 — Issue an enrollment token

In the admin UI:
1. Log in as `admin@demo.com`.
2. Go to **Admin → Endpoint agents**.
3. Click **"Cấp enrollment token"**.
4. Copy the returned `o47enr_...` token. It expires in 2 hours by default.
5. Hand the token (and your server URL) to the person installing the agent.

You can also issue via API:
```bash
curl -X POST https://ueba.corp.example/api/agents/enrollment-tokens \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"expires_minutes": 120}'
```

### 1.3 — Publish the agent binaries (one-time per release)

Build the binaries on a build host and attach them to a GitHub Release:

```bash
# On any Linux/macOS/Windows build host
./scripts/build_agent_binary.sh --target all
gh release create v0.1.0 \
    dist/agent-linux-x86_64 \
    dist/agent-darwin-x86_64 dist/agent-darwin-arm64 \
    dist/agent-windows-x86_64.exe \
    dist/SHA256SUMS \
    --title "UEBA Agent v0.1.0" --notes "..."
```

The release assets live at:
```
https://github.com/<org>/<repo>/releases/latest/download/SHA256SUMS
https://github.com/<org>/<repo>/releases/latest/download/agent-linux-x86_64
https://github.com/<org>/<repo>/releases/latest/download/agent-darwin-arm64
https://github.com/<org>/<repo>/releases/latest/download/agent-windows-x86_64.exe
```

If you're self-hosting the artifacts (S3, GitLab, internal CDN), override
the base URL via the `UEBA_RELEASE_URL` env var.

Also publish the two bootstrap scripts (these can live in your repo, not
on the release page):
```
https://raw.githubusercontent.com/<org>/<repo>/main/scripts/install_via_curl.sh
https://raw.githubusercontent.com/<org>/<repo>/main/scripts/install_via_curl.ps1
```

### 1.4 — Optional: pre-create the device + user records

If you want the agent bound to a specific device + user from day 1, pass
`--device-id PC-1234 --assigned-user-id ACM0001` at enroll time. Otherwise
the admin can patch the agent later via `PATCH /api/agents/{id}`.

---

## 2. Install on each employee machine

### A. Install via curl (RECOMMENDED)

**No pip, no Python on the target.** Downloads a single ~60 MB binary,
verifies its SHA256 against `SHA256SUMS`, drops it at `/usr/local/bin/agent`,
registers a systemd/launchd service, and (optionally) enrolls and starts.

#### Linux / macOS

```bash
# 1. Non-interactive (typical IT push — token passed inline):
curl -sSL https://github.com/<org>/<repo>/releases/latest/download/install_via_curl.sh | \
    sudo bash -s -- \
    --server-url https://ueba.corp.example \
    --enrollment-token o47enr_xxxxxxxx

# 2. Per-machine (bind to a known device + user):
curl -sSL https://.../install_via_curl.sh | \
    sudo bash -s -- \
    --server-url https://ueba.corp.example \
    --enrollment-token o47enr_xxxxxxxx \
    --device-id PC-1234 \
    --assigned-user-id ACM0001

# 3. Without a token (enroll later manually):
curl -sSL https://.../install_via_curl.sh | sudo bash -s -- --no-start
```

What happens:
1. Auto-detects OS (linux/darwin) and arch (x86_64/arm64).
2. Downloads `SHA256SUMS` + matching binary from the release URL.
3. **Verifies SHA256** (refuses to install on mismatch — set
   `UEBA_SKIP_VERIFY=1` to override, not recommended).
4. Drops binary at `/usr/local/bin/agent` (mode 0755).
5. Creates `/var/lib/ueba-agent` (state) + `/var/log/ueba-agent` (logs).
6. Creates the `ueba-agent` system user.
7. Enrolls if `--enrollment-token` is given.
8. Writes + enables a systemd unit (Linux) or launchd plist (macOS).
9. Starts the service.

Environment overrides:
- `UEBA_RELEASE_URL` — point to a custom artifact host
  (e.g. `https://artifacts.corp.example/ueba-agent`).
- `UEBA_VERSION` — pin to a specific version (e.g. `0.1.0`); default: `latest`.
- `UEBA_INSTALL_DIR` — override install dir (default: `/usr/local/bin`).
- `UEBA_SKIP_VERIFY=1` — skip SHA256 check (NOT recommended).

Verify:
```bash
sudo systemctl status ueba-agent         # Linux
sudo launchctl list | grep ueba-agent    # macOS
sudo journalctl -u ueba-agent -f         # Linux logs
tail -f /var/log/ueba-agent/agent.log    # macOS logs
```

### B. Install via PowerShell (Windows)

**No pip, no MSI.** Downloads a single ~60 MB `.exe`, verifies SHA256,
drops it at `C:\Program Files\UEBA Agent\agent.exe`, registers a
Scheduled Task, and (optionally) enrolls and starts.

```powershell
# 1. Non-interactive (in an elevated PowerShell):
$body = @{
    ServerUrl        = 'https://ueba.corp.example'
    EnrollmentToken  = 'o47enr_xxxxxxxx'
}
iwr https://github.com/<org>/<repo>/releases/latest/download/install_via_curl.ps1 -useb | iex; `
    Install-UebaAgent @body

# 2. Minimal (no auto-enroll):
iwr .../install_via_curl.ps1 -useb | iex; Install-UebaAgent
```

What happens:
1. Detects Windows + x86_64.
2. Downloads `SHA256SUMS` + `agent-windows-x86_64.exe`.
3. Verifies SHA256.
4. Copies binary to `C:\Program Files\UEBA Agent\agent.exe`.
5. Creates `C:\ProgramData\UEBA Agent` (state + logs).
6. Enrolls if `-EnrollmentToken` is given.
7. Registers a Scheduled Task **"UEBA Agent"** (SYSTEM, AtStartup, RestartCount=5).
8. Starts the task.

Environment overrides: `$env:UEBA_RELEASE_URL`, `$env:UEBA_VERSION`,
`$env:UEBA_SKIP_VERIFY`.

Verify:
```powershell
Get-ScheduledTask -TaskName "UEBA Agent" | Get-ScheduledTaskInfo
Get-EventLog -LogName Application -Source "UEBA Agent" -Newest 20
```

### C. pip install + systemd (Linux)

Use this if you prefer source-level installs (or want to debug the agent
on a dev machine).

**Prerequisites**: Python 3.10+, root (sudo) access, systemd.

```bash
sudo ./scripts/install_agent.sh
sudo -u ueba-agent /opt/ueba-agent/venv/bin/agent enroll \
    --server-url https://ueba.corp.example \
    --enrollment-token o47enr_xxxxxxxx \
    --state-path /var/lib/ueba-agent/state.json
sudo systemctl start ueba-agent
```

### D. pip install + Task Scheduler (Windows)

**Prerequisites**: Python 3.10+ (install via `winget install Python.Python.3.12` if missing), Administrator PowerShell.

```powershell
.\scripts\install_agent.ps1
& "C:\Program Files\UEBA Agent\venv\Scripts\agent.exe" enroll `
    --server-url https://ueba.corp.example `
    --enrollment-token o47enr_xxxxxxxx `
    --state-path "C:\ProgramData\UEBA Agent\state.json"
Start-ScheduledTask -TaskName "UEBA Agent"
```

### E. pip install + launchd (macOS)

**Prerequisites**: Python 3.10+ (install via `brew install python@3.12` if missing), root (sudo) access.

```bash
sudo ./scripts/install_agent_macos.sh
sudo -u _ueba-agent /opt/ueba-agent/venv/bin/agent enroll \
    --server-url https://ueba.corp.example \
    --enrollment-token o47enr_xxxxxxxx \
    --state-path /var/lib/ueba-agent/state.json
sudo launchctl load -w /Library/LaunchDaemons/com.vespionage.ueba-agent.plist
```

---

## 3. Verify it's working

After install + enroll + start, you should see within 30 seconds:

### Backend side
- New row in `endpoint_agents` table with the agent's hostname.
- Heartbeat updates `last_heartbeat` to "now" every 60s.
- First batch of raw logs (from `logon` collector if Linux) appears in
  `raw_user_logs` within 10-30s of login activity.
- Within 10-30s of those logs being inserted, the normalizer converts them
  to `event_logs` and triggers ML scoring.

### Admin UI
- The agent shows up in **Admin → Endpoint agents** with status `active`.
- Click into the detail page → you should see:
  - `policy_version` = 10 (or whatever the server has).
  - `last_heartbeat` = "5s ago" (rolling).
  - `last_config_pull` = "3 phút trước" (every 5 minutes).
  - Recent alerts from the assigned user (if any).

### Agent side
- Linux: `journalctl -u ueba-agent -f` shows the legal banner at start,
  then periodic `DEBUG` lines from collectors.
- Windows: `Get-EventLog -LogName Application -Source "UEBA Agent" -Newest 20`.
- macOS: `log show --predicate 'process == "agent"' --last 10m`.

---

## 4. Update the agent

The agent supports **self-update from the binary** (no re-install needed).
The currently-running binary downloads a newer version from the release
URL, verifies SHA256, replaces itself, and (on Linux/macOS) asks the
supervisor to restart.

```bash
# Update to the latest release (default):
sudo /usr/local/bin/agent update

# Update to a specific version:
sudo /usr/local/bin/agent update --version 0.2.0

# Check what's available without replacing:
/usr/local/bin/agent update --dry-run

# Skip SHA256 check (NOT recommended):
/usr/local/bin/agent update --skip-verify
```

After update on Linux/macOS, the systemd unit / launchd plist restarts the
agent under the new binary. On Windows, the running `.exe` is held open
by the OS, so the new binary is staged as `<bin>.new`; a one-shot
scheduled task swaps it on next start.

To roll out an update to the whole fleet, just push a new GitHub Release;
IT staff can then run the update on each machine, OR install a
`systemd timer` / `cron job` that calls `agent update` periodically.

### Alternative: from source (dev / IT-managed)

```bash
cd /path/to/ueba-endpoint-monitoring
git pull
sudo /opt/ueba-agent/venv/bin/pip install --quiet --upgrade .
sudo systemctl restart ueba-agent
```

### Alternative: from a new wheel

```bash
sudo /opt/ueba-agent/venv/bin/pip install --quiet --upgrade ueba-agent==0.2.0
sudo systemctl restart ueba-agent
```

---

## 5. Roll out to a fleet

### Small (≤ 50 machines) — manual
1. Run `install_agent.sh` on each machine via SSH / Ansible / RDP.
2. Manually enroll each one with a per-machine token from the admin UI.

### Medium (50-500) — scriptable
1. Issue a token for each machine (or one token, reused — works because
   the same agent_id gets re-registered; the server overwrites).
2. Distribute the install script via Ansible/Salt/Chef/Puppet, with the
   server URL and token passed as parameters.
3. Verify each agent appears in the admin UI within 1 minute.

### Large (500+) — binary + MDM
1. Build a single binary per OS via `scripts/build_agent_binary.sh`.
2. Push via MDM (Intune, Jamf, Workspace ONE, etc.) as a managed app.
3. The first-run experience can be:
   - Bundle a pre-filled `state.json` (skip enroll; just deploy).
   - Or have the user run a one-time guided enroll on first login.

### MSI / .pkg (Windows / macOS) — proper enterprise
For best UX on Windows, wrap the binary in an MSI (use WiX Toolset).
For macOS, wrap in a `.pkg` (use `pkgbuild` + `productbuild`).
Sign with your enterprise code-signing cert to avoid SmartScreen / Gatekeeper
warnings.

---

## 6. Operations

### 6.1 — Update the blocklist (centrally)

The blocklist is managed via the admin UI or API and pushed to all agents
within `config_pull_interval` (5 minutes by default). New domains are picked
up automatically.

```bash
# Add a domain
curl -X POST https://ueba.corp.example/api/agents/blocklist \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pattern":"malicious-c2.example","pattern_type":"domain","category":"c2"}'
```

### 6.2 — Disable an agent

When an employee leaves:
```bash
curl -X DELETE https://ueba.corp.example/api/agents/agent-abc123 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

The agent will get 403 on its next heartbeat / log upload and stop sending
events. To fully stop the process:
```bash
sudo systemctl stop ueba-agent   # Linux
Stop-ScheduledTask -TaskName "UEBA Agent"   # Windows
sudo launchctl unload /Library/LaunchDaemons/com.vespionage.ueba-agent.plist   # macOS
```

### 6.3 — Re-enroll a machine (lost state file)

If the state file is lost or corrupted, the agent will get 401 / 403 from
the server. To re-enroll:
1. Stop the service.
2. Delete the old state file.
3. Issue a new token from the admin UI.
4. Run `agent enroll ...` again.
5. Start the service.

### 6.4 — Stale agents (no heartbeat)

Agents that haven't sent a heartbeat in `agent_heartbeat_timeout_minutes`
(default 10) are marked `offline` automatically. To manually trigger:
```bash
curl -X POST https://ueba.corp.example/api/admin/agents/mark-stale \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Or click **"Đánh dấu quá hạn"** in **Admin → Endpoint agents**.

---

## 7. Compliance & legal

The agent prints a legal banner on every startup (Nghị định 13/2023/PDPD +
GDPR Art. 88). The banner explains what is collected:

> Logon / logoff events, USB device (connect/disconnect), file access, web
> browsing / DNS, running processes, network connections, email activity.
> Collection is used solely for security and compliance.

**Do not install on personal devices.** Only on company-issued hardware.
Surface the legal banner to end users in your company's acceptable-use policy.

The login page also shows a `LegalBanner` component (Phase 4) so admin /
analyst users see the same disclosure when they access the dashboard.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `agent enroll` fails with "token not found" | Token expired (default 2h) | Re-issue from admin UI |
| `agent enroll` fails with "device_id violates FK" | The user/device record doesn't exist yet | Either omit `--device-id`, or create the records first via `POST /api/devices` and `POST /api/users` |
| Service starts then immediately stops | `journalctl` shows "no state file" | Run `agent enroll` first |
| Heartbeat returns 403 | Agent was revoked from admin UI | Re-enroll with a new token |
| Heartbeat returns 401 | `api_key` got corrupted or rotated | Re-enroll |
| Logs show "No such file or directory: /var/log/wtmp" | Expected on non-Linux or container env | The logon collector will mark itself unhealthy but the rest still works |
| High CPU on Linux | wtmp file is large; collector polls every 5s | Default is fine; the offset is persisted so it doesn't re-read |
| Backend doesn't see the agent | Server URL wrong, or DNS / firewall | Test with `curl <server-url>/api/health` from the agent host |
| `pip install` fails on Linux with "externally-managed-environment" | PEP 668 (Debian 12+, Fedora 38+) | The install script uses a venv, so this should not happen. If you see it, check `PYTHON_BIN` env var. |
| Windows SmartScreen blocks the binary | Unsigned executable | Code-sign with your enterprise cert, or distribute via MDM that trusts your cert |
