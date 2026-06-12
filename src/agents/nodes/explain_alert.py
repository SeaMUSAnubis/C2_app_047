from src.agents.state import AgentState
from src.services.llm import explain_alert


def explain_alert_node(state: AgentState) -> AgentState:
    context = state.get("context", {})
    return {**state, "explanation": explain_alert(context)}
