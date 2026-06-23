from src.agents.state import AgentState
from src.models.explanation import AlertExplanationRequest
from src.services.llm.explanation_service import generate_explanation


def explain_alert_node(state: AgentState) -> AgentState:
    context = state.get("context", {})
    try:
        request = AlertExplanationRequest(
            alert_id=context.get("alert_id", "unknown"),
            user_id=context.get("user_id", "unknown"),
            device_id=context.get("device_id"),
            risk_score=context.get("risk_score", 0.0),
            severity=context.get("severity", "low"),
            alert_status=context.get("alert_status", "new"),
            anomaly_score=context.get("anomaly_score"),
            additional_context=context
        )
        response = generate_explanation(request)
        explanation = f"{response.summary}\n\nLý do: " + ", ".join(response.why_suspicious)
    except Exception as e:
        explanation = f"Lỗi tạo giải thích: {e}"

    return {**state, "explanation": explanation}
