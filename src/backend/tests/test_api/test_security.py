"""Security test cases."""

import uuid

import pytest

from src.backend.tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


async def _ensure_account_active(email: str) -> None:
    from src.backend.app.db import session as database
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE app_accounts SET is_active = TRUE WHERE email = %s", (email,))


async def _admin_token(client) -> str:
    await _ensure_account_active("admin@demo.com")
    resp = await client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


@pytest.mark.asyncio
@requires_postgres
async def test_sec01_sql_injection_login_email() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.post("/api/auth/login", json={"email": "'; DROP TABLE users; --", "password": "anything"})
    assert resp.status_code == 401
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        users = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert users.status_code == 200
    assert len(users.json()) >= 3


@pytest.mark.asyncio
@requires_postgres
async def test_sec02_sql_injection_path_param() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/users/'; DROP TABLE users; --", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (404, 422)


@pytest.mark.asyncio
@requires_postgres
async def test_sec03_sql_injection_query_param() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/raw-logs?event_type='; DROP TABLE raw_user_logs; --", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
@requires_postgres
async def test_sec04_xss_in_user_full_name() -> None:
    uid = uuid.uuid4().hex[:8]
    xss_payload = "<script>alert('xss')</script>"
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"XSS{uid}", "username": f"xss{uid}", "full_name": xss_payload})
    assert resp.status_code == 201
    assert resp.json()["full_name"] == xss_payload


@pytest.mark.asyncio
@requires_postgres
async def test_sec05_invalid_email_format() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.post("/api/auth/login", json={"email": "not-an-email", "password": "admin123"})
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
@requires_postgres
async def test_sec06_negative_risk_score() -> None:
    uid = uuid.uuid4().hex[:8]
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"NEG{uid}", "username": f"neg{uid}", "full_name": "Negative Test", "risk_score": -1})
    assert resp.status_code in (201, 422)


@pytest.mark.asyncio
@requires_postgres
async def test_sec07_extreme_risk_score() -> None:
    uid = uuid.uuid4().hex[:8]
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
            json={"id": f"BIG{uid}", "username": f"big{uid}", "full_name": "Big Score", "risk_score": 999999999})
    assert resp.status_code in (201, 422)


@pytest.mark.asyncio
async def test_sec08_cors_allows_configured_origin() -> None:
    async with get_test_client() as client:
        resp = await client.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


@pytest.mark.asyncio
async def test_sec09_cors_rejects_unknown_origin() -> None:
    async with get_test_client() as client:
        resp = await client.options("/api/health", headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"})
    allow_origin = resp.headers.get("access-control-allow-origin", "")
    assert allow_origin != "http://evil.com"
