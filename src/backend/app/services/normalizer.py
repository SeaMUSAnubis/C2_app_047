"""Normalizer worker — chuyển `raw_user_logs` → `event_logs` rồi trigger ML scoring.

Phase 3 component. Khi agent ingest raw log qua `/api/raw-logs/batch`, dòng được
insert vào `raw_user_logs` với `normalized_event_id = NULL`. Worker này:

1. Đọc batch pending (`normalized_event_id IS NULL`).
2. Map `raw_payload` → `EventIngest` theo `event_type` (logon, device, file,
   http, email, process, network, ldap, psychometric, custom).
3. Insert vào `event_logs` (idempotent trên `source_id`).
4. Update `raw_user_logs.normalized_event_id`.
5. Track distinct `user_id` đã có event mới → trả về cho caller để trigger
   `score_user` (user_scoring service).

Design notes:
- Idempotent: re-run cùng raw_log không tạo duplicate event_log (nhờ
  `ON CONFLICT(source_id)` của `ingest_event`).
- Defensive: collector đôi khi push payload hơi khác nhau, normalizer phải
  tolerate thiếu field, không crash.
- `source_file` cho event_log lấy từ `collector_type` + raw_log_id
  (vd: `endpoint_agent:raw:42`) để trace lại nguồn.
- Sync helpers (`normalize_raw_log`, `Normalizer.run_once`) — blocking.
  Background loop wraps in `asyncio.to_thread` to avoid blocking the
  FastAPI event loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.backend.app.config import settings
from src.backend.app.db import session as database
from src.backend.app.schemas.schemas import EventIngest

logger = logging.getLogger(__name__)


@dataclass
class NormalizerStats:
    """In-memory running stats for the normalizer worker."""

    total_runs: int = 0
    total_processed: int = 0
    total_failed: int = 0
    total_scoring_calls: int = 0
    last_run_at: str | None = None
    last_duration_ms: float = 0.0
    last_processed: int = 0
    last_failed: int = 0
    last_pending: int = 0
    last_users_to_score: list[str] = field(default_factory=list)
    last_errors: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)


def _safe_iso_now() -> str:
    from src.backend.app.db.session import utc_now

    return utc_now()


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _first_str(*candidates: Any) -> str | None:
    for c in candidates:
        s = _coerce_str(c)
        if s:
            return s
    return None


def _normalize_logon(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a logon raw payload into event_log fields.

    Recognised payload shapes (agent + CSV-compatible):
    - {"user": "...", "pc": "...", "activity": "Logon"/"Logoff"}
    - {"action": "logon"/"logoff", "device": "...", "user": "..."}
    """
    action = (
        _first_str(raw.get("activity"), raw.get("action")) or "logon"
    ).lower()
    if action in ("logoff", "logout", "log_off"):
        action = "logoff"
    elif action in ("logon", "login", "log_on"):
        action = "logon"
    resource = _first_str(raw.get("pc"), raw.get("device"), raw.get("hostname"))
    metadata = {
        k: v
        for k, v in raw.items()
        if k
        in {
            "user",
            "pc",
            "activity",
            "device",
            "hostname",
            "ip",
            "ip_address",
            "logon_id",
            "logon_type",
        }
        and v is not None
    }
    return {
        "action": action,
        "resource": resource,
        "metadata": metadata,
    }


def _normalize_device(raw: dict[str, Any]) -> dict[str, Any]:
    action = (
        _first_str(raw.get("activity"), raw.get("action")) or "connect"
    ).lower()
    if action not in ("connect", "disconnect"):
        action = "connect" if "connect" in action else "disconnect"
    resource = _first_str(
        raw.get("filename"),
        raw.get("device"),
        raw.get("usb_device"),
        raw.get("product"),
    )
    metadata = {
        k: v
        for k, v in raw.items()
        if k
        in {
            "filename",
            "activity",
            "device",
            "usb_device",
            "product",
            "vendor",
            "serial",
            "disconnect",
        }
        and v is not None
    }
    return {"action": action, "resource": resource, "metadata": metadata}


