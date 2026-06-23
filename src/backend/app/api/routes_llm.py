"""LLM endpoints: chat, feedback, memory admin, stats (Phase 3.5 of PLAN_LLM.md).

Endpoints:
  POST /api/alerts/{alert_id}/chat/message     — send a message, stream SSE
  GET  /api/alerts/{alert_id}/conversation     — full thread
  POST /api/alerts/{alert_id}/conversation/reset
  POST /api/alerts/{alert_id}/feedback
  GET  /api/alerts/{alert_id}/feedback
  GET  /api/admin/llm-memory
  DELETE /api/admin/llm-memory/{memory_id}
  GET  /api/admin/llm-memory/stats
  GET  /api/admin/llm-stats
  GET  /api/admin/db-pool-stats
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.backend.app.api.routes import require_role
from src.backend.app.db import session as database
from src.backend.app.db.pool import get_pool_stats
from src.backend.app.schemas.schemas import (
    ChatMessageCreate,
    ChatMessageRead,
    ConversationCreate,
    ConversationRead,
    ConversationSummaryRead,
    ConversationUpdate,
    FeedbackCreate,
    FeedbackRead,
    MemoryRead,
)
from src.backend.app.services.llm import get_stats as get_llm_stats
from src.backend.app.services.llm_chat import ChatSession, get_or_create_conversation
from src.backend.app.services.llm_feedback import get_feedback_service
from src.backend.app.services.llm_memory import get_memory_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["llm"])


# Auth deps.
_analyst_dep = require_role("admin", "analyst", "security_manager")
_chat_dep = require_role("admin", "analyst", "security_manager", "employee")
_admin_dep = require_role("admin")


# ---- Helper: alert must exist ----


def _get_alert_or_404(alert_id: int) -> dict[str, Any]:
    alert = database.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"alert {alert_id} not found")
    return alert


def _api_time(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _linked_user_id_for_account(account: dict[str, Any]) -> str | None:
    try:
        account_id = int(account.get("id") or 0)
    except (TypeError, ValueError):
        return None
    user = database.get_user_by_app_account_id(account_id)
    return str(user["id"]) if user and user.get("id") else None


def _authorize_chat_alert(alert: dict[str, Any], account: dict[str, Any]) -> str | None:
    role = str(account.get("role") or "")
    if role != "employee":
        return None
    linked_user_id = _linked_user_id_for_account(account)
    if not linked_user_id or str(alert.get("user_id") or "") != linked_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee can only access their own alert chat",
        )
    return linked_user_id


def _message_read(row: dict[str, Any]) -> ChatMessageRead:
    return ChatMessageRead(
        id=row["id"],
        role=row["role"],
        content=row["content"],
        model=row.get("model"),
        latency_ms=row.get("latency_ms"),
        memory_used_ids=row.get("memory_used_ids"),
        created_at=_api_time(row.get("created_at")),
    )


def _conversation_summary(row: dict[str, Any]) -> ConversationSummaryRead:
    return ConversationSummaryRead(
        id=row["id"],
        alert_id=row["alert_id"],
        user_id=row["user_id"],
        title=row["title"],
        message_count=int(row.get("message_count") or 0),
        updated_at=_api_time(row.get("updated_at")),
    )


def _conversation_read(row: dict[str, Any], messages: list[dict[str, Any]]) -> ConversationRead:
    return ConversationRead(
        id=row["id"],
        alert_id=row["alert_id"],
        user_id=row["user_id"],
        title=row["title"],
        summary=row.get("summary"),
        messages=[_message_read(m) for m in messages],
        updated_at=_api_time(row.get("updated_at")),
    )


def _conversation_or_404(
    alert_id: int,
    account: dict[str, Any],
    conversation_id: int | None = None,
) -> dict[str, Any]:
    alert = _get_alert_or_404(alert_id)
    _authorize_chat_alert(alert, account)
    if account.get("role") == "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee chat is not persisted",
        )
    conv = (
        database.get_conversation_by_id(conversation_id)
        if conversation_id is not None
        else database.get_conversation_by_alert(alert_id)
    )
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")
    if conv.get("alert_id") != alert_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")
    if str(conv.get("user_id")) != str(account.get("id") or account.get("email") or "unknown") and account.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="conversation belongs to another account")
    return conv


# ---- Chat ----


@router.post("/alerts/{alert_id}/chat/message")
async def send_chat_message(
    alert_id: int,
    payload: ChatMessageCreate,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> Any:
    """Send a user message. Streams SSE chunks if `payload.stream=true`, else JSON.

    SSE format: `data: {"type": "token", "text": "..."}\\n\\n` per chunk,
    ending with `data: {"type": "done", "message_id": ..., "latency_ms": ...}\\n\\n`.
    """
    alert = _get_alert_or_404(alert_id)
    linked_user_id = _authorize_chat_alert(alert, current_account)
    title = alert.get("title") or f"Alert {alert_id}"
    actor_role = str(current_account.get("role") or "analyst")
    actor_id = str(current_account.get("id") or current_account.get("email") or "unknown")
    if actor_role == "employee":
        conv = {"id": 0, "user_id": actor_id}
    elif payload.conversation_id:
        conv = _conversation_or_404(alert_id, current_account, payload.conversation_id)
    else:
        existing = database.get_conversation_by_alert(alert_id)
        conv = existing or get_or_create_conversation(alert_id=alert_id, user_id=actor_id, title=title)
    session = ChatSession(
        conversation_id=conv["id"],
        alert_id=alert_id,
        user_id=conv["user_id"],
        actor_role=actor_role,
        actor_email=str(current_account.get("email") or ""),
        linked_user_id=linked_user_id,
    )

    if payload.stream:
        async def event_gen():
            try:
                async for ev in session.send_message_stream(payload.content):
                    yield f"data: {json.dumps(ev.to_dict(), ensure_ascii=False)}\n\n"
            except Exception as exc:  # noqa: BLE001
                logger.exception("chat stream failure")
                err = json.dumps(
                    {"type": "error", "code": "internal", "message": str(exc)},
                    ensure_ascii=False,
                )
                yield f"data: {err}\n\n"

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    # Non-streaming: collect events, return the final content
    full = ""
    last_event: dict[str, Any] | None = None
    async for ev in session.send_message_stream(payload.content):
        last_event = ev.to_dict()
        if ev.type == "token":
            full += ev.data.get("text", "")
    if last_event and last_event.get("type") == "error":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=last_event.get("message", "provider error"),
        )
    return {
        "message_id": last_event.get("message_id") if last_event else None,
        "content": full,
        "latency_ms": last_event.get("latency_ms") if last_event else None,
    }


@router.get("/alerts/{alert_id}/conversation", response_model=ConversationRead)
async def get_conversation(
    alert_id: int,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> ConversationRead:
    alert = _get_alert_or_404(alert_id)
    _authorize_chat_alert(alert, current_account)
    if current_account.get("role") == "employee":
        return ConversationRead(
            id=0,
            alert_id=alert_id,
            user_id=str(current_account.get("id") or ""),
            title=alert.get("title") or f"Alert {alert_id}",
            messages=[],
            updated_at="",
        )
    conv = database.get_conversation_by_alert(alert_id)
    if conv is None:
        # Return empty thread; chat panel can detect and prompt to start
        return ConversationRead(
            id=0, alert_id=alert_id, user_id="", title="", updated_at=""
        )
    return _conversation_read(conv, database.load_recent_messages(conv["id"], limit=100))


@router.get("/alerts/{alert_id}/conversations", response_model=list[ConversationSummaryRead])
async def list_conversations(
    alert_id: int,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> list[ConversationSummaryRead]:
    alert = _get_alert_or_404(alert_id)
    _authorize_chat_alert(alert, current_account)
    if current_account.get("role") == "employee":
        return []
    actor_id = str(current_account.get("id") or current_account.get("email") or "unknown")
    user_filter = None if current_account.get("role") == "admin" else actor_id
    rows = database.list_conversations_for_alert(alert_id, user_id=user_filter)
    return [_conversation_summary(row) for row in rows]


@router.post(
    "/alerts/{alert_id}/conversations",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    alert_id: int,
    payload: ConversationCreate,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> ConversationRead:
    alert = _get_alert_or_404(alert_id)
    _authorize_chat_alert(alert, current_account)
    if current_account.get("role") == "employee":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee chat is not persisted")
    title = (payload.title or alert.get("title") or f"Alert {alert_id}").strip()
    conv = get_or_create_conversation(
        alert_id=alert_id,
        user_id=str(current_account.get("id") or current_account.get("email") or "unknown"),
        title=title,
    )
    return _conversation_read(conv, [])


@router.get("/alerts/{alert_id}/conversations/{conversation_id}", response_model=ConversationRead)
async def get_conversation_by_id(
    alert_id: int,
    conversation_id: int,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> ConversationRead:
    conv = _conversation_or_404(alert_id, current_account, conversation_id)
    return _conversation_read(conv, database.load_recent_messages(conv["id"], limit=100))


@router.patch("/alerts/{alert_id}/conversation", response_model=ConversationRead)
async def update_conversation(
    alert_id: int,
    payload: ConversationUpdate,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> ConversationRead:
    conv = _conversation_or_404(alert_id, current_account)
    return await update_conversation_by_id(alert_id, conv["id"], payload, current_account)


@router.patch("/alerts/{alert_id}/conversations/{conversation_id}", response_model=ConversationRead)
async def update_conversation_by_id(
    alert_id: int,
    conversation_id: int,
    payload: ConversationUpdate,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> ConversationRead:
    conv = _conversation_or_404(alert_id, current_account, conversation_id)
    updated = database.update_conversation_title(conv["id"], payload.title.strip())
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")
    msgs = database.load_recent_messages(updated["id"], limit=100)
    return _conversation_read(updated, msgs)


@router.delete("/alerts/{alert_id}/conversation")
async def delete_conversation(
    alert_id: int,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> dict[str, Any]:
    conv = _conversation_or_404(alert_id, current_account)
    return await delete_conversation_by_id(alert_id, conv["id"], current_account)


@router.delete("/alerts/{alert_id}/conversations/{conversation_id}")
async def delete_conversation_by_id(
    alert_id: int,
    conversation_id: int,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> dict[str, Any]:
    conv = _conversation_or_404(alert_id, current_account, conversation_id)
    deleted = database.delete_conversation(conv["id"])
    return {"deleted": deleted, "conversation_id": conv["id"]}


@router.post("/alerts/{alert_id}/conversation/reset")
async def reset_conversation(
    alert_id: int,
    current_account: Annotated[dict, Depends(_chat_dep)],
) -> dict[str, Any]:
    alert = _get_alert_or_404(alert_id)
    _authorize_chat_alert(alert, current_account)
    if current_account.get("role") == "employee":
        return {"reset": False, "reason": "employee_chat_has_no_persisted_thread"}
    conv = database.get_conversation_by_alert(alert_id)
    if conv is None:
        return {"reset": False, "reason": "no conversation"}
    with database.get_connection(write=True) as conn:
        conn.execute(
            "DELETE FROM llm_messages WHERE conversation_id = %s", (conv["id"],)
        )
        conn.execute(
            "UPDATE llm_conversations SET summary = NULL, summarized_through_msg_id = NULL WHERE id = %s",
            (conv["id"],),
        )
    return {"reset": True, "conversation_id": conv["id"]}


# ---- Feedback ----


@router.post(
    "/alerts/{alert_id}/feedback",
    response_model=FeedbackRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    alert_id: int,
    payload: FeedbackCreate,
    current_account: Annotated[dict, Depends(_analyst_dep)],
) -> FeedbackRead:
    _get_alert_or_404(alert_id)
    row = get_feedback_service().submit(
        alert_id=alert_id,
        analyst_id=str(current_account.get("id") or current_account.get("email") or "unknown"),
        verdict=payload.verdict,
        note=payload.note,
    )
    return FeedbackRead(
        id=row["id"],
        alert_id=row["alert_id"],
        analyst_id=row["analyst_id"],
        verdict=row["verdict"],
        note=row.get("note"),
        created_at=_api_time(row.get("created_at")),
    )


@router.get("/alerts/{alert_id}/feedback", response_model=list[FeedbackRead])
async def list_feedback(
    alert_id: int,
    current_account: Annotated[dict, Depends(_analyst_dep)],
) -> list[FeedbackRead]:
    _get_alert_or_404(alert_id)
    rows = get_feedback_service().list_for_alert(alert_id)
    return [
        FeedbackRead(
            id=r["id"],
            alert_id=r["alert_id"],
            analyst_id=r["analyst_id"],
            verdict=r["verdict"],
            note=r.get("note"),
            created_at=_api_time(r.get("created_at")),
        )
        for r in rows
    ]


# ---- Admin: memory ----


@router.get("/admin/llm-memory", response_model=list[MemoryRead])
async def list_memories_admin(
    current_account: Annotated[dict, Depends(_admin_dep)],
    scope: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    limit: int = 100,
) -> list[MemoryRead]:
    rows = get_memory_store().list_admin(scope=scope, kind=kind, tag=tag, limit=limit)
    return [
        MemoryRead(
            id=r["id"],
            scope=r["scope"],
            scope_id=r.get("scope_id"),
            kind=r["kind"],
            content=r["content"],
            tags=list(r.get("tags") or []),
            use_count=r["use_count"],
            last_used_at=_api_time(r.get("last_used_at")) if r.get("last_used_at") is not None else None,
            created_at=_api_time(r.get("created_at")),
        )
        for r in rows
    ]


@router.delete("/admin/llm-memory/{memory_id}")
async def forget_memory(
    memory_id: int,
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    get_memory_store().forget(memory_id)
    return {"forgotten": memory_id}


@router.get("/admin/llm-memory/stats")
async def memory_stats(
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    rows = get_memory_store().get_stats()
    return {"by_scope_kind": rows}


# ---- Admin: LLM + pool ----


@router.get("/admin/llm-stats")
async def llm_stats(
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    return get_llm_stats().get_stats()


@router.get("/admin/db-pool-stats")
async def db_pool_stats(
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    return get_pool_stats()
