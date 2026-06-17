"""Authentication test cases."""

import time

import pytest

from tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


async def _login(client, email: str, password: str) -> dict:
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def _ensure_account_active(email: str) -> None:
    from src.services import database
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE app_accounts SET is_active = TRUE WHERE email = %s", (email,))


async def _admin_token(client) -> str:
    await _ensure_account_active("admin@demo.com")
    resp = await _login(client, "admin@demo.com", "admin123")
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def _analyst_token(client) -> str:
    await _ensure_account_active("analyst@demo.com")
    resp = await _login(client, "analyst@demo.com", "analyst123")
    assert resp.status_code == 200
    return resp.json()["accessToken"]


@pytest.mark.asyncio
@requires_postgres
async def test_auth01_login_success_admin() -> None:
    async with get_test_client(init_db=True) as client:
        await _ensure_account_active("admin@demo.com")
        resp = await _login(client, "admin@demo.com", "admin123")
    assert resp.status_code == 200
    data = resp.json()
    assert "accessToken" in data
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
@requires_postgres
async def test_auth02_login_success_analyst() -> None:
    async with get_test_client(init_db=True) as client:
        await _ensure_account_active("analyst@demo.com")
        resp = await _login(client, "analyst@demo.com", "analyst123")
    assert resp.status_code == 200
    data = resp.json()
    assert "accessToken" in data
    assert data["user"]["role"] == "analyst"


@pytest.mark.asyncio
@requires_postgres
async def test_auth03_login_wrong_password() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await _login(client, "admin@demo.com", "wrongpassword")
    assert resp.status_code == 401


@pytest.mark.asyncio
@requires_postgres
async def test_auth04_login_nonexistent_email() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await _login(client, "notexist@test.com", "admin123")
    assert resp.status_code == 401


@pytest.mark.asyncio
@requires_postgres
async def test_auth05_login_missing_email() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.post("/api/auth/login", json={"password": "admin123"})
    assert resp.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_auth06_login_missing_password() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.post("/api/auth/login", json={"email": "admin@demo.com"})
    assert resp.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_auth07_login_empty_body() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.post("/api/auth/login", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_auth08_login_response_format() -> None:
    async with get_test_client(init_db=True) as client:
        await _ensure_account_active("admin@demo.com")
        resp = await _login(client, "admin@demo.com", "admin123")
    data = resp.json()
    assert "accessToken" in data
    assert "access_token" not in data
    user = data["user"]
    assert "id" in user
    assert "email" in user
    assert "name" in user
    assert "role" in user


@pytest.mark.asyncio
@requires_postgres
async def test_auth09_valid_token_access_protected() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@demo.com"


@pytest.mark.asyncio
async def test_auth10_expired_token_rejected() -> None:
    from src.services import auth
    expired_token, _ = auth.create_access_token("1", "admin", expires_minutes=-1)
    async with get_test_client() as client:
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth11_forged_token_rejected() -> None:
    forged_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicm9sZSI6ImFkbWluIn0.invalid_signature"
    async with get_test_client() as client:
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth12_token_missing_sub() -> None:
    import base64
    import json

    from src.services import auth

    token, _ = auth.create_access_token("1", "admin")
    parts = token.split(".")
    payload_data = {"role": "admin", "iat": int(time.time()), "exp": int(time.time()) + 3600}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    bad_token = f"{parts[0]}.{payload_b64}.{parts[2]}"
    async with get_test_client() as client:
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
@requires_postgres
async def test_auth14_wrong_auth_header_format() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.get("/api/users", headers={"Authorization": "Token abc123"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
@requires_postgres
async def test_auth15_missing_auth_header() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.get("/api/users")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
@requires_postgres
async def test_auth16_empty_bearer_token() -> None:
    async with get_test_client(init_db=True) as client:
        resp = await client.get("/api/users", headers={"Authorization": "Bearer "})
    assert resp.status_code in (401, 403)


def test_auth17_password_hashed_with_pbkdf2() -> None:
    from src.services import auth
    password = "testpassword123"
    hashed = auth.hash_password(password)
    assert "$" in hashed
    salt, digest = hashed.split("$", 1)
    assert len(salt) > 0
    assert len(digest) > 0
    assert auth.verify_password(password, hashed) is True
    assert auth.verify_password("wrong", hashed) is False


def test_auth18_same_password_different_salt() -> None:
    from src.services import auth
    password = "samepassword"
    hash1 = auth.hash_password(password)
    hash2 = auth.hash_password(password)
    salt1 = hash1.split("$")[0]
    salt2 = hash2.split("$")[0]
    assert salt1 != salt2
    assert auth.verify_password(password, hash1)
    assert auth.verify_password(password, hash2)


def test_auth19_timing_safe_comparison() -> None:
    import inspect

    from src.services import auth

    source = inspect.getsource(auth.verify_password)
    assert "compare_digest" in source


@pytest.mark.asyncio
@requires_postgres
async def test_auth20_inactive_account_cannot_login() -> None:
    async with get_test_client(init_db=True) as client:
        await _ensure_account_active("admin@demo.com")
        from src.services import database
        with database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE app_accounts SET is_active = FALSE WHERE email = %s", ("admin@demo.com",))
        resp = await _login(client, "admin@demo.com", "admin123")
    assert resp.status_code == 401


@pytest.mark.asyncio
@requires_postgres
async def test_auth21_inactive_account_token_revoked() -> None:
    async with get_test_client(init_db=True) as client:
        from src.services import database
        with database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE app_accounts SET is_active = TRUE WHERE email = %s", ("admin@demo.com",))
        token = await _admin_token(client)
        me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        with database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE app_accounts SET is_active = FALSE WHERE email = %s", ("admin@demo.com",))
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
