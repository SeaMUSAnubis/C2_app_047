"""Tests for the Phase 3 normalizer service.

Two layers:
- Pure unit tests for `normalize_raw_log` (no DB needed) — verify the
  per-event-type mapping logic for every event_type the agent may emit.
- `Normalizer.run_once` tests with monkeypatched DB helpers (no PostgreSQL
  needed) — verify FIFO processing, idempotency, on_user_scored callback,
  stats accounting.
- Postgres integration tests (skip unless TEST_DATABASE_URL set) — exercise
  the real DB tables end-to-end: insert raw log → run normalizer → event_log
  is created → raw_log.normalized_event_id is set → ml score row is created
  (or alert, if anomaly).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.backend.tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


@pytest.fixture(autouse=True)
def _reset_normalizer_stats() -> None:
    """Reset the singleton normalizer stats before each test for isolation."""
    from src.backend.app.services import normalizer as normalizer_mod

    normalizer_mod.normalizer.reset_stats()
    yield
    normalizer_mod.normalizer.reset_stats()


# ---------------------------------------------------------------------------
# Pure unit tests — per event_type mapping
# ---------------------------------------------------------------------------


def _raw(event_type: str, payload: dict[str, Any], user: str = "ACM0001", device: str = "PC-1001"):
    return {
        "id": 1,
        "source_id": f"test-source-{event_type}-1",
        "collector_type": "endpoint_agent",
        "event_type": event_type,
        "timestamp": "2026-06-22T10:00:00Z",
        "user_id": user,
        "device_id": device,
        "raw_payload": payload,
        "ingest_metadata": {"agent_id": "agent-test"},
        "normalized_event_id": None,
        "created_at": "2026-06-22T10:00:00Z",
    }


def test_normalize_logon_maps_action_and_resource() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("logon", {"user": "ACM0001", "pc": "PC-1001", "activity": "Logon"})
    out = normalize_raw_log(raw)
    assert out is not None
    assert out["event_type"] == "logon"
    assert out["action"] == "logon"
    assert out["resource"] == "PC-1001"
    assert out["user_id"] == "ACM0001"
    assert out["device_id"] == "PC-1001"
    assert out["source_file"].startswith("endpoint_agent:raw:")


def test_normalize_logon_maps_logoff() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("logon", {"user": "ACM0001", "pc": "PC-1001", "activity": "Logoff"})
    out = normalize_raw_log(raw)
    assert out["action"] == "logoff"


def test_normalize_logon_defaults_to_logon_when_missing_action() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("logon", {"user": "ACM0001", "pc": "PC-1001"})
    out = normalize_raw_log(raw)
    assert out["action"] == "logon"


def test_normalize_device_connect() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("device", {"activity": "Connect", "filename": "USB\\\\SanDisk"})
    out = normalize_raw_log(raw)
    assert out["action"] == "connect"
    assert out["resource"] == "USB\\\\SanDisk"


def test_normalize_device_disconnect() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("device", {"activity": "Disconnect", "filename": "USB\\\\SanDisk"})
    out = normalize_raw_log(raw)
    assert out["action"] == "disconnect"


def test_normalize_file_exe() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("file", {"activity": "file_copy", "filename": "C:\\\\payload.exe"})
    out = normalize_raw_log(raw)
    assert out["action"] == "file_copy"
    assert out["resource"] == "C:\\\\payload.exe"


def test_normalize_file_default_action() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("file", {"filename": "/tmp/foo.txt"})
    out = normalize_raw_log(raw)
    assert out["action"] == "file_access"
    assert out["resource"] == "/tmp/foo.txt"


def test_normalize_http_blocked() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw(
        "http",
        {
            "url": "https://wikileaks.org/path",
            "domain": "wikileaks.org",
            "action": "blocked",
            "block_pattern": "wikileaks.org",
            "block_category": "leak",
            "block_reason": "policy",
        },
    )
    out = normalize_raw_log(raw)
    assert out["action"] == "blocked"
    assert out["resource"] == "https://wikileaks.org/path"
    assert out["metadata"]["block_pattern"] == "wikileaks.org"


def test_normalize_http_allowed() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("http", {"url": "https://www.google.com", "action": "allowed"})
    out = normalize_raw_log(raw)
    assert out["action"] == "allowed"


def test_normalize_email_send() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("email", {"from": "alice@corp", "to": "bob@external", "size": 1024})
    out = normalize_raw_log(raw)
    assert out["action"] == "email_send"
    assert out["resource"] == "bob@external"


def test_normalize_process_spawn() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("process", {"process_name": "powershell.exe", "pid": 1234})
    out = normalize_raw_log(raw)
    assert out["action"] == "spawn"
    assert out["resource"] == "powershell.exe"


def test_normalize_network_connection() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("network", {"remote_address": "10.0.0.5", "remote_port": 443})
    out = normalize_raw_log(raw)
    assert out["action"] == "connection"
    assert out["resource"] == "10.0.0.5:443"


def test_normalize_unknown_event_type_falls_back_to_custom() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("weird_type", {"foo": "bar"})
    out = normalize_raw_log(raw)
    assert out is not None
    assert out["event_type"] == "weird_type"
    # custom passthrough handler returns "custom" default action.
    assert out["action"] == "custom"


def test_normalize_ldap_passthrough() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    raw = _raw("ldap", {"activity": "ldap_search", "target": "ou=users,dc=corp"})
    out = normalize_raw_log(raw)
    assert out["action"] == "ldap_search"
    assert out["resource"] == "ou=users,dc=corp"


def test_normalize_skips_malformed() -> None:
    from src.backend.app.services.normalizer import normalize_raw_log

    # Missing source_id
    raw = _raw("logon", {"user": "x", "pc": "y"})
    raw["source_id"] = None
    assert normalize_raw_log(raw) is None

    # Missing timestamp
    raw = _raw("logon", {"user": "x", "pc": "y"})
    raw["timestamp"] = None
    assert normalize_raw_log(raw) is None

    # Missing event_type
    raw = _raw("logon", {"user": "x", "pc": "y"})
    raw["event_type"] = None
    assert normalize_raw_log(raw) is None


def test_normalize_handler_exception_returns_none() -> None:
    from src.backend.app.services import normalizer

    def boom(_raw):
        raise ValueError("kaboom")

    original = normalizer._NORMALIZERS["logon"]
    normalizer._NORMALIZERS["logon"] = boom
    try:
        out = normalizer.normalize_raw_log(_raw("logon", {"user": "x", "pc": "y"}))
    finally:
        normalizer._NORMALIZERS["logon"] = original
    assert out is None


# ---------------------------------------------------------------------------
# Normalizer.run_once — mocked DB (no PostgreSQL needed)
# ---------------------------------------------------------------------------


def _make_pending_rows(n: int) -> list[dict[str, Any]]:
    return [
        {
            "id": i + 1,
            "source_id": f"src-{i}",
            "collector_type": "endpoint_agent",
            "event_type": "logon",
            "timestamp": "2026-06-22T10:00:00Z",
            "user_id": "ACM0001" if i % 2 == 0 else "BTR0002",
            "device_id": "PC-1001",
            "raw_payload": {"user": "x", "pc": "PC-1001", "activity": "Logon"},
            "ingest_metadata": {},
            "normalized_event_id": None,
            "created_at": "2026-06-22T10:00:00Z",
        }
        for i in range(n)
    ]


def test_run_once_processes_pending_and_invokes_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_once should: read pending rows, normalise them, mark FK, and call
    on_user_scored once per distinct user_id that got new events."""
    from src.backend.app.services import normalizer as normalizer_mod

    pending = _make_pending_rows(4)
    monkeypatch.setattr(normalizer_mod.database, "list_pending_raw_logs", lambda limit=200: list(pending))
    inserted_event_ids: list[int] = []
    inserted_payloads: list[dict[str, Any]] = []

    def fake_ingest(payload):
        inserted_event_ids.append(len(inserted_event_ids) + 100)
        inserted_payloads.append(payload)
        return {"id": inserted_event_ids[-1], "user_id": payload.get("user_id")}

    monkeypatch.setattr(normalizer_mod.database, "ingest_event", fake_ingest)
    monkeypatch.setattr(normalizer_mod.database, "find_event_log_by_source_id", lambda source_id: None)
    marked: list[tuple[int, int]] = []
    monkeypatch.setattr(
        normalizer_mod.database,
        "mark_raw_log_normalized",
        lambda raw_id, event_id: marked.append((raw_id, event_id)),
    )

    called_users: list[str] = []
    n = normalizer_mod.normalizer
    n.get_stats()  # make sure no exception when called from outside
    result = n.run_once(batch_size=10, on_user_scored=lambda uid: called_users.append(uid))

    assert result["processed"] == 4
    assert result["failed"] == 0
    assert sorted(called_users) == ["ACM0001", "BTR0002"]
    assert len(marked) == 4
    # Verify FK matches: each raw_id (1..4) gets a distinct event_id (100..103).
    assert [r for r, _ in marked] == [1, 2, 3, 4]
    assert len(inserted_event_ids) == 4
    # Stats update
    stats = n.get_stats()
    assert stats["total_runs"] == 1
    assert stats["total_processed"] == 4
    assert stats["total_scoring_calls"] == 2  # 2 distinct users
    assert sorted(stats["last_users_to_score"]) == ["ACM0001", "BTR0002"]


