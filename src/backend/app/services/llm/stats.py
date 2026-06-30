"""Call stats for the LLM service (Phase 3.2 of PLAN_LLM.md).

Thread-safe singleton. Tracks per-call latency, token usage, status,
fallback reason. Exposed via `GET /api/admin/llm-stats`.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from src.backend.app.config import settings


@dataclass
class _Stats:
    total_calls: int = 0
    total_streamed_calls: int = 0
    total_fallback: int = 0
    total_retries: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_ms_sum: int = 0
    recent: deque = field(default_factory=lambda: deque(maxlen=50))


class LLMCallStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats = _Stats()

    def reset(self) -> None:
        with self._lock:
            self._stats = _Stats()

    def record(
        self,
        *,
        provider: str,
        model: str,
        latency_ms: int,
        status: str,
        fallback_reason: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        streamed: bool = False,
    ) -> None:
        tokens_in_value = max(0, tokens_in or 0)
        tokens_out_value = max(0, tokens_out or 0)
        estimated_cost = estimate_llm_cost(tokens_in_value, tokens_out_value)
        with self._lock:
            self._stats.total_calls += 1
            if streamed:
                self._stats.total_streamed_calls += 1
            if status != "ok":
                self._stats.total_fallback += 1
            self._stats.total_input_tokens += tokens_in_value
            self._stats.total_output_tokens += tokens_out_value
            self._stats.total_latency_ms_sum += max(0, latency_ms)
            self._stats.recent.append(
                {
                    "provider": provider,
                    "model": model,
                    "latency_ms": latency_ms,
                    "status": status,
                    "fallback_reason": fallback_reason,
                    "tokens_in": tokens_in_value,
                    "tokens_out": tokens_out_value,
                    "estimated_cost": estimated_cost,
                    "streamed": streamed,
                }
            )

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            s = self._stats
            avg_latency = (
                s.total_latency_ms_sum / s.total_calls if s.total_calls else 0
            )
            total_estimated_cost = estimate_llm_cost(
                s.total_input_tokens, s.total_output_tokens
            )
            return {
                "total_calls": s.total_calls,
                "total_streamed_calls": s.total_streamed_calls,
                "total_fallback": s.total_fallback,
                "total_retries": s.total_retries,
                "total_input_tokens": s.total_input_tokens,
                "total_output_tokens": s.total_output_tokens,
                "input_cost_per_1m_tokens": settings.llm_input_cost_per_1m_tokens,
                "output_cost_per_1m_tokens": settings.llm_output_cost_per_1m_tokens,
                "total_estimated_cost": total_estimated_cost,
                "cost_currency": settings.llm_cost_currency,
                "avg_latency_ms": round(avg_latency, 1),
                "model": settings.llm_chat_model,
                "provider": settings.llm_provider,
                "enabled": settings.llm_chat_enabled,
                "recent": list(s.recent)[-10:],
            }


# Module-level singleton.
_stats_instance: LLMCallStats | None = None
_stats_lock = threading.Lock()


def estimate_llm_cost(tokens_in: int, tokens_out: int) -> float:
    """Estimate provider spend from token usage and configured per-1M rates."""
    input_cost = (max(0, tokens_in) / 1_000_000) * settings.llm_input_cost_per_1m_tokens
    output_cost = (max(0, tokens_out) / 1_000_000) * settings.llm_output_cost_per_1m_tokens
    return round(input_cost + output_cost, 8)


def get_stats() -> LLMCallStats:
    global _stats_instance
    with _stats_lock:
        if _stats_instance is None:
            _stats_instance = LLMCallStats()
        return _stats_instance


def reset_stats() -> None:
    global _stats_instance
    with _stats_lock:
        _stats_instance = None


@contextmanager
def track_call(
    *,
    provider: str,
    model: str,
    streamed: bool = False,
) -> Iterator[dict[str, Any]]:
    """Context manager: times the wrapped block, records to stats.

    Usage:
        with track_call(provider=..., model=...) as ctx:
            response = provider.complete(...)
            ctx["tokens_in"] = response.tokens_in
            ctx["tokens_out"] = response.tokens_out
    """
    import time

    payload: dict[str, Any] = {"tokens_in": None, "tokens_out": None}
    start = time.perf_counter()
    status = "ok"
    fallback_reason: str | None = None
    try:
        yield payload
    except Exception as exc:
        status = "error"
        fallback_reason = type(exc).__name__
        raise
    finally:
        latency_ms = int((time.perf_counter() - start) * 1000)
        get_stats().record(
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            status=status,
            fallback_reason=fallback_reason,
            tokens_in=payload.get("tokens_in"),
            tokens_out=payload.get("tokens_out"),
            streamed=streamed,
        )
