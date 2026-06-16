import pytest

from tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


async def _mock_admin_token(client) -> str:
    """Get a token using mocked auth (no DB required)."""
    response = await client.post(
        "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
    )
    assert response.status_code == 200
    return response.json()["accessToken"]


def _patch_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch auth-related DB calls so login works without PostgreSQL."""
    from src.services import auth, database

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


# ---------------------------------------------------------------------------
# Non-PostgreSQL tests: monkeypatch database helpers to verify serialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    async with get_test_client() as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_dashboard_summary_serializes_camel_case(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services import database

    _patch_auth(monkeypatch)

    fake_summary = {
        "totalUsers": 128,
        "totalDevices": 96,
        "totalLogs": 54210,
        "openAlerts": 14,
        "highCriticalAlerts": 5,
        "averageRiskScore": 42.0,
        "currentModelVersion": "iForest-v0.1-demo",
        "lastImportTime": "2026-06-13T09:30:00+07:00",
    }
    monkeypatch.setattr(database, "get_dashboard_summary", lambda: fake_summary)

    async with get_test_client() as client:
        token = await _mock_admin_token(client)
        response = await client.get(
            "/api/dashboard/summary", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["totalUsers"] == 128
    assert data["totalDevices"] == 96
    assert data["totalLogs"] == 54210
    assert data["openAlerts"] == 14
    assert data["highCriticalAlerts"] == 5
    assert data["averageRiskScore"] == 42.0
    assert data["currentModelVersion"] == "iForest-v0.1-demo"
    assert data["lastImportTime"] == "2026-06-13T09:30:00+07:00"


@pytest.mark.asyncio
async def test_users_serializes_camel_case(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services import database

    _patch_auth(monkeypatch)

    fake_users = [
        {
            "id": "ACM0001",
            "account": "acm0001",
            "name": "Alice M. Carter",
            "department": "Finance",
            "role": "Accountant",
            "status": "active",
            "riskScore": 18,
            "assignedDevices": 1,
            "openAlerts": 0,
            "lastSeen": "2026-06-13T08:12:00Z",
        },
    ]
    monkeypatch.setattr(database, "list_frontend_users", lambda limit=200: fake_users)

    async with get_test_client() as client:
        token = await _mock_admin_token(client)
        response = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["id"] == "ACM0001"
    assert item["account"] == "acm0001"
    assert item["name"] == "Alice M. Carter"
    assert item["department"] == "Finance"
    assert item["role"] == "Accountant"
    assert item["status"] == "active"
    assert item["riskScore"] == 18
    assert item["assignedDevices"] == 1
    assert item["openAlerts"] == 0
    assert item["lastSeen"] == "2026-06-13T08:12:00Z"


@pytest.mark.asyncio
async def test_devices_serializes_camel_case(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services import database

    _patch_auth(monkeypatch)

    fake_devices = [
        {
            "id": "PC-1001",
            "hostname": "FIN-WS-1001",
            "assignedUser": "acm0001",
            "department": "Finance",
            "status": "active",
            "riskScore": 12,
            "openAlerts": 0,
            "lastSeen": "2026-06-13T08:12:00Z",
        },
    ]
    monkeypatch.setattr(database, "list_frontend_devices", lambda limit=200: fake_devices)

    async with get_test_client() as client:
        token = await _mock_admin_token(client)
        response = await client.get("/api/devices", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["id"] == "PC-1001"
    assert item["hostname"] == "FIN-WS-1001"
    assert item["assignedUser"] == "acm0001"
    assert item["department"] == "Finance"
    assert item["status"] == "active"
    assert item["riskScore"] == 12
    assert item["openAlerts"] == 0
    assert item["lastSeen"] == "2026-06-13T08:12:00Z"


@pytest.mark.asyncio
async def test_logs_serializes_camel_case(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services import database

    _patch_auth(monkeypatch)

    fake_logs = [
        {
            "id": "1",
            "timestamp": "2026-06-13T16:10:00+07:00",
            "eventType": "logon",
            "userId": "ACM0001",
            "deviceId": "PC-1001",
            "action": "LOGIN_SUCCESS",
            "sourceFile": "logon.csv",
            "sourceId": "cert-r42:logon:123",
            "rawDetail": "Successful logon from FIN-WS-1001",
        },
    ]
    monkeypatch.setattr(database, "list_frontend_logs", lambda limit=100: fake_logs)

    async with get_test_client() as client:
        token = await _mock_admin_token(client)
        response = await client.get("/api/logs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["id"] == "1"
    assert item["timestamp"] == "2026-06-13T16:10:00+07:00"
    assert item["eventType"] == "logon"
    assert item["userId"] == "ACM0001"
    assert item["deviceId"] == "PC-1001"
    assert item["action"] == "LOGIN_SUCCESS"
    assert item["sourceFile"] == "logon.csv"
    assert item["sourceId"] == "cert-r42:logon:123"
    assert item["rawDetail"] == "Successful logon from FIN-WS-1001"


@pytest.mark.asyncio
async def test_model_infer_uses_deployed_ocsvm_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import settings
    from src.services.ueba_ml import inference

    _patch_auth(monkeypatch)
    inference.get_deployed_ocsvm_model.cache_clear()

    async with get_test_client() as client:
        token = await _mock_admin_token(client)
        response = await client.post(
            f"/api/models/{settings.ocsvm_model_version}/infer",
            headers={"Authorization": f"Bearer {token}"},
            json={"features": {"logon_count": 4, "email_size_sum": 18400}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["modelVersion"] == settings.ocsvm_model_version
    assert data["prediction"] in {"normal", "anomaly"}
    assert isinstance(data["isAnomaly"], bool)
    assert 0 <= data["riskScore"] <= 100
    assert "featureColumns" in data
    assert "missingFeatures" in data


@pytest.mark.asyncio
async def test_model_infer_rejects_unknown_model_version(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_auth(monkeypatch)

    async with get_test_client() as client:
        token = await _mock_admin_token(client)
        response = await client.post(
            "/api/models/unknown/infer",
            headers={"Authorization": f"Bearer {token}"},
            json={"features": {"logon_count": 4}},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Model not found"


@pytest.mark.asyncio
async def test_model_detail_returns_deployed_ocsvm_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import settings
    from src.services.ueba_ml import inference

    _patch_auth(monkeypatch)
    inference.get_deployed_ocsvm_model.cache_clear()

    async with get_test_client() as client:
        token = await _mock_admin_token(client)
        response = await client.get(
            f"/api/models/{settings.ocsvm_model_version}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["modelVersion"] == settings.ocsvm_model_version
    assert data["algorithm"] == "OneClassSVM"
    assert data["kernel"] == "rbf"
    assert len(data["featureColumns"]) == 20


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
    assert item["id"] == "ACM0001"
    assert item["account"] == "acm0001"
    assert item["name"] == "Alice M. Carter"
    assert item["department"] == "Finance"
    assert item["role"] == "Accountant"
    assert item["status"] == "active"
    assert item["riskScore"] == 18
    assert item["assignedDevices"] == 1
    assert item["openAlerts"] == 0


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
    assert item["id"] == "PC-1001"
    assert item["hostname"] == "FIN-WS-1001"
    assert item["assignedUser"] == "acm0001"
    assert item["department"] == "Finance"
    assert item["status"] == "active"
    assert item["riskScore"] == 12
    assert item["openAlerts"] == 0


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
    assert data["totalUsers"] == 3
    assert data["totalDevices"] == 3
    assert data["totalLogs"] == 0
    assert data["openAlerts"] == 0
    assert data["highCriticalAlerts"] == 0
    assert isinstance(data["averageRiskScore"], int | float)
    assert data["averageRiskScore"] > 0


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