def _normalize_file(raw: dict[str, Any]) -> dict[str, Any]:
    action = (_first_str(raw.get("activity"), raw.get("action")) or "file_access").lower()
    if action not in ("file_access", "file_copy", "file_delete", "file_open", "file_write"):
        action = "file_access"
    resource = _first_str(raw.get("filename"), raw.get("path"), raw.get("resource"))
    metadata = {
        k: v
        for k, v in raw.items()
        if k
        in {"filename", "path", "activity", "size", "extension", "from_removable_media"}
        and v is not None
    }
    return {"action": action, "resource": resource, "metadata": metadata}


def _normalize_http(raw: dict[str, Any]) -> dict[str, Any]:
    action = (_first_str(raw.get("action"), raw.get("activity")) or "allowed").lower()
    if action not in ("allowed", "blocked"):
        action = "blocked" if "block" in action else "allowed"
    resource = _first_str(raw.get("url"), raw.get("domain"))
    metadata = {
        k: v
        for k, v in raw.items()
        if k
        in {
            "url",
            "domain",
            "block_pattern",
            "block_category",
            "block_reason",
            "method",
            "user_agent",
            "status_code",
        }
        and v is not None
    }
    return {"action": action, "resource": resource, "metadata": metadata}


def _normalize_email(raw: dict[str, Any]) -> dict[str, Any]:
    action = (
        _first_str(raw.get("activity"), raw.get("action")) or "email_send"
    ).lower()
    if action not in ("email_send", "email_read", "email_forward", "email_delete"):
        action = "email_send"
    resource = _first_str(raw.get("to"), raw.get("recipient"), raw.get("from"))
    metadata = {
        k: v
        for k, v in raw.items()
        if k
        in {
            "from",
            "to",
            "cc",
            "bcc",
            "subject",
            "size",
            "attachments",
            "activity",
        }
        and v is not None
    }
    return {"action": action, "resource": resource, "metadata": metadata}


def _normalize_process(raw: dict[str, Any]) -> dict[str, Any]:
    action = (_first_str(raw.get("activity"), raw.get("action")) or "spawn").lower()
    if action not in ("spawn", "exit", "start", "stop"):
        action = "spawn"
    resource = _first_str(raw.get("process_name"), raw.get("image"), raw.get("path"))
    metadata = {
        k: v
        for k, v in raw.items()
        if k
        in {
            "process_name",
            "image",
            "path",
            "pid",
            "ppid",
            "cmdline",
            "user",
        }
        and v is not None
    }
    return {"action": action, "resource": resource, "metadata": metadata}


def _normalize_network(raw: dict[str, Any]) -> dict[str, Any]:
    action = (
        _first_str(raw.get("activity"), raw.get("action")) or "connection"
    ).lower()
    if action not in ("connection", "disconnect", "dns_query", "listen"):
        action = "connection"
    remote = _first_str(raw.get("remote_address"), raw.get("dst_ip"))
    port = raw.get("remote_port") or raw.get("dst_port")
    resource = f"{remote}:{port}" if remote and port else remote
    metadata = {
        k: v
        for k, v in raw.items()
        if k
        in {
            "remote_address",
            "remote_port",
            "dst_ip",
            "dst_port",
            "src_ip",
            "src_port",
            "protocol",
            "domain",
            "activity",
        }
        and v is not None
    }
    return {"action": action, "resource": resource, "metadata": metadata}


def _normalize_passthrough(raw: dict[str, Any], default_action: str) -> dict[str, Any]:
    """Fallback for ldap/psychometric/custom: keep action/resource, dump rest to metadata."""
    action = _coerce_str(raw.get("activity")) or _coerce_str(raw.get("action")) or default_action
    resource = _first_str(raw.get("resource"), raw.get("target"), raw.get("name"))
    return {"action": action, "resource": resource, "metadata": dict(raw)}


_NORMALIZERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "logon": _normalize_logon,
    "device": _normalize_device,
    "file": _normalize_file,
    "http": _normalize_http,
    "email": _normalize_email,
    "process": _normalize_process,
    "network": _normalize_network,
    "ldap": lambda r: _normalize_passthrough(r, "ldap_query"),
    "psychometric": lambda r: _normalize_passthrough(r, "psychometric_update"),
    "custom": lambda r: _normalize_passthrough(r, "custom"),
}


