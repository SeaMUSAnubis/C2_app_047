"""Tests for the DB connection pool (Phase A.0 of PLAN_LLM.md).

Unit tests run without Postgres (they mock psycopg_pool). Integration tests
require `TEST_DATABASE_URL` and exercise the real pool end-to-end.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.backend.app.config import settings
from src.backend.app.db import pool as pool_module
from src.backend.tests.conftest import postgres_tests_enabled

# ---------- Unit tests (no Postgres) ----------


def test_get_pool_stats_when_not_initialised() -> None:
    pool_module._pool = None
    stats = pool_module.get_pool_stats()
    assert stats["initialised"] is False
    assert stats["min_size"] == settings.db_pool_min_size
    assert stats["max_size"] == settings.db_pool_max_size


def test_set_timeout_for_kind_long_running_sets_zero() -> None:
    if settings.db_statement_timeout_streaming_ms != 0:
        pytest.skip("streaming timeout is not 0; would not test the disabled branch")

    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.execute = MagicMock()

    pool_module._set_timeout_for_kind(conn, write=False, long_running=True)

    # Should have run exactly one SET statement_timeout
    cur = conn.cursor.return_value.__enter__.return_value
    cur.execute.assert_called_once()
    sql, = cur.execute.call_args.args
    assert sql == "SET statement_timeout = '0ms'"
    conn.commit.assert_called_once()


def test_set_timeout_for_kind_write_uses_write_timeout() -> None:
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.execute = MagicMock()

    pool_module._set_timeout_for_kind(conn, write=True, long_running=False)

    cur = conn.cursor.return_value.__enter__.return_value
    cur.execute.assert_called_once()
    sql, = cur.execute.call_args.args
    assert sql == f"SET statement_timeout = '{settings.db_statement_timeout_write_ms}ms'"


def test_set_timeout_for_kind_read_returns_early() -> None:
    """Read timeout is already applied in `_configure_connection`; helper is a no-op."""
    conn = MagicMock()
    pool_module._set_timeout_for_kind(conn, write=False, long_running=False)
    # Should not touch the connection at all.
    conn.cursor.assert_not_called()


def test_reset_to_read_timeout_sets_expected_value() -> None:
    conn = MagicMock()
    pool_module._reset_to_read_timeout(conn)
    cur = conn.cursor.return_value.__enter__.return_value
    cur.execute.assert_called_once()
    sql, = cur.execute.call_args.args
    assert sql == f"SET statement_timeout = '{settings.db_statement_timeout_read_ms}ms'"
    conn.commit.assert_called_once()


def test_reset_to_read_timeout_swallows_rollback_failure() -> None:
    """A failing rollback after a failed SET must not raise."""
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.execute.side_effect = RuntimeError("SET failed")
    conn.rollback.side_effect = RuntimeError("rollback also failed")
    # Must not raise
    pool_module._reset_to_read_timeout(conn)
    conn.rollback.assert_called_once()


def test_configure_connection_sets_application_name_and_timeouts() -> None:
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.execute = MagicMock()

    pool_module._configure_connection(conn)

    # Should have run 3 statements: application_name, idle_in_tx, statement_timeout
    assert cur.execute.call_count == 3
    sqls = [c.args[0] for c in cur.execute.call_args_list]
    assert any("application_name" in s for s in sqls)
    assert any("idle_in_transaction_session_timeout" in s for s in sqls)
    assert any("statement_timeout" in s for s in sqls)
    conn.commit.assert_called_once()


def test_init_pool_idempotent() -> None:
    """Calling init_pool twice does not create two pools."""
    fake_pool = MagicMock()
    with patch.object(pool_module, "ConnectionPool", return_value=fake_pool) as ctor:
        pool_module._pool = None
        pool_module.init_pool()
        pool_module.init_pool()
    # Constructor should have been called exactly once
    ctor.assert_called_once()
    # Clean up
    pool_module._pool = None


def test_init_pool_failure_closes_partial_state() -> None:
    """If pool.open() raises, the partial pool must be closed and global reset."""
    fake_pool = MagicMock()
    fake_pool.wait.side_effect = RuntimeError("boom")
    with patch.object(pool_module, "ConnectionPool", return_value=fake_pool):
        pool_module._pool = None
        with pytest.raises(RuntimeError):
            pool_module.init_pool()
    assert pool_module._pool is None
    fake_pool.close.assert_called_once()


def test_close_pool_idempotent_when_none() -> None:
    pool_module._pool = None
    pool_module.close_pool()  # must not raise
    assert pool_module._pool is None


def test_close_pool_closes_and_resets() -> None:
    fake_pool = MagicMock()
    pool_module._pool = fake_pool
    pool_module.close_pool()
    fake_pool.close.assert_called_once()
    assert pool_module._pool is None


# ---------- Integration tests (need Postgres) ----------


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_pool_handles_concurrent_acquires() -> None:
    """50 concurrent acquires against a pool of 20 must serialise, not crash."""
    pool_module.init_pool()
    try:
        results: list[int] = []
        lock = threading.Lock()

        def worker(i: int) -> None:
            with pool_module.pooled_connection() as conn:
                row = conn.execute("SELECT %s AS i", (i,)).fetchone()
                with lock:
                    results.append(int(row["i"]))
                # tiny sleep to force overlap
                time.sleep(0.01)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert sorted(results) == list(range(50))
    finally:
        pool_module.close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_statement_timeout_enforced() -> None:
    """A `pg_sleep(10)` on a read connection should be cancelled in ~5s."""
    pool_module.init_pool()
    try:
        import psycopg

        with pool_module.pooled_connection() as conn:
            with pytest.raises(psycopg.errors.QueryCanceled):
                conn.execute("SELECT pg_sleep(10)").fetchone()
    finally:
        pool_module.close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_long_running_disables_statement_timeout() -> None:
    pool_module.init_pool()
    try:
        with pool_module.pooled_connection(long_running=True) as conn:
            # pg_sleep(1) on a 0ms-timeout connection should succeed.
            row = conn.execute("SELECT pg_sleep(1) AS r").fetchone()
            assert row is not None
    finally:
        pool_module.close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_no_connection_leak_under_load() -> None:
    """1000 sequential checkouts must not grow pool_size beyond max_size."""
    pool_module.init_pool()
    try:
        for _ in range(1000):
            with pool_module.pooled_connection() as conn:
                conn.execute("SELECT 1").fetchone()
        stats = pool_module.get_pool_stats()
        assert stats["pool_size"] <= settings.db_pool_max_size
        # Pool should be fully available again.
        assert stats["pool_in_use"] == 0
    finally:
        pool_module.close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_get_connection_helper_uses_pool() -> None:
    """`db.session.get_connection` must share the same global pool."""
    from src.backend.app.db.session import get_connection

    pool_module.init_pool()
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT 1 AS r").fetchone()
            assert int(row["r"]) == 1
        stats = pool_module.get_pool_stats()
        assert stats["initialised"] is True
    finally:
        pool_module.close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_statement_timeout_resets_between_checkouts() -> None:
    """After a write checkout (30s), a subsequent read checkout must see 5s.

    Regression test for a bug where `_set_timeout_for_kind` did not reset
    on putconn, so the next read inherited the previous write's 30s timeout.
    """
    pool_module.init_pool()
    try:
        # 1. Write checkout — sets 30s timeout
        with pool_module.pooled_connection(write=True) as conn:
            row = conn.execute("SHOW statement_timeout").fetchone()
            assert "30s" in (row.get("statement_timeout") or "").lower() or "30" in str(row)

        # 2. Read checkout — should now be 5s, not 30s
        with pool_module.pooled_connection() as conn:
            row = conn.execute("SHOW statement_timeout").fetchone()
            timeout_str = (row.get("statement_timeout") or "").lower()
            assert "5s" in timeout_str, f"expected 5s, got {timeout_str!r}"
    finally:
        pool_module.close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_long_running_disables_statement_timeout_even_after_write() -> None:
    """`long_running=True` must override previous checkout's write timeout."""
    pool_module.init_pool()
    try:
        with pool_module.pooled_connection(write=True) as _:
            pass
        with pool_module.pooled_connection(long_running=True) as conn:
            row = conn.execute("SHOW statement_timeout").fetchone()
            # 0 = disabled
            assert (row.get("statement_timeout") or "").strip() in ("0", "0ms", "0s")
    finally:
        pool_module.close_pool()
