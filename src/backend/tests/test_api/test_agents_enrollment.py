"""Tests for endpoint agent enrollment, auth, heartbeat, config, blocklist, revoke.

Two layers:
- Non-Postgres tests monkeypatch `src.backend.app.db.agents` helpers so they run
  in any environment (no PostgreSQL needed). These verify route wiring, auth
  branching, response shape, status codes.
- Postgres integration tests (skip unless TEST_DATABASE_URL set) exercise the
  real DB tables + helpers end-to-end, including the cross-router integration
  where an enrolled agent ingests raw logs via /api/raw-logs/batch using
  X-API-Key instead of a human JWT.
"""

from __future__ import annotations

import pytest

from src.backend.tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


# ---------------------------------------------------------------------------
# Non-Postgres tests: monkeypatch agent DB helpers
# ---------------------------------------------------------------------------


def _patch_admin_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.core import security as auth
    from src.backend.app.db import session as database

    monkeypatch.setattr(
        database,
        "get_account_by_email",
        lambda email: {
            "id": 1,
            "email": "admin@demo.com",
            "full_name": "Demo Admin",
            "role": "admin",
            "password_hash": auth.hash_password("admin123"),
            "is_active": True,
        }
        if email == "admin@demo.com"
        else None,
    )
    monkeypatch.setattr(
        database,
        "get_account_by_id",
        lambda aid: {
            "id": aid,
            "email": "admin@demo.com",
            "full_name": "Demo Admin",
            "role": "admin",
            "password_hash": auth.hash_password("admin123"),
            "is_active": True,
        }
        if aid == 1
        else None,
    )


async def _admin_token(client) -> str:
    response = await client.post(
        "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
    )
    assert response.status_code == 200
    return response.json()["accessToken"]


