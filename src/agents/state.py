from typing import TypedDict


class AgentState(TypedDict, total=False):
    alert_id: str
    context: dict
    explanation: str
