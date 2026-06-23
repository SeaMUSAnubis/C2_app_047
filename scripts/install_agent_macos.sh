#!/usr/bin/env bash
# Install the UEBA endpoint agent on macOS via launchd.
#
# Usage:
#   sudo ./scripts/install_agent_macos.sh
#
# After install:
#   # 1. Enroll:
#   sudo -u ueba-agent /usr/local/bin/agent enroll \
#       --server-url https://ueba.corp.example \
#       --enrollment-token o47enr_xxxxxxxx \
#       --state-path /var/lib/ueba-agent/state.json
#
#   # 2. Start:
#   sudo launchctl load -w /Library/LaunchDaemons/com.vespionage.ueba-agent.plist
#
#   # 3. Logs:
#   tail -f /var/log/ueba-agent/agent.log
#   log show --predicate 'process == "agent"' --last 1h

set -euo pipefail

INSTALL_PREFIX="${UEBA_AGENT_INSTALL_PREFIX:-/opt/ueba-agent}"
STATE_DIR="/var/lib/ueba-agent"
LOG_DIR="/var/log/ueba-agent"
SERVICE_USER="_ueba-agent"
SERVICE_GROUP="_ueba-agent"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_NAME="com.vespionage.ueba-agent"
PLIST_PATH="/Library/LaunchDaemons/${PLIST_NAME}.plist"

log() { echo "[install-agent] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

[[ $EUID -eq 0 ]] || die "must run as root (use sudo)"

# 1. Check Python.
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    log "Python not found. Install via Homebrew: brew install python@3.12"
    log "Or set PYTHON_BIN=/path/to/python3 and re-run."
    exit 1
fi

# 2. Create system user (dscl is the legacy way but still works on Sonoma+).
if ! dscl . -read "/Users/${SERVICE_USER}" >/dev/null 2>&1; then
    log "Creating system user ${SERVICE_USER}"
    # Unique UID/GID in the system range (under 500).
    local uid=440
    while dscl . -list /Users UniqueID 2>/dev/null | awk '{print $2}' | grep -q "^${uid}$"; do
        uid=$((uid + 1))
    done
    dscl . create "/Users/${SERVICE_USER}" UniqueID "${uid}"
    dscl . create "/Users/${SERVICE_USER}" PrimaryGroupID "${uid}"
    dscl . create "/Users/${SERVICE_USER}" UserShell /usr/bin/false
    dscl . create "/Users/${SERVICE_USER}" RealName "UEBA Endpoint Agent"
    # Hide from login window.
    dscl . create "/Users/${SERVICE_USER}" IsHidden 1
fi

# 3. Create directories.
log "Creating ${STATE_DIR} and ${LOG_DIR}"
install -d -m 0750 -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" "${STATE_DIR}"
install -d -m 0750 -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" "${LOG_DIR}"

# 4. Install the agent into a venv.
log "Creating venv at ${INSTALL_PREFIX}/venv"
install -d -m 0755 "${INSTALL_PREFIX}"
"${PYTHON_BIN}" -m venv "${INSTALL_PREFIX}/venv"

"${INSTALL_PREFIX}/venv/bin/pip" install --quiet --upgrade pip wheel

if [[ -f "${REPO_DIR}/pyproject.toml" ]] && grep -q '^name = "ueba-agent"' "${REPO_DIR}/pyproject.toml"; then
    log "Installing from local source (${REPO_DIR})"
    "${INSTALL_PREFIX}/venv/bin/pip" install --quiet "${REPO_DIR}"
else
    log "Installing ueba-agent from PyPI"
    "${INSTALL_PREFIX}/venv/bin/pip" install --quiet "ueba-agent"
fi

ln -sf "${INSTALL_PREFIX}/venv/bin/agent" /usr/local/bin/agent

# 5. Install launchd plist.
log "Installing launchd plist at ${PLIST_PATH}"
install -m 0644 "${REPO_DIR}/packaging/${PLIST_NAME}.plist" "${PLIST_PATH}"
# launchd requires the plist to be owned by root.
chown root:wheel "${PLIST_PATH}"

# 6. Bootstrap the service. We do NOT load it now (admin must enroll first).
log "Bootstrap successful; service not loaded (enroll first)"

cat <<EOF

============================================================
  UEBA Endpoint Agent installed (macOS).
============================================================

Next steps:

  1. As the ${SERVICE_USER} user, enroll the agent using a one-time
     enrollment token from the admin UI:

       sudo -u ${SERVICE_USER} ${INSTALL_PREFIX}/venv/bin/agent enroll \\
           --server-url https://YOUR-SERVER \\
           --enrollment-token o47enr_xxxxxxxx \\
           --state-path ${STATE_DIR}/state.json

  2. Start the service:

       sudo launchctl load -w ${PLIST_PATH}

  3. Verify:

       sudo launchctl list | grep ueba-agent
       tail -f ${LOG_DIR}/agent.log
       log show --predicate 'process == "agent"' --last 10m

State directory : ${STATE_DIR}
Log directory   : ${LOG_DIR}
Install prefix  : ${INSTALL_PREFIX}
============================================================
EOF
