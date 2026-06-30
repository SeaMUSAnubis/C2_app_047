"""Tests for llm_memory + llm_feedback services (Phase 3.7 of PLAN_LLM.md).

Unit tests use mocks for the DB. Integration tests require TEST_DATABASE_URL.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.backend.app.services.llm_memory import MemoryStore, get_memory_store, reset_memory_store
from src.backend.app.services.llm_feedback import FeedbackService, get_feedback_service
from src.backend.tests.conftest import postgres_tests_enabled


# ---------- MemoryStore unit ----------


def test_memory_store_retrieve_returns_empty_when_disabled(monkeypatch) -> None:
    from src.backend.app.config import settings
    monkeypatch.setattr(settings, "llm_memory_enabled", False)
    store = MemoryStore()
    assert store.retrieve(user_id="U-1") == []


def test_memory_store_write_calls_db(monkeypatch) -> None:
    from src.backend.app.config import settings
    monkeypatch.setattr(settings, "llm_memory_enabled", True)

    with patch("src.backend.app.services.llm_memory.db.upsert_memory") as up:
        up.return_value = {"id": 7}
        store = MemoryStore()
        row = store.write(scope="user", scope_id="U-1", kind="fact", content="c", tags=["a"])
    up.assert_called_once()
    assert row["id"] == 7


def test_memory_store_touch_skips_empty() -> None:
    store = MemoryStore()
    with patch("src.backend.app.services.llm_memory.db.touch_memories") as t:
        store.touch([])
    t.assert_not_called()


def test_memory_store_touch_passes_ids() -> None:
    store = MemoryStore()
    with patch("src.backend.app.services.llm_memory.db.touch_memories") as t:
        store.touch([1, 2, 3])
    t.assert_called_once_with([1, 2, 3])


def test_memory_store_forget_calls_db() -> None:
    store = MemoryStore()
    with patch("src.backend.app.services.llm_memory.db.forget_memory") as f:
        store.forget(42)
    f.assert_called_once_with(42)


def test_memory_store_singleton() -> None:
    reset_memory_store()
    a = get_memory_store()
    b = get_memory_store()
    assert a is b
    reset_memory_store()


# ---------- FeedbackService unit ----------


def test_feedback_invalid_verdict_raises() -> None:
    svc = FeedbackService()
    with pytest.raises(ValueError):
        svc.submit(alert_id=1, analyst_id="A-1", verdict="bogus")


def test_feedback_valid_creates_row(monkeypatch) -> None:
    fake_row = {"id": 1, "alert_id": 1, "analyst_id": "A-1", "verdict": "false_positive", "note": "n", "created_at": "now"}
    with patch("src.backend.app.services.llm_feedback.db.insert_feedback", return_value=fake_row), \
         patch.object(FeedbackService, "_auto_write_memory") as auto:
        svc = FeedbackService()
        row = svc.submit(alert_id=1, analyst_id="A-1", verdict="false_positive", note="n")
    assert row["id"] == 1
    auto.assert_called_once_with(fake_row)


def test_feedback_skips_auto_memory_when_disabled(monkeypatch) -> None:
    from src.backend.app.config import settings
    monkeypatch.setattr(settings, "llm_memory_auto_feedback", False)
    fake_row = {"id": 2, "alert_id": 1, "analyst_id": "A-1", "verdict": "benign", "note": None, "created_at": "now"}
    with patch("src.backend.app.services.llm_feedback.db.insert_feedback", return_value=fake_row), \
         patch.object(FeedbackService, "_auto_write_memory") as auto:
        FeedbackService().submit(alert_id=1, analyst_id="A-1", verdict="benign")
    auto.assert_not_called()


def test_feedback_auto_memory_handles_missing_alert(monkeypatch) -> None:
    fake_row = {"id": 3, "alert_id": 99, "analyst_id": "A-1", "verdict": "false_positive", "note": "x", "created_at": "now"}
    with patch("src.backend.app.services.llm_feedback.db.insert_feedback", return_value=fake_row), \
         patch("src.backend.app.services.llm_feedback.db.get_alert", return_value=None), \
         patch("src.backend.app.services.llm_feedback.get_memory_store") as gms:
        FeedbackService().submit(alert_id=99, analyst_id="A-1", verdict="false_positive", note="x")
    gms.return_value.write.assert_not_called()


# ---------- Integration tests ----------


@pytest.mark.skipif(not postgres_tests_enabled(), reason="TEST_DATABASE_URL not set")
def test_feedback_auto_writes_memory(db_setup):
    """Submitting feedback should produce an analyst_pattern memory."""
    # First seed an alert + user
    from src.backend.app.db import session as db

    with db.get_connection(write=True) as conn:
        conn.execute(
            "INSERT INTO users (id, username, full_name, created_at, updated_at) "
            "VALUES (%s, %s, %s, NOW(), NOW()) ON CONFLICT (id) DO NOTHING",
            ("U-fb-1", "fb_user_1", "FB User 1"),
        )
        conn.execute(
            "INSERT INTO alerts (user_id, title, severity, risk_score, status, detected_at, updated_at) "
            "VALUES (%s, %s, %s, %s, 'new', NOW(), NOW()) RETURNING id",
            ("U-fb-1", "test alert for feedback", "high", 80),
        )
        alert_id_row = conn.execute(
            "SELECT id FROM alerts WHERE user_id = %s ORDER BY id DESC LIMIT 1", ("U-fb-1",)
        ).fetchone()
    alert_id = int(alert_id_row["id"])

    FeedbackService().submit(
        alert_id=alert_id, analyst_id="A-fb", verdict="false_positive", note="test note"
    )
    memories = MemoryStore().list_admin(scope="user", kind="analyst_pattern")
    assert any("test note" in m["content"] for m in memories)
    assert any(m["scope_id"] == "U-fb-1" for m in memories)
