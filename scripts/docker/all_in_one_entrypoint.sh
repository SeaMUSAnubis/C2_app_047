#!/usr/bin/env bash
# ── all_in_one_entrypoint.sh ────────────────────────────────────────────
# Starts PostgreSQL, initialises the DB, then launches the FastAPI app.
# Runs inside the all-in-one Docker image on Linux, Windows, macOS.
set -euo pipefail

# ── CRLF guard ──────────────────────────────────────────────────────────
# If this script contains carriage returns (Windows CRLF checkout), strip
# them and re-execute. We stream through 'tr' into a new bash process so
# we never modify the on-disk file (which may be read-only inside the
# container). The Dockerfile also strips CR with 'tr' at build time — this
# is a defence-in-depth fallback for edge cases (e.g. bind-mount override).
if grep -q $'\r' "$0" 2>/dev/null; then
    echo "[entrypoint] CRLF detected — re-executing with stripped line endings" >&2
    tr -d '\r' < "$0" | exec bash -s "$@"
fi

PGDATA="${PGDATA:-/var/lib/postgresql/data}"
POSTGRES_USER="${POSTGRES_USER:-ueba_user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ueba_password}"
POSTGRES_DB="${POSTGRES_DB:-ueba_db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

# ── Locate PostgreSQL binaries ──────────────────────────────────────────
# Uses -exec dirname (POSIX) instead of -printf (GNU only).
POSTGRES_BIN_DIR="$(
    find /usr/lib/postgresql -type f -name initdb \
        -exec dirname {} \; 2>/dev/null \
    | sort -V | tail -1
)"

if [[ -z "${POSTGRES_BIN_DIR}" ]]; then
    # Fallback: scan common Debian/Ubuntu PostgreSQL install paths
    for candidate in /usr/lib/postgresql/*/bin; do
        if [[ -x "${candidate}/initdb" ]]; then
            POSTGRES_BIN_DIR="${candidate}"
            break
        fi
    done
fi

if [[ -z "${POSTGRES_BIN_DIR}" ]]; then
    echo "ERROR: Cannot find PostgreSQL binaries (initdb) in /usr/lib/postgresql." >&2
    echo "Installed PostgreSQL packages:" >&2
    dpkg -l | grep -i postgres 2>/dev/null || true
    exit 1
fi

echo "[entrypoint] PostgreSQL binary dir : ${POSTGRES_BIN_DIR}"

# ── Init data directory ─────────────────────────────────────────────────
mkdir -p "${PGDATA}"

# chown may fail on bind mounts from Windows hosts (NTFS doesn't support
# Linux ownership). That's fine — the named volume in docker-compose.yml
# avoids this, but we guard anyway for custom setups.
if ! chown -R postgres:postgres "${PGDATA}" 2>/dev/null; then
    echo "[entrypoint] WARNING: chown failed on ${PGDATA}" >&2
    echo "[entrypoint] If you are using a Windows bind mount, switch to the" >&2
    echo "[entrypoint] named volume 'postgres_data' defined in docker-compose.yml." >&2
fi

if [[ ! -s "${PGDATA}/PG_VERSION" ]]; then
    echo "[entrypoint] Initialising PostgreSQL data directory at ${PGDATA} ..."
    su postgres -c "${POSTGRES_BIN_DIR}/initdb -D '${PGDATA}' --locale=C.UTF-8 --encoding=UTF8"
    {
        echo "listen_addresses = '*'"
        echo "port = ${POSTGRES_PORT}"
    } >> "${PGDATA}/postgresql.conf"
    {
        echo "host all all 127.0.0.1/32 scram-sha-256"
        echo "host all all 0.0.0.0/0 scram-sha-256"
    } >> "${PGDATA}/pg_hba.conf"
fi

# Fix locale references (C.UTF-8 is always available on Debian)
sed -i \
    -e "s/en_US\.utf8/C.UTF-8/g" \
    -e "s/en_US\.UTF-8/C.UTF-8/g" \
    "${PGDATA}/postgresql.conf" 2>/dev/null || true
chown postgres:postgres "${PGDATA}/postgresql.conf" 2>/dev/null || true

# ── Start PostgreSQL ────────────────────────────────────────────────────
echo "[entrypoint] Starting PostgreSQL on port ${POSTGRES_PORT} ..."
su postgres -c "${POSTGRES_BIN_DIR}/pg_ctl -D '${PGDATA}' -w start"

cleanup() {
    echo "[entrypoint] Shutting down PostgreSQL ..."
    su postgres -c "${POSTGRES_BIN_DIR}/pg_ctl -D '${PGDATA}' -m fast -w stop" || true
}
trap cleanup INT TERM EXIT

# ── Create user & database ─────────────────────────────────────────────
if ! su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER}'\"" | grep -q 1; then
    echo "[entrypoint] Creating role: ${POSTGRES_USER}"
    su postgres -c "createuser '${POSTGRES_USER}'"
fi

su postgres -c "psql -v ON_ERROR_STOP=1 -c \"ALTER USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';\""

if ! su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'\"" | grep -q 1; then
    echo "[entrypoint] Creating database: ${POSTGRES_DB}"
    su postgres -c "createdb -O '${POSTGRES_USER}' '${POSTGRES_DB}'"
fi

su postgres -c "psql -v ON_ERROR_STOP=1 -d '${POSTGRES_DB}' -c \"GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};\""
su postgres -c "psql -v ON_ERROR_STOP=1 -d '${POSTGRES_DB}' -c \"GRANT ALL ON SCHEMA public TO ${POSTGRES_USER};\""
su postgres -c "psql -v ON_ERROR_STOP=1 -d '${POSTGRES_DB}' -c \"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${POSTGRES_USER};\""
su postgres -c "psql -v ON_ERROR_STOP=1 -d '${POSTGRES_DB}' -c \"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${POSTGRES_USER};\""

# ── Launch FastAPI ──────────────────────────────────────────────────────
export POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
export DATABASE_URL="${DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}}"

echo "[entrypoint] Starting FastAPI on port 8000 ..."
exec uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000
