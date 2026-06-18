"""API endpoint test cases."""

import uuid

import pytest

from tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


async def _login(client, email: str, password: str) -> str:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def _ensure_account_active(email: str) -> None:
    from src.services import database
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE app_accounts SET is_active = TRUE WHERE email = %s", (email,))


async def _admin_token(client) -> str:
    await _ensure_account_active("admin@demo.com")
    return await _login(client, "admin@demo.com", "admin123")


async def _analyst_token(client) -> str:
    await _ensure_account_active("analyst@demo.com")
    return await _login(client, "analyst@demo.com", "analyst123")


@pytest.mark.asyncio
@requires_postgres
async def test_api01_list_users() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 3


@pytest.mark.asyncio
@requires_postgres
async def test_api02_get_user_by_id() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/users/ACM0001", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "ACM0001"


@pytest.mark.asyncio
@requires_postgres
async def test_api03_get_user_not_found() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/users/NOTEXIST", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
@requires_postgres
async def test_api04_create_user() -> None:
    uid = uuid.uuid4().hex[:8]
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"API{uid}", "username": f"api{uid}", "full_name": "API Test User"})
    assert resp.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_api05_create_user_duplicate_id() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
            json={"id": "ACM0001", "username": "duplicate", "full_name": "Duplicate"})
    assert resp.status_code == 409


@pytest.mark.asyncio
@requires_postgres
async def test_api06_create_user_missing_fields() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
            json={"id": "API006"})
    assert resp.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_api07_update_user() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.patch("/api/users/ACM0001", headers={"Authorization": f"Bearer {token}"},
            json={"department": "New Department"})
    assert resp.status_code == 200
    assert resp.json()["department"] == "New Department"


@pytest.mark.asyncio
@requires_postgres
async def test_api08_update_user_not_found() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.patch("/api/users/NOTEXIST", headers={"Authorization": f"Bearer {token}"},
            json={"department": "Test"})
    assert resp.status_code == 404


@pytest.mark.asyncio
@requires_postgres
async def test_api09_users_response_camel_case() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()
    if len(data) > 0:
        item = data[0]
        assert "riskScore" in item
        assert "openAlerts" in item


@pytest.mark.asyncio
@requires_postgres
async def test_api10_list_devices() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/devices", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 3


@pytest.mark.asyncio
@requires_postgres
async def test_api11_get_device_by_id() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/devices/PC-1001", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "PC-1001"


@pytest.mark.asyncio
@requires_postgres
async def test_api12_get_device_not_found() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/devices/NOTEXIST", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
@requires_postgres
async def test_api13_create_device() -> None:
    uid = uuid.uuid4().hex[:8]
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/devices", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"API-DEV-{uid}", "hostname": f"api-pc-{uid}"})
    assert resp.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_api14_create_device_duplicate_id() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/devices", headers={"Authorization": f"Bearer {token}"},
            json={"id": "PC-1001", "hostname": "duplicate-pc"})
    assert resp.status_code == 409


@pytest.mark.asyncio
@requires_postgres
async def test_api15_create_device_invalid_user() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/devices", headers={"Authorization": f"Bearer {token}"},
            json={"id": "API-DEV-15", "hostname": "api-pc-15", "assigned_user_id": "NOTEXIST"})
    assert resp.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_api16_update_device() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.patch("/api/devices/PC-1001", headers={"Authorization": f"Bearer {token}"},
            json={"status": "offline"})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_api17_devices_response_camel_case() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/devices", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()
    if len(data) > 0:
        item = data[0]
        assert "riskScore" in item
        assert "openAlerts" in item


@pytest.mark.asyncio
@requires_postgres
async def test_api18_list_logs() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
@requires_postgres
async def test_api19_ingest_log() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "api:test:log:19", "source_file": "test.csv", "timestamp": "2026-01-01T00:00:00Z", "event_type": "logon"})
    assert resp.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_api20_ingest_log_idempotent() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        payload = {"source_id": "api:test:log:20", "source_file": "test.csv", "timestamp": "2026-01-01T00:00:00Z", "event_type": "logon"}
        resp1 = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
        resp2 = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
@requires_postgres
async def test_api21_ingest_log_missing_fields() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "api:test:log:21"})
    assert resp.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_api22_logs_response_camel_case() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/logs", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()
    if len(data) > 0:
        item = data[0]
        assert "eventType" in item


@pytest.mark.asyncio
@requires_postgres
async def test_api23_single_ingest_raw_log() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "api:raw:23", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z"})
    assert resp.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_api24_batch_ingest_raw_logs() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/batch", headers={"Authorization": f"Bearer {token}"},
            json={"records": [
                {"source_id": "api:batch:24a", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z"},
                {"source_id": "api:batch:24b", "collector_type": "endpoint_agent", "event_type": "file", "timestamp": "2026-01-01T00:01:00Z"}
            ]})
    assert resp.status_code == 200
    assert resp.json()["created_or_updated"] == 2


@pytest.mark.asyncio
@requires_postgres
async def test_api25_batch_mixed_valid_invalid() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/batch", headers={"Authorization": f"Bearer {token}"},
            json={"records": [
                {"source_id": "api:batch:25a", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z"},
                {"source_id": "api:batch:25b", "collector_type": "endpoint_agent", "event_type": "invalid_type", "timestamp": "2026-01-01T00:01:00Z"}
            ]})
    assert resp.json()["created_or_updated"] == 1
    assert resp.json()["failed"] == 1


@pytest.mark.asyncio
@requires_postgres
async def test_api27_raw_logs_pagination() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/raw-logs?limit=2&offset=0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["limit"] == 2


@pytest.mark.asyncio
@requires_postgres
async def test_api28_raw_logs_filter() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/raw-logs?event_type=logon", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_api29_get_raw_log_by_id() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        create_resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "api:get:raw:29", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z"})
        log_id = create_resp.json()["id"]
        resp = await client.get(f"/api/raw-logs/{log_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_api30_get_raw_log_not_found() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/raw-logs/999999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
@requires_postgres
async def test_api31_invalid_event_type() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "api:bad:type:31", "collector_type": "endpoint_agent", "event_type": "invalid_type", "timestamp": "2026-01-01T00:00:00Z"})
    assert resp.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_api32_model_infer() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/models/ocsvm-cert-r42-chunked/infer", headers={"Authorization": f"Bearer {token}"},
            json={"features": {"logon_count": 4, "email_size_sum": 18400}})
    assert resp.status_code in (200, 503)


@pytest.mark.asyncio
@requires_postgres
async def test_api33_model_infer_unknown_version() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/models/unknown/infer", headers={"Authorization": f"Bearer {token}"},
            json={"features": {"logon_count": 4}})
    assert resp.status_code == 404


@pytest.mark.asyncio
@requires_postgres
async def test_api34_model_metadata() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/models/ocsvm-cert-r42-chunked", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (200, 503)


@pytest.mark.asyncio
@requires_postgres
async def test_api35_model_metrics() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/models/ocsvm-cert-r42-chunked/metrics", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (200, 503)


@pytest.mark.asyncio
@requires_postgres
async def test_api36_dashboard_summary() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "totalUsers" in data
    assert "totalDevices" in data


@pytest.mark.asyncio
@requires_postgres
async def test_api37_dashboard_camel_case() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()
    assert "totalUsers" in data
    assert "total_devices" not in data
