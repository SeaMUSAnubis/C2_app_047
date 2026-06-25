"""Analyst feedback service (Phase 3.3 of PLAN_LLM.md).

Wraps the DB helper and triggers an automatic memory write when
`LLM_MEMORY_AUTO_FEEDBACK=true` (default).
"""

from __future__ import annotations

import logging
from typing import Any

from src.backend.app.config import settings
from src.backend.app.db import session as db
from src.backend.app.services.llm_memory import get_memory_store

logger = logging.getLogger(__name__)

VALID_VERDICTS = frozenset(
    {"true_positive", "false_positive", "benign", "needs_investigation"}
)


class FeedbackService:
    def submit(
        self,
        *,
        alert_id: int,
        analyst_id: str,
        verdict: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                f"invalid verdict {verdict!r}; must be one of {sorted(VALID_VERDICTS)}"
            )
        row = db.insert_feedback(alert_id, analyst_id, verdict, note)
        if settings.llm_memory_auto_feedback:
            self._auto_write_memory(row)
        return row

    def list_for_alert(self, alert_id: int) -> list[dict[str, Any]]:
        return db.get_feedback_for_alert(alert_id)

    def _auto_write_memory(self, feedback_row: dict[str, Any]) -> None:
        """Write an `analyst_pattern` memory derived from the feedback."""
        try:
            alert_id = feedback_row["alert_id"]
            alert = db.get_alert(alert_id)
        except Exception:
            logger.exception("feedback: failed to load alert %s", alert_id)
            return
        if alert is None:
            return
        verdict_vi = {
            "true_positive": "xác nhận true positive",
            "false_positive": "đánh giá false positive",
            "benign": "ghi nhận benign",
            "needs_investigation": "cần điều tra thêm",
        }.get(feedback_row["verdict"], feedback_row["verdict"])
        content = (
            f"Analyst {feedback_row['analyst_id']} {verdict_vi} cho alert "
            f"trên user {alert.get('user_id', 'unknown')}: "
            f"{feedback_row.get('note') or '(không có ghi chú)'}"
        )
        factors = alert.get("risk_factors") or []
        tags = list(factors) if isinstance(factors, list) else []
        tags.append(feedback_row["verdict"])
        get_memory_store().write(
            scope="user",
            scope_id=alert.get("user_id"),
            kind="analyst_pattern",
            content=content,
            tags=tags,
            created_by=feedback_row["analyst_id"],
        )


_instance: FeedbackService | None = None


def get_feedback_service() -> FeedbackService:
    global _instance
    if _instance is None:
        _instance = FeedbackService()
    return _instance


def reset_feedback_service() -> None:
    global _instance
    _instance = None