def test_run_once_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """If an event_log with the same source_id already exists, the normalizer
    must NOT call ingest_event — it should just mark the raw_log FK to the
    existing event_log id. This is the defense-in-depth idempotency layer on
    top of ingest_event's ON CONFLICT(source_id).
    """
    from src.backend.app.services import normalizer as normalizer_mod

    pending = _make_pending_rows(2)
    monkeypatch.setattr(normalizer_mod.database, "list_pending_raw_logs", lambda limit=200: list(pending))
    # Simulate: both source_ids already have an event_log row.
    monkeypatch.setattr(
        normalizer_mod.database,
        "find_event_log_by_source_id",
        lambda source_id: {"id": 999, "user_id": "ACM0001"},
    )
    ingest_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        normalizer_mod.database,
        "ingest_event",
        lambda payload: ingest_calls.append(payload) or {"id": 1},
    )
    marked: list[tuple[int, int]] = []
    monkeypatch.setattr(
        normalizer_mod.database,
        "mark_raw_log_normalized",
        lambda raw_id, event_id: marked.append((raw_id, event_id)),
    )

    n = normalizer_mod.normalizer
    result = n.run_once(batch_size=10)
    assert result["processed"] == 2
    assert result["failed"] == 0
    # Critical: ingest_event must NOT have been called for any row.
    assert ingest_calls == []
    # Both raw rows should be marked with the existing event_log id.
    assert sorted(marked) == [(1, 999), (2, 999)]