def normalize_raw_log(raw_log: dict[str, Any]) -> dict[str, Any] | None:
    """Map one `raw_user_logs` row → dict ready to be inserted into `event_logs`.

    Returns a dict with keys matching `EventIngest` (sans source_id/timestamp
    which are taken from the raw log). Returns None if the row is malformed
    enough that we cannot safely normalise (caller should treat as failed).
    """
    source_id = raw_log.get("source_id")
    timestamp = raw_log.get("timestamp")
    user_id = raw_log.get("user_id")
    device_id = raw_log.get("device_id")
    event_type = raw_log.get("event_type")
    raw_payload = raw_log.get("raw_payload") or {}
    collector_type = raw_log.get("collector_type") or "endpoint_agent"
    raw_log_id = raw_log.get("id")

    if not source_id or not timestamp or not event_type:
        logger.warning(
            "normalizer: skip malformed raw_log id=%s (missing source_id/timestamp/event_type)",
            raw_log_id,
        )
        return None

    # Validate device_id references an existing device; FK constraint on
    # event_logs requires it. If the device doesn't exist, drop device_id
    # to avoid a persistent FK violation that would never self-heal.
    if device_id:
        dev = database.get_device(device_id)
        if not dev:
            logger.warning(
                "normalizer: device_id=%s not found for raw_log id=%s, dropping device_id",
                device_id,
                raw_log_id,
            )
            device_id = None

    handler = _NORMALIZERS.get(event_type) or _NORMALIZERS["custom"]
    try:
        mapped = handler(raw_payload if isinstance(raw_payload, dict) else {})
    except Exception:
        logger.exception(
            "normalizer: handler %s failed for raw_log id=%s", event_type, raw_log_id
        )
        return None

    source_file = f"{collector_type}:raw:{raw_log_id}" if raw_log_id else f"{collector_type}:raw"
    ingest = EventIngest(
        source_id=source_id,
        source_file=source_file,
        timestamp=timestamp,
        user_id=user_id,
        device_id=device_id,
        event_type=event_type,
        action=mapped.get("action"),
        resource=mapped.get("resource"),
        metadata=mapped.get("metadata") or {},
        raw=raw_payload if isinstance(raw_payload, dict) else {},
    )
    return ingest.model_dump()


