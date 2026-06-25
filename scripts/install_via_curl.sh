#!/usr/bin/env bash
# Install the UEBA agent from a GitHub release (or any HTTPS artifact host).
# This script is meant to be piped from curl:
#
#   curl -sSL https://github.com/vespionage/ueba-endpoint-monitoring/releases/latest/download/install.sh | sudo bash -s -- \
#       --server-url https://ueba.corp.example \
#       --enrollment-token o47enr_xxx
#
# It will:
#   1. Detect OS (linux/macos) + arch (x86_64/arm64).
#   2. Download the matching binary + SHA256SUMS to a temp dir.
#   3. Verify the checksum (required — refuses to install on mismatch).
#   4. Drop the binary at /usr/local/bin/agent.
#   5. Register a system service (systemd on Linux, launchd on macOS).
#   6. Optionally enroll (if --enrollment-token given) and start.
#
# Idempotent: running twice updates the binary in place.
# Tested on: Ubuntu 20.04+, Debian 11+, RHEL 9+, macOS 12+ (Intel + Apple Silicon).
#
# Environment overrides:
#   UEBA_RELEASE_URL  — base URL (default: GitHub releases/latest/download)
#   UEBA_VERSION      — pin to a specific version (default: "latest")
#   UEBA_INSTALL_DIR  — where to drop the binary (default: /usr/local/bin)
#   UEBA_SKIP_VERIFY  — set to 1 to skip SHA256 check (NOT recommended)

set -euo pipefail

# --- Defaults --------------------------------------------------------------

RELEASE_URL_DEFAULT="https://github.com/vespionage/ueba-endpoint-monitoring/releases/latest/download"
RELEASE_URL="${UEBA_RELEASE_URL:-${RELEASE_URL_DEFAULT}}"
VERSION="${UEBA_VERSION:-latest}"
INSTALL_DIR="${UEBA_INSTALL_DIR:-/usr/local/bin}"
STATE_DIR_DEFAULT="/var/lib/ueba-agent"
STATE_DIR="${UEBA_STATE_DIR:-${STATE_DIR_DEFAULT}}"
LOG_DIR="/var/log/ueba-agent"
SERVICE_USER="ueba-agent"
SERVER_URL=""
ENROLLMENT_TOKEN=""
DEVICE_ID=""
ASSIGNED_USER_ID=""

# --- CLI -------------------------------------------------------------------

usage() {
    cat <<EOF
Usage: install.sh [OPTIONS]

Options:
  --server-url URL          UEBA backend URL (required for enroll)
  --enrollment-token TOKEN  one-time enrollment token from admin UI
  --device-id ID            bind agent to a specific device record
  --assigned-user-id ID     bind agent to a specific user record
  --state-dir DIR           where state.json + buffer.db live (default: ${STATE_DIR_DEFAULT})
  --no-start                install but don't start the service
  --no-service              don't register a system service
  -h, --help                show this help

Environment:
  UEBA_RELEASE_URL   override the artifact base URL
  UEBA_VERSION       pin to a specific version (e.g. "0.1.0"); default: latest
  UEBA_INSTALL_DIR   override install dir (default: /usr/local/bin)
  UEBA_SKIP_VERIFY   set to 1 to skip SHA256 check (NOT recommended)

Examples:
  # Interactive: prompts for token
  curl -sSL \$UEBA_RELEASE_URL/install.sh | sudo bash

  # Non-interactive (typical IT push):
  curl -sSL \$UEBA_RELEASE_URL/install.sh | sudo bash -s -- \\
      --server-url https://ueba.corp.example \\
      --enrollment-token o47enr_xxxxxxxx

  # Per-machine (bind to known device + user):
  curl -sSL \$UEBA_RELEASE_URL/install.sh | sudo bash -s -- \\
      --server-url https://ueba.corp.example \\
      --enrollment-token o47enr_xxxxxxxx \\
      --device-id PC-1234 \\
      --assigned-user-id ACM0001
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server-url)         SERVER_URL="$2"; shift 2 ;;
        --enrollment-token)   ENROLLMENT_TOKEN="$2"; shift 2 ;;
        --device-id)          DEVICE_ID="$2"; shift 2 ;;
        --assigned-user-id)   ASSIGNED_USER_ID="$2"; shift 2 ;;
        --state-dir)          STATE_DIR="$2"; shift 2 ;;
        --no-start)           NO_START=1; shift ;;
        --no-service)         NO_SERVICE=1; shift ;;
        -h|--help)            usage; exit 0 ;;
        *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
    esac
