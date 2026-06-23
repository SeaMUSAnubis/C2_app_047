#!/usr/bin/env bash
# Install the UEBA endpoint agent on Linux.
#
# This script:
#   1. Validates it's run as root.
#   2. Creates the `ueba-agent` system user (no login, no home).
#   3. Installs the agent into a Python venv at /opt/ueba-agent.
#   4. Drops the systemd unit file at /etc/systemd/system/ueba-agent.service.
#   5. Reloads systemd and enables the service (does NOT start it — you must
#      enroll first to get an agent_id + api_key, then start).
#
# Usage:
#   sudo ./scripts/install_agent.sh
#
# After install:
#   # 1. Enroll with a token from the admin UI:
#   sudo -u ueba-agent /opt/ueba-agent/venv/bin/agent enroll \
#       --server-url https://ueba.corp.example \
#       --enrollment-token o47enr_xxxxxxxx \
#       --state-path /var/lib/ueba-agent/state.json
#
#   # 2. Start the service:
#   sudo systemctl enable --now ueba-agent
#
#   # 3. Check status:
#   sudo systemctl status ueba-agent
#   sudo journalctl -u ueba-agent -f

set -euo pipefail

# --- Configuration ---------------------------------------------------------

PACKAGE_NAME="ueba-agent"
INSTALL_PREFIX="${UEBA_AGENT_INSTALL_PREFIX:-/opt/ueba-agent}"
STATE_DIR="/var/lib/ueba-agent"
LOG_DIR="/var/log/ueba-agent"
SERVICE_USER="ueba-agent"
SERVICE_GROUP="ueba-agent"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Helpers ---------------------------------------------------------------

log() { echo "[install-agent] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

require_root() {
    [[ $EUID -eq 0 ]] || die "must run as root (use sudo)"
}

detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "${ID:-unknown}"
    elif command -v lsb_release >/dev/null 2>&1; then
        lsb_release -is | tr '[:upper:]' '[:lower:]'
    else
        echo "unknown"
    fi
}

# --- Main ------------------------------------------------------------------

require_root

log "Detected distro: $(detect_distro)"
log "Install prefix:  ${INSTALL_PREFIX}"
log "State dir:       ${STATE_DIR}"
log "Log dir:         ${LOG_DIR}"

# 1. Create the system user (no login, no home).
if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
    log "Creating system user ${SERVICE_USER}"
    if command -v useradd >/dev/null 2>&1; then
        useradd --system \
                --no-create-home \
                --shell /usr/sbin/nologin \
                --comment "UEBA Endpoint Agent" \
                "${SERVICE_USER}"
    elif command -v adduser >/dev/null 2>&1; then
        adduser --system \
                --no-create-home \
                --shell /usr/sbin/nologin \
                --group \
                "${SERVICE_USER}"
    else
        die "neither useradd nor adduser found"
    fi
fi

# 2. Create runtime directories.
log "Creating ${STATE_DIR} and ${LOG_DIR}"
install -d -m 0750 -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" "${STATE_DIR}"
install -d -m 0750 -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" "${LOG_DIR}"

# 3. Install the agent into a venv.
log "Creating venv at ${INSTALL_PREFIX}/venv"
install -d -m 0755 "${INSTALL_PREFIX}"
"${PYTHON_BIN}" -m venv "${INSTALL_PREFIX}/venv"

log "Upgrading pip + wheel"
"${INSTALL_PREFIX}/venv/bin/pip" install --quiet --upgrade pip wheel

# Prefer local source install (editable) if we're running from a repo checkout.
# Otherwise fall back to the published package.
if [[ -f "${REPO_DIR}/pyproject.toml" ]] && grep -q '^name = "ueba-agent"' "${REPO_DIR}/pyproject.toml"; then
    log "Installing from local source (${REPO_DIR})"
    "${INSTALL_PREFIX}/venv/bin/pip" install --quiet "${REPO_DIR}"
else
    log "Installing ${PACKAGE_NAME} from PyPI"
    "${INSTALL_PREFIX}/venv/bin/pip" install --quiet "${PACKAGE_NAME}"
fi

# Make the `agent` command visible on PATH for the service user.
install -d -m 0755 /usr/local/bin
ln -sf "${INSTALL_PREFIX}/venv/bin/agent" /usr/local/bin/agent

# 4. Install the systemd unit file.
if [[ -d /etc/systemd/system ]]; then
    log "Installing systemd unit"
    install -m 0644 \
        "${REPO_DIR}/packaging/ueba-agent.service" \
        /etc/systemd/system/ueba-agent.service
    systemctl daemon-reload
    systemctl enable ueba-agent.service
    log "Service enabled (NOT started — enroll first)"
else
    log "systemd not detected; skipping service install. Run the agent manually:"
    log "    ${INSTALL_PREFIX}/venv/bin/agent run \\"
    log "        --state-path ${STATE_DIR}/state.json \\"
    log "        --buffer-path ${STATE_DIR}/buffer.db \\"
    log "        --log-path ${LOG_DIR}/agent.log"
fi

cat <<EOF

============================================================
  UEBA Endpoint Agent installed.
============================================================

Next steps:

  1. As the ${SERVICE_USER} user, enroll the agent using a one-time
     enrollment token from the admin UI (Admin → Endpoint agents →
     "Cấp enrollment token"):

       sudo -u ${SERVICE_USER} ${INSTALL_PREFIX}/venv/bin/agent enroll \\
           --server-url https://YOUR-SERVER \\
           --enrollment-token o47enr_xxxxxxxx \\
           --state-path ${STATE_DIR}/state.json

  2. Start the service:

       sudo systemctl start ueba-agent

  3. Verify:

       sudo systemctl status ueba-agent
       sudo journalctl -u ueba-agent -f
       sudo -u ${SERVICE_USER} ${INSTALL_PREFIX}/venv/bin/agent version

State directory : ${STATE_DIR}
Log directory   : ${LOG_DIR}
Install prefix  : ${INSTALL_PREFIX}
============================================================
EOF
