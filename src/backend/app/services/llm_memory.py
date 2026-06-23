"""Long-term memory service (Phase 3.3 of PLAN_LLM.md).

v1: tag-based retrieval via `db.session.retrieve_memories` (no embeddings).

Public API:
    MemoryStore          — class with .retrieve / .write / .touch / .forget / .list / .get_stats
    get_memory_store()   — singleton accessor
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from src.backend.app.config import settings
from src.backend.app.db import session as db

logger = logging.getLogger(__name__)


class MemoryStore:
    def retrieve(
        self,
        user_id: str | None = None,
        device_id: str | None = None,
        factor_tags: Iterable[str] | None = None,
        top_k: int | None = None,
        decay_days: int | None = None,
    ) -> list[dict[str, Any]]:
        if not settings.llm_memory_enabled:
            return []
        top_k = top_k or settings.llm_memory_max_retrieve
        decay_days = decay_days or settings.llm_memory_decay_days
        return db.retrieve_memories(
            user_id=user_id,
            device_id=device_id,
            factor_tags=list(factor_tags or []),
            top_k=top_k,
            decay_days=decay_days,
        )

    def write(
        self,
        scope: str,
        scope_id: str | None,
        kind: str,
        content: str,
        tags: Iterable[str] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        if not settings.llm_memory_enabled:
            return {}
        return db.upsert_memory(
            scope=scope,
            scope_id=scope_id,
            kind=kind,
            content=content,
            tags=list(tags or []),
            created_by=created_by,
        )

    def touch(self, memory_ids: list[int]) -> None:
        if not memory_ids:
            return
        db.touch_memories(memory_ids)

    def forget(self, memory_id: int) -> None:
        db.forget_memory(memory_id)

    def list_admin(
        self,
        scope: str | None = None,
        kind: str | None = None,
        tag: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return db.list_memories_admin(scope=scope, kind=kind, tag=tag, limit=limit)

    def get_stats(self) -> list[dict[str, Any]]:
        return db.get_memory_stats()


_instance: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _instance
    if _instance is None:
        _instance = MemoryStore()
    return _instance


def reset_memory_store() -> None:
    global _instance
    _instance = None
