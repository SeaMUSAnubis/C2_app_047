#!/usr/bin/env bash
# ── all_in_one_entrypoint.sh ────────────────────────────────────────────
# Starts PostgreSQL, initialises the DB, then launches the FastAPI app.
# Runs inside the all-in-one Docker image on Linux, Windows (WSL2), macOS.
set -euo pipefail

# ── Strip CR characters (defence in depth when repo is cloned on Windows)
# The Dockerfile already does this, but this guard catches any edge case.
if grep -q $'\r' "$0" 2>/dev/null; then
    sed -i 's/\r$//' "$0"
    exec bash "$0" "$@"
fi

PGDATA="${PGDATA:-/var/lib/postgresql/data}"
POSTGRES_USER="${POSTGRES_USER:-ueba_user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ueba_password}"
POSTGRES_DB="${POSTGRES_DB:-ueba_db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

# ── Locate PostgreSQL binaries ──────────────────────────────────────────
# Uses -exec dirname (POSIX) instead of -printf (GNU only) for portability.
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
    echo "Is the 'postgresql' package installed?" >&2
    exit 1
fi

echo "[entrypoint] Using PostgreSQL binaries from: ${POSTGRES_BIN_DIR}"

# ── Init data directory ─────────────────────────────────────────────────
mkdir -p "${PGDATA}"
chown -R postgres:postgres "${PGDATA}"

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

# Fix locale references (the C.UTF-8 locale is always available on Debian)
sed -i \
    -e "s/en_US\.utf8/C.UTF-8/g" \
    -e "s/en_US\.UTF-8/C.UTF-8/g" \
    "${PGDATA}/postgresql.conf"
chown postgres:postgres "${PGDATA}/postgresql.conf"

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
