from __future__ import annotations

from typing import Any

import httpx

from src.config import settings

SYSTEM_PROMPT = (
    "You are a SOC analyst assistant for a UEBA endpoint monitoring product. "
    "Explain anomaly alerts using only the provided context. "
    "Be concise, factual, and include likely risk factors and recommended next step. "
    "Do not invent evidence that is not in the context."
)


def explain_alert(context: dict[str, Any]) -> str:
    fallback = _fallback_explanation(context)
    if not settings.mistral_api_key:
        return fallback

    try:
        explanation = _call_mistral(context)
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return fallback
    return explanation or fallback


def _call_mistral(context: dict[str, Any]) -> str:
    payload = {
        "model": settings.mistral_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _format_alert_context(context)},
        ],
        "temperature": 0.2,
        "max_tokens": 350,
        "response_format": {"type": "text"},
    }
    headers = {
        "Authorization": f"Bearer {settings.mistral_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=20) as client:
        response = client.post(settings.mistral_chat_completions_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _format_alert_context(context: dict[str, Any]) -> str:
    fields = {
        "alert_id": context.get("alert_id"),
        "user_id": context.get("user_id"),
        "device_id": context.get("device_id"),
        "severity": context.get("severity"),
        "risk_score": context.get("risk_score"),
        "anomaly_score": context.get("anomaly_score"),
        "top_features": context.get("top_features") or context.get("risk_factors"),
        "baseline": context.get("baseline") or context.get("baseline_context"),
        "timeline": context.get("timeline"),
    }
    lines = ["Explain this UEBA alert for an analyst:"]
    for key, value in fields.items():
        if value is not None:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _fallback_explanation(context: dict[str, Any]) -> str:
    alert_id = context.get("alert_id", "unknown")
    severity = context.get("severity", "unknown")
    risk_score = context.get("risk_score", "not scored")
    factors = context.get("top_features") or context.get("risk_factors") or []
    if isinstance(factors, list):
        factor_text = ", ".join(str(item) for item in factors[:5]) or "no specific feature details"
    else:
        factor_text = str(factors)
    return (
        f"Alert {alert_id} is classified as {severity} with risk score {risk_score}. "
        f"Primary risk factors: {factor_text}. "
        "Review the related user/device timeline and mark the alert as investigating, resolved, or false_positive."
    )