done

# --- Pre-flight -----------------------------------------------------------

log()  { echo "[install] $*" >&2; }
die()  { log "ERROR: $*"; exit 1; }

[[ $EUID -eq 0 ]] || die "must run as root (re-run with sudo; the curl|bash pattern requires root to install system services)"

command -v curl >/dev/null || die "curl not found — install with: apt install curl / brew install curl"
command -v sha256sum >/dev/null || command -v shasum >/dev/null \
    || die "neither sha256sum nor shasum found"

# --- Detect OS + arch -----------------------------------------------------

OS_NAME=""
case "$(uname -s)" in
    Linux*)  OS_NAME="linux" ;;
    Darwin*) OS_NAME="darwin" ;;
    *)       die "unsupported OS: $(uname -s). This script handles Linux + macOS. For Windows, use install.ps1" ;;
esac

ARCH_NAME=""
case "$(uname -m)" in
    x86_64|amd64)    ARCH_NAME="x86_64" ;;
    aarch64|arm64)   ARCH_NAME="arm64" ;;
    *)               die "unsupported arch: $(uname -m)" ;;
esac

BINARY_NAME="agent-${OS_NAME}-${ARCH_NAME}"
EXT=""
[[ "$OS_NAME" == "windows" ]] && EXT=".exe"   # never reached on Linux/macOS, kept for symmetry

log "Detected: ${OS_NAME} / ${ARCH_NAME}"
log "Release URL: ${RELEASE_URL}"
log "Version:     ${VERSION}"

# --- Download + verify ----------------------------------------------------

TMP_DIR="$(mktemp -d -t ueba-agent-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

DOWNLOAD_URL_BASE="${RELEASE_URL}"
# If user passed a "version" like "v0.1.0" or "0.1.0", expand the URL.
if [[ "${VERSION}" != "latest" ]]; then
    case "${RELEASE_URL}" in
        *"/releases/latest/download"*)
            DOWNLOAD_URL_BASE="${RELEASE_URL%/releases/latest/download}/releases/download/v${VERSION#v}"
            ;;
    esac
fi

log "Downloading SHA256SUMS"
if ! curl --fail --silent --show-error --location --retry 3 --retry-delay 2 \
        -o "${TMP_DIR}/SHA256SUMS" \
        "${DOWNLOAD_URL_BASE}/SHA256SUMS"; then
    die "failed to download SHA256SUMS from ${DOWNLOAD_URL_BASE}/SHA256SUMS"
fi

log "Downloading ${BINARY_NAME}"
if ! curl --fail --silent --show-error --location --retry 3 --retry-delay 2 \
        -o "${TMP_DIR}/${BINARY_NAME}" \
        "${DOWNLOAD_URL_BASE}/${BINARY_NAME}"; then
    die "failed to download ${BINARY_NAME} from ${DOWNLOAD_URL_BASE}/${BINARY_NAME}"
fi

# Verify checksum (always — refuse to install on mismatch).
EXPECTED="$(grep -E "[[:space:]]${BINARY_NAME}\$" "${TMP_DIR}/SHA256SUMS" | awk '{print $1}' || true)"
[[ -n "${EXPECTED}" ]] || die "${BINARY_NAME} not found in SHA256SUMS — wrong release artifact?"

