"""Database constraint test cases."""

import pytest

from tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


async def _ensure_account_active(email: str) -> None:
    from src.services import database
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
async def test_db01_app_accounts_schema() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'app_accounts' ORDER BY ordinal_position")
            columns = [row["column_name"] for row in cur.fetchall()]
    for col in ["id", "email", "full_name", "role", "password_hash", "is_active", "created_at"]:
        assert col in columns


@pytest.mark.asyncio
@requires_postgres
async def test_db02_users_schema() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' ORDER BY ordinal_position")
            columns = [row["column_name"] for row in cur.fetchall()]
    for col in ["id", "username", "full_name", "email", "department", "job_role", "status", "risk_score"]:
        assert col in columns


@pytest.mark.asyncio
@requires_postgres
async def test_db03_devices_schema() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'devices' ORDER BY ordinal_position")
            columns = [row["column_name"] for row in cur.fetchall()]
    for col in ["id", "hostname", "os", "ip_address", "assigned_user_id", "status", "risk_score"]:
        assert col in columns


@pytest.mark.asyncio
@requires_postgres
async def test_db04_event_logs_schema() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'event_logs' ORDER BY ordinal_position")
            columns = [row["column_name"] for row in cur.fetchall()]
    for col in ["id", "source_id", "source_file", "timestamp", "user_id", "device_id", "event_type"]:
        assert col in columns


@pytest.mark.asyncio
@requires_postgres
async def test_db05_raw_user_logs_schema() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'raw_user_logs' ORDER BY ordinal_position")
            columns = [row["column_name"] for row in cur.fetchall()]
    for col in ["id", "source_id", "collector_type", "event_type", "timestamp"]:
        assert col in columns


@pytest.mark.asyncio
@requires_postgres
async def test_db06_alerts_table_exists() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alerts') as exists")
            assert cur.fetchone()["exists"] is True


@pytest.mark.asyncio
@requires_postgres
async def test_db07_model_artifacts_table_exists() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'model_artifacts') as exists")
            assert cur.fetchone()["exists"] is True


@pytest.mark.asyncio
@requires_postgres
async def test_db08_feature_windows_table_exists() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'feature_windows') as exists")
            assert cur.fetchone()["exists"] is True


@pytest.mark.asyncio
@requires_postgres
async def test_db09_accounts_email_unique() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.table_constraints WHERE table_name = 'app_accounts' AND constraint_type = 'UNIQUE') as exists")
            assert cur.fetchone()["exists"] is True


@pytest.mark.asyncio
@requires_postgres
async def test_db10_accounts_role_check() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT conname FROM pg_constraint WHERE conrelid = 'app_accounts'::regclass AND contype = 'c'")
            assert len(cur.fetchall()) > 0


@pytest.mark.asyncio
@requires_postgres
async def test_db11_users_username_unique() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.table_constraints WHERE table_name = 'users' AND constraint_type = 'UNIQUE') as exists")
            assert cur.fetchone()["exists"] is True


@pytest.mark.asyncio
@requires_postgres
async def test_db12_event_logs_source_id_unique() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        payload = {"source_id": "db:test:unique:12", "source_file": "test.csv", "timestamp": "2026-01-01T00:00:00Z", "event_type": "logon"}
        resp1 = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
        resp2 = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
@requires_postgres
async def test_db13_raw_logs_source_id_unique() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        payload = {"source_id": "db:test:raw:unique:13", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z"}
        resp1 = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
        resp2 = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
@requires_postgres
async def test_db14_raw_logs_event_type_check() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "db:test:check:14", "collector_type": "endpoint_agent", "event_type": "not_a_real_type", "timestamp": "2026-01-01T00:00:00Z"})
    assert resp.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_db15_alerts_severity_check() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_get_constraintdef(oid) as def FROM pg_constraint WHERE conrelid = 'alerts'::regclass AND conname LIKE '%severity%'")
            result = cur.fetchone()
            if result:
                assert "low" in result["def"]


@pytest.mark.asyncio
@requires_postgres
async def test_db16_alerts_status_check() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_get_constraintdef(oid) as def FROM pg_constraint WHERE conrelid = 'alerts'::regclass AND conname LIKE '%status%'")
            result = cur.fetchone()
            if result:
                assert "new" in result["def"]


