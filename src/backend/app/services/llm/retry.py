"""Retry helper with exponential backoff (Phase 3.2 of PLAN_LLM.md)."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Exceptions that are safe to retry.
RETRIABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)

# HTTP status codes that warrant a retry.
RETRIABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


class RetriableLLMError(Exception):
    """Raised when a transient error persists after max_attempts."""


def retry_with_backoff(
    func: Callable[..., T],
    *args: object,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retriable_exceptions: tuple[type[BaseException], ...] = RETRIABLE_EXCEPTIONS,
    retriable_status_codes: frozenset[int] = RETRIABLE_STATUS_CODES,
    **kwargs: object,
) -> T:
    """Call `func` with exponential backoff + jitter on retriable failures.

    Retriable:
      - exceptions in `retriable_exceptions` (network/timeout)
      - HTTP responses whose status code is in `retriable_status_codes`
        — detected by re-raising from the function. Callers can raise
        `httpx.HTTPStatusError` themselves, or raise a `RetriableLLMError`
        with a `.status_code` attribute.

    Non-retriable exceptions are re-raised immediately.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except retriable_exceptions as exc:  # type: ignore[misc]
            last_exc = exc
            if attempt == max_attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = delay * (0.5 + random.random() * 0.5)  # jitter
            logger.warning(
                "retry %s/%s after %.2fs: %s", attempt, max_attempts, delay, exc
            )
            time.sleep(delay)
        except RetriableLLMError as exc:
            last_exc = exc
            if attempt == max_attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = delay * (0.5 + random.random() * 0.5)
            logger.warning(
                "retry %s/%s after %.2fs: %s", attempt, max_attempts, delay, exc
            )
            time.sleep(delay)
    raise RetriableLLMError(f"max_attempts={max_attempts} exhausted: {last_exc}")
