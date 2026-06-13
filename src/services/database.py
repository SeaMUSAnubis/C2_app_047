from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import settings
from src.services.auth import hash_password


def initialize_database() -> None:
    db_path = _database_path()
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS app_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'analyst')),
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                email TEXT,
                department TEXT,
                job_role TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                risk_score INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                hostname TEXT NOT NULL,
                os TEXT,
                ip_address TEXT,
                assigned_user_id TEXT,
                status TEXT NOT NULL DEFAULT 'offline',
                risk_score INTEGER NOT NULL DEFAULT 0,
                last_seen TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (assigned_user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS event_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL UNIQUE,
                source_file TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                device_id TEXT,
                event_type TEXT NOT NULL,
                action TEXT,
                resource TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (device_id) REFERENCES devices(id)
            );

            CREATE TABLE IF NOT EXISTS feature_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                device_id TEXT,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                feature_summary_json TEXT NOT NULL DEFAULT '{}',
                baseline_context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (device_id) REFERENCES devices(id)
            );

            CREATE TABLE IF NOT EXISTS model_artifacts (
                model_version TEXT PRIMARY KEY,
                artifact_path TEXT NOT NULL,
                training_config_json TEXT NOT NULL DEFAULT '{}',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                device_id TEXT,
                event_log_id INTEGER,
                model_version TEXT,
                title TEXT NOT NULL,
                severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
                status TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'investigating', 'resolved', 'false_positive')),
                risk_score INTEGER NOT NULL,
                anomaly_score REAL,
                risk_factors_json TEXT NOT NULL DEFAULT '[]',
                explanation TEXT,
                detected_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (device_id) REFERENCES devices(id),
                FOREIGN KEY (event_log_id) REFERENCES event_logs(id),
                FOREIGN KEY (model_version) REFERENCES model_artifacts(model_version)
            );

            CREATE INDEX IF NOT EXISTS idx_event_logs_timestamp ON event_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_event_logs_user ON event_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_event_logs_device ON event_logs(device_id);
            CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
            CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
            """
        )
        _seed_accounts(conn)
        _seed_domain_data(conn)


@contextmanager
def get_connection() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(_database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_account_by_email(email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM app_accounts WHERE lower(email) = lower(?)", (email,)).fetchone()
        return _row_to_dict(row)


def get_account_by_id(account_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM app_accounts WHERE id = ?", (account_id,)).fetchone()
        return _row_to_dict(row)


def list_users(filters: dict[str, Any]) -> list[dict[str, Any]]:
    where, params = _user_filters(filters)
    return _fetch_all("SELECT * FROM users", where, params, "risk_score DESC, username ASC", filters)


def count_users(filters: dict[str, Any]) -> int:
    where, params = _user_filters(filters)
    return _count("users", where, params)


def get_user(user_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        return _row_to_dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def create_user(payload: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    user_id = payload["id"]
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, full_name, email, department, job_role, status, risk_score, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                payload["username"],
                payload["full_name"],
                payload.get("email"),
                payload.get("department"),
                payload.get("job_role"),
                payload.get("status", "active"),
                payload.get("risk_score", 0),
                now,
                now,
            ),
        )
    return get_user(user_id) or {}


def update_user(user_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _update_by_id("users", user_id, payload, allowed={"email", "department", "job_role", "status", "risk_score"})


def list_devices(filters: dict[str, Any]) -> list[dict[str, Any]]:
    where, params = _device_filters(filters)
    rows = _fetch_all(
        """
        SELECT d.*, u.username AS assigned_username, u.full_name AS assigned_user_name
        FROM devices d
        LEFT JOIN users u ON u.id = d.assigned_user_id
        """,
        where,
        params,
        "d.risk_score DESC, d.hostname ASC",
        filters,
    )
    return rows


def count_devices(filters: dict[str, Any]) -> int:
    where, params = _device_filters(filters)
    return _count("devices d", where, params)


def get_device(device_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT d.*, u.username AS assigned_username, u.full_name AS assigned_user_name
            FROM devices d
            LEFT JOIN users u ON u.id = d.assigned_user_id
            WHERE d.id = ?
            """,
            (device_id,),
        ).fetchone()
        return _row_to_dict(row)


def create_device(payload: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    device_id = payload["id"]
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO devices (id, hostname, os, ip_address, assigned_user_id, status, risk_score, last_seen, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                payload["hostname"],
                payload.get("os"),
                payload.get("ip_address"),
                payload.get("assigned_user_id"),
                payload.get("status", "offline"),
                payload.get("risk_score", 0),
                payload.get("last_seen"),
                now,
                now,
            ),
        )
    return get_device(device_id) or {}


