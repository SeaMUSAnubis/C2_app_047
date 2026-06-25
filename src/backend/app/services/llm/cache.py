"""In-memory LRU+TTL cache for LLM explanations (Phase 3.2 of PLAN_LLM.md).

Key is a deterministic hash of the inputs that should yield the same
explanation (alert_id, factors, risk_score). On alert edit/update the
caller should call `invalidate(alert_id)`.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict

logger = logging.getLogger(__name__)


class LLMCache:
    def __init__(self, *, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        self._lock = threading.Lock()
        self._data: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    @staticmethod
    def make_key(parts: list[str]) -> str:
        joined = "|".join(parts)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts > self._ttl:
                del self._data[key]
                return None
            # LRU touch
            self._data.move_to_end(key)
            return value

    def put(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (time.time(), value)
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def invalidate(self, prefix_or_key: str) -> int:
        """Delete entries whose key starts with the given prefix. Returns count removed."""
        with self._lock:
            removed = 0
            keys_to_delete = [k for k in self._data if k.startswith(prefix_or_key)]
            for k in keys_to_delete:
                del self._data[k]
                removed += 1
            return removed

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"size": len(self._data), "max_size": self._max_size, "ttl_seconds": self._ttl}


# Module-level singleton. Tests can replace with `LLMCache()`.
_cache: LLMCache | None = None
_cache_lock = threading.Lock()


def get_cache() -> LLMCache:
    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = LLMCache()
        return _cache


def reset_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None
