from __future__ import annotations

from typing import Any

import httpx

from src.backend.app.config import settings

SYSTEM_PROMPT = (
    "You are a SOC analyst assistant for a UEBA endpoint monitoring product. "
    "Explain anomaly alerts using only the provided context. "
    "Do not invent evidence that is not in the context. "
    "IMPORTANT: You MUST write your analysis and response entirely in Vietnamese. "
    "Return exactly three short lines in this format:\n"
    "Tóm tắt: <one sentence>\n"
    "Yếu tố rủi ro: <comma-separated evidence from context>\n"
    "Gợi ý xử lý: <one concrete analyst action>"
)


def explain_alert(context: dict[str, Any]) -> str:
    fallback = _fallback_explanation(context)
    if not settings.mistral_api_key:
        print("LLM Fallback: MISTRAL_API_KEY is not set.")
        return fallback

    try:
        explanation = _call_mistral(context)
    except Exception as e:
        print(f"LLM Fallback triggered due to error: {e}")
        return fallback
    return _normalize_explanation(explanation, context) if explanation else fallback


def _call_mistral(context: dict[str, Any]) -> str:
    payload = {
        "model": settings.mistral_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _format_alert_context(context)},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }
    headers = {
        "Authorization": f"Bearer {settings.mistral_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(settings.mistral_chat_completions_url, headers=headers, json=payload)

        try:
            data = response.json()
        except Exception:
            data = {}

        if isinstance(data, dict) and "error" in data:
            error_field = data["error"]
            error_msg = error_field.get("message", "Unknown error") if isinstance(error_field, dict) else str(error_field)
            print("Mistral Error:", error_msg)
            raise RuntimeError(error_msg)

        response.raise_for_status()

        if "choices" not in data:
            print("ERROR: Mistral response missing 'choices':", response.text)
            raise KeyError("choices")
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
        factor_text = ", ".join(str(item) for item in factors[:5]) or "chưa có yếu tố cụ thể"
    else:
        factor_text = str(factors)
    return (
        f"Tóm tắt: Alert {alert_id} có mức {severity} với risk score {risk_score}.\n"
        f"Yếu tố rủi ro: {factor_text}.\n"
        "Gợi ý xử lý: Kiểm tra timeline user/device liên quan rồi cập nhật trạng thái alert."
    )


def _normalize_explanation(explanation: str, context: dict[str, Any]) -> str:
    text = explanation.strip()
    required_labels = ("Tóm tắt:", "Yếu tố rủi ro:", "Gợi ý xử lý:")
    if all(label in text for label in required_labels):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        picked_lines: list[str] = []
        for label in required_labels:
            picked_lines.append(next(line for line in lines if line.startswith(label)))
        return "\n".join(picked_lines)

    alert_id = context.get("alert_id", "unknown")
    risk_score = context.get("risk_score", "not scored")
    factors = context.get("top_features") or context.get("risk_factors") or []
    if isinstance(factors, list):
        factor_text = ", ".join(str(item) for item in factors[:5]) or "chưa có yếu tố cụ thể"
    else:
        factor_text = str(factors)
    summary = text.replace("\n", " ")
    return (
        f"Tóm tắt: {summary}\n"
        f"Yếu tố rủi ro: alert {alert_id}, risk score {risk_score}, {factor_text}.\n"
        "Gợi ý xử lý: Kiểm tra timeline user/device liên quan rồi cập nhật trạng thái alert."
    )
