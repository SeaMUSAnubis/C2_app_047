"""LLM provider abstraction (Phase 3.1 of PLAN_LLM.md).

Defines `LLMProvider` Protocol + `MistralProvider` concrete implementation.
`OpenAICompatibleProvider` is scaffolded but not yet implemented (v2 work).
Factory `get_provider()` reads `settings.llm_provider` and caches a singleton.

Public API:
    LLMProvider          — Protocol
    MistralProvider      — concrete
    OpenAICompatibleProvider — TODO v2
    LLMResponse          — data class
    get_provider()       — factory

Note: streaming and embedding are also part of the protocol but live in
their own modules to keep this file focused on the chat completion path.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx

from src.backend.app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Unified response shape returned by `LLMProvider.complete()`."""

    content: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 500,
        **kwargs: Any,
    ) -> LLMResponse: ...

    async def complete_stream(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> AsyncIterator[str]: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class MistralProvider:
    """Mistral AI chat completions + embeddings.

    Synchronous `complete()`; async `complete_stream()` and `embed()`.
    Authentication: `MISTRAL_API_KEY` env var.
    """

    name = "mistral"
    base_url = "https://api.mistral.ai/v1"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("MISTRAL_API_KEY is empty")
        self._api_key = api_key
        # Lazy-init HTTP clients. Reusing the client gives us:
        #  - HTTP/2 + connection pooling (one TCP+TLS handshake amortised over many calls)
        #  - DNS cache (no repeated lookups)
        # Without reuse each `complete()` / `complete_stream()` call would
        # re-resolve the host and re-do the TLS handshake.
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    def _sync(self) -> httpx.Client:
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(timeout=settings.llm_timeout_seconds)
        return self._sync_client

    def _async(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
        return self._async_client

    async def aclose(self) -> None:
        """Close both HTTP clients. Call from FastAPI lifespan shutdown."""
        if self._async_client is not None and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None
        if self._sync_client is not None and not self._sync_client.is_closed:
            self._sync_client.close()
            self._sync_client = None

    # -------- Chat completion (sync) --------

    def complete(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 500,
        **kwargs: Any,
    ) -> LLMResponse:
        import time

        start = time.perf_counter()
        model = model or settings.llm_chat_model
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        client = self._sync()
        response = client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        try:
            data = response.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            msg = err.get("message", "unknown") if isinstance(err, dict) else str(err)
            raise RuntimeError(f"mistral error: {msg}")
        response.raise_for_status()
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            logger.error("mistral response missing choices: %s", response.text[:500])
            raise RuntimeError(f"malformed mistral response: {exc}") from exc
        usage = data.get("usage", {}) or {}
        return LLMResponse(
            content=content,
            model=data.get("model", model),
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
            latency_ms=latency_ms,
            raw=data,
        )

    # -------- Chat completion (async stream) --------

    async def complete_stream(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> AsyncIterator[str]:
        model = model or settings.llm_chat_model
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        client = self._async()
        async with client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[len("data:"):].strip()
                if chunk == "[DONE]":
                    break
                try:
                    evt = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                try:
                    delta = evt["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, AttributeError):
                    continue
                if delta:
                    yield delta

    # -------- Embeddings --------

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Call Mistral embeddings API. `mistral-embed` returns 1024-dim vectors."""
        if not texts:
            return []
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.llm_embedding_model,
            "input": texts,
        }
        response = await self._async().post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data.get("data", [])]


class OpenAICompatibleProvider:
    """Stub for the v2 OpenAI-compatible provider.

    Will be implemented when the project needs to swap to OpenAI, Ollama,
    vLLM, etc. Same interface as `MistralProvider`; only base URL and
    payload schema differ.
    """

    name = "openai_compatible"

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url

    def complete(self, system: str, user: str, **kwargs: Any) -> LLMResponse:  # pragma: no cover
        raise NotImplementedError("OpenAICompatibleProvider is v2 work")

    async def complete_stream(self, system: str, user: str, **kwargs: Any) -> AsyncIterator[str]:  # pragma: no cover
        raise NotImplementedError("OpenAICompatibleProvider is v2 work")
        yield ""  # unreachable, makes this an async generator

    async def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        raise NotImplementedError("OpenAICompatibleProvider is v2 work")


# -------- Factory --------

_provider_instance: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return a process-wide singleton `LLMProvider` based on settings.

    Raises `ValueError` if no provider can be constructed (e.g. no API key
    and the provider needs one).
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance
    name = settings.llm_provider
    if name == "mistral":
        _provider_instance = MistralProvider(api_key=settings.mistral_api_key)
    elif name == "openai_compatible":
        if not settings.llm_openai_api_key or not settings.llm_openai_base_url:
            raise ValueError(
                "OPENAI_API_KEY and OPENAI_BASE_URL required for llm_provider=openai_compatible"
            )
        _provider_instance = OpenAICompatibleProvider(
            api_key=settings.llm_openai_api_key,
            base_url=settings.llm_openai_base_url,
        )
    else:
        raise ValueError(f"unknown LLM_PROVIDER: {name!r}")
    logger.info("llm provider initialised: %s", _provider_instance.name)
    return _provider_instance


def reset_provider() -> None:
    """Drop the cached provider. Used by tests."""
    global _provider_instance
    _provider_instance = None
