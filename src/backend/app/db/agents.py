"""Database helpers for endpoint agent enrollment, auth, heartbeat, config, and blocklist.

These helpers operate on the tables created by `session.initialize_database()`:
`endpoint_agents`, `agent_enrollment_tokens`, `agent_blocklist`, `agent_policy`.
They use the same `session.get_connection()` context manager and `session.utc_now()`
helper to stay consistent with the rest of the data layer.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from src.backend.app.config import settings
from src.backend.app.db.session import get_connection, utc_now

API_KEY_PREFIX = "o47ag_"
ENROLLMENT_TOKEN_PREFIX = "o47enr_"
DEFAULT_BLOCKLIST_SEED: tuple[tuple[str, str, str, str], ...] = (
    ("wikileaks.org", "domain", "exfiltration", "WikiLeaks - data exfiltration risk"),
    ("pastebin.com", "domain", "exfiltration", "Pastebin - paste site"),
    ("mega.nz", "domain", "exfiltration", "Mega - file sharing"),
    ("webmail providers", "category", "policy", "Personal webmail blocked by policy"),
)


def _hash_secret(value: str) -> str:
    """Deterministic SHA-256 hash for tokens and API keys (lookup by hash)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def _generate_enrollment_token() -> str:
    return ENROLLMENT_TOKEN_PREFIX + secrets.token_urlsafe(24)


def _generate_agent_id() -> str:
    return "agent-" + secrets.token_hex(8)


def create_enrollment_token(
    created_by_account_id: int, expires_minutes: int | None = None
) -> dict[str, Any]:
    """Create a one-time enrollment token. Returns the plaintext token + metadata."""
    ttl = expires_minutes or settings.agent_enrollment_token_ttl_minutes
    token = _generate_enrollment_token()
    token_hash = _hash_secret(token)
    now = utc_now()
    from datetime import UTC, datetime, timedelta

    expires_at_dt = datetime.now(UTC) + timedelta(minutes=ttl)
    expires_at = expires_at_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_enrollment_tokens
                (token_hash, created_by_account_id, expires_at, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            (token_hash, created_by_account_id, expires_at, now),
        )
    return {
        "token": token,
        "token_id": token_hash[:12],
        "expires_at": expires_at,
        "created_at": now,
    }


def _consume_enrollment_token(conn: Any, token: str) -> dict[str, Any]:
    """Validate + consume an enrollment token within an existing transaction.

    Raises ValueError with a code-friendly message on failure.
    """
    token_hash = _hash_secret(token)
    row = conn.execute(
        """
        SELECT token_hash, used_by_agent_id, expires_at, created_at
        FROM agent_enrollment_tokens
        WHERE token_hash = %s
        """,
        (token_hash,),
    ).fetchone()
    if not row:
        raise ValueError("Invalid enrollment token")
    if row["used_by_agent_id"] is not None:
        raise ValueError("Enrollment token already used")
    if row["expires_at"] < utc_now():
        raise ValueError("Enrollment token expired")
    return dict(row)


def register_agent(
    enrollment_token: str,
    hostname: str,
    os: str | None = None,
    os_version: str | None = None,
    device_id: str | None = None,
    assigned_user_id: str | None = None,
) -> dict[str, Any]:
    """Enroll a new endpoint agent. Returns dict with agent_id + plaintext api_key.

    Steps:
      1. Validate + consume enrollment token (in same transaction).
      2. Generate agent_id + api_key, store api_key_hash.
      3. Mark token as used.
    """
    if not hostname or not hostname.strip():
        raise ValueError("hostname is required")
    agent_id = _generate_agent_id()
    api_key = _generate_api_key()
    api_key_hash = _hash_secret(api_key)
    now = utc_now()
    with get_connection() as conn:
        token_row = _consume_enrollment_token(conn, enrollment_token)
        conn.execute(
            """
            INSERT INTO endpoint_agents (
                agent_id, hostname, os, os_version, device_id, assigned_user_id,
                api_key_hash, status, policy_version, enrolled_at,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'enrolled', 1, %s, %s, %s)
            """,
            (
                agent_id, hostname, os, os_version, device_id, assigned_user_id,
                api_key_hash, now, now, now,
            ),
        )
        conn.execute(
            "UPDATE agent_enrollment_tokens SET used_by_agent_id = %s WHERE token_hash = %s",
            (agent_id, token_row["token_hash"]),
        )
    return {
        "agent_id": agent_id,
        "api_key": api_key,
        "policy_version": 1,
        "issued_at": now,
    }