class Normalizer:
    """Stateless (per-call) normalizer with shared in-memory stats.

    Designed to be called both:
    - From a periodic background loop (lifespan task) — polls every N seconds.
    - From the admin endpoint `POST /api/admin/run-normalizer` — manual trigger.

    The class is process-safe via a lock (so admin endpoint and background
    loop never trample on each other). The lock is intentionally short-held
    so admin-triggered runs don't block the background loop for long.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats = NormalizerStats()

    def reset_stats(self) -> None:
        """Reset in-memory stats. Used by tests; not for production code."""
        with self._lock:
            self._stats = NormalizerStats()

    @property
    def stats(self) -> NormalizerStats:
        return self._stats

    def get_stats(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of normalizer stats."""
        with self._lock:
            return {
                "total_runs": self._stats.total_runs,
                "total_processed": self._stats.total_processed,
                "total_failed": self._stats.total_failed,
                "total_scoring_calls": self._stats.total_scoring_calls,
                "last_run_at": self._stats.last_run_at,
                "last_duration_ms": round(self._stats.last_duration_ms, 2),
                "last_processed": self._stats.last_processed,
                "last_failed": self._stats.last_failed,
                "last_pending": self._stats.last_pending,
                "last_users_to_score": list(self._stats.last_users_to_score),
                "last_errors": list(self._stats.last_errors[-10:]),
                "uptime_seconds": round(time.time() - self._stats.started_at, 1),
                "enabled": settings.normalizer_enabled,
                "poll_interval_seconds": settings.normalizer_poll_interval_seconds,
                "batch_size": settings.normalizer_batch_size,
            }

    def run_once(
        self, batch_size: int | None = None, on_user_scored: Callable[[str], None] | None = None
    ) -> dict[str, Any]:
        """Process up to `batch_size` pending raw_user_logs.

        `on_user_scored` (optional) is called once per distinct user_id that
        got new event_logs in this run. The caller (background loop or admin
        endpoint) decides whether to enqueue async ML scoring there.
        """
        size = batch_size or settings.normalizer_batch_size
        run_start = time.time()
        started_at = _safe_iso_now()

        processed = 0
        failed = 0
        errors: list[dict[str, Any]] = []
        users_with_new_events: set[str] = set()
        pending_rows: list[dict[str, Any]] = []

        with self._lock:
            self._stats.total_runs += 1
            pending_rows = database.list_pending_raw_logs(limit=size)
            self._stats.last_pending = len(pending_rows)
            for row in pending_rows:
                raw_id = row.get("id")
                try:
                    ingest_payload = normalize_raw_log(row)
                    if ingest_payload is None:
                        failed += 1
                        errors.append(
                            {"raw_log_id": raw_id, "error": "normalization_returned_none"}
                        )
                        continue
                    existing = database.find_event_log_by_source_id(ingest_payload["source_id"])
                    if existing is None:
                        event_log = database.ingest_event(ingest_payload)
                    else:
                        event_log = existing
                    database.mark_raw_log_normalized(raw_id, event_log["id"])
                    processed += 1
                    user_id = event_log.get("user_id")
                    if user_id:
                        users_with_new_events.add(user_id)
                except Exception as exc:
                    logger.exception("normalizer: failed to process raw_log id=%s", raw_id)
                    failed += 1
                    errors.append({"raw_log_id": raw_id, "error": str(exc)})

            duration_ms = (time.time() - run_start) * 1000.0
            self._stats.total_processed += processed
            self._stats.total_failed += failed
            self._stats.total_scoring_calls += len(users_with_new_events)
            self._stats.last_processed = processed
            self._stats.last_failed = failed
            self._stats.last_users_to_score = sorted(users_with_new_events)
            self._stats.last_errors = errors
            self._stats.last_run_at = started_at
            self._stats.last_duration_ms = duration_ms

        if on_user_scored is not None:
            for uid in sorted(users_with_new_events):
                try:
                    on_user_scored(uid)
                except Exception:
                    logger.exception("normalizer: on_user_scored callback failed for %s", uid)

        return {
            "started_at": started_at,
            "duration_ms": round(duration_ms, 2),
            "processed": processed,
            "failed": failed,
            "pending_before": len(pending_rows),
            "users_with_new_events": sorted(users_with_new_events),
            "errors": errors[:10],
        }


# Module-level singleton (used by background loop and admin endpoint).
normalizer = Normalizer()


def get_normalizer() -> Normalizer:
    return normalizer


async def normalizer_loop(stop_event: asyncio.Event) -> None:
    """Long-running background task: poll pending raw logs and normalize them.

    The loop is cancellation-friendly: when `stop_event` is set, the next
    sleep returns immediately and the loop exits cleanly. Errors are caught +
    logged so a transient DB failure does not kill the worker permanently.

    All blocking work (`run_once`, `score_user`) runs in the default thread
    pool via `asyncio.to_thread` so we don't block the FastAPI event loop.
    """
    interval = max(0.5, settings.normalizer_poll_interval_seconds)
    logger.info(
        "normalizer_loop: started (interval=%.1fs, batch=%d, enabled=%s)",
        interval,
        settings.normalizer_batch_size,
        settings.normalizer_enabled,
    )

    async def _enqueue_score(uid: str) -> None:
        from src.backend.app.services import user_scoring

        def _do() -> None:
            try:
                user_scoring.get_user_scoring().score_user(uid)
            except Exception:
                logger.exception("user_scoring.score_user failed for %s", uid)

        await asyncio.to_thread(_do)

    async def _tick() -> None:
        if not settings.normalizer_enabled:
            return
        result = await asyncio.to_thread(normalizer.run_once, None, None)
        if result.get("users_with_new_events"):
            for uid in result["users_with_new_events"]:
                await _enqueue_score(uid)

    if settings.normalizer_run_on_startup:
        try:
            await _tick()
        except Exception:
            logger.exception("normalizer_loop: initial run failed")

    while not stop_event.is_set():
        try:
            await _tick()
        except Exception:
            logger.exception("normalizer_loop: tick failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue
        else:
            break
    logger.info("normalizer_loop: stopped")