ACTUAL=""
if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL="$(sha256sum "${TMP_DIR}/${BINARY_NAME}" | awk '{print $1}')"
else
    ACTUAL="$(shasum -a 256 "${TMP_DIR}/${BINARY_NAME}" | awk '{print $1}')"
fi

if [[ "${EXPECTED}" != "${ACTUAL}" ]]; then
    if [[ "${UEBA_SKIP_VERIFY:-0}" == "1" ]]; then
        log "WARN: SHA256 mismatch (expected=${EXPECTED:0:16}… actual=${ACTUAL:0:16}…) — UEBA_SKIP_VERIFY=1, continuing"
    else
        die "SHA256 mismatch! expected=${EXPECTED} actual=${ACTUAL} — refusing to install. Set UEBA_SKIP_VERIFY=1 to override (NOT recommended)."
    fi
fi
log "SHA256 verified: ${ACTUAL:0:16}…"

chmod +x "${TMP_DIR}/${BINARY_NAME}"

# --- Install binary --------------------------------------------------------

install -d -m 0755 "${INSTALL_DIR}"
install -m 0755 "${TMP_DIR}/${BINARY_NAME}" "${INSTALL_DIR}/agent"
log "Installed binary to ${INSTALL_DIR}/agent"

# --- Runtime dirs + user ---------------------------------------------------

install -d -m 0750 "${STATE_DIR}"
install -d -m 0750 "${LOG_DIR}"

if [[ "${OS_NAME}" == "linux" ]]; then
    if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
        log "Creating system user ${SERVICE_USER}"
        useradd --system --no-create-home --shell /usr/sbin/nologin --comment "UEBA Endpoint Agent" "${SERVICE_USER}"
    fi
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${STATE_DIR}" "${LOG_DIR}"
elif [[ "${OS_NAME}" == "darwin" ]]; then
    if ! dscl . -read "/Users/_${SERVICE_USER}" >/dev/null 2>&1; then
        log "Creating system user _${SERVICE_USER}"
        local uid=440
        while dscl . -list /Users UniqueID 2>/dev/null | awk '{print $2}' | grep -q "^${uid}$"; do
            uid=$((uid + 1))
        done
        dscl . create "/Users/_${SERVICE_USER}" UniqueID "${uid}"
        dscl . create "/Users/_${SERVICE_USER}" PrimaryGroupID "${uid}"
        dscl . create "/Users/_${SERVICE_USER}" UserShell /usr/bin/false
        dscl . create "/Users/_${SERVICE_USER}" RealName "UEBA Endpoint Agent"
        dscl . create "/Users/_${SERVICE_USER}" IsHidden 1
        SERVICE_USER="_${SERVICE_USER}"
    else
        SERVICE_USER="_${SERVICE_USER}"
    fi
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${STATE_DIR}" "${LOG_DIR}"
fi

# --- Optional: enroll ------------------------------------------------------

if [[ -n "${ENROLLMENT_TOKEN}" && -n "${SERVER_URL}" ]]; then
    log "Enrolling with ${SERVER_URL}"
    ARGS=(
        enroll
        --server-url "${SERVER_URL}"
        --enrollment-token "${ENROLLMENT_TOKEN}"
        --state-path "${STATE_DIR}/state.json"
    )
    [[ -n "${DEVICE_ID}" ]]        && ARGS+=(--device-id "${DEVICE_ID}")
    [[ -n "${ASSIGNED_USER_ID}" ]] && ARGS+=(--assigned-user-id "${ASSIGNED_USER_ID}")
    if sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/agent" "${ARGS[@]}"; then
        log "Enrolled. agent_id stored in ${STATE_DIR}/state.json"
    else
        log "WARN: enroll failed (token may be expired). Run it manually later:"
        log "  sudo -u ${SERVICE_USER} ${INSTALL_DIR}/agent enroll --server-url ... --enrollment-token ... --state-path ${STATE_DIR}/state.json"
    fi
fi

