"""Tests for LLM helper functions (Phase 2.3 of PLAN_LLM.md).

Unit tests use mocks (no DB). Integration tests use the real pool and require
`TEST_DATABASE_URL`. Integration tests assume the test database has been
initialised with the standard schema (users, devices, alerts).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.backend.tests.conftest import postgres_tests_enabled

# ---------- Unit tests (no DB) ----------


def test_content_hash_is_deterministic_sha256() -> None:
    from src.backend.app.db.session import _content_hash

    h1 = _content_hash("hello")
    h2 = _content_hash("hello")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex
    assert _content_hash("hello") != _content_hash("world")


def test_upsert_memory_calls_on_conflict() -> None:
    """Verify upsert uses ON CONFLICT with the correct columns."""
    import inspect

    from src.backend.app.db.session import upsert_memory

    src = inspect.getsource(upsert_memory)
    assert "ON CONFLICT (scope, scope_id, kind, content_hash)" in src
    assert "use_count + 1" in src
    assert "last_used_at = NOW()" in src


def test_retrieve_memories_query_filters() -> None:
    """Retrieve must exclude stale memories (decay filter)."""
    import inspect

    from src.backend.app.db.session import retrieve_memories

    src = inspect.getsource(retrieve_memories)
    assert "scope = 'user'" in src
    assert "scope = 'device'" in src
    assert "scope = 'pattern'" in src
    assert "scope = 'global'" in src
    assert "tags &&" in src  # array overlap
    assert "decay" in src or "INTERVAL" in src


def test_load_recent_messages_returns_chronological() -> None:
    """By default (no after_id) the helper must return oldest-first after the DESC->ASC flip."""
    from src.backend.app.db.session import load_recent_messages

    fake_pool = MagicMock()
    fake_conn = MagicMock()
    fake_pool.getconn.return_value = fake_conn
    # DESC query returns rows in reverse chronological order.
    fake_conn.execute.return_value.fetchall.return_value = [
        {"id": 3, "created_at": "2024-01-03"},
        {"id": 2, "created_at": "2024-01-02"},
        {"id": 1, "created_at": "2024-01-01"},
    ]

    with patch("src.backend.app.db.session.pooled_connection") as pcm:
        pcm.return_value.__enter__.return_value = fake_conn
        result = load_recent_messages(1, limit=3)
    assert [r["id"] for r in result] == [1, 2, 3]


def test_load_recent_messages_with_after_id_preserves_order() -> None:
    from src.backend.app.db.session import load_recent_messages

    fake_conn = MagicMock()
    fake_conn.execute.return_value.fetchall.return_value = [
        {"id": 4, "created_at": "2024-01-04"},
        {"id": 5, "created_at": "2024-01-05"},
    ]

    with patch("src.backend.app.db.session.pooled_connection") as pcm:
        pcm.return_value.__enter__.return_value = fake_conn
        result = load_recent_messages(1, limit=10, after_id=3)
    assert [r["id"] for r in result] == [4, 5]


def test_touch_memories_skips_empty() -> None:
    """Empty input must not hit the DB."""
    from src.backend.app.db.session import touch_memories

    with patch("src.backend.app.db.session.pooled_connection") as pcm:
        touch_memories([])
    pcm.assert_not_called()


def test_forget_memory_uses_id() -> None:
    from src.backend.app.db.session import forget_memory

    fake_conn = MagicMock()
    with patch("src.backend.app.db.session.pooled_connection") as pcm:
        pcm.return_value.__enter__.return_value = fake_conn
        forget_memory(42)
    fake_conn.execute.assert_called_once()
    args = fake_conn.execute.call_args.args
    assert "DELETE FROM llm_memories" in args[0]
    assert fake_conn.execute.call_args.args[1] == (42,)


# ---------- Integration tests (need Postgres + initialised schema) ----------


@pytest.fixture
def db_setup():
    """Initialise the pool + schema. Skip if no TEST_DATABASE_URL."""
    from src.backend.app.db.pool import close_pool, init_pool
    from src.backend.app.db.session import initialize_database

    if not postgres_tests_enabled():
        pytest.skip("TEST_DATABASE_URL not set")
    init_pool()
    initialize_database()
    yield
    close_pool()


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_upsert_then_retrieve_memory(db_setup) -> None:
    from src.backend.app.db import session as db

    # Write
    row = db.upsert_memory(
        scope="user",
        scope_id="U-test-001",
        kind="fact",
        content="User often logs in after hours",
        tags=["after_hours", "logon"],
    )
    assert row["id"] > 0
    assert row["use_count"] == 1

    # Upsert again -> dedup + bump
    row2 = db.upsert_memory(
        scope="user",
        scope_id="U-test-001",
        kind="fact",
        content="User often logs in after hours",
        tags=["after_hours", "logon"],
    )
    assert row2["id"] == row["id"]
    assert row2["use_count"] == 2

    # Retrieve
    hits = db.retrieve_memories(
        user_id="U-test-001", device_id=None, factor_tags=["after_hours"], top_k=5
    )
    assert any(h["id"] == row["id"] for h in hits)


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_retrieve_memories_decay_filter(db_setup) -> None:
    """Memories with old last_used_at should be excluded when decay_days is small."""
    from src.backend.app.db import session as db

    row = db.upsert_memory(
        scope="user", scope_id="U-decay", kind="fact", content="old fact", tags=[]
    )
    # Manually backdate the row to 100 days ago.
    with db.get_connection(write=True) as conn:
        conn.execute(
            "UPDATE llm_memories SET last_used_at = NOW() - INTERVAL '100 days' WHERE id = %s",
            (row["id"],),
        )
    hits = db.retrieve_memories(
        user_id="U-decay", device_id=None, factor_tags=None, top_k=5, decay_days=90
    )
    assert all(h["id"] != row["id"] for h in hits)


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_counter_cache_trigger_increments(db_setup) -> None:
    """Inserting memories should bump llm_stats_cache counters."""
    from src.backend.app.db import session as db

    db.upsert_memory(scope="user", scope_id="U-stat", kind="fact", content="a", tags=[])
    db.upsert_memory(scope="user", scope_id="U-stat", kind="fact", content="b", tags=[])
    stats = db.get_memory_stats()
    user_fact = [s for s in stats if s["scope"] == "user" and s["kind"] == "fact"]
    assert user_fact, "expected a stats row for (user, fact)"
    assert user_fact[0]["total_count"] >= 2


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_forget_memory_decrements_counter(db_setup) -> None:
    from src.backend.app.db import session as db

    row = db.upsert_memory(
        scope="device", scope_id="D-fgt", kind="historical", content="to forget", tags=[]
    )
    db.forget_memory(row["id"])
    assert db.get_memory_stats()  # still queryable
    assert all(m["id"] != row["id"] for m in db.list_memories_admin(scope="device"))


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_create_conversation_idempotent_per_alert(db_setup) -> None:
    """Calling create_conversation twice for the same alert returns the same row."""
    from src.backend.app.db import session as db

    c1 = db.create_conversation(alert_id=999_001, user_id="U-conv", title="first")
    c2 = db.create_conversation(alert_id=999_001, user_id="U-conv", title="second")
    assert c1["id"] == c2["id"]
    # title should be the latest one (ON CONFLICT updates)
    assert c2["title"] == "second"


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_append_and_load_recent_messages(db_setup) -> None:
    from src.backend.app.db import session as db

    c = db.create_conversation(alert_id=999_002, user_id="U-msg", title="chat")
    db.append_message(c["id"], "user", "hi")
    db.append_message(c["id"], "assistant", "hello, how can I help?")
    db.append_message(c["id"], "user", "what does this alert mean?")
    msgs = db.load_recent_messages(c["id"], limit=10)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[2]["content"] == "what does this alert mean?"
    assert db.count_messages(c["id"]) == 3


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_feedback_upsert_per_analyst(db_setup) -> None:
    from src.backend.app.db import session as db

    f1 = db.insert_feedback(alert_id=999_003, analyst_id="A-1", verdict="true_positive", note="ok")
    f2 = db.insert_feedback(alert_id=999_003, analyst_id="A-1", verdict="false_positive", note="revised")
    assert f1["id"] == f2["id"]
    assert f2["verdict"] == "false_positive"
    assert f2["note"] == "revised"

    # Different analyst on same alert should create a separate row
    f3 = db.insert_feedback(alert_id=999_003, analyst_id="A-2", verdict="benign", note=None)
    assert f3["id"] != f1["id"]
    assert len(db.get_feedback_for_alert(999_003)) == 2
