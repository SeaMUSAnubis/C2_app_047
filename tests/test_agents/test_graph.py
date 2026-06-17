from src.agents.graph import run_explanation_graph


def test_explanation_graph_returns_explanation() -> None:
    state = run_explanation_graph({"context": {"alert_id": "demo"}})

    assert "explanation" in state


def test_explanation_graph_uses_rule_fallback_without_openrouter_key(monkeypatch) -> None:
    from src.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", "")

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

    assert "Alert A-1 is classified as high" in state["explanation"]
    assert "after_hours_logon" in state["explanation"]


def test_explanation_graph_calls_openrouter_when_key_is_configured(monkeypatch) -> None:
    from src.config import settings
    from src.services import llm

    seen = {}

    def fake_call_openrouter(context):
        seen["context"] = context
        return "OpenRouter explanation"

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(llm, "_call_openrouter", fake_call_openrouter)

    state = run_explanation_graph({"context": {"alert_id": "A-2", "risk_score": 64}})

    assert state["explanation"] == "OpenRouter explanation"
    assert seen["context"]["alert_id"] == "A-2"
