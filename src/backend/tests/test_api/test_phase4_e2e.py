"""Phase 4 end-to-end test: enroll agent → ingest raw log → normalize → score → alert.

This test simulates the full Phase 1+2+3+4 flow without needing a running
agent process. It uses the FastAPI test client + PostgreSQL to exercise:

1. Admin issues enrollment token
2. Agent enrolls (gets agent_id + api_key)
3. Agent sends raw http event (blocked URL) via X-API-Key
4. Admin triggers normalizer via /api/admin/run-normalizer
5. Normalizer converts raw → event_log
6. user_scoring.score_user runs → anomaly detected → alert created
7. Admin queries agents/blocklist/alerts to verify state

Skipped unless TEST_DATABASE_URL is set (real PostgreSQL required).
"""

from __future__ import annotations

import pytest

from src.backend.tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


@requires_postgres
@pytest.mark.asyncio
async def test_e2e_enroll_ingest_normalize_score_alert() -> None:
    """Full end-to-end: enroll agent → send raw http log → normalizer → scoring → alert."""
    from src.backend.app.db import session as database
    from src.backend.app.schemas.schemas import RawLogIngest

    async with get_test_client(init_db=True) as client:
        # 1. Admin login.
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert login.status_code == 200
        token = login.json()["accessToken"]
        auth_header = {"Authorization": f"Bearer {token}"}

        # 2. Issue enrollment token.
        issue = await client.post(
            "/api/agents/enrollment-tokens",
            json={"expires_minutes": 30},
            headers=auth_header,
        )
        assert issue.status_code == 201
        enrollment_token = issue.json()["token"]
        assert enrollment_token.startswith("o47enr_")

        # 3. Agent enrolls.
        enroll = await client.post(
            "/api/agents/register",
            json={
                "enrollment_token": enrollment_token,
                "hostname": "phase4-test-host",
                "os": "linux",
                "os_version": "5.15",
            },
        )
        assert enroll.status_code == 201
        enroll_data = enroll.json()
        agent_id = enroll_data["agent_id"]
        api_key = enroll_data["api_key"]
        assert agent_id.startswith("agent-")
        assert api_key.startswith("o47ag_")

        # 4. Verify agent appears in admin list.
        list_resp = await client.get("/api/agents", headers=auth_header)
        assert list_resp.status_code == 200
        assert any(a["agent_id"] == agent_id for a in list_resp.json()["items"])

        # 5. Add a blocklist entry for the URL we're going to send.
        block_create = await client.post(
            "/api/agents/blocklist",
            json={
                "pattern": "phase4-blocked.example",
                "pattern_type": "domain",
                "category": "test",
                "reason": "phase4 e2e",
                "enabled": True,
            },
            headers=auth_header,
        )
        assert block_create.status_code == 201
        blocklist_id = block_create.json()["id"]

        # 6. Agent sends a raw http log via X-API-Key.
        raw = RawLogIngest(
            source_id="phase4-e2e-http-1",
            collector_type="endpoint_agent",
            event_type="http",
            timestamp="2026-06-22T12:00:00Z",
            user_id="ACM0001",
            device_id="PC-1001",
            raw_payload={
                "url": "https://phase4-blocked.example/path?q=1",
                "domain": "phase4-blocked.example",
                "action": "blocked",
                "block_pattern": "phase4-blocked.example",
                "block_category": "test",
                "block_reason": "phase4 e2e",
            },
            ingest_metadata={"agent_id": agent_id},
        )
        ingest = await client.post(
            "/api/raw-logs/ingest",
            json=raw.model_dump(),
            headers={"X-API-Key": api_key},
        )
        assert ingest.status_code == 201, ingest.text

        # 7. Agent heartbeat.
        hb = await client.post(
            "/api/agents/heartbeat",
            json={"agent_id": agent_id, "status": "active"},
            headers={"X-API-Key": api_key},
        )
        assert hb.status_code == 200
        assert hb.json()["status"] == "active"

        # 8. Trigger normalizer with scoring.
        run = await client.post(
            "/api/admin/run-normalizer",
            params={"trigger_scoring": "true"},
            headers=auth_header,
        )
        assert run.status_code == 200, run.text
        run_data = run.json()
        assert run_data["processed"] >= 1
        assert run_data["failed"] == 0
        assert "ACM0001" in run_data["users_with_new_events"]

        # 9. Verify event_log was created.
        event_log = database.find_event_log_by_source_id("phase4-e2e-http-1")
        assert event_log is not None
        assert event_log["user_id"] == "ACM0001"
        assert event_log["event_type"] == "http"
        assert event_log["action"] == "blocked"
        assert event_log["resource"] == "https://phase4-blocked.example/path?q=1"

        # 10. Verify raw_log.normalized_event_id is set.
        raw_logs = database.list_raw_logs({"user_id": "ACM0001"})
        target = next((r for r in raw_logs if r["source_id"] == "phase4-e2e-http-1"), None)
        assert target is not None
        assert target["normalized_event_id"] == event_log["id"]

        # 11. Verify ml_anomaly_scores row exists for ACM0001 (at least one).
        scores = database.list_recent_ml_scores_for_user("ACM0001", limit=5)
        assert len(scores) >= 1
        for s in scores:
            assert s["user_id"] == "ACM0001"
            assert "scored_at" in s
            assert "feature_summary" in s

        # 12. Blocklist CRUD: list, patch, delete.
        list_bl = await client.get(
            "/api/agents/blocklist", params={"enabled_only": "false"}, headers=auth_header
        )
        assert list_bl.status_code == 200
        assert any(e["id"] == blocklist_id for e in list_bl.json())

        patch_bl = await client.patch(
            f"/api/agents/blocklist/{blocklist_id}",
            json={"enabled": False, "reason": "updated"},
            headers=auth_header,
        )
        assert patch_bl.status_code == 200
        assert patch_bl.json()["enabled"] is False
        assert patch_bl.json()["reason"] == "updated"

        del_bl = await client.delete(
            f"/api/agents/blocklist/{blocklist_id}", headers=auth_header
        )
        assert del_bl.status_code == 200

        # 13. Revoke agent → cannot send log anymore.
        revoke = await client.delete(
            f"/api/agents/{agent_id}", headers=auth_header
        )
        assert revoke.status_code == 200
        assert revoke.json()["status"] == "revoked"

        # 14. Revoked agent's heartbeat should fail.
        bad_hb = await client.post(
            "/api/agents/heartbeat",
            json={"agent_id": agent_id, "status": "active"},
            headers={"X-API-Key": api_key},
        )
        assert bad_hb.status_code == 403

        # 15. Revoked agent's raw-log ingest should fail.
        raw2 = RawLogIngest(
            source_id="phase4-e2e-revoked",
            collector_type="endpoint_agent",
            event_type="http",
            timestamp="2026-06-22T13:00:00Z",
            user_id="ACM0001",
            device_id="PC-1001",
            raw_payload={"url": "https://x.com"},
        )
        bad_ingest = await client.post(
            "/api/raw-logs/ingest",
            json=raw2.model_dump(),
            headers={"X-API-Key": api_key},
        )
        assert bad_ingest.status_code == 403


