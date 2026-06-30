import os
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if test_database_url := os.getenv("TEST_DATABASE_URL"):
    os.environ.setdefault("DATABASE_URL", test_database_url)
os.environ.setdefault("JWT_SECRET", "test-secret")


def postgres_tests_enabled() -> bool:
    if not os.getenv("TEST_DATABASE_URL"):
        return False
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return False
    return True


def _cleanup_llm_test_data() -> None:
    from src.backend.app.db import session as db

    with db.get_connection(write=True) as conn:
        conn.execute(
            """
            DELETE FROM alerts
            WHERE user_id IN ('U-chat-1', 'U-fb-1')
               OR title IN ('chat test', 'test alert for feedback')
            """
        )
        conn.execute(
            """
            DELETE FROM llm_memories
            WHERE scope_id IN ('U-chat-1', 'U-fb-1')
               OR created_by IN ('U-chat-1', 'U-fb-1', 'A-fb')
               OR content LIKE %s
            """,
            ("%test note%",),
        )
        conn.execute("DELETE FROM users WHERE id IN ('U-chat-1', 'U-fb-1', 'A-fb')")


@pytest.fixture
def db_setup():
    if not postgres_tests_enabled():
        pytest.skip("TEST_DATABASE_URL not set")

    from src.backend.app.db.pool import close_pool, init_pool
    from src.backend.app.db.session import initialize_database

    close_pool()
    init_pool()
    if os.getenv("SKIP_TEST_DB_INIT") != "1":
        initialize_database()
    _cleanup_llm_test_data()
    from src.backend.app.db import session as db

    with db.get_connection(write=True) as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, full_name, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            ("A-fb", "analyst_fb", "Feedback Analyst"),
        )
    try:
        yield
    finally:
        _cleanup_llm_test_data()
        close_pool()


def get_test_client(*, init_db: bool = False):
    import httpx

    from src.backend.app.main import app

    if init_db:
        from src.backend.app.db.session import initialize_database

        initialize_database()

    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")
