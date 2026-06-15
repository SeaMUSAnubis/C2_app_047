import pytest

from tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    async with get_test_client() as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
@requires_postgres
async def test_login_returns_frontend_compatible_response() -> None:
    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert login.status_code == 200
        data = login.json()
        assert "accessToken" in data
        assert "access_token" not in data
        assert data["user"]["email"] == "admin@demo.com"
        assert data["user"]["name"] == "Demo Admin"
        assert data["user"]["role"] == "admin"
        assert data["user"]["id"]


@pytest.mark.asyncio
@requires_postgres
async def test_login_and_me_endpoint() -> None:
    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        assert login.status_code == 200
        token = login.json()["accessToken"]

        me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@demo.com"
    assert me.json()["role"] == "admin"


@pytest.mark.asyncio
@requires_postgres
async def test_login_invalid_credentials() -> None:
    async with get_test_client(init_db=True) as client:
        response = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "wrong"}
        )
    assert response.status_code == 401


@pytest.mark.asyncio
@requires_postgres
async def test_protected_endpoint_requires_token() -> None:
    async with get_test_client(init_db=True) as client:
        response = await client.get("/api/users")

        assert response.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_analyst_cannot_create_user() -> None:
    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "analyst@demo.com", "password": "analyst123"}
        )
        token = login.json()["accessToken"]

        response = await client.post(
            "/api/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "id": "ZZZ9001",
                "username": "zzz9001",
                "full_name": "Blocked User",
                "status": "active",
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_users_returns_frontend_compatible_array() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)

        users = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})

    assert users.status_code == 200
    data = users.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    item = data[0]
    assert "id" in item
    assert "account" in item
    assert "name" in item
    assert "department" in item
    assert "role" in item
    assert "status" in item
    assert "riskScore" in item
    assert "assignedDevices" in item
    assert "openAlerts" in item


@pytest.mark.asyncio
@requires_postgres
async def test_devices_returns_frontend_compatible_array() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)

        devices = await client.get("/api/devices", headers={"Authorization": f"Bearer {token}"})

    assert devices.status_code == 200
    data = devices.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    item = data[0]
    assert "id" in item
    assert "hostname" in item
    assert "assignedUser" in item
    assert "status" in item
    assert item["status"] in ("active", "inactive")
    assert "riskScore" in item
    assert "openAlerts" in item


@pytest.mark.asyncio
@requires_postgres
async def test_logs_returns_frontend_compatible_array() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)

        logs = await client.get("/api/logs", headers={"Authorization": f"Bearer {token}"})

    assert logs.status_code == 200
    data = logs.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
