from src.backend.app.agents.graph import run_explanation_graph


def test_explanation_graph_returns_explanation() -> None:
    state = run_explanation_graph({"context": {"alert_id": "demo"}})

    assert "explanation" in state


def test_explanation_graph_uses_rule_fallback_without_mistral_key(monkeypatch) -> None:
    from src.backend.app.config import settings

    monkeypatch.setattr(settings, "mistral_api_key", "")

    state = run_explanation_graph(
        {
            "context": {
                "alert_id": "A-1",
                "severity": "high",
                "risk_score": 82,
                "top_features": ["after_hours_logon", "usb_copy_spike"],
            }
        }
    )

    assert "Tóm tắt: Alert A-1 có mức high" in state["explanation"]
    assert "after_hours_logon" in state["explanation"]


def test_explanation_graph_calls_mistral_when_key_is_configured(monkeypatch) -> None:
    from src.backend.app.config import settings
    from src.backend.app.services.llm import providers
    from src.backend.app.services.llm.cache import reset_cache

    seen = {}

    class FakeProvider:
        name = "fake"

        def complete(self, system: str, user: str, **kwargs) -> object:
            seen["system"] = system
            seen["user"] = user
            from src.backend.app.services.llm.providers import LLMResponse
            return LLMResponse(
                content=(
                    "Tóm tắt: Alert cần kiểm tra.\n"
                    "Yếu tố rủi ro: risk score 64.\n"
                    "Gợi ý xử lý: Kiểm tra timeline."
                ),
                model="fake-model",
                tokens_in=10,
                tokens_out=20,
                latency_ms=100,
            )

    monkeypatch.setattr(settings, "mistral_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    reset_cache()
    providers._provider_instance = FakeProvider()  # type: ignore[assignment]

    state = run_explanation_graph({"context": {"alert_id": "A-2", "risk_score": 64}})

    assert state["explanation"] == (
        "Tóm tắt: Alert cần kiểm tra.\n"
        "Yếu tố rủi ro: risk score 64.\n"
        "Gợi ý xử lý: Kiểm tra timeline."
    )
    assert "alert_id" in seen["user"] or "A-2" in seen["user"]
    # cleanup
    providers._provider_instance = None
    reset_cache()
