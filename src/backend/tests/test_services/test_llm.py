import httpx

from src.backend.app.config import settings
from src.backend.app.services import llm


def test_mistral_chat_completion_payload_and_headers(monkeypatch) -> None:
    seen = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            seen["raised"] = False

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "Tóm tắt: User có hành vi bất thường.\n"
                                "Yếu tố rủi ro: after_hours_logon, usb_copy_spike.\n"
                                "Gợi ý xử lý: Kiểm tra timeline user và device."
                            )
                        }
                    }
                ]
            }

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

    monkeypatch.setattr(settings, "mistral_api_key", "test-mistral-key")
    monkeypatch.setattr(settings, "mistral_model", "mistral-small")
    monkeypatch.setattr(
        settings, "mistral_chat_completions_url", "https://api.mistral.ai/v1/chat/completions"
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

    assert explanation == (
        "Tóm tắt: User có hành vi bất thường.\n"
        "Yếu tố rủi ro: after_hours_logon, usb_copy_spike.\n"
        "Gợi ý xử lý: Kiểm tra timeline user và device."
    )
    assert seen["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert seen["headers"] == {
        "Authorization": "Bearer test-mistral-key",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    assert seen["payload"]["model"] == "mistral-small"
    assert seen["payload"]["temperature"] == 0.2
    assert seen["payload"]["max_tokens"] == 500
    assert seen["payload"]["messages"][0]["role"] == "system"
    assert seen["payload"]["messages"][1]["role"] == "user"
    assert "Tóm tắt:" in seen["payload"]["messages"][0]["content"]
    assert "A-42" in seen["payload"]["messages"][1]["content"]
    assert "after_hours_logon" in seen["payload"]["messages"][1]["content"]


def test_mistral_http_error_returns_rule_based_fallback(monkeypatch) -> None:
    def raise_http_error(context):
        raise httpx.HTTPError("mistral unavailable")

    monkeypatch.setattr(settings, "mistral_api_key", "test-mistral-key")
    monkeypatch.setattr(llm, "_call_mistral", raise_http_error)

    explanation = llm.explain_alert(
        {
            "alert_id": "A-99",
            "severity": "critical",
            "risk_score": 95,
            "risk_factors": ["bulk_file_copy"],
        }
    )

    assert "Tóm tắt: Alert A-99 có mức critical" in explanation
    assert "bulk_file_copy" in explanation
    assert "Gợi ý xử lý:" in explanation


def test_mistral_missing_key_returns_rule_based_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mistral_api_key", "")

    explanation = llm.explain_alert({"alert_id": "A-100", "risk_score": 61})

    assert "Tóm tắt: Alert A-100" in explanation
    assert "risk score 61" in explanation
    assert "Yếu tố rủi ro:" in explanation
    assert "Gợi ý xử lý:" in explanation


def test_mistral_freeform_response_is_normalized(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mistral_api_key", "test-mistral-key")
    monkeypatch.setattr(llm, "_call_mistral", lambda context: "User đăng nhập bất thường.")

    explanation = llm.explain_alert(
        {
            "alert_id": "A-101",
            "risk_score": 77,
            "risk_factors": ["after_hours_logon"],
        }
    )

    assert explanation == (
        "Tóm tắt: User đăng nhập bất thường.\n"
        "Yếu tố rủi ro: alert A-101, risk score 77, after_hours_logon.\n"
        "Gợi ý xử lý: Kiểm tra timeline user/device liên quan rồi cập nhật trạng thái alert."
    )