def get_agent_by_api_key(api_key: str) -> dict[str, Any] | None:
    """Look up an agent by its plaintext API key. Returns None if not found/revoked."""
    if not api_key or not api_key.startswith(API_KEY_PREFIX):
        return None
    api_key_hash = _hash_secret(api_key)
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT agent_id, hostname, os, os_version, device_id, assigned_user_id,
                   api_key_hash, status, policy_version, last_heartbeat,
                   last_config_pull, enrolled_at, created_at, updated_at
            FROM endpoint_agents
            WHERE api_key_hash = %s
            """,
            (api_key_hash,),
        ).fetchone()
    if not row:
        return None
    if not _constant_time_eq(row["api_key_hash"], api_key_hash):
        return None
    return dict(row)


def get_agent(agent_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT agent_id, hostname, os, os_version, device_id, assigned_user_id,
                   status, policy_version, last_heartbeat, last_config_pull,
                   enrolled_at, created_at, updated_at
            FROM endpoint_agents
            WHERE agent_id = %s
            """,
            (agent_id,),
        ).fetchone()
    return dict(row) if row else None


def list_agents(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT agent_id, hostname, os, os_version, device_id, assigned_user_id,
                       status, policy_version, last_heartbeat, last_config_pull,
                       enrolled_at, created_at, updated_at
                FROM endpoint_agents
                WHERE status = %s
                ORDER BY enrolled_at DESC
                LIMIT %s OFFSET %s
                """,
                (status, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT agent_id, hostname, os, os_version, device_id, assigned_user_id,
                       status, policy_version, last_heartbeat, last_config_pull,
                       enrolled_at, created_at, updated_at
                FROM endpoint_agents
                ORDER BY enrolled_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()
    return [dict(r) for r in rows]


def count_agents(status: str | None = None) -> int:
    with get_connection() as conn:
        if status:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM endpoint_agents WHERE status = %s",
                (status,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS c FROM endpoint_agents").fetchone()
    return int(row["c"] if row else 0)


def update_agent_heartbeat(
    agent_id: str, metrics: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Update last_heartbeat and flip status to 'active'. Returns updated agent or None."""
    now = utc_now()
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE endpoint_agents
            SET last_heartbeat = %s, status = 'active', updated_at = %s
            WHERE agent_id = %s AND status != 'revoked'
            RETURNING agent_id, status, policy_version, last_heartbeat
            """,
            (now, now, agent_id),
        ).fetchone()
    return dict(row) if row else None


def touch_config_pull(agent_id: str) -> None:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE endpoint_agents SET last_config_pull = %s, updated_at = %s WHERE agent_id = %s",
            (now, now, agent_id),
        )


def update_agent(
    agent_id: str,
    status: str | None = None,
    device_id: str | None = None,
    assigned_user_id: str | None = None,
    policy_version: int | None = None,
) -> dict[str, Any] | None:
    """Update mutable agent fields. When status='revoked', api_key_hash is invalidated."""
    now = utc_now()
    sets: list[str] = ["updated_at = %s"]
    params: list[Any] = [now]
    if status is not None:
        sets.append("status = %s")
        params.append(status)
    if device_id is not None:
        sets.append("device_id = %s")
        params.append(device_id)
    if assigned_user_id is not None:
        sets.append("assigned_user_id = %s")
        params.append(assigned_user_id)
    if policy_version is not None:
        sets.append("policy_version = %s")
        params.append(policy_version)
    with get_connection() as conn:
        params.append(agent_id)
        row = conn.execute(
            f"""
            UPDATE endpoint_agents SET {", ".join(sets)}
            WHERE agent_id = %s
            RETURNING agent_id, hostname, os, os_version, device_id, assigned_user_id,
                      status, policy_version, last_heartbeat, last_config_pull,
                      enrolled_at, created_at, updated_at
            """,
            tuple(params),
        ).fetchone()
    return dict(row) if row else None


def revoke_agent(agent_id: str) -> dict[str, Any] | None:
    return update_agent(agent_id, status="revoked")


def mark_stale_agents_offline(timeout_minutes: int | None = None) -> int:
    """Flip agents whose last_heartbeat is older than timeout to 'offline'.

    Returns the number of agents flipped. Skips agents already revoked/offline.
    """
    timeout = timeout_minutes or settings.agent_heartbeat_timeout_minutes
    cutoff_sql = (
        f"((CAST(now() AS TIMESTAMPTZ) - CAST(last_heartbeat AS TIMESTAMPTZ)) "
        f"> INTERVAL '{int(timeout)} minutes')"
    )
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            UPDATE endpoint_agents
            SET status = 'offline', updated_at = %s
            WHERE status IN ('enrolled', 'active')
              AND last_heartbeat IS NOT NULL
              AND {cutoff_sql}
            RETURNING agent_id
            """,
            (utc_now(),),
        ).fetchall()
    return len(rows)


