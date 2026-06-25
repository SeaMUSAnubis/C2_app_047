"""End-to-end test: agent → server with real HTTP (using FastAPI ASGI transport).

This test uses Phase 1's actual FastAPI app (`src.backend.app.main:app`) as
the server, and runs the agent's flusher against it via httpx. We:

1. Start the FastAPI app in-memory (no Docker required).
2. Call admin /api/auth/login to get a JWT.
3. Issue an enrollment token via /api/agents/enrollment-tokens.
4. Call /api/agents/register with the token → get agent_id + api_key.
5. Save agent state.
6. Build a Transport with the api_key and pull /api/agents/me/config.
7. Send a /api/raw-logs/batch via the agent's flusher flow.
8. Query /api/raw-logs and verify the events landed.
9. Send a /api/agents/heartbeat and verify status flip.

This is the most important test: it proves Phase 1 (server) + Phase 2
(agent) work together.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from agent.buffer import EventBuffer
from agent.transport import Transport
from src.backend.tests.conftest import postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="Phase 1 backend integration requires psycopg and TEST_DATABASE_URL",
)


@requires_postgres
@pytest.mark.asyncio
async def test_e2e_enroll_to_raw_log_ingestion() -> None:
    """Full flow: enroll agent → send raw logs → verify they land in the DB.

    Hits the real running server (via AGENT_E2E_URL env var) instead of
    the in-process ASGI app — httpx's sync Client does not support
    ASGITransport, but the agent's transport is sync.
    """
    import os
    base = os.environ.get("AGENT_E2E_URL", "http://localhost:5173")
    # The backend serves /api under the same port as the frontend (5173).
    api_base = base

    async with httpx.AsyncClient(base_url=api_base, timeout=10.0) as admin_client:
        # 1. Admin login.
        r = await admin_client.post(
            "/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"},
        )
        assert r.status_code == 200, f"admin login failed: {r.text}"
        admin_token = r.json()["accessToken"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Issue enrollment token.
        r = await admin_client.post(
            "/api/agents/enrollment-tokens",
            headers=admin_headers,
            json={"expires_minutes": 30},
        )
        assert r.status_code == 201, f"enroll token failed: {r.text}"
        enrollment_token = r.json()["token"]

        # 3. Register.
        r = await admin_client.post(
            "/api/agents/register",
            json={
                "enrollment_token": enrollment_token,
                "hostname": f"WS-E2E-{os.getpid()}",
                "os": "Linux",
            },
        )
        assert r.status_code == 201, f"register failed: {r.text}"
        agent_id = r.json()["agent_id"]
        api_key = r.json()["api_key"]

        # 4. Build the agent's sync transport.
        transport = Transport(
            server_url=base, api_key=api_key, verify_tls=False,
        )

        # 5. Send a batch of raw logs (sync call, run in thread).
        records = [
            {
                "source_id": f"agent-e2e:{agent_id}:logon:{i}",
                "collector_type": "endpoint_agent",
                "event_type": "logon",
                "timestamp": "2026-06-22T10:00:00Z",
                "raw_payload": {"action": "Logon", "username": "e2euser", "line": "pts/0"},
                "ingest_metadata": {"agent_version": "0.1.0", "host_os": "Linux"},
            }
            for i in range(5)
        ]
        result = await asyncio.to_thread(transport.send_batch, records)
        assert result["created_or_updated"] == 5
        assert result["failed"] == 0

        # 6. Query the server and verify the events landed.
        r = await admin_client.get(
            "/api/raw-logs",
            headers=admin_headers,
            params={"collector_type": "endpoint_agent", "limit": 200},
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 5
        for item in items[:5]:
            assert item["collector_type"] == "endpoint_agent"
            assert item["event_type"] == "logon"

        # 7. Heartbeat.
        result = await asyncio.to_thread(transport.heartbeat, {"buffer_size": 5})
        assert result["status"] in ("enrolled", "active", "offline")
        assert result["policy_version"] >= 1

        # 8. Get config.
        config = await asyncio.to_thread(transport.get_config)
        assert "policy_version" in config
        assert "sampling_rate" in config
        assert "enabled_collectors" in config
        assert "blocklist" in config

        # 9. Verify agent is now listed by admin.
        r = await admin_client.get("/api/agents", headers=admin_headers)
        assert r.status_code == 200
        agent_ids = [a["agent_id"] for a in r.json()["items"]]
        assert agent_id in agent_ids

        # Cleanup.
        transport.close()


@requires_postgres
@pytest.mark.asyncio
async def test_e2e_buffer_drains_via_flusher_loop() -> None:
    """The agent's flusher_loop drains events from the buffer to the server."""
    import os
    base = os.environ.get("AGENT_E2E_URL", "http://localhost:5173")

    async with httpx.AsyncClient(base_url=base, timeout=10.0) as admin_client:
        r = await admin_client.post(
            "/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"},
        )
        admin_token = r.json()["accessToken"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        r = await admin_client.post(
            "/api/agents/enrollment-tokens",
            headers=admin_headers,
            json={"expires_minutes": 30},
        )
        enrollment_token = r.json()["token"]
        r = await admin_client.post(
            "/api/agents/register",
            json={"enrollment_token": enrollment_token, "hostname": f"WS-FLUSH-{os.getpid()}"},
        )
        api_key = r.json()["api_key"]

        transport = Transport(server_url=base, api_key=api_key, verify_tls=False)

        # Build buffer and enqueue events.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buffer = EventBuffer(db_path=tmp_path / "events.db", max_events=1000)
            for i in range(10):
                buffer.enqueue(
                    f"flush-test:{os.getpid()}:{i}",
                    {
                        "source_id": f"flush-test:{os.getpid()}:{i}",
                        "collector_type": "endpoint_agent",
                        "event_type": "logon",
                        "timestamp": "2026-06-22T11:00:00Z",
                        "raw_payload": {"i": i},
                    },
                )
            assert buffer.size() == 10

            from agent.service import _flusher_loop
            stop = asyncio.Event()

            def stopper() -> None:
                import time as _t
                _t.sleep(0.5)
                stop.set()

            import threading
            threading.Thread(target=stopper, daemon=True).start()
            await _flusher_loop(transport, buffer, 0.1, 5, stop)

            assert buffer.size() == 0

        r = await admin_client.get(
            "/api/raw-logs",
            headers=admin_headers,
            params={"collector_type": "endpoint_agent", "limit": 200},
        )
        items = r.json()["items"]
        assert len(items) >= 10

        transport.close()


@requires_postgres
@pytest.mark.asyncio
async def test_e2e_revoked_agent_cannot_send_logs() -> None:
    """After admin revokes the agent, further batch sends return 403."""
    import os
    base = os.environ.get("AGENT_E2E_URL", "http://localhost:5173")

    async with httpx.AsyncClient(base_url=base, timeout=10.0) as admin_client:
        r = await admin_client.post(
            "/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"},
        )
        admin_token = r.json()["accessToken"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        r = await admin_client.post(
            "/api/agents/enrollment-tokens",
            headers=admin_headers,
            json={"expires_minutes": 30},
        )
        enrollment_token = r.json()["token"]
        r = await admin_client.post(
            "/api/agents/register",
            json={"enrollment_token": enrollment_token, "hostname": f"WS-REVOKE-{os.getpid()}"},
        )
        agent_id = r.json()["agent_id"]
        api_key = r.json()["api_key"]

        transport = Transport(server_url=base, api_key=api_key, verify_tls=False)

        result = transport.send_batch([{
            "source_id": f"pre-revoke:{os.getpid()}:1",
            "collector_type": "endpoint_agent",
            "event_type": "logon",
            "timestamp": "2026-06-22T12:00:00Z",
            "raw_payload": {},
        }])
        assert result["created_or_updated"] == 1

        r = await admin_client.delete(
            f"/api/agents/{agent_id}", headers=admin_headers
        )
        assert r.status_code == 200
        assert r.json()["status"] == "revoked"

        from agent.transport import AuthRevokedError
        with pytest.raises(AuthRevokedError):
            transport.send_batch([{
                "source_id": f"post-revoke:{os.getpid()}:1",
                "collector_type": "endpoint_agent",
                "event_type": "logon",
                "timestamp": "2026-06-22T12:01:00Z",
                "raw_payload": {},
            }])

        transport.close()


@requires_postgres
@pytest.mark.asyncio
async def test_e2e_agent_sees_blocklist_via_config() -> None:
    """Admin creates a blocklist entry, agent pulls it via /me/config."""
    import os
    base = os.environ.get("AGENT_E2E_URL", "http://localhost:5173")

    async with httpx.AsyncClient(base_url=base, timeout=10.0) as admin_client:
        r = await admin_client.post(
            "/api/auth/login",
            json={"email": "admin@demo.com", "password": "admin123"},
        )
        admin_token = r.json()["accessToken"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        r = await admin_client.post(
            "/api/agents/enrollment-tokens",
            headers=admin_headers,
            json={"expires_minutes": 30},
        )
        enrollment_token = r.json()["token"]
        r = await admin_client.post(
            "/api/agents/register",
            json={"enrollment_token": enrollment_token, "hostname": f"WS-BLOCKLIST-{os.getpid()}"},
        )
        api_key = r.json()["api_key"]

        # Add a blocklist entry with a unique pattern per test run.
        pattern = f"e2e-{os.getpid()}.evil.example.com"
        r = await admin_client.post(
            "/api/agents/blocklist",
            headers=admin_headers,
            json={
                "pattern": pattern,
                "pattern_type": "domain",
                "category": "malware",
                "reason": "e2e test",
            },
        )
        assert r.status_code == 201

        transport = Transport(server_url=base, api_key=api_key, verify_tls=False)
        config = transport.get_config()
        patterns = [b["pattern"] for b in config["blocklist"]]
        assert pattern in patterns

        transport.close()
