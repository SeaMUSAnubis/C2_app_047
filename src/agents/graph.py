from src.agents.nodes.explain_alert import explain_alert_node
from src.agents.state import AgentState


def run_explanation_graph(state: AgentState) -> AgentState:
    return explain_alert_node(state)