# ---------------------------------------------------------------------------
# Policy + blocklist
# ---------------------------------------------------------------------------


def get_agent_policy() -> dict[str, Any]:
    """Return the singleton policy row."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT policy_version, sampling_rate, enabled_collectors_json, updated_at
            FROM agent_policy WHERE id = 1
            """
        ).fetchone()
    if not row:
        return {
            "policy_version": 1,
            "sampling_rate": 100,
            "enabled_collectors": [
                "logon", "device", "file", "http", "email", "process", "network"
            ],
            "updated_at": utc_now(),
        }
    out = dict(row)
    try:
        out["enabled_collectors"] = json.loads(out.pop("enabled_collectors_json"))
    except (json.JSONDecodeError, KeyError):
        out["enabled_collectors"] = [
            "logon", "device", "file", "http", "email", "process", "network"
        ]
    return out


def update_agent_policy(
    sampling_rate: int | None = None,
    enabled_collectors: list[str] | None = None,
) -> dict[str, Any]:
    """Bump policy_version and update fields. Returns the new policy row."""
    now = utc_now()
    sets: list[str] = ["updated_at = %s", "policy_version = policy_version + 1"]
    params: list[Any] = [now]
    if sampling_rate is not None:
        sets.append("sampling_rate = %s")
        params.append(sampling_rate)
    if enabled_collectors is not None:
        sets.append("enabled_collectors_json = %s")
        params.append(json.dumps(enabled_collectors, sort_keys=True))
    with get_connection() as conn:
        row = conn.execute(
            f"""
            UPDATE agent_policy SET {", ".join(sets)}
            WHERE id = 1
            RETURNING policy_version, sampling_rate, enabled_collectors_json, updated_at
            """,
            tuple(params),
        ).fetchone()
    out = dict(row)
    out["enabled_collectors"] = json.loads(out.pop("enabled_collectors_json"))
    return out


def get_agent_config(agent_id: str) -> dict[str, Any]:
    """Build the full config payload an agent pulls on startup + periodically."""
    policy = get_agent_policy()
    blocklist = list_blocklist(enabled_only=True)
    touch_config_pull(agent_id)
    return {
        "policy_version": policy["policy_version"],
        "sampling_rate": policy["sampling_rate"],
        "enabled_collectors": policy["enabled_collectors"],
        "blocklist": blocklist,
        "server_time": utc_now(),
    }


def list_blocklist(enabled_only: bool = False) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if enabled_only:
            rows = conn.execute(
                """
                SELECT id, pattern, pattern_type, category, reason, enabled,
                       created_at, updated_at
                FROM agent_blocklist
                WHERE enabled = TRUE
                ORDER BY id ASC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, pattern, pattern_type, category, reason, enabled,
                       created_at, updated_at
                FROM agent_blocklist
                ORDER BY id ASC
                """
            ).fetchall()
    return [dict(r) for r in rows]


def create_blocklist_entry(
    pattern: str,
    pattern_type: str = "domain",
    category: str | None = None,
    reason: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    now = utc_now()
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO agent_blocklist (pattern, pattern_type, category, reason, enabled,
                                          created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pattern) DO UPDATE SET
                pattern_type = EXCLUDED.pattern_type,
                category = EXCLUDED.category,
                reason = EXCLUDED.reason,
                enabled = EXCLUDED.enabled,
                updated_at = EXCLUDED.updated_at
            RETURNING id, pattern, pattern_type, category, reason, enabled,
                      created_at, updated_at
            """,
            (pattern, pattern_type, category, reason, enabled, now, now),
        ).fetchone()
    return dict(row)


def update_blocklist_entry(entry_id: int, **fields: Any) -> dict[str, Any] | None:
    allowed = {"pattern", "pattern_type", "category", "reason", "enabled"}
    sets: list[str] = ["updated_at = %s"]
    params: list[Any] = [utc_now()]
    for key, value in fields.items():
        if key in allowed and value is not None:
            sets.append(f"{key} = %s")
            params.append(value)
    params.append(entry_id)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            UPDATE agent_blocklist SET {", ".join(sets)}
            WHERE id = %s
            RETURNING id, pattern, pattern_type, category, reason, enabled,
                      created_at, updated_at
            """,
            tuple(params),
        ).fetchone()
    return dict(row) if row else None


def delete_blocklist_entry(entry_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "DELETE FROM agent_blocklist WHERE id = %s RETURNING id", (entry_id,)
        ).fetchone()
    return row is not None
