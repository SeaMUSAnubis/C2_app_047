#!/usr/bin/env bash
set -euo pipefail

PGDATA="${PGDATA:-/var/lib/postgresql/data}"
POSTGRES_USER="${POSTGRES_USER:-ueba_user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ueba_password}"
POSTGRES_DB="${POSTGRES_DB:-ueba_db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

POSTGRES_BIN_DIR="$(find /usr/lib/postgresql -type f -name initdb -printf '%h\n' | sort -V | tail -1)"
if [[ -z "${POSTGRES_BIN_DIR}" ]]; then
    echo "Khong tim thay PostgreSQL binaries trong image." >&2
    exit 1
fi

mkdir -p "${PGDATA}"
chown -R postgres:postgres "${PGDATA}"

if [[ ! -s "${PGDATA}/PG_VERSION" ]]; then
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

sed -i \
    -e "s/en_US\.utf8/C.UTF-8/g" \
    -e "s/en_US\.UTF-8/C.UTF-8/g" \
    "${PGDATA}/postgresql.conf"
chown postgres:postgres "${PGDATA}/postgresql.conf"

su postgres -c "${POSTGRES_BIN_DIR}/pg_ctl -D '${PGDATA}' -w start"

cleanup() {
    su postgres -c "${POSTGRES_BIN_DIR}/pg_ctl -D '${PGDATA}' -m fast -w stop" || true
}
trap cleanup INT TERM EXIT

if ! su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER}'\"" | grep -q 1; then
    su postgres -c "createuser '${POSTGRES_USER}'"
fi
su postgres -c "psql -v ON_ERROR_STOP=1 -c \"ALTER USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';\""

if ! su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'\"" | grep -q 1; then
    su postgres -c "createdb -O '${POSTGRES_USER}' '${POSTGRES_DB}'"
fi

su postgres -c "psql -v ON_ERROR_STOP=1 -d '${POSTGRES_DB}' -c \"GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};\""
su postgres -c "psql -v ON_ERROR_STOP=1 -d '${POSTGRES_DB}' -c \"GRANT ALL ON SCHEMA public TO ${POSTGRES_USER};\""
su postgres -c "psql -v ON_ERROR_STOP=1 -d '${POSTGRES_DB}' -c \"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${POSTGRES_USER};\""
su postgres -c "psql -v ON_ERROR_STOP=1 -d '${POSTGRES_DB}' -c \"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${POSTGRES_USER};\""

export POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
export DATABASE_URL="${DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}}"

exec uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000
