import os

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


def get_test_client(*, init_db: bool = False):
    import httpx

    from src.main import app

    if init_db:
        from src.services.database import initialize_database

        initialize_database()

    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")
