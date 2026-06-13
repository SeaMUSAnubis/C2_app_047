import os
from pathlib import Path

os.environ.setdefault("UEBA_DATABASE_PATH", str(Path("/tmp") / "c2_app_047_test.sqlite3"))
os.environ.setdefault("JWT_SECRET", "test-secret")


def get_test_client():
    import httpx

    from src.main import app

    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")