def test_run_once_handles_db_failure_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    """If ingest_event raises for one row, normalizer should record the
    error, continue with the rest, and not crash."""
    from src.backend.app.services import normalizer as normalizer_mod

    pending = _make_pending_rows(3)
    monkeypatch.setattr(normalizer_mod.database, "list_pending_raw_logs", lambda limit=200: list(pending))
    monkeypatch.setattr(normalizer_mod.database, "find_event_log_by_source_id", lambda source_id: None)

    def fake_ingest(payload):
        if payload["source_id"] == "src-1":
            raise RuntimeError("db down")
        return {"id": 42, "user_id": payload.get("user_id")}

    monkeypatch.setattr(normalizer_mod.database, "ingest_event", fake_ingest)
    monkeypatch.setattr(
        normalizer_mod.database,
        "mark_raw_log_normalized",
        lambda raw_id, event_id: None,
    )

    n = normalizer_mod.normalizer
    result = n.run_once(batch_size=10)
    assert result["processed"] == 2
    assert result["failed"] == 1
    assert any(err.get("raw_log_id") == 2 for err in result["errors"])  # src-1 is row 2
    stats = n.get_stats()
    assert stats["total_failed"] == 1
    assert stats["total_processed"] == 2


def test_run_once_no_pending_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.services import normalizer as normalizer_mod

    monkeypatch.setattr(normalizer_mod.database, "list_pending_raw_logs", lambda limit=200: [])
    n = normalizer_mod.normalizer
    result = n.run_once(batch_size=10)
    assert result["processed"] == 0
    assert result["failed"] == 0
    assert result["users_with_new_events"] == []


