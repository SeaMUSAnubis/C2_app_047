#!/usr/bin/env bash
# Uninstall the UEBA endpoint agent on Linux.
#
# - Stops and disables the systemd service
# - Removes the service unit file
# - Removes /opt/ueba-agent (the venv + install prefix)
# - Optionally removes state and log directories (asks first)
# - Leaves the `ueba-agent` system user in place (in case other apps use it)

set -euo pipefail

INSTALL_PREFIX="${UEBA_AGENT_INSTALL_PREFIX:-/opt/ueba-agent}"
STATE_DIR="/var/lib/ueba-agent"
LOG_DIR="/var/log/ueba-agent"

[[ $EUID -eq 0 ]] || { echo "must run as root (use sudo)" >&2; exit 1; }

if [[ -d /etc/systemd/system ]] && systemctl list-unit-files 2>/dev/null | grep -q ueba-agent.service; then
    echo "[uninstall] stopping + disabling ueba-agent.service"
    systemctl stop ueba-agent.service 2>/dev/null || true
    systemctl disable ueba-agent.service 2>/dev/null || true
    rm -f /etc/systemd/system/ueba-agent.service
    systemctl daemon-reload
fi

if [[ -e /usr/local/bin/agent ]]; then
    echo "[uninstall] removing /usr/local/bin/agent symlink"
    rm -f /usr/local/bin/agent
fi

if [[ -d "${INSTALL_PREFIX}" ]]; then
    echo "[uninstall] removing ${INSTALL_PREFIX}"
    rm -rf "${INSTALL_PREFIX}"
fi

if [[ -d "${STATE_DIR}" ]]; then
    read -r -p "[uninstall] remove ${STATE_DIR} (agent state + buffer)? [y/N] " ans
    if [[ "${ans}" =~ ^[Yy]$ ]]; then
        rm -rf "${STATE_DIR}"
        echo "[uninstall] removed ${STATE_DIR}"
    else
        echo "[uninstall] keeping ${STATE_DIR}"
    fi
fi

if [[ -d "${LOG_DIR}" ]]; then
    read -r -p "[uninstall] remove ${LOG_DIR} (logs)? [y/N] " ans
    if [[ "${ans}" =~ ^[Yy]$ ]]; then
        rm -rf "${LOG_DIR}"
        echo "[uninstall] removed ${LOG_DIR}"
    else
        echo "[uninstall] keeping ${LOG_DIR}"
    fi
fi

echo "[uninstall] done. The 'ueba-agent' system user is preserved (delete manually with 'userdel ueba-agent' if no longer needed)."