# --- Register + start service ---------------------------------------------

if [[ "${NO_SERVICE:-0}" == "1" ]]; then
    log "Skipping service registration (--no-service)"
else
    if [[ "${OS_NAME}" == "linux" ]]; then
        # The system unit file is shipped in the binary's tarball, but since
        # we're using a one-file binary, we write the unit here.
        UNIT_FILE="/etc/systemd/system/ueba-agent.service"
        log "Installing systemd unit at ${UNIT_FILE}"
        cat > "${UNIT_FILE}" <<EOF
[Unit]
Description=UEBA Endpoint Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${STATE_DIR}
StateDirectory=ueba-agent
LogsDirectory=ueba-agent
ExecStart=${INSTALL_DIR}/agent run \\
    --state-path ${STATE_DIR}/state.json \\
    --buffer-path ${STATE_DIR}/buffer.db \\
    --log-path ${LOG_DIR}/agent.log
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=${STATE_DIR} ${LOG_DIR}
ReadOnlyPaths=/var/log/wtmp
RestrictSUIDSGID=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_NETLINK
SystemCallArchitectures=native
MemoryMax=512M
TasksMax=64
KillSignal=SIGTERM
TimeoutStopSec=30
FinalKillSignal=SIGKILL

[Install]
WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        if [[ "${NO_START:-0}" != "1" ]]; then
            systemctl enable ueba-agent.service
            systemctl restart ueba-agent.service
            log "Service started. Tail logs with: journalctl -u ueba-agent -f"
        else
            systemctl enable ueba-agent.service
            log "Service enabled but not started (--no-start)"
        fi
    elif [[ "${OS_NAME}" == "darwin" ]]; then
        PLIST="/Library/LaunchDaemons/com.vespionage.ueba-agent.plist"
        log "Installing launchd plist at ${PLIST}"
        cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.vespionage.ueba-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>${INSTALL_DIR}/agent</string>
        <string>run</string>
        <string>--state-path</string><string>${STATE_DIR}/state.json</string>
        <string>--buffer-path</string><string>${STATE_DIR}/buffer.db</string>
        <string>--log-path</string><string>${LOG_DIR}/agent.log</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><dict><key>Crashed</key><true/></dict>
    <key>ThrottleInterval</key><integer>10</integer>
    <key>ProcessType</key><string>Background</string>
    <key>StandardOutPath</key><string>${LOG_DIR}/agent.out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/agent.err.log</string>
    <key>WorkingDirectory</key><string>${STATE_DIR}</string>
    <key>UserName</key><string>${SERVICE_USER}</string>
</dict>
</plist>
EOF
        chown root:wheel "${PLIST}"
        chmod 0644 "${PLIST}"
        if [[ "${NO_START:-0}" != "1" ]]; then
            launchctl unload "${PLIST}" 2>/dev/null || true
            launchctl load -w "${PLIST}"
            log "Service started. View logs: tail -f ${LOG_DIR}/agent.out.log"
        fi
    fi
fi

cat <<EOF

============================================================
  UEBA Endpoint Agent installed (binary, no pip needed).
============================================================

Binary path  : ${INSTALL_DIR}/agent
State path   : ${STATE_DIR}/state.json
Buffer DB    : ${STATE_DIR}/buffer.db
Logs         : ${LOG_DIR}/agent.log
Version      : ${VERSION}
Source       : ${RELEASE_URL}

Next steps (if you didn't pass --enrollment-token):
  sudo -u ${SERVICE_USER} ${INSTALL_DIR}/agent enroll \\
      --server-url https://YOUR-SERVER \\
      --enrollment-token o47enr_xxxxxxxx \\
      --state-path ${STATE_DIR}/state.json

Update to a newer version later:
  ${INSTALL_DIR}/agent update
  (or re-run this install.sh — it overwrites the binary in place)

Uninstall:
  ${INSTALL_DIR}/agent update --uninstall
============================================================
EOF
