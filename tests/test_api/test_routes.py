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
async def test_login_and_me_endpoint() -> None:
    async with get_test_client(init_db=True) as client:
        login = await client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"})
        assert login.status_code == 200
        token = login.json()["access_token"]

        me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@demo.com"
    assert me.json()["role"] == "admin"


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
        login = await client.post("/api/auth/login", json={"email": "analyst@demo.com", "password": "analyst123"})
        token = login.json()["access_token"]

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
async def test_admin_can_read_seed_users_and_devices() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)

        users = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
        devices = await client.get("/api/devices", headers={"Authorization": f"Bearer {token}"})

    assert users.status_code == 200
    assert users.json()["total"] >= 3
    assert devices.status_code == 200
    assert devices.json()["total"] >= 3


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

        first = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
        second = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
        logs = await client.get(
            "/api/logs?user_id=ACM0001&event_type=logon",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert logs.status_code == 200
    assert any(item["source_id"] == "pytest:logon:1" for item in logs.json()["items"])


async def _admin_token(client) -> str:
    response = await client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"})
    assert response.status_code == 200
    return response.json()["access_token"]
