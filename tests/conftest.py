def get_test_client():
    from fastapi.testclient import TestClient

    from src.main import app

    return TestClient(app)
