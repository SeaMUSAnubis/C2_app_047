"""Email collector.

Email monitoring is fundamentally different from device/file/network
collection: there is no clean OS-level hook on either Windows (MAPI/Exchange)
or Linux (Thunderbird/IMAP). So this collector is mostly programmatic:

1. `record_email(op, from_, to, subject, size, attachments)` — call this from
   - A Thunderbird / Outlook add-on (highest fidelity; we have full content
     metadata, can redact + hash body before sending)
   - An IMAP IDLE poller (see `IMAPPoller` below; lower fidelity, works for
     any IMAP server)
   - A custom SMTP proxy on the mail server (best for enterprise)

2. `IMAPPoller` (Linux, optional) — connects to an IMAP server with IDLE
   support, watches the INBOX, emits events for new arrivals. Requires
   `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD` env vars OR a `mail_watch_config`
   in the agent config. NOT enabled by default; opt-in via policy.

Events emitted: `event_type="email"`, `action` in {email_send, email_read,
email_forward, email_delete}. `resource` = recipient (or sender for reads).
Email BODY is NEVER sent — only size, attachment count, subject hash, etc.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import UTC, datetime
from typing import Any

from agent.collectors.base import Collector

logger = logging.getLogger(__name__)


_VALID_OPS = {"email_send", "email_read", "email_forward", "email_delete"}


def _redact_subject(subject: str | None) -> str | None:
    """Hash the subject so we get a stable identifier without leaking content."""
    if not subject:
        return None
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]


class EmailCollector(Collector):
    """Programmatic email collector. The integration layer calls
    `record_email(...)` to feed events.

    Thread-safe: callers can fire-and-forget from any thread.
    """

    name = "email"

    def __init__(self, config_client: Any):
        super().__init__(config_client)
        self._lock = threading.Lock()
        self._emitted: int = 0

    def start(self) -> None:
        self.mark_healthy()
        logger.info("EmailCollector started (programmatic mode)")

    def stop(self) -> None:
        return None

    def record_email(
        self,
        op: str,
        from_: str | None = None,
        to: str | None = None,
        subject: str | None = None,
        size: int | None = None,
        attachments: int | None = None,
        user: str | None = None,
    ) -> None:
        """Emit an email event. The body is NEVER sent.

        `op` must be one of: email_send, email_read, email_forward,
        email_delete. Other values are clamped to email_send.
        `subject` is hashed (sha256[:16]) for privacy.
        `size` and `attachments` are optional metadata.
        `user` overrides the agent's running user for this event (used by
        multi-account setups where each user has their own mail client).
        """
        if op not in _VALID_OPS:
            op = "email_send"
        # For sends/forwards/deletes the "other party" is the recipient; for
        # reads the other party is the sender.
        if op in ("email_read",):
            resource = from_ or to or "unknown"
        else:
            resource = to or from_ or "unknown"
        raw_payload: dict[str, Any] = {
            "activity": op,
            "from": from_,
            "to": to,
            "subject_hash": _redact_subject(subject),
        }
        if size is not None:
            raw_payload["size"] = size
        if attachments is not None:
            raw_payload["attachments"] = attachments
        metadata: dict[str, Any] = {"source": "email_api"}
        if user:
            metadata["user_override"] = user
        source_id = f"email:{op}:{resource}:{int(datetime.now(UTC).timestamp() * 1000)}"
        with self._lock:
            self._emitted += 1
        self.emit(
            source_id=source_id,
            event_type="email",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload=raw_payload,
            action=op,
            resource=resource,
            metadata=metadata,
        )

    @property
    def emitted_count(self) -> int:
        with self._lock:
            return self._emitted


class IMAPPollerEmailCollector(Collector):
    """Optional IMAP IDLE poller. Disabled by default.

    Activated by setting `IMAP_HOST` (and `IMAP_USER` + `IMAP_PASSWORD` or
    `IMAP_PASSWORD_FILE`) in the agent's environment. The collector
    connects, selects the INBOX, subscribes to IDLE, and emits an
    `email_read` event for every new message arrival.

    The poller is intentionally minimal: it only signals "new mail arrived"
    and the size on disk; full body parsing is left to a downstream IMAP
    filter. The agent's job is to flag the activity, not to inspect the
    content.
    """

    name = "email"

    def __init__(
        self,
        config_client: Any,
        imap_host: str | None = None,
        imap_port: int = 993,
        imap_user: str | None = None,
        imap_password: str | None = None,
        poll_interval: float = 30.0,
    ):
        super().__init__(config_client)
        self._imap_host = imap_host
        self._imap_port = imap_port
        self._imap_user = imap_user
        self._imap_password = imap_password
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_uid: int = 0
        self._connected = False

    def start(self) -> None:
        if self._thread is not None:
            return
        if not (self._imap_host and self._imap_user and self._imap_password):
            self.mark_unhealthy("IMAPPoller requires host/user/password")
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="email-imap-collector", daemon=True
        )
        self._thread.start()
        logger.info("IMAPPollerEmailCollector started (host=%s)", self._imap_host)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run(self) -> None:
        consecutive_errors = 0
        while not self._stop.is_set():
            try:
                self._poll_once()
                self.mark_healthy()
                consecutive_errors = 0
            except Exception as exc:  # noqa: BLE001
                self.mark_unhealthy(f"IMAP poll error: {exc}")
                consecutive_errors += 1
            wait = self._poll_interval * (2 ** min(consecutive_errors, 4))
            wait = min(wait, 300.0)
            self._stop.wait(wait)

    def _poll_once(self) -> None:
        """One-shot IMAP IDLE-style poll. Uses imaplib if available; otherwise
        the collector just reports the connection state without fetching.
        """
        try:
            import imaplib  # noqa: F401  (stdlib, always available)
        except ImportError:  # pragma: no cover
            self.mark_unhealthy("imaplib not available")
            return
        # The poll logic here is deliberately conservative: connect, list the
        # latest UID, and emit an event if it changed. A real deployment would
        # use IMAP IDLE (server push) for sub-second latency, but that requires
        # a long-lived socket — kept simple here.
        import imaplib as _imaplib

        with _imaplib.IMAP4_SSL(self._imap_host, self._imap_port) as imap:
            imap.login(self._imap_user, self._imap_password)
            imap.select("INBOX", readonly=True)
            typ, data = imap.uid("SEARCH", None, "ALL")
            if typ != "OK" or not data or not data[0]:
                return
            uids = [int(u) for u in data[0].split() if u.strip().isdigit()]
            if not uids:
                return
            latest = max(uids)
            if latest > self._last_uid:
                if self._last_uid > 0:
                    # New mail arrived since last poll.
                    for uid in range(self._last_uid + 1, latest + 1):
                        typ2, msg_data = imap.uid("FETCH", str(uid), "(RFC822.SIZE)")
                        size = None
                        if typ2 == "OK" and msg_data and msg_data[0]:
                            meta = msg_data[0]
                            # imaplib returns meta as a tuple (literal, body).
                            # The literal (meta[0]) holds the metadata string
                            # like b'1 (RFC822.SIZE 1234 RFC822.HEADER ...)'.
                            # We search recursively in any bytes/str parts.
                            def _search_size(obj: Any) -> int | None:
                                if isinstance(obj, bytes | str):
                                    text = obj.decode("utf-8", errors="replace") if isinstance(obj, bytes) else obj
                                    if "RFC822.SIZE" in text:
                                        try:
                                            return int(text.split("RFC822.SIZE")[1].split()[0].rstrip(")"))
                                        except (ValueError, IndexError):
                                            return None
                                elif isinstance(obj, tuple | list):
                                    for item in obj:
                                        s = _search_size(item)
                                        if s is not None:
                                            return s
                                return None
                            size = _search_size(meta)
                        self._emit_read_event(size)
                self._last_uid = latest
                self._connected = True

    def _emit_read_event(self, size: int | None) -> None:
        """Emit a single email_read event for a new IMAP message."""
        from datetime import UTC, datetime

        source_id = f"email:imap:{int(datetime.now(UTC).timestamp() * 1000)}"
        raw_payload: dict[str, Any] = {
            "activity": "email_read",
            "from": None,
            "to": self._imap_user,
            "source": "imap_poller",
        }
        if size is not None:
            raw_payload["size"] = size
        self.emit(
            source_id=source_id,
            event_type="email",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload=raw_payload,
            action="email_read",
            resource=self._imap_user or "unknown",
            metadata={"source": "imap_poller"},
        )
