"""Backwards-compatible tests for the LLM service.

The original tests targeted `services/llm._call_mistral`. After Phase 3.1
refactor the internals live behind the `LLMProvider` Protocol; this file
adapts the original tests to monkeypatch the provider at the new
boundary. New internals (cache, retry, stats, schema parse) are covered
in `test_llm_package.py`.
"""

from __future__ import annotations

import httpx

from src.backend.app.config import settings
from src.backend.app.services.llm import cache as llm_cache
from src.backend.app.services.llm import providers as llm_providers


def _install_fake_provider(monkeypatch, *, content: str, model: str = "mistral-small") -> None:
    from src.backend.app.services.llm.providers import LLMResponse

    class FakeProvider:
        name = "fake"

        def complete(self, system, user, **kwargs) -> LLMResponse:
            return LLMResponse(content=content, model=model, tokens_in=10, tokens_out=20, latency_ms=50)

    monkeypatch.setattr(settings, "mistral_api_key", "test-mistral-key")
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    llm_cache.reset_cache()
    llm_providers._provider_instance = FakeProvider()  # type: ignore[assignment]


def test_mistral_chat_completion_payload_and_headers(monkeypatch) -> None:
    from src.backend.app.services import llm

    seen = {}

    def fake_complete(self, system, user, **kwargs):
        seen["system"] = system
        seen["user"] = user
        from src.backend.app.services.llm.providers import LLMResponse
        return LLMResponse(
            content=(
                "Tóm tắt: User có hành vi bất thường.\n"
                "Yếu tố rủi ro: after_hours_logon, usb_copy_spike.\n"
                "Gợi ý xử lý: Kiểm tra timeline user và device."
            ),
            model="mistral-small",
            tokens_in=100, tokens_out=80, latency_ms=200,
        )

    monkeypatch.setattr(settings, "mistral_api_key", "test-mistral-key")
    monkeypatch.setattr(settings, "llm_chat_model", "mistral-small")
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    llm_cache.reset_cache()
    monkeypatch.setattr(llm_providers.MistralProvider, "complete", fake_complete)
    llm_providers._provider_instance = None

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
    assert "Tóm tắt:" in seen["system"]
    assert "A-42" in seen["user"]
    assert "after_hours_logon" in seen["user"]


def test_mistral_http_error_returns_rule_based_fallback(monkeypatch) -> None:
    from src.backend.app.services import llm

    def raise_http_error(self, system, user, **kwargs):
        raise httpx.HTTPError("mistral unavailable")

    monkeypatch.setattr(settings, "mistral_api_key", "test-mistral-key")
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    llm_cache.reset_cache()
    monkeypatch.setattr(llm_providers.MistralProvider, "complete", raise_http_error)
    llm_providers._provider_instance = None

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
    from src.backend.app.services import llm

    monkeypatch.setattr(settings, "mistral_api_key", "")
    llm_cache.reset_cache()
    llm_providers._provider_instance = None

    explanation = llm.explain_alert({"alert_id": "A-100", "risk_score": 61})

    assert "Tóm tắt: Alert A-100" in explanation
    assert "risk score 61" in explanation
    assert "Yếu tố rủi ro:" in explanation
    assert "Gợi ý xử lý:" in explanation


def test_mistral_freeform_response_is_normalized(monkeypatch) -> None:
    from src.backend.app.services import llm

    def freeform(self, system, user, **kwargs):
        from src.backend.app.services.llm.providers import LLMResponse
        return LLMResponse(content="User đăng nhập bất thường.", model="m", tokens_in=5, tokens_out=10, latency_ms=30)

    monkeypatch.setattr(settings, "mistral_api_key", "test-mistral-key")
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    llm_cache.reset_cache()
    monkeypatch.setattr(llm_providers.MistralProvider, "complete", freeform)
    llm_providers._provider_instance = None

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