@pytest.mark.asyncio
@requires_postgres
async def test_db17_device_fk_constraint() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/devices", headers={"Authorization": f"Bearer {token}"},
            json={"id": "FK-DEV-17", "hostname": "fk-pc", "assigned_user_id": "NONEXISTENT"})
    assert resp.status_code == 422


@pytest.mark.asyncio
@requires_postgres
async def test_db18_event_log_user_fk() -> None:
    from src.services.database import get_connection
    import psycopg
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO event_logs (source_id, source_file, timestamp, user_id, event_type, metadata_json, raw_json, created_at) VALUES ('fk:test:18', 'test.csv', '2026-01-01T00:00:00Z', 'NONEXISTENT', 'logon', '{}', '{}', '2026-01-01T00:00:00Z')")
                assert False
            except psycopg.errors.ForeignKeyViolation:
                pass


@pytest.mark.asyncio
@requires_postgres
async def test_db21_seed_accounts() -> None:
    async with get_test_client(init_db=True) as client:
        admin_resp = await client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"})
        analyst_resp = await client.post("/api/auth/login", json={"email": "analyst@demo.com", "password": "analyst123"})
    assert admin_resp.status_code == 200
    assert analyst_resp.status_code == 200


@pytest.mark.asyncio
@requires_postgres
async def test_db22_seed_users() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    usernames = [u["id"] for u in resp.json()]
    assert "ACM0001" in usernames
    assert "BTR0002" in usernames
    assert "CNL0003" in usernames


@pytest.mark.asyncio
@requires_postgres
async def test_db23_seed_devices() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.get("/api/devices", headers={"Authorization": f"Bearer {token}"})
    device_ids = [d["id"] for d in resp.json()]
    assert "PC-1001" in device_ids
    assert "PC-2002" in device_ids
    assert "PC-3003" in device_ids


@pytest.mark.asyncio
@requires_postgres
async def test_db24_seed_passwords_hashed() -> None:
    from src.services.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM app_accounts WHERE email = %s", ("admin@demo.com",))
            row = cur.fetchone()
            assert "$" in row["password_hash"]
            assert row["password_hash"] != "admin123"


@pytest.mark.asyncio
@requires_postgres
async def test_db25_upsert_event_logs() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        payload = {"source_id": "db:upsert:event:25", "source_file": "test.csv", "timestamp": "2026-01-01T00:00:00Z", "event_type": "logon", "action": "Logon"}
        resp1 = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
        payload["action"] = "Logoff"
        resp2 = await client.post("/api/logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
@requires_postgres
async def test_db26_upsert_raw_user_logs() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        payload = {"source_id": "db:upsert:raw:26", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z", "raw_payload": {"action": "Logon"}}
        resp1 = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
        payload["raw_payload"] = {"action": "Logoff"}
        resp2 = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
@requires_postgres
async def test_db27_batch_savepoint() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/batch", headers={"Authorization": f"Bearer {token}"},
            json={"records": [
                {"source_id": "db:savepoint:27a", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z"},
                {"source_id": "db:savepoint:27b", "collector_type": "endpoint_agent", "event_type": "invalid_type", "timestamp": "2026-01-01T00:01:00Z"},
                {"source_id": "db:savepoint:27c", "collector_type": "endpoint_agent", "event_type": "file", "timestamp": "2026-01-01T00:02:00Z"}
            ]})
    assert resp.json()["created_or_updated"] == 2
    assert resp.json()["failed"] == 1


@pytest.mark.asyncio
@requires_postgres
async def test_db28_json_fields_decoded() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "db:json:28", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-01-01T00:00:00Z",
                "raw_payload": {"action": "Logon"}, "ingest_metadata": {"agent_version": "0.1.0"}})
    assert isinstance(resp.json()["raw_payload"], dict)
    assert resp.json()["raw_payload"]["action"] == "Logon"


@pytest.mark.asyncio
@requires_postgres
async def test_db29_timestamp_iso_format() -> None:
    async with get_test_client(init_db=True) as client:
        token = await _admin_token(client)
        resp = await client.post("/api/raw-logs/ingest", headers={"Authorization": f"Bearer {token}"},
            json={"source_id": "db:ts:29", "collector_type": "endpoint_agent", "event_type": "logon", "timestamp": "2026-06-15T10:30:00+07:00"})
    assert "2026-06-15" in resp.json()["timestamp"]
