"""Tests for the LLM schema (Phase 2.1+2.2 of PLAN_LLM.md).

All integration tests require `TEST_DATABASE_URL`. Unit tests verify the
schema DDL is non-empty and idempotent by parsing.
"""

from __future__ import annotations

import pytest

from src.backend.tests.conftest import postgres_tests_enabled

SCHEMA_SQL_FRAGMENTS = [
    "CREATE TABLE IF NOT EXISTS llm_conversations",
    "CREATE TABLE IF NOT EXISTS llm_messages",
    "CREATE TABLE IF NOT EXISTS llm_feedback",
    "CREATE TABLE IF NOT EXISTS llm_memories",
    "CREATE TABLE IF NOT EXISTS llm_stats_cache",
    "CREATE INDEX IF NOT EXISTS idx_llm_conv_user_updated",
    "CREATE INDEX IF NOT EXISTS idx_llm_conv_updated",
    "CREATE INDEX IF NOT EXISTS idx_llm_msg_conv_created",
    "CREATE INDEX IF NOT EXISTS idx_llm_msg_model_created",
    "CREATE INDEX IF NOT EXISTS idx_llm_feedback_analyst_created",
    "CREATE INDEX IF NOT EXISTS idx_llm_feedback_alert_verdict",
    "CREATE INDEX IF NOT EXISTS idx_llm_mem_scope_lookup",
    "CREATE INDEX IF NOT EXISTS idx_llm_mem_tags_gin",
    "CREATE INDEX IF NOT EXISTS idx_llm_mem_created",
    "CREATE INDEX IF NOT EXISTS idx_llm_mem_hot",
    "touch_updated_at",
    "llm_memories_stats_sync",
]


def test_create_llm_schema_function_exists() -> None:
    from src.backend.app.db import session as db

    assert callable(getattr(db, "_create_llm_schema", None))


def test_create_llm_schema_contains_required_ddl() -> None:
    """Static check: schema SQL must declare all 4 tables + indexes + triggers."""
    import inspect

    from src.backend.app.db import session as db

    src = inspect.getsource(db._create_llm_schema)
    for fragment in SCHEMA_SQL_FRAGMENTS:
        assert fragment in src, f"missing schema fragment: {fragment}"


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_schema_creates_all_tables() -> None:
    from src.backend.app.db import session as db
    from src.backend.app.db.pool import init_pool

    init_pool()
    try:
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename LIKE 'llm_%' ORDER BY tablename"
            ).fetchall()
        names = {r["tablename"] for r in rows}
        assert names == {
            "llm_conversations",
            "llm_feedback",
            "llm_memories",
            "llm_messages",
            "llm_stats_cache",
        }
    finally:
        from src.backend.app.db.pool import close_pool
        close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_schema_creates_all_indexes() -> None:
    from src.backend.app.db import session as db
    from src.backend.app.db.pool import init_pool

    init_pool()
    try:
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
                "AND indexname LIKE 'idx_llm_%' ORDER BY indexname"
            ).fetchall()
        names = {r["indexname"] for r in rows}
        expected = {
            "idx_llm_conv_user_updated",
            "idx_llm_conv_updated",
            "idx_llm_msg_conv_created",
            "idx_llm_msg_model_created",
            "idx_llm_feedback_analyst_created",
            "idx_llm_feedback_alert_verdict",
            "idx_llm_mem_scope_lookup",
            "idx_llm_mem_tags_gin",
            "idx_llm_mem_created",
            "idx_llm_mem_hot",
        }
        missing = expected - names
        assert not missing, f"missing indexes: {missing}"
    finally:
        from src.backend.app.db.pool import close_pool
        close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_schema_creates_triggers() -> None:
    from src.backend.app.db import session as db
    from src.backend.app.db.pool import init_pool

    init_pool()
    try:
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT tgname FROM pg_trigger WHERE tgname LIKE 'trg_llm_%' ORDER BY tgname"
            ).fetchall()
        names = {r["tgname"] for r in rows}
        assert "trg_llm_conv_updated" in names
        assert "trg_llm_memories_stats" in names
    finally:
        from src.backend.app.db.pool import close_pool
        close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_schema_is_idempotent() -> None:
    """Running initialize_database twice must not raise."""
    from src.backend.app.db.pool import init_pool
    from src.backend.app.db.session import initialize_database

    init_pool()
    initialize_database()  # first run
    initialize_database()  # second run — must not raise