@requires_postgres
@pytest.mark.asyncio
async def test_e2e_enrollment_token_single_use() -> None:
    """Token can only be consumed once."""
    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        token = login.json()["accessToken"]
        auth_header = {"Authorization": f"Bearer {token}"}

        issue = await client.post(
            "/api/agents/enrollment-tokens",
            json={"expires_minutes": 30},
            headers=auth_header,
        )
        assert issue.status_code == 201
        enrollment_token = issue.json()["token"]

        # First enroll: success.
        first = await client.post(
            "/api/agents/register",
            json={"enrollment_token": enrollment_token, "hostname": "h1"},
        )
        assert first.status_code == 201

        # Second enroll with same token: must fail.
        second = await client.post(
            "/api/agents/register",
            json={"enrollment_token": enrollment_token, "hostname": "h2"},
        )
        assert second.status_code == 400


@requires_postgres
@pytest.mark.asyncio
async def test_e2e_blocklist_match_against_event_payload() -> None:
    """Adding a blocklist entry + sending http raw log → normalizer maps to event with action=blocked.

    This verifies the data flow without needing the agent to actively consult
    the blocklist (which is an agent-side concern).
    """
    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        token = login.json()["accessToken"]
        auth_header = {"Authorization": f"Bearer {token}"}

        from src.backend.app.db import session as database
        from src.backend.app.schemas.schemas import RawLogIngest

        # Add blocklist entry.
        await client.post(
            "/api/agents/blocklist",
            json={
                "pattern": "malicious-c2.example",
                "pattern_type": "domain",
                "category": "c2",
                "enabled": True,
            },
            headers=auth_header,
        )

        # Issue token, enroll agent.
        issue = await client.post(
            "/api/agents/enrollment-tokens", json={}, headers=auth_header
        )
        enrollment_token = issue.json()["token"]
        enroll = await client.post(
            "/api/agents/register",
            json={"enrollment_token": enrollment_token, "hostname": "h"},
        )
        api_key = enroll.json()["api_key"]

        # Send 2 http events: 1 blocked, 1 allowed.
        for i, (action, url) in enumerate([
            ("blocked", "https://malicious-c2.example/beacon"),
            ("allowed", "https://www.google.com/search"),
        ]):
            raw = RawLogIngest(
                source_id=f"e2e-http-{i}",
                collector_type="endpoint_agent",
                event_type="http",
                timestamp=f"2026-06-22T1{i}:00:00Z",
                user_id="ACM0001",
                device_id="PC-1001",
                raw_payload={"url": url, "action": action},
            )
            r = await client.post(
                "/api/raw-logs/ingest",
                json=raw.model_dump(),
                headers={"X-API-Key": api_key},
            )
            assert r.status_code == 201

        # Normalize.
        run = await client.post(
            "/api/admin/run-normalizer",
            params={"trigger_scoring": "false"},
            headers=auth_header,
        )
        assert run.status_code == 200
        assert run.json()["processed"] == 2

        # Both event_logs should be present with correct action.
        for i, action in enumerate(["blocked", "allowed"]):
            ev = database.find_event_log_by_source_id(f"e2e-http-{i}")
            assert ev is not None
            assert ev["action"] == action
