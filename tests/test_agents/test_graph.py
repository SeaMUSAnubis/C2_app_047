from src.agents.graph import run_explanation_graph


def test_explanation_graph_returns_explanation() -> None:
    state = run_explanation_graph({"context": {"alert_id": "demo"}})

    assert "explanation" in state


def test_explanation_graph_uses_rule_fallback_without_openrouter_key(monkeypatch) -> None:
    from src.config import settings

    monkeypatch.setattr(settings, "llm_api_key", "")

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

    assert "Cảnh báo A-1" in state["explanation"]


def test_explanation_graph_calls_openrouter_when_key_is_configured(monkeypatch) -> None:
    from src.config import settings
    from src.services.llm.client import LLMClient

    seen = {}

    def fake_generate(self, system_prompt: str, user_prompt: str, is_json_response: bool = True):
        seen["user_prompt"] = user_prompt
        return """{
            "alert_id": "A-2",
            "summary": "Mocked LLM summary",
            "why_suspicious": ["Mocked reason"],
            "evidence": [],
            "recommended_actions": [],
            "suspicious_domains": [],
            "confidence": 0.9,
            "limitations": [],
            "generated_by": "llm",
            "prompt_version": "v1",
            "risk_score": 64.0,
            "severity": "medium",
            "safety_flags": [],
            "generated_at": "2023-01-01T00:00:00Z",
            "trace_id": "mock-trace"
        }"""

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(LLMClient, "generate", fake_generate)

    state = run_explanation_graph({"context": {"alert_id": "A-2", "severity": "medium", "risk_score": 64}})

    assert "Mocked LLM summary" in state["explanation"]
    assert "Mocked reason" in state["explanation"]
