"""PostgreSQL connection pool for the UEBA backend.

Phase A.0 of `docs/PLAN_LLM.md`. Replaces the per-request `psycopg.connect`
pattern in `db/session.py` with a shared pool so the chat/SSE workload does
not pay TCP+TLS+auth cost on every request and does not exhaust Postgres
`max_connections`.

Public API:
    init_pool()                 — call once at app startup (lifespan).
    close_pool()                — call once at app shutdown.
    get_connection()            — context manager, see db/session.py.
    get_pool_stats()            — dict for admin endpoint.

Settings (see `app.config.settings`):
    db_pool_min_size            — default 2
    db_pool_max_size            — default 20  (user quyết định 20)
    db_pool_acquire_timeout_s   — default 5.0
    db_statement_timeout_read_ms   — default 5000
    db_statement_timeout_write_ms  — default 30000
    db_statement_timeout_stream_ms — default 0   (disabled)
    db_idle_in_tx_timeout_ms       — default 10000
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

try:
    from psycopg_pool import ConnectionPool
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "psycopg-pool is required. Install with `pip install -r requirements.txt`."
    ) from exc

from src.backend.app.config import settings

logger = logging.getLogger(__name__)


_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _read_timeout_ms() -> int:
    return int(settings.db_statement_timeout_read_ms)


def _write_timeout_ms() -> int:
    return int(settings.db_statement_timeout_write_ms)


def _stream_timeout_ms() -> int:
    return int(settings.db_statement_timeout_streaming_ms)


def _idle_in_tx_timeout_ms() -> int:
    return int(settings.db_idle_in_transaction_timeout_ms)


def _configure_connection(conn: Any) -> None:
    """psycopg_pool `configure` callback — runs once per new connection.

    Sets session-level config so every checkout starts with predictable
    timeouts. Statement timeout is set conservatively (read) and callers
    can override per-checkout via `_set_timeout_for_kind`.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SET application_name = 'ueba-backend'")
            cur.execute(f"SET idle_in_transaction_session_timeout = '{_idle_in_tx_timeout_ms()}ms'")
            cur.execute(f"SET statement_timeout = '{_read_timeout_ms()}ms'")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _set_timeout_for_kind(conn: Any, *, write: bool, long_running: bool) -> None:
    """Override `statement_timeout` for a single checkout.

    - `long_running=True` (SSE streams) → 0 (disabled).
    - `write=True`                    → write timeout.
    - default                         → read timeout (set in _configure_connection).
    """
    if long_running:
        ms = _stream_timeout_ms()
    elif write:
        ms = _write_timeout_ms()
    else:
        return  # read timeout already set in _configure_connection
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{ms}ms'")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_pool() -> None:
    """Create the global pool. Idempotent. Safe to call multiple times."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            return
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is empty; cannot init pool.")
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            timeout=settings.db_pool_acquire_timeout_seconds,
            configure=_configure_connection,
            open=False,  # open lazily on first checkout, lifespan can warm up via .wait()
            name="ueba-backend",
            # Supabase pooler/PgBouncer can reuse server-side session state in a
            # way that conflicts with psycopg's auto prepared statements.
            # Disabling them avoids DuplicatePreparedStatement on pooled DB URLs.
            kwargs={"row_factory": None, "prepare_threshold": None},
        )
        try:
            _pool.open()
            _pool.wait(timeout=settings.db_pool_acquire_timeout_seconds)
            logger.info(
                "db pool initialised min=%s max=%s",
                settings.db_pool_min_size,
                settings.db_pool_max_size,
            )
        except Exception:
            logger.exception("db pool init failed; closing partial state")
            _pool.close()
            _pool = None
            raise


def close_pool() -> None:
    """Close the global pool. Idempotent."""
    global _pool
    with _pool_lock:
        if _pool is None:
            return
        try:
            _pool.close()
            logger.info("db pool closed")
        except Exception:
            logger.exception("db pool close error")
        finally:
            _pool = None


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("db pool not initialised; call init_pool() at startup")
    return _pool


def get_pool_stats() -> dict[str, Any]:
    """Snapshot of pool stats for the admin endpoint.

    Returns a dict that's safe to JSON-serialize. `psycopg_pool` exposes
    `pool.get_stats()` which already returns a dict; we add a couple of
    convenience fields and keep the original.
    """
    pool = _pool
    if pool is None:
        return {
            "initialised": False,
            "min_size": settings.db_pool_min_size,
            "max_size": settings.db_pool_max_size,
        }
    raw = pool.get_stats()
    pool_size = raw.get("pool_size", 0)
    pool_available = raw.get("pool_available", 0)
    in_use = max(pool_size - pool_available, 0)
    return {
        "initialised": True,
        "min_size": settings.db_pool_min_size,
        "max_size": settings.db_pool_max_size,
        "acquire_timeout_seconds": settings.db_pool_acquire_timeout_seconds,
        "statement_timeout_read_ms": _read_timeout_ms(),
        "statement_timeout_write_ms": _write_timeout_ms(),
        "statement_timeout_streaming_ms": _stream_timeout_ms(),
        "idle_in_transaction_timeout_ms": _idle_in_tx_timeout_ms(),
        "pool_size": pool_size,
        "pool_available": pool_available,
        "pool_in_use": in_use,
        "requests_waiting": raw.get("requests_waiting", 0),
        "requests_errors": raw.get("requests_errors", 0),
        "requests_num": raw.get("requests_num", 0),
        "usage_ms": raw.get("usage_ms", 0),
    }


def _reset_to_read_timeout(conn: Any) -> None:
    """Reset statement_timeout to the read default before returning to pool.

    Without this, a write checkout (30s timeout) would persist on the connection
    and the next read checkout would inherit a 30s timeout instead of the
    intended 5s. Cheap (1 round-trip) and safe.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{_read_timeout_ms()}ms'")
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


@contextmanager
def pooled_connection(*, write: bool = False, long_running: bool = False) -> Iterator[Any]:
    """Checkout a connection from the pool, apply per-checkout timeout, return it.

    Used by `db/session.py::get_connection()`. Callers MUST NOT call `conn.close()`
    — the pool does that on `__exit__`. They MAY `conn.rollback()` and the pool
    will still re-use the connection.

    Always sets statement_timeout explicitly (even for read), so the connection's
    state is deterministic regardless of what the previous checkout left behind.
    Resets to read timeout on putconn.
    """
    pool = get_pool()
    conn = pool.getconn(timeout=settings.db_pool_acquire_timeout_seconds)
    try:
        if long_running:
            _set_timeout_for_kind(conn, write=False, long_running=True)
        elif write:
            _set_timeout_for_kind(conn, write=True, long_running=False)
        else:
            # Always explicit — do not rely on `_configure_connection` from a
            # previous lifecycle.
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = '{_read_timeout_ms()}ms'")
            conn.commit()
        yield conn
    finally:
        _reset_to_read_timeout(conn)
        try:
            pool.putconn(conn)
        except Exception:
            logger.exception("db pool putconn error")