@requires_postgres
async def test_dashboard_summary_returns_frontend_compatible_response() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)

        response = await client.get(
            "/api/dashboard/summary", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "totalUsers" in data
    assert "totalDevices" in data
    assert "totalLogs" in data
    assert "openAlerts" in data
    assert "highCriticalAlerts" in data
    assert "averageRiskScore" in data
    assert isinstance(data["totalUsers"], int)
    assert isinstance(data["totalDevices"], int)
    assert data["totalUsers"] >= 3
    assert data["totalDevices"] >= 3


@pytest.mark.asyncio
@requires_postgres
async def test_ingest_log_is_idempotent_by_source_id() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        payload = {
            "source_id": "pytest:logon:1",
            "source_file": "logon.csv",
            "timestamp": "2010-01-04T08:15:00Z",
            "user_id": "ACM0001",
            "device_id": "PC-1001",
            "event_type": "logon",
            "action": "Logon",
            "resource": "PC-1001",
            "metadata": {"source": "pytest"},
            "raw": {"line": 1},
        }

        first = await client.post(
            "/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload
        )
        second = await client.post(
            "/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
@requires_postgres
async def test_ingest_then_logs_appear_in_frontend_endpoint() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        payload = {
            "source_id": "pytest:logon:frontend:1",
            "source_file": "logon.csv",
            "timestamp": "2010-01-04T08:15:00Z",
            "user_id": "ACM0001",
            "device_id": "PC-1001",
            "event_type": "logon",
            "action": "Logon",
            "resource": "PC-1001",
        }
        await client.post(
            "/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload
        )

        logs = await client.get("/api/logs", headers={"Authorization": f"Bearer {token}"})

    assert logs.status_code == 200
    data = logs.json()
    assert isinstance(data, list)
    assert any(item["sourceId"] == "pytest:logon:frontend:1" for item in data)


async def _admin_token(client) -> str:
    response = await client.post(
        "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
    )
    assert response.status_code == 200
    return response.json()["accessToken"]


async def _analyst_token(client) -> str:
    response = await client.post(
        "/api/auth/login", json={"email": "analyst@demo.com", "password": "analyst123"}
    )
    assert response.status_code == 200
    return response.json()["accessToken"]


@pytest.mark.asyncio
@requires_postgres
async def test_unauthorized_raw_log_ingest_returns_auth_error() -> None:
    async with get_test_client(init_db=True) as client:
        response = await client.post(
            "/api/raw-logs/ingest",
            json={
                "source_id": "test:1",
                "collector_type": "endpoint_agent",
                "event_type": "logon",
                "timestamp": "2026-06-15T08:15:00Z",
            },
        )
    assert response.status_code == 403


@pytest.mark.asyncio
@requires_postgres
async def test_admin_can_ingest_raw_log() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        response = await client.post(
            "/api/raw-logs/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "source_id": "agent:PC-1001:logon:2026-06-15T08:15:00Z",
                "collector_type": "endpoint_agent",
                "event_type": "logon",
                "timestamp": "2026-06-15T08:15:00Z",
                "user_id": "ACM0001",
                "device_id": "PC-1001",
                "raw_payload": {"action": "Logon", "username": "acm0001", "pc": "PC-1001"},
                "ingest_metadata": {"agent_version": "0.1.0", "host_os": "Windows 11"},
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert data["source_id"] == "agent:PC-1001:logon:2026-06-15T08:15:00Z"
    assert data["raw_payload"]["action"] == "Logon"
    assert data["ingest_metadata"]["agent_version"] == "0.1.0"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
@requires_postgres
async def test_analyst_can_ingest_raw_log() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _analyst_token(client)
        response = await client.post(
            "/api/raw-logs/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "source_id": "agent:PC-2002:file:2026-06-15T09:00:00Z",
                "collector_type": "endpoint_agent",
                "event_type": "file",
                "timestamp": "2026-06-15T09:00:00Z",
                "user_id": "BTR0002",
                "device_id": "PC-2002",
                "raw_payload": {"action": "FileCreate", "path": "/tmp/test.txt"},
            },
        )
    assert response.status_code == 201


@pytest.mark.asyncio
@requires_postgres
async def test_duplicate_source_id_is_idempotent() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        payload = {
            "source_id": "agent:PC-1001:logon:2026-06-15T10:00:00Z",
            "collector_type": "endpoint_agent",
            "event_type": "logon",
            "timestamp": "2026-06-15T10:00:00Z",
            "user_id": "ACM0001",
            "raw_payload": {"action": "Logon"},
        }
        first = await client.post(
            "/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload
        )
        second = await client.post(
            "/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload
        )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
@requires_postgres
async def test_batch_ingest_saves_valid_and_reports_invalid() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        response = await client.post(
            "/api/raw-logs/batch",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "records": [
                    {
                        "source_id": "batch:valid:1",
                        "collector_type": "endpoint_agent",
                        "event_type": "logon",
                        "timestamp": "2026-06-15T08:00:00Z",
                        "raw_payload": {"action": "Logon"},
                    },
                    {
                        "source_id": "batch:invalid:1",
                        "collector_type": "endpoint_agent",
                        "event_type": "invalid_type",
                        "timestamp": "2026-06-15T08:01:00Z",
                    },
                    {
                        "source_id": "batch:valid:2",
                        "collector_type": "endpoint_agent",
                        "event_type": "device",
                        "timestamp": "2026-06-15T08:02:00Z",
                        "raw_payload": {"action": "USBInsert"},
                    },
                ]
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["created_or_updated"] == 2
    assert data["failed"] == 1
    assert data["errors"][0]["index"] == 1


@pytest.mark.asyncio
@requires_postgres
async def test_single_ingest_rejects_invalid_event_type() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        response = await client.post(
            "/api/raw-logs/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "source_id": "test:bad_type",
                "collector_type": "endpoint_agent",
                "event_type": "lgoon",
                "timestamp": "2026-06-15T08:15:00Z",
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_get_raw_logs_filter_by_event_type() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        await client.post(
            "/api/raw-logs/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "source_id": "filter:logon:1",
                "collector_type": "endpoint_agent",
                "event_type": "logon",
                "timestamp": "2026-06-15T08:00:00Z",
                "raw_payload": {"action": "Logon"},
            },
        )
        await client.post(
            "/api/raw-logs/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "source_id": "filter:http:1",
                "collector_type": "endpoint_agent",
                "event_type": "http",
                "timestamp": "2026-06-15T08:01:00Z",
                "raw_payload": {"url": "http://example.com"},
            },
        )
        response = await client.get(
            "/api/raw-logs?event_type=logon",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["event_type"] == "logon" for item in items)


@pytest.mark.asyncio
@requires_postgres
async def test_get_raw_log_by_id_returns_404_when_missing() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        response = await client.get(
            "/api/raw-logs/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404
