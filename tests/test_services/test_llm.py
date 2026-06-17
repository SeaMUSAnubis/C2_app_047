import httpx

from src.config import settings
from src.services import llm


def test_openrouter_chat_completion_payload_and_headers(monkeypatch) -> None:
    seen = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            seen["raised"] = False

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "  Analyst-ready explanation.  "}}]}

    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            seen["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            seen["closed"] = True

        def post(self, url: str, *, headers: dict, json: dict) -> FakeResponse:
            seen["url"] = url
            seen["headers"] = headers
            seen["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(settings, "openrouter_model", "openrouter/free")
    monkeypatch.setattr(
        settings, "openrouter_chat_completions_url", "https://openrouter.ai/api/v1/chat/completions"
    )
    monkeypatch.setattr(llm.httpx, "Client", FakeClient)

    explanation = llm.explain_alert(
        {
            "alert_id": "A-42",
            "user_id": "ACM0001",
            "device_id": "PC-1001",
            "severity": "high",
            "risk_score": 88,
            "top_features": ["after_hours_logon", "usb_copy_spike"],
        }
    )

    assert explanation == "Analyst-ready explanation."
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["headers"] == {
        "Authorization": "Bearer test-openrouter-key",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "Vespionage UEBA",
    }
    assert seen["payload"]["model"] == "openrouter/free"
    assert seen["payload"]["temperature"] == 0.2
    assert seen["payload"]["max_tokens"] == 500
    assert seen["payload"]["messages"][0]["role"] == "system"
    assert seen["payload"]["messages"][1]["role"] == "user"
    assert "A-42" in seen["payload"]["messages"][1]["content"]
    assert "after_hours_logon" in seen["payload"]["messages"][1]["content"]


def test_openrouter_http_error_returns_error_message(monkeypatch) -> None:
    def raise_http_error(context):
        raise httpx.HTTPError("openrouter unavailable")

    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(llm, "_call_openrouter", raise_http_error)

    explanation = llm.explain_alert(
        {
            "alert_id": "A-99",
            "severity": "critical",
            "risk_score": 95,
            "risk_factors": ["bulk_file_copy"],
        }
    )

    assert "Lỗi khi gọi AI" in explanation
    assert "openrouter unavailable" in explanation


def test_openrouter_missing_key_returns_rule_based_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    explanation = llm.explain_alert({"alert_id": "A-100", "risk_score": 61})

    assert "Alert A-100" in explanation
    assert "risk score 61" in explanation
