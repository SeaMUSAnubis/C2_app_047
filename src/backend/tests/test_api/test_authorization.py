"""Authorization / RBAC test cases."""

import uuid

import pytest

from src.backend.tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


async def _login(client, email: str, password: str) -> str:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def _ensure_account_active(email: str) -> None:
    from src.backend.app.db import session as database
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE app_accounts SET is_active = TRUE WHERE email = %s", (email,))


async def _admin_token(client) -> str:
    await _ensure_account_active("admin@demo.com")
    return await _login(client, "admin@demo.com", "admin123")


async def _analyst_token(client) -> str:
    await _ensure_account_active("analyst@demo.com")
    return await _login(client, "analyst@demo.com", "analyst123")


async def _security_manager_token(client) -> str:
    await _ensure_account_active("security@demo.com")
    return await _login(client, "security@demo.com", "security123")


async def _employee_token(client) -> str:
    await _ensure_account_active("employee@demo.com")
    return await _login(client, "employee@demo.com", "employee123")


@pytest.mark.asyncio
@requires_postgres
async def test_authz01_admin_can_create_user() -> None:
    uid = uuid.uuid4().hex[:8]
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"AUTHZ{uid}", "username": f"authz{uid}", "full_name": "AuthZ Test User"})
    assert resp.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_authz02_analyst_cannot_create_user() -> None:
    uid = uuid.uuid4().hex[:8]
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"AUTHZ{uid}", "username": f"authz{uid}", "full_name": "Blocked"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz03_no_token_cannot_create_user() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.post("/api/users", json={"id": "AUTHZ03", "username": "authz03", "full_name": "Blocked"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
@requires_postgres
async def test_authz04_admin_can_update_user() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.patch("/api/users/ACM0001", headers={"Authorization": f"Bearer {token}"},
            json={"department": "Updated Department"})
    assert resp.status_code == 200
    assert resp.json()["department"] == "Updated Department"


@pytest.mark.asyncio
@requires_postgres
async def test_authz05_analyst_cannot_update_user() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.patch("/api/users/ACM0001", headers={"Authorization": f"Bearer {token}"},
            json={"department": "Blocked"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz06_admin_can_create_device() -> None:
    uid = uuid.uuid4().hex[:8]
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/devices", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"AUTHZ-DEV-{uid}", "hostname": f"authz-pc-{uid}"})
    assert resp.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_authz07_analyst_cannot_create_device() -> None:
    uid = uuid.uuid4().hex[:8]
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.post("/api/devices", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"AUTHZ-DEV-{uid}", "hostname": f"blocked-pc-{uid}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz08_admin_can_update_device() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.patch("/api/devices/PC-1001", headers={"Authorization": f"Bearer {token}"},
            json={"status": "offline"})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_authz09_analyst_cannot_update_device() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.patch("/api/devices/PC-1001", headers={"Authorization": f"Bearer {token}"},
            json={"status": "offline"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz10_admin_can_ingest_raw_log() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "authz:admin:raw:1", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z"})
    assert resp.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_authz11_analyst_can_ingest_raw_log() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "authz:analyst:raw:1", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:01:00Z"})
    assert resp.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_authz12_no_token_cannot_ingest_raw_log() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.post("/api/raw-logs/ingest",
            json={"source_id": "authz:notoken:raw:1", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:02:00Z"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
@requires_postgres
async def test_authz13_admin_can_batch_ingest() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/batch", headers={"Authorization": f"Bearer {token}"},
            json={"records": [{"source_id": "authz:batch:1", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z"}]})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_authz14_analyst_can_batch_ingest() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.post("/api/raw-logs/batch", headers={"Authorization": f"Bearer {token}"},
            json={"records": [{"source_id": "authz:batch:2", "collector_type": "endpoint_agent", "event_type": "file", "timestamp": "2026-01-01T00:01:00Z"}]})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_authz15_admin_can_list_raw_logs() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/raw-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_authz16_analyst_can_list_raw_logs() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.get("/api/raw-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_authz17_admin_can_call_model_infer() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/models/ocsvm-cert-r42-chunked/infer", headers={"Authorization": f"Bearer {token}"},
            json={"features": {"logon_count": 4, "email_size_sum": 18400}})
    assert resp.status_code in (200, 503)


@pytest.mark.asyncio
@requires_postgres
async def test_authz18_analyst_can_call_model_infer() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.post("/api/models/ocsvm-cert-r42-chunked/infer", headers={"Authorization": f"Bearer {token}"},
            json={"features": {"logon_count": 4, "email_size_sum": 18400}})
    assert resp.status_code in (200, 503)


@pytest.mark.asyncio
@requires_postgres
async def test_authz19_admin_can_view_profile() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
@requires_postgres
async def test_authz20_analyst_can_view_profile() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "analyst"


@pytest.mark.asyncio
@requires_postgres
async def test_authz21_admin_can_view_dashboard() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_authz22_analyst_can_view_dashboard() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_authz23_admin_can_list_users() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
@requires_postgres
async def test_authz24_analyst_can_list_users() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_authz25_health_endpoint_public() -> None:
    async with get_test_client() as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_authz26_root_endpoint_public() -> None:
    async with get_test_client() as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "service" in data
    assert "status" in data


@pytest.mark.asyncio
@requires_postgres
async def test_authz27_security_manager_cannot_create_user() -> None:
    uid = uuid.uuid4().hex[:8]
    async with get_test_client(init_db=True) as client:
        token = await _security_manager_token(client)
        resp = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"SM{uid}", "username": f"sm{uid}", "full_name": "Blocked"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz28_security_manager_can_ingest_raw_log() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _security_manager_token(client)
        resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "authz:sm:raw:1", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:03:00Z"})
    assert resp.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_authz29_security_manager_can_analyze_all() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _security_manager_token(client)
        resp = await client.post("/api/demo/analyze-all", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_authz30_analyst_cannot_analyze_all() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.post("/api/demo/analyze-all", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz31_employee_cannot_list_users() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _employee_token(client)
        resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz32_employee_cannot_list_alerts() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _employee_token(client)
        resp = await client.get("/api/alerts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz33_employee_can_view_own_overview() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _employee_token(client)
        resp = await client.get("/api/me/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
@requires_postgres
async def test_authz34_employee_cannot_ingest_raw_log() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _employee_token(client)
        resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "authz:emp:raw:1", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:04:00Z"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz35_admin_can_list_accounts() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/admin/accounts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
@requires_postgres
async def test_authz36_analyst_cannot_list_accounts() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        resp = await client.get("/api/admin/accounts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_authz37_security_manager_cannot_list_accounts() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _security_manager_token(client)
        resp = await client.get("/api/admin/accounts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
