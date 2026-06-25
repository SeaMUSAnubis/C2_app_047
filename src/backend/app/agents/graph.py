from src.backend.app.agents.nodes.explain_alert import explain_alert_node
from src.backend.app.agents.state import AgentState


def run_explanation_graph(state: AgentState) -> AgentState:
    return explain_alert_node(state)
