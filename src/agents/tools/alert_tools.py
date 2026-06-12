from collections.abc import Mapping


def summarize_alert_context(context: Mapping[str, object]) -> str:
    alert_id = context.get("alert_id", "unknown")
    return f"alert_id={alert_id}"
