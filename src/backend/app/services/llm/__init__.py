"""LLM service package (Phase 3 of PLAN_LLM.md).

Public API:
    explain_alert(context)   — back-compat shim used by demo_pipeline + user_scoring
    get_provider()           — provider factory
    chat_stream(...)         — multi-turn streaming (see llm_chat module)

The original `services/llm.py` module is preserved as a thin re-export so
`from src.backend.app.services.llm import explain_alert` keeps working.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from src.backend.app.config import settings
from src.backend.app.services.llm.cache import get_cache
from src.backend.app.services.llm.providers import (
    LLMProvider,
    LLMResponse,
    MistralProvider,
    get_provider,
)
from src.backend.app.services.llm.retry import retry_with_backoff
from src.backend.app.services.llm.schemas import Explanation, parse_explanation
from src.backend.app.services.llm.stats import get_stats, track_call

logger = logging.getLogger(__name__)

__all__ = [
    "Explanation",
    "LLMProvider",
    "LLMResponse",
    "MistralProvider",
    "explain_alert",
    "get_cache",
    "get_provider",
    "get_stats",
    "parse_explanation",
    "retry_with_backoff",
    "track_call",
]


def _fallback_explanation(context: Mapping[str, Any]) -> str:
    """Rule-based fallback used when no provider / call fails / parse fails."""
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


def explain_alert(context: Mapping[str, Any]) -> str:
    """Generate the 3-line Vietnamese explanation for an alert.

    Behaviour:
    1. Build cache key from stable alert attributes.
    2. Cache hit → return cached text.
    3. Try the configured provider (with retry).
    4. Parse the response via `parse_explanation`. If parse fails, fall back.
    5. On any provider error, fall back to the rule-based explanation.
    6. Record stats (latency, status, token usage, fallback reason).

    Backwards compatible with the previous function signature — no caller
    of the old `llm.explain_alert` needs to change.
    """
    from src.backend.app.services.llm.prompts import (
        SYSTEM_PROMPT,
        build_user_message,
    )

    # Cache key
    cache_parts = [
        str(context.get("alert_id", "")),
        str(context.get("severity", "")),
        str(context.get("risk_score", "")),
        str(context.get("anomaly_score", "")),
        str(context.get("user_id", "")),
        ",".join(map(str, context.get("top_features") or context.get("risk_factors") or [])),
    ]
    key = get_cache().make_key(cache_parts)
    cached = get_cache().get(key)
    if cached is not None:
        get_stats().record(
            provider="cache", model=settings.llm_chat_model,
            latency_ms=0, status="ok",
        )
        return cached

    # No API key → fallback (do not raise)
    if not settings.mistral_api_key:
        logger.info("explain_alert: MISTRAL_API_KEY not set, using fallback")
        get_stats().record(
            provider=settings.llm_provider, model=settings.llm_chat_model,
            latency_ms=0, status="fallback", fallback_reason="no_api_key",
        )
        return _fallback_explanation(context)

    try:
        provider = get_provider()
        with track_call(provider=provider.name, model=settings.llm_chat_model) as ctx:
            response: LLMResponse = retry_with_backoff(
                provider.complete,
                SYSTEM_PROMPT,
                build_user_message(context),
                max_attempts=settings.llm_max_retries,
            )
            ctx["tokens_in"] = response.tokens_in
            ctx["tokens_out"] = response.tokens_out
    except Exception as exc:
        logger.warning("explain_alert: provider call failed: %s", exc)
        get_stats().record(
            provider=settings.llm_provider, model=settings.llm_chat_model,
            latency_ms=0, status="fallback", fallback_reason=type(exc).__name__,
        )
        return _fallback_explanation(context)

    # Parse / normalise
    parsed = parse_explanation(response.content, model=response.model)
    if parsed is None:
        logger.warning("explain_alert: could not parse provider response into Explanation shape")
        # Use a permissive normaliser that still preserves the 3-line shape.
        normalised = _normalise_freeform(response.content, context)
        get_cache().put(key, normalised)
        return normalised

    formatted = (
        f"Tóm tắt: {parsed.summary}\n"
        f"Yếu tố rủi ro: {', '.join(parsed.risk_factors) or 'chưa có yếu tố cụ thể'}\n"
        f"Gợi ý xử lý: {parsed.recommended_action}"
    )
    get_cache().put(key, formatted)
    return formatted


def _normalise_freeform(text: str, context: Mapping[str, Any]) -> str:
    """Build a 3-line response when the model freeforms but misses labels."""
    alert_id = context.get("alert_id", "unknown")
    risk_score = context.get("risk_score", "not scored")
    factors = context.get("top_features") or context.get("risk_factors") or []
    if isinstance(factors, list):
        factor_text = ", ".join(str(f) for f in factors[:5]) or "chưa có yếu tố cụ thể"
    else:
        factor_text = str(factors)
    summary = text.replace("\n", " ").strip()
    return (
        f"Tóm tắt: {summary}\n"
        f"Yếu tố rủi ro: alert {alert_id}, risk score {risk_score}, {factor_text}.\n"
        "Gợi ý xử lý: Kiểm tra timeline user/device liên quan rồi cập nhật trạng thái alert."
    )