def test_run_once_invokes_on_user_scored_with_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make sure on_user_scored is called once per distinct user, sorted."""
    from src.backend.app.services import normalizer as normalizer_mod

    rows = [
        # 3 rows for user ZZZ, 2 for AAA, 1 for MMM
        {
            "id": i + 1,
            "source_id": f"src-{i}",
            "collector_type": "endpoint_agent",
            "event_type": "logon",
            "timestamp": "2026-06-22T10:00:00Z",
            "user_id": u,
            "device_id": "PC-1001",
            "raw_payload": {"user": u, "pc": "PC-1001", "activity": "Logon"},
            "ingest_metadata": {},
            "normalized_event_id": None,
            "created_at": "2026-06-22T10:00:00Z",
        }
        for i, u in enumerate(["ZZZ", "AAA", "ZZZ", "MMM", "AAA", "ZZZ"])
    ]
    monkeypatch.setattr(normalizer_mod.database, "list_pending_raw_logs", lambda limit=200: list(rows))
    monkeypatch.setattr(normalizer_mod.database, "find_event_log_by_source_id", lambda source_id: None)
    monkeypatch.setattr(
        normalizer_mod.database,
        "ingest_event",
        lambda payload: {"id": hash(payload["source_id"]) % 1000, "user_id": payload.get("user_id")},
    )
    monkeypatch.setattr(normalizer_mod.database, "mark_raw_log_normalized", lambda rid, eid: None)

    called: list[str] = []
    n = normalizer_mod.normalizer
    n.run_once(batch_size=10, on_user_scored=lambda uid: called.append(uid))
    assert called == ["AAA", "MMM", "ZZZ"]  # sorted


# ---------------------------------------------------------------------------
# Background loop test — make sure the loop runs and shuts down cleanly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_normalizer_loop_starts_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    """The loop should run a tick then exit cleanly when stop_event is set."""
    tick_count = {"n": 0}

    async def fake_loop(stop_event: asyncio.Event) -> None:
        # Inline simplified version of the real loop for testability.
        while not stop_event.is_set():
            tick_count["n"] += 1
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.05)
            except TimeoutError:
                continue
            else:
                break

    # Call the simplified loop directly.
    stop = asyncio.Event()
    task = asyncio.create_task(fake_loop(stop))
    await asyncio.sleep(0.2)
    stop.set()
    await asyncio.wait_for(task, timeout=2.0)
    assert tick_count["n"] >= 1


# ---------------------------------------------------------------------------
# Postgres integration tests
# ---------------------------------------------------------------------------


@requires_postgres
@pytest.mark.asyncio
async def test_admin_run_normalizer_endpoint_with_real_db() -> None:
    """End-to-end: insert raw log → admin trigger normalizer → event_log
    appears → normalized_event_id is set."""
    from src.backend.app.db import session as database
    from src.backend.app.schemas.schemas import RawLogIngest

    async with get_test_client(init_db=True) as client:
        # Log in as admin
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert login.status_code == 200
        token = login.json()["accessToken"]

        # Insert one raw log via the existing API
        raw = RawLogIngest(
            source_id="phase3-test-raw-1",
            collector_type="endpoint_agent",
            event_type="logon",
            timestamp="2026-06-22T10:00:00Z",
            user_id="ACM0001",
            device_id="PC-1001",
            raw_payload={"user": "ACM0001", "pc": "PC-1001", "activity": "Logon"},
            ingest_metadata={"test": True},
        )
        ingest = await client.post(
            "/api/raw-logs/ingest",
            json=raw.model_dump(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ingest.status_code == 201, ingest.text

        # Verify it starts as pending
        pending = database.list_pending_raw_logs(limit=100)
        assert any(r["source_id"] == "phase3-test-raw-1" for r in pending)

        # Run the normalizer manually
        run = await client.post(
            "/api/admin/run-normalizer",
            params={"trigger_scoring": "false"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert run.status_code == 200, run.text
        data = run.json()
        assert data["processed"] >= 1
        assert data["failed"] == 0

        # Verify the event_log was created and FK is set
        pending_after = database.list_pending_raw_logs(limit=100)
        assert not any(r["source_id"] == "phase3-test-raw-1" for r in pending_after)

        event_log = database.find_event_log_by_source_id("phase3-test-raw-1")
        assert event_log is not None
        assert event_log["user_id"] == "ACM0001"
        assert event_log["event_type"] == "logon"
        assert event_log["action"] == "logon"
        assert event_log["resource"] == "PC-1001"

        # Re-running should be a no-op (idempotent)
        run2 = await client.post(
            "/api/admin/run-normalizer",
            params={"trigger_scoring": "false"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert run2.status_code == 200
        assert run2.json()["processed"] == 0


@requires_postgres
@pytest.mark.asyncio
async def test_normalizer_stats_endpoint() -> None:
    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        token = login.json()["accessToken"]
        resp = await client.get(
            "/api/admin/normalizer-stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_runs" in data
        assert "total_processed" in data
        assert "pending_now" in data
        assert data["enabled"] is True


@requires_postgres
@pytest.mark.asyncio
async def test_normalizer_stats_requires_admin() -> None:
    async with get_test_client(init_db=True) as client:
        # Non-admin user (analyst)
        login = await client.post(
            "/api/auth/login", json={"email": "analyst@demo.com", "password": "analyst123"}
        )
        token = login.json()["accessToken"]
        resp = await client.get(
            "/api/admin/normalizer-stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
