"""Multi-turn chat session (Phase 3.4 of PLAN_LLM.md).

Public API:
    ChatSession         — class wrapping a conversation
    send_message_stream — async generator yielding `ChatEvent` dicts

Flow per user message:
  1. Insert user message into llm_messages
  2. Build context: system + alert context + recent messages + memories + feedback
  3. Stream from provider; yield `{"type": "token", "text": "..."}` per chunk
  4. On finish: insert assistant message + touch memories; yield `{"type": "done", ...}`

The user message is always persisted (even on stream failure) so the
analyst can retry. The assistant message is only persisted on success.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from src.backend.app.config import settings
from src.backend.app.db import session as db
from src.backend.app.services.llm import get_provider
from src.backend.app.services.llm.prompts import (
    build_chat_system_prompt,
    build_chat_user_message,
)
from src.backend.app.services.llm_memory import get_memory_store

logger = logging.getLogger(__name__)


@dataclass
class ChatEvent:
    type: str  # "token" | "done" | "error" | "memory_used"
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}


class ChatSession:
    def __init__(
        self,
        conversation_id: int,
        alert_id: int,
        user_id: str,
        *,
        actor_role: str = "analyst",
        actor_email: str = "",
        linked_user_id: str | None = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.alert_id = alert_id
        self.user_id = user_id
        self.actor_role = actor_role
        self.actor_email = actor_email
        self.linked_user_id = linked_user_id

    def load_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        limit = limit or settings.llm_chat_max_context_messages
        return db.load_recent_messages(self.conversation_id, limit=limit)

    async def send_message_stream(
        self,
        user_msg: str,
    ) -> AsyncIterator[ChatEvent]:
        """Persist the user message, stream the assistant response, persist it on success."""
        if not user_msg or not user_msg.strip():
            yield ChatEvent("error", {"code": "empty_message", "message": "empty message"})
            return

        guard_response = self._role_guard_response(user_msg)
        if guard_response:
            yield ChatEvent("token", {"text": guard_response})
            yield ChatEvent(
                "done",
                {
                    "message_id": None,
                    "latency_ms": 0,
                    "model": "rbac-guard",
                },
            )
            return

        # 1. Insert user message
        try:
            db.append_message(self.conversation_id, "user", user_msg.strip())
        except Exception as exc:
            logger.exception("chat: append user message failed")
            yield ChatEvent("error", {"code": "db_error", "message": str(exc)})
            return

        # 2. Build context
        try:
            alert_ctx = self._load_alert_context()
            memories: list[dict[str, Any]] = []
            feedback: list[dict[str, Any]] = []
            memory_ids: list[int] = []
            if settings.llm_memory_enabled:
                memories = get_memory_store().retrieve(
                    user_id=alert_ctx.get("user_id"),
                    device_id=alert_ctx.get("device_id"),
                    factor_tags=alert_ctx.get("top_factors") or [],
                )
                memory_ids = [m["id"] for m in memories]
                if memory_ids:
                    yield ChatEvent("memory_used", {"ids": memory_ids, "count": len(memory_ids)})
                feedback = db.get_feedback_for_alert(self.alert_id)
        except Exception as exc:
            logger.exception("chat: context build failed")
            yield ChatEvent("error", {"code": "context_error", "message": str(exc)})
            return

        # 3. Stream from provider
        provider = get_provider()
        system_prompt = build_chat_system_prompt(self.actor_role)
        user_prompt = build_chat_user_message(
            alert_context=alert_ctx,
            user_question=user_msg.strip(),
            actor_context={
                "account_id": self.user_id,
                "email": self.actor_email,
                "role": self.actor_role,
                "linked_user_id": self.linked_user_id,
            },
            memories=memories,
            feedback=feedback,
        )

        start = time.perf_counter()
        chunks: list[str] = []
        full_content = ""
        tokens_out: int | None = None
        try:
            async for chunk in provider.complete_stream(system_prompt, user_prompt):
                chunks.append(chunk)
                full_content += chunk
                yield ChatEvent("token", {"text": chunk})
        except asyncio.CancelledError:
            logger.info("chat: client cancelled stream")
            raise
        except Exception as exc:
            logger.exception("chat: provider stream failed")
            yield ChatEvent("error", {"code": "provider_error", "message": str(exc)})
            return

        latency_ms = int((time.perf_counter() - start) * 1000)

        # 4. Persist assistant message + touch memories
        if not full_content.strip():
            yield ChatEvent("error", {"code": "empty_response", "message": "model returned no content"})
            return

        try:
            assistant_row = db.append_message(
                self.conversation_id,
                "assistant",
                full_content.strip(),
                model=provider.name,
                latency_ms=latency_ms,
                memory_used_ids=memory_ids or None,
                tokens_out=tokens_out,
            )
            if memory_ids:
                get_memory_store().touch(memory_ids)
        except Exception as exc:
            logger.exception("chat: persist assistant message failed")
            yield ChatEvent("error", {"code": "db_error", "message": str(exc)})
            return

        yield ChatEvent(
            "done",
            {
                "message_id": assistant_row["id"],
                "latency_ms": latency_ms,
                "model": provider.name,
            },
        )

    def _load_alert_context(self) -> dict[str, Any]:
        alert = db.get_alert(self.alert_id)
        if alert is None:
            return {"alert_id": self.alert_id}
        return {
            "alert_id": alert.get("id"),
            "user_id": alert.get("user_id"),
            "device_id": alert.get("device_id"),
            "title": alert.get("title"),
            "severity": alert.get("severity"),
            "risk_score": alert.get("risk_score"),
            "anomaly_score": alert.get("anomaly_score"),
            "top_factors": alert.get("risk_factors") or [],
        }

    def _role_guard_response(self, user_msg: str) -> str | None:
        question = user_msg.strip().lower()
        if self.actor_role == "employee":
            return (
                "Tôi không thể hỗ trợ phân tích bảo mật/SOC, điều tra người dùng khác, "
                "người có quyền cao hơn hoặc cấu hình hệ thống với quyền nhân viên. "
                "Bạn có thể xem hồ sơ cá nhân trong trang này và liên hệ SOC/quản trị viên "
                "nếu cần giải thích chi tiết hoặc xử lý cảnh báo."
            )

        forbidden_for_all = (
            "mật khẩu",
            "password",
            "secret",
            "api key",
            "apikey",
            "token",
            "private key",
            "jwt",
            "bypass",
            "né phát hiện",
            "vượt quyền",
            "leo thang quyền",
        )
        if any(term in question for term in forbidden_for_all):
            return (
                "Tôi không thể cung cấp mật khẩu, token, secret, cách vượt quyền hoặc cách né phát hiện. "
                "Hãy dùng kênh quản trị hợp lệ và quy trình bảo mật nội bộ."
            )

        analyst_admin_terms = (
            "tài khoản hệ thống",
            "quản trị tài khoản",
            "admin account",
            "llm memory",
            "cấp quyền admin",
            "thu hồi quyền admin",
            "tạo tài khoản",
            "xóa tài khoản",
        )
        if self.actor_role == "analyst" and any(term in question for term in analyst_admin_terms):
            return (
                "Role analyst không được phép xử lý câu hỏi quản trị hệ thống hoặc tài khoản quyền cao. "
                "Bạn có thể hỏi về triage cảnh báo hiện tại, bằng chứng, risk score, timeline hoặc đề xuất escalation."
            )

        manager_admin_terms = (
            "tạo tài khoản",
            "xóa tài khoản",
            "đổi role",
            "cấp quyền admin",
            "thu hồi quyền admin",
            "llm memory admin",
        )
        if self.actor_role == "security_manager" and any(term in question for term in manager_admin_terms):
            return (
                "Role security_manager không được phép quản trị tài khoản hệ thống hoặc quyền admin. "
                "Hãy chuyển yêu cầu này cho quản trị viên."
            )

        return None


# -------- Factory helpers --------


def get_or_create_conversation(alert_id: int, user_id: str, title: str) -> dict[str, Any]:
    """Single round-trip — `create_conversation` already does ON CONFLICT."""
    return db.create_conversation(alert_id=alert_id, user_id=user_id, title=title)
