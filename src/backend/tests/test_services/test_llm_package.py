"""Tests for the new LLM service internals (Phase 3.1+3.2 of PLAN_LLM.md).

Covers:
- retry helper (transient + success)
- schema parser (3-line extraction)
- cache (LRU + TTL + invalidation)
- stats singleton
- provider factory
- prompt builders
- explain_alert end-to-end via fake provider
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.backend.app.services.llm import retry, schemas, cache, stats, providers
from src.backend.app.services.llm.prompts import (
    SYSTEM_PROMPT,
    build_chat_user_message,
    build_user_message,
)


# ---------- retry ----------


def test_retry_succeeds_first_try() -> None:
    calls = {"n": 0}

    def func() -> str:
        calls["n"] += 1
        return "ok"

    assert retry.retry_with_backoff(func, max_attempts=3, base_delay=0.001) == "ok"
    assert calls["n"] == 1


def test_retry_succeeds_after_two_transient_failures() -> None:
    calls = {"n": 0}

    def func() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return "ok"

    result = retry.retry_with_backoff(
        func, max_attempts=3, base_delay=0.001, max_delay=0.01
    )
    assert result == "ok"
    assert calls["n"] == 3


def test_retry_exhausts_max_attempts() -> None:
    def always_fail() -> None:
        raise httpx.ReadTimeout("nope")

    with pytest.raises(retry.RetriableLLMError):
        retry.retry_with_backoff(always_fail, max_attempts=2, base_delay=0.001, max_delay=0.01)


def test_retry_does_not_retry_non_retriable() -> None:
    calls = {"n": 0}

    def func() -> None:
        calls["n"] += 1
        raise ValueError("not retriable")

    with pytest.raises(ValueError):
        retry.retry_with_backoff(func, max_attempts=5, base_delay=0.001)
    assert calls["n"] == 1


# ---------- schema parse ----------


def test_parse_explanation_extracts_three_lines() -> None:
    text = (
        "Tóm tắt: User có hành vi bất thường.\n"
        "Yếu tố rủi ro: after_hours_logon, usb_copy_spike\n"
        "Gợi ý xử lý: Kiểm tra timeline"
    )
    parsed = schemas.parse_explanation(text, model="m")
    assert parsed is not None
    assert parsed.summary == "User có hành vi bất thường."
    assert parsed.risk_factors == ["after_hours_logon", "usb_copy_spike"]
    assert parsed.recommended_action == "Kiểm tra timeline"


def test_parse_explanation_returns_none_when_label_missing() -> None:
    text = "Tóm tắt: something"
    assert schemas.parse_explanation(text) is None


def test_parse_explanation_strips_blank_lines() -> None:
    text = (
        "Tóm tắt: ok\n"
        "\n"
        "Yếu tố rủi ro: a, b\n"
        "Gợi ý xử lý: do this"
    )
    parsed = schemas.parse_explanation(text)
    assert parsed is not None
    assert parsed.risk_factors == ["a", "b"]


# ---------- cache ----------


def test_cache_put_get_basic() -> None:
    c = cache.LLMCache(max_size=10, ttl_seconds=60)
    c.put("k1", "v1")
    assert c.get("k1") == "v1"


def test_cache_ttl_expiry() -> None:
    c = cache.LLMCache(max_size=10, ttl_seconds=0)  # expires immediately
    c.put("k1", "v1")
    # ensure some clock progression
    time.sleep(0.01)
    assert c.get("k1") is None


def test_cache_lru_eviction() -> None:
    c = cache.LLMCache(max_size=2, ttl_seconds=60)
    c.put("a", "1")
    c.put("b", "2")
    c.put("c", "3")  # evicts a
    assert c.get("a") is None
    assert c.get("b") == "2"
    assert c.get("c") == "3"


def test_cache_invalidate_by_prefix() -> None:
    c = cache.LLMCache(max_size=10, ttl_seconds=60)
    c.put("alert_1_hash", "v1")
    c.put("alert_2_hash", "v2")
    c.put("other", "v3")
    removed = c.invalidate("alert_")
    assert removed == 2
    assert c.get("other") == "v3"


# ---------- stats ----------


def test_stats_record_and_snapshot() -> None:
    s = stats.LLMCallStats()
    s.reset()
    s.record(provider="p", model="m", latency_ms=100, status="ok", tokens_in=10, tokens_out=20)
    s.record(provider="p", model="m", latency_ms=200, status="error", fallback_reason="Timeout")
    snap = s.get_stats()
    assert snap["total_calls"] == 2
    assert snap["total_fallback"] == 1
    assert snap["total_input_tokens"] == 10
    assert snap["total_output_tokens"] == 20
    assert snap["avg_latency_ms"] == 150.0
    assert len(snap["recent"]) == 2


# ---------- provider factory ----------


def test_get_provider_factory_mistral(monkeypatch) -> None:
    from src.backend.app.config import settings
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    monkeypatch.setattr(settings, "mistral_api_key", "test-key")
    providers.reset_provider()
    p = providers.get_provider()
    assert isinstance(p, providers.MistralProvider)
    assert p.name == "mistral"
    # Idempotent
    assert providers.get_provider() is p
    providers.reset_provider()


def test_get_provider_factory_missing_key_raises(monkeypatch) -> None:
    from src.backend.app.config import settings
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    monkeypatch.setattr(settings, "mistral_api_key", "")
    providers.reset_provider()
    with pytest.raises(ValueError):
        providers.get_provider()


def test_mistral_provider_reuses_sync_client() -> None:
    """Multiple `complete()` calls must share the same httpx.Client (saves TLS handshake)."""
    from src.backend.app.services.llm.providers import MistralProvider

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "ok"}, "index": 0}],
        "model": "m",
    }
    fake_response.raise_for_status = MagicMock()
    provider = MistralProvider(api_key="k")
    provider._sync_client = MagicMock()
    provider._sync_client.is_closed = False
    provider._sync_client.post.return_value = fake_response

    provider.complete("s", "u")
    provider.complete("s", "u")
    # Should NOT have re-instantiated the client
    assert provider._sync().post.call_count == 2


def test_mistral_provider_aclose_closes_both_clients() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from src.backend.app.services.llm.providers import MistralProvider

    provider = MistralProvider(api_key="k")
    sync_mock = MagicMock()
    sync_mock.is_closed = False
    async_mock = AsyncMock()
    async_mock.is_closed = False
    provider._sync_client = sync_mock
    provider._async_client = async_mock

    asyncio.run(provider.aclose())

    # Assert on the captured references (provider's attrs are now None)
    sync_mock.close.assert_called_once()
    async_mock.aclose.assert_called_once()
    assert provider._sync_client is None
    assert provider._async_client is None


def test_mistral_provider_recreates_closed_client() -> None:
    """If a client was closed externally, _sync should create a fresh one."""
    from src.backend.app.services.llm.providers import MistralProvider

    provider = MistralProvider(api_key="k")
    old_mock = MagicMock()
    old_mock.is_closed = True
    provider._sync_client = old_mock
    new = provider._sync()
    # The old mock should have been replaced
    assert provider._sync_client is not old_mock
    assert new is provider._sync_client
    assert not new.is_closed


# ---------- prompts ----------


def test_system_prompt_has_scope_guard() -> None:
    assert "KHÔNG" in SYSTEM_PROMPT
    assert "phạm vi" in SYSTEM_PROMPT.lower() or "pham vi" in SYSTEM_PROMPT.lower()


def test_build_user_message_includes_all_known_fields() -> None:
    ctx = {
        "alert_id": "A-1",
        "user_id": "U-1",
        "device_id": "D-1",
        "severity": "high",
        "risk_score": 80,
        "anomaly_score": -0.3,
        "top_features": ["a", "b"],
        "timeline": "...",
    }
    msg = build_user_message(ctx)
    assert "A-1" in msg
    assert "U-1" in msg
    assert "high" in msg
    assert "a" in msg and "b" in msg


def test_build_chat_user_message_includes_context_and_question() -> None:
    msg = build_chat_user_message(
        alert_context={"alert_id": "A-1", "severity": "high"},
        user_question="Tại sao risk cao?",
        memories=[{"kind": "analyst_pattern", "scope": "user", "content": "user thường làm việc khuya"}],
    )
    assert "[CONTEXT ALERT]" in msg
    assert "[KIẾN THỨC LIÊN QUAN]" in msg
    assert "[CÂU HỎI MỚI]" in msg
    assert "Tại sao risk cao?" in msg


# ---------- explain_alert end-to-end ----------


def test_explain_alert_uses_fake_provider(monkeypatch) -> None:
    from src.backend.app.config import settings
    from src.backend.app.services import llm

    class FakeProvider:
        name = "fake"

        def complete(self, system, user, **kwargs):
            return providers.LLMResponse(
                content=(
                    "Tóm tắt: tóm tắt test\n"
                    "Yếu tố rủi ro: a, b\n"
                    "Gợi ý xử lý: hành động test"
                ),
                model="fake",
                tokens_in=10, tokens_out=15, latency_ms=50,
            )

    monkeypatch.setattr(settings, "mistral_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    cache.reset_cache()
    providers._provider_instance = FakeProvider()  # type: ignore[assignment]

    out = llm.explain_alert({"alert_id": "A-1", "severity": "high", "risk_score": 80, "top_features": ["a", "b"]})
    assert "Tóm tắt: tóm tắt test" in out
    assert "Yếu tố rủi ro: a, b" in out
    assert "Gợi ý xử lý: hành động test" in out

    # Second call hits the cache, not the provider
    out2 = llm.explain_alert({"alert_id": "A-1", "severity": "high", "risk_score": 80, "top_features": ["a", "b"]})
    assert out2 == out

    providers._provider_instance = None
    cache.reset_cache()


def test_explain_alert_records_stats(monkeypatch) -> None:
    from src.backend.app.config import settings
    from src.backend.app.services import llm

    class FakeProvider:
        name = "fake"

        def complete(self, system, user, **kwargs):
            return providers.LLMResponse(content=(
                "Tóm tắt: s\nYếu tố rủi ro: a\nGợi ý xử lý: r"
            ), model="f", tokens_in=5, tokens_out=8, latency_ms=30)

    monkeypatch.setattr(settings, "mistral_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    cache.reset_cache()
    stats.reset_stats()
    providers._provider_instance = FakeProvider()  # type: ignore[assignment]

    llm.explain_alert({"alert_id": "Z-9", "risk_score": 50})
    snap = stats.get_stats().get_stats()
    assert snap["total_calls"] >= 1
    providers._provider_instance = None
    cache.reset_cache()
    stats.reset_stats()