def update_device(device_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _update_by_id(
        "devices",
        device_id,
        payload,
        allowed={"hostname", "os", "ip_address", "assigned_user_id", "status", "risk_score", "last_seen"},
    )


def ingest_event(payload: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    metadata_json = json.dumps(payload.get("metadata") or {}, sort_keys=True)
    raw_json = json.dumps(payload.get("raw") or {}, sort_keys=True)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO event_logs (
                source_id, source_file, timestamp, user_id, device_id, event_type,
                action, resource, metadata_json, raw_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                source_file = excluded.source_file,
                timestamp = excluded.timestamp,
                user_id = excluded.user_id,
                device_id = excluded.device_id,
                event_type = excluded.event_type,
                action = excluded.action,
                resource = excluded.resource,
                metadata_json = excluded.metadata_json,
                raw_json = excluded.raw_json
            """,
            (
                payload["source_id"],
                payload["source_file"],
                payload["timestamp"],
                payload.get("user_id"),
                payload.get("device_id"),
                payload["event_type"],
                payload.get("action"),
                payload.get("resource"),
                metadata_json,
                raw_json,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM event_logs WHERE source_id = ?", (payload["source_id"],)).fetchone()
        return _decode_json_fields(_row_to_dict(row) or {})


def list_events(filters: dict[str, Any]) -> list[dict[str, Any]]:
    where, params = _event_filters(filters)
    rows = _fetch_all("SELECT * FROM event_logs", where, params, "timestamp DESC, id DESC", filters)
    return [_decode_json_fields(row) for row in rows]


def count_events(filters: dict[str, Any]) -> int:
    where, params = _event_filters(filters)
    return _count("event_logs", where, params)


def count_rows(table: str, filters: dict[str, Any] | None = None) -> int:
    filters = filters or {}
    where, params = _build_filters(filters, {})
    sql = f"SELECT COUNT(*) AS count FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with get_connection() as conn:
        return int(conn.execute(sql, params).fetchone()["count"])


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _database_path() -> str:
    return settings.database_path


def _seed_accounts(conn: sqlite3.Connection) -> None:
    now = utc_now()
    accounts = [
        ("admin@demo.com", "Demo Admin", "admin", "admin123"),
        ("analyst@demo.com", "Demo Analyst", "analyst", "analyst123"),
    ]
    for email, full_name, role, password in accounts:
        conn.execute(
            """
            INSERT OR IGNORE INTO app_accounts (email, full_name, role, password_hash, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (email, full_name, role, hash_password(password), now),
        )


def _seed_domain_data(conn: sqlite3.Connection) -> None:
    now = utc_now()
    users = [
        ("ACM0001", "acm0001", "Alice M. Carter", "alice.carter@example.com", "Finance", "Accountant", "active", 18),
        ("BTR0002", "btr0002", "Bao Tran", "bao.tran@example.com", "Engineering", "Developer", "active", 42),
        ("CNL0003", "cnl0003", "Chi Nguyen", "chi.nguyen@example.com", "HR", "HR Specialist", "active", 7),
    ]
    for row in users:
        conn.execute(
            """
            INSERT OR IGNORE INTO users
            (id, username, full_name, email, department, job_role, status, risk_score, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*row, now, now),
        )

    devices = [
        ("PC-1001", "FIN-WS-1001", "Windows 11", "10.10.1.21", "ACM0001", "online", 12, "2026-06-13T08:12:00Z"),
        ("PC-2002", "ENG-LT-2002", "Ubuntu 24.04", "10.10.2.44", "BTR0002", "online", 39, "2026-06-13T08:09:00Z"),
        ("PC-3003", "HR-WS-3003", "Windows 10", "10.10.3.18", "CNL0003", "offline", 4, "2026-06-12T17:42:00Z"),
    ]
    for row in devices:
        conn.execute(
            """
            INSERT OR IGNORE INTO devices
            (id, hostname, os, ip_address, assigned_user_id, status, risk_score, last_seen, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*row, now, now),
        )


def _build_filters(filters: dict[str, Any], columns: dict[str, str]) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    for key, column in columns.items():
        value = filters.get(key)
        if value is not None:
            where.append(f"{column} = ?")
            params.append(value)
    return where, params


def _user_filters(filters: dict[str, Any]) -> tuple[list[str], list[Any]]:
    where, params = _build_filters(
        filters,
        {
            "department": "department",
            "job_role": "job_role",
            "status": "status",
        },
    )
    search = filters.get("search")
    if search:
        where.append("(lower(username) LIKE ? OR lower(full_name) LIKE ? OR lower(email) LIKE ?)")
        term = f"%{search.lower()}%"
        params.extend([term, term, term])
    return where, params


def _device_filters(filters: dict[str, Any]) -> tuple[list[str], list[Any]]:
    return _build_filters(
        filters,
        {
            "status": "d.status",
            "os": "d.os",
            "assigned_user_id": "d.assigned_user_id",
        },
    )


def _event_filters(filters: dict[str, Any]) -> tuple[list[str], list[Any]]:
    return _build_filters(
        filters,
        {
            "user_id": "user_id",
            "device_id": "device_id",
            "event_type": "event_type",
        },
    )


def _fetch_all(
    base_sql: str,
    where: list[str],
    params: list[Any],
    order_by: str,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    sql = base_sql
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
    params = [*params, filters.get("limit", 50), filters.get("offset", 0)]
    with get_connection() as conn:
        return [_row_to_dict(row) or {} for row in conn.execute(sql, params).fetchall()]


def _count(table: str, where: list[str], params: list[Any]) -> int:
    sql = f"SELECT COUNT(*) AS count FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with get_connection() as conn:
        return int(conn.execute(sql, params).fetchone()["count"])


def _update_by_id(table: str, row_id: str, payload: dict[str, Any], *, allowed: set[str]) -> dict[str, Any] | None:
    updates = {key: value for key, value in payload.items() if key in allowed}
    if not updates:
        return get_user(row_id) if table == "users" else get_device(row_id)
    updates["updated_at"] = utc_now()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = [*updates.values(), row_id]
    with get_connection() as conn:
        result = conn.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", values)
        if result.rowcount == 0:
            return None
    return get_user(row_id) if table == "users" else get_device(row_id)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _decode_json_fields(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("metadata_json", "raw_json", "risk_factors_json", "feature_summary_json", "baseline_context_json"):
        if key in row:
            decoded_key = key.removesuffix("_json")
            row[decoded_key] = json.loads(row.pop(key) or "{}")
    return row