@pytest.mark.asyncio
async def test_create_enrollment_token_returns_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_admin_auth(monkeypatch)
    from src.backend.app.db import agents as agent_db

    captured: dict = {}

    def fake_create(created_by_account_id, expires_minutes=None):
        captured["account_id"] = created_by_account_id
        captured["ttl"] = expires_minutes
        return {
            "token": "o47enr_testtoken123",
            "token_id": "abc123def456",
            "expires_at": "2026-06-22T12:00:00Z",
            "created_at": "2026-06-22T11:00:00Z",
        }

    monkeypatch.setattr(agent_db, "create_enrollment_token", fake_create)

    async with get_test_client() as client:
        token = await _admin_token(client)
        response = await client.post(
            "/api/agents/enrollment-tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"expires_minutes": 120},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["token"] == "o47enr_testtoken123"
    assert data["token_id"]
    assert captured["account_id"] == 1
    assert captured["ttl"] == 120


@pytest.mark.asyncio
async def test_register_agent_returns_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.db import agents as agent_db

    captured: dict = {}

    def fake_register(
        enrollment_token, hostname, os=None, os_version=None,
        device_id=None, assigned_user_id=None,
    ):
        captured.update(
            enrollment_token=enrollment_token, hostname=hostname, os=os,
            device_id=device_id, assigned_user_id=assigned_user_id,
        )
        return {
            "agent_id": "agent-deadbeefcafe",
            "api_key": "o47ag_secretkey123",
            "policy_version": 1,
            "issued_at": "2026-06-22T11:05:00Z",
        }

    monkeypatch.setattr(agent_db, "register_agent", fake_register)

    async with get_test_client() as client:
        response = await client.post(
            "/api/agents/register",
            json={
                "enrollment_token": "o47enr_testtoken123",
                "hostname": "WS-001",
                "os": "Windows 11",
                "os_version": "23H2",
                "device_id": "PC-1001",
                "assigned_user_id": "ACM0001",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["agent_id"] == "agent-deadbeefcafe"
    assert data["api_key"] == "o47ag_secretkey123"
    assert data["policy_version"] == 1
    assert captured["enrollment_token"] == "o47enr_testtoken123"
    assert captured["hostname"] == "WS-001"
    assert captured["device_id"] == "PC-1001"


@pytest.mark.asyncio
async def test_register_agent_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.db import agents as agent_db

    def fake_register(**kwargs):
        raise ValueError("Invalid enrollment token")

    monkeypatch.setattr(agent_db, "register_agent", fake_register)

    async with get_test_client() as client:
        response = await client.post(
            "/api/agents/register",
            json={"enrollment_token": "bogus", "hostname": "WS-001"},
        )

    assert response.status_code == 400
    assert "Invalid" in response.json()["detail"]


@pytest.mark.asyncio
async def test_heartbeat_requires_api_key() -> None:
    async with get_test_client() as client:
        response = await client.post(
            "/api/agents/heartbeat",
            json={"metrics": {}},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_heartbeat_with_valid_agent_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.db import agents as agent_db

    fake_agent = {
        "agent_id": "agent-abc",
        "hostname": "WS-001",
        "status": "active",
        "policy_version": 1,
    }
    monkeypatch.setattr(
        agent_db,
        "get_agent_by_api_key",
        lambda key: fake_agent if key == "o47ag_valid" else None,
    )
    monkeypatch.setattr(
        agent_db,
        "update_agent_heartbeat",
        lambda agent_id, metrics=None: {
            "agent_id": agent_id,
            "status": "active",
            "policy_version": 1,
            "last_heartbeat": "2026-06-22T11:10:00Z",
        },
    )

    async with get_test_client() as client:
        response = await client.post(
            "/api/agents/heartbeat",
            headers={"X-API-Key": "o47ag_valid"},
            json={"metrics": {"events_buffered": 12}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["policy_version"] == 1
    assert data["last_heartbeat"]


@pytest.mark.asyncio
async def test_revoked_agent_cannot_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.db import agents as agent_db

    fake_agent = {
        "agent_id": "agent-xyz",
        "hostname": "WS-002",
        "status": "revoked",
        "policy_version": 1,
    }
    monkeypatch.setattr(
        agent_db,
        "get_agent_by_api_key",
        lambda key: fake_agent if key == "o47ag_revoked" else None,
    )

    async with get_test_client() as client:
        response = await client.post(
            "/api/agents/heartbeat",
            headers={"X-API-Key": "o47ag_revoked"},
            json={},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_agent_config_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.db import agents as agent_db

    monkeypatch.setattr(
        agent_db,
        "get_agent_by_api_key",
        lambda key: {"agent_id": "agent-cfg", "status": "active"} if key == "o47ag_cfg" else None,
    )
    monkeypatch.setattr(
        agent_db,
        "get_agent_config",
        lambda agent_id: {
            "policy_version": 2,
            "sampling_rate": 50,
            "enabled_collectors": ["logon", "http"],
            "blocklist": [{"id": 1, "pattern": "wikileaks.org", "enabled": True}],
            "server_time": "2026-06-22T11:15:00Z",
        },
    )

    async with get_test_client() as client:
        response = await client.get(
            "/api/agents/me/config",
            headers={"X-API-Key": "o47ag_cfg"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["policy_version"] == 2
    assert data["sampling_rate"] == 50
    assert data["enabled_collectors"] == ["logon", "http"]
    assert data["blocklist"][0]["pattern"] == "wikileaks.org"


@pytest.mark.asyncio
async def test_admin_list_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_admin_auth(monkeypatch)
    from src.backend.app.db import agents as agent_db

    monkeypatch.setattr(
        agent_db,
        "list_agents",
        lambda status_filter, limit, offset: [
            {"agent_id": "agent-1", "hostname": "WS-001", "status": "active",
             "policy_version": 1, "os": None, "os_version": None, "device_id": None,
             "assigned_user_id": None, "last_heartbeat": "t", "last_config_pull": "t",
             "enrolled_at": "t", "created_at": "t", "updated_at": "t"},
        ],
    )
    monkeypatch.setattr(agent_db, "count_agents", lambda status_filter=None: 1)

    async with get_test_client() as client:
        token = await _admin_token(client)
        response = await client.get(
            "/api/agents",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["agent_id"] == "agent-1"


@pytest.mark.asyncio
async def test_blocklist_crud(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_admin_auth(monkeypatch)
    from src.backend.app.db import agents as agent_db

    monkeypatch.setattr(
        agent_db,
        "create_blocklist_entry",
        lambda **kwargs: {
            "id": 7, "pattern": kwargs["pattern"], "pattern_type": kwargs.get("pattern_type", "domain"),
            "category": kwargs.get("category"), "reason": kwargs.get("reason"),
            "enabled": kwargs.get("enabled", True),
            "created_at": "t", "updated_at": "t",
        },
    )

    async with get_test_client() as client:
        token = await _admin_token(client)
        response = await client.post(
            "/api/agents/blocklist",
            headers={"Authorization": f"Bearer {token}"},
            json={"pattern": "evil.example.com", "pattern_type": "domain",
                  "category": "malware", "reason": "C2 server"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 7
    assert data["pattern"] == "evil.example.com"
    assert data["pattern_type"] == "domain"


# ---------------------------------------------------------------------------
# Postgres integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@requires_postgres
async def test_full_enroll_and_raw_log_with_agent_key() -> None:
    """End-to-end: admin issues token -> enroll agent -> agent sends raw log via X-API-Key."""

    async with get_test_client(init_db=True) as client:
        # 1. admin login
        token = await _admin_token(client)
        admin_headers = {"Authorization": f"Bearer {token}"}

        # 2. issue enrollment token
        resp = await client.post(
            "/api/agents/enrollment-tokens",
            headers=admin_headers,
            json={"expires_minutes": 30},
        )
        assert resp.status_code == 201
        enrollment_token = resp.json()["token"]

        # 3. register agent
        resp = await client.post(
            "/api/agents/register",
            json={
                "enrollment_token": enrollment_token,
                "hostname": "WS-IT-001",
                "os": "Linux",
                "os_version": "Ubuntu 22.04",
            },
        )
        assert resp.status_code == 201
        agent_id = resp.json()["agent_id"]
        api_key = resp.json()["api_key"]

        # 4. agent sends raw log with X-API-Key (no Bearer)
        resp = await client.post(
            "/api/raw-logs/ingest",
            headers={"X-API-Key": api_key},
            json={
                "source_id": f"agent:{agent_id}:logon:1",
                "collector_type": "endpoint_agent",
                "event_type": "logon",
                "timestamp": "2026-06-22T08:00:00Z",
                "raw_payload": {"action": "Logon", "username": "acm0001"},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["source_id"] == f"agent:{agent_id}:logon:1"

        # 5. agent heartbeat
        resp = await client.post(
            "/api/agents/heartbeat",
            headers={"X-API-Key": api_key},
            json={"metrics": {"events_buffered": 1}},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        # 6. agent pulls config
        resp = await client.get(
            "/api/agents/me/config",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200
        cfg = resp.json()
        assert cfg["policy_version"] >= 1
        assert "logon" in cfg["enabled_collectors"]

        # 7. admin can list and see the agent
        resp = await client.get("/api/agents", headers=admin_headers)
        assert resp.status_code == 200
        assert any(a["agent_id"] == agent_id for a in resp.json()["items"])

        # 8. revoke
        resp = await client.delete(f"/api/agents/{agent_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"

        # 9. revoked agent cannot send raw log
        resp = await client.post(
            "/api/raw-logs/ingest",
            headers={"X-API-Key": api_key},
            json={
                "source_id": f"agent:{agent_id}:logon:2",
                "collector_type": "endpoint_agent",
                "event_type": "logon",
                "timestamp": "2026-06-22T08:05:00Z",
            },
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_batch_ingest_with_agent_key_inherits_user_device() -> None:
    """Agent with assigned_user_id + device_id auto-fills them on raw-logs/batch."""

    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        admin_headers = {"Authorization": f"Bearer {token}"}

        # enroll agent
        resp = await client.post(
            "/api/agents/enrollment-tokens",
            headers=admin_headers,
            json={"expires_minutes": 30},
        )
        enrollment_token = resp.json()["token"]

        # create a user + device first so we can attach to the agent (idempotent:
        # 409 is OK if they already exist from a previous test run)
        resp = await client.post(
            "/api/users",
            headers=admin_headers,
            json={"id": "AGTUSR001", "username": "agtusr001",
                  "full_name": "Agent User", "email": "agtusr001@demo.com",
                  "department": "IT", "job_role": "Engineer"},
        )
        assert resp.status_code in (200, 201, 409)
        resp = await client.post(
            "/api/devices",
            headers=admin_headers,
            json={"id": "PC-AGT-001", "hostname": "WS-IT-002", "os": "Linux"},
        )
        assert resp.status_code in (200, 201, 409)

        resp = await client.post(
            "/api/agents/register",
            json={
                "enrollment_token": enrollment_token,
                "hostname": "WS-IT-002",
                "device_id": "PC-AGT-001",
                "assigned_user_id": "AGTUSR001",
            },
        )
        assert resp.status_code == 201
        api_key = resp.json()["api_key"]

        # batch raw-log ingest without explicit user_id/device_id
        resp = await client.post(
            "/api/raw-logs/batch",
            headers={"X-API-Key": api_key},
            json={
                "records": [
                    {
                        "source_id": "agent-batch:1",
                        "collector_type": "endpoint_agent",
                        "event_type": "http",
                        "timestamp": "2026-06-22T09:00:00Z",
                        "raw_payload": {"url": "example.com", "action": "allowed"},
                    },
                    {
                        "source_id": "agent-batch:2",
                        "collector_type": "endpoint_agent",
                        "event_type": "http",
                        "timestamp": "2026-06-22T09:01:00Z",
                        "raw_payload": {"url": "wikileaks.org", "action": "blocked"},
                    },
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_or_updated"] == 2
        assert data["failed"] == 0

        # verify user_id + device_id were auto-filled
        resp = await client.get(
            "/api/raw-logs?user_id=AGTUSR001&device_id=PC-AGT-001",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2


@pytest.mark.asyncio
@requires_postgres
async def test_enrollment_token_single_use() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        admin_headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/agents/enrollment-tokens",
            headers=admin_headers,
            json={"expires_minutes": 30},
        )
        enrollment_token = resp.json()["token"]

        # first use succeeds
        resp = await client.post(
            "/api/agents/register",
            json={"enrollment_token": enrollment_token, "hostname": "WS-A"},
        )
        assert resp.status_code == 201

        # second use fails
        resp = await client.post(
            "/api/agents/register",
            json={"enrollment_token": enrollment_token, "hostname": "WS-B"},
        )
        assert resp.status_code == 400
        assert "already used" in resp.json()["detail"]


@pytest.mark.asyncio
@requires_postgres
async def test_blocklist_full_crud() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        admin_headers = {"Authorization": f"Bearer {token}"}

        # create
        resp = await client.post(
            "/api/agents/blocklist",
            headers=admin_headers,
            json={"pattern": "blocked.example.net", "pattern_type": "domain",
                  "category": "policy", "reason": "test", "enabled": True},
        )
        assert resp.status_code == 201
        entry_id = resp.json()["id"]

        # list
        resp = await client.get("/api/agents/blocklist", headers=admin_headers)
        assert resp.status_code == 200
        assert any(e["id"] == entry_id for e in resp.json())

        # patch
        resp = await client.patch(
            f"/api/agents/blocklist/{entry_id}",
            headers=admin_headers,
            json={"enabled": False, "reason": "disabled for test"},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

        # delete
        resp = await client.delete(
            f"/api/agents/blocklist/{entry_id}", headers=admin_headers
        )
        assert resp.status_code == 204


@pytest.mark.asyncio
@requires_postgres
async def test_policy_update_bumps_version() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        admin_headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get("/api/agents/policy", headers=admin_headers)
        initial_version = resp.json()["policy_version"]

        resp = await client.patch(
            "/api/agents/policy",
            headers=admin_headers,
            json={"sampling_rate": 75, "enabled_collectors": ["logon", "http", "file"]},
        )
        assert resp.status_code == 200
        new_policy = resp.json()
        assert new_policy["policy_version"] == initial_version + 1
        assert new_policy["sampling_rate"] == 75
        assert new_policy["enabled_collectors"] == ["logon", "http", "file"]
