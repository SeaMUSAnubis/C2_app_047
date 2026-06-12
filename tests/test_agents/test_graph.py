from src.agents.graph import run_explanation_graph


def test_explanation_graph_returns_explanation() -> None:
    state = run_explanation_graph({"context": {"alert_id": "demo"}})

    assert "explanation" in state
