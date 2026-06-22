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
    from src.backend.app.services import llm

    seen = {}

    def fake_call_mistral(context):
        seen["context"] = context
        return (
            "Tóm tắt: Alert cần kiểm tra.\n"
            "Yếu tố rủi ro: risk score 64.\n"
            "Gợi ý xử lý: Kiểm tra timeline."
        )

    monkeypatch.setattr(settings, "mistral_api_key", "test-key")
    monkeypatch.setattr(llm, "_call_mistral", fake_call_mistral)

    state = run_explanation_graph({"context": {"alert_id": "A-2", "risk_score": 64}})

    assert state["explanation"] == (
        "Tóm tắt: Alert cần kiểm tra.\n"
        "Yếu tố rủi ro: risk score 64.\n"
        "Gợi ý xử lý: Kiểm tra timeline."
    )
    assert seen["context"]["alert_id"] == "A-2"
