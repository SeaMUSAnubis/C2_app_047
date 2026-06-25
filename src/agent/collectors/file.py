"""File access collector.

Two operating modes:

1. **Polling mode** (Linux): every `poll_interval` seconds, walk a configured
   directory (default `/tmp`), record file metadata (size, mtime) into an
   in-memory dict, and emit events for newly-seen or modified files.

2. **Programmatic mode** (cross-platform): other components (auditd hooks,
   file-system watchers, test code) call `record_access(path, op, user)`
   directly. The collector buffers calls and emits one event per call.

Windows: stub. A real impl would use ReadDirectoryChangesW or the
`4663` Security Event Log channel; both need pywin32 or `evtx` parsing.

Events emitted have `event_type="file"`, `action` in
{file_access, file_copy, file_write, file_delete}, and `resource` = file path.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.collectors.base import Collector

logger = logging.getLogger(__name__)


class LinuxFileCollector(Collector):
    """Poll a directory for new/modified files and emit events.

    The `watch_path` argument defaults to `/tmp` (where sensitive data
    exfiltration often lands in CERT r4.2 scenarios). In production this
    should be configured by the admin via policy, not hard-coded.
    """

    name = "file"

    def __init__(
        self,
        config_client: Any,
        watch_path: str | Path = "/tmp",
        poll_interval: float = 10.0,
        max_depth: int = 2,
    ):
        super().__init__(config_client)
        self._watch_path = Path(watch_path)
        self._poll_interval = poll_interval
        self._max_depth = max_depth
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot: dict[str, tuple[int, float]] = {}

    def start(self) -> None:
        if self._thread is not None:
            return
        if not self._watch_path.is_dir():
            self.mark_unhealthy(f"watch path not a directory: {self._watch_path}")
            return
        self._stop.clear()
        # Seed the snapshot.
        self._snapshot = self._scan_files()
        self._thread = threading.Thread(
            target=self._run, name="file-collector", daemon=True
        )
        self._thread.start()
        logger.info(
            "LinuxFileCollector started (watch=%s, poll=%.1fs, files_seen=%d)",
            self._watch_path, self._poll_interval, len(self._snapshot),
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._scan_once()
                self.mark_healthy()
            except Exception as exc:  # noqa: BLE001
                self.mark_unhealthy(f"scan error: {exc}")
            self._stop.wait(self._poll_interval)

    def _scan_files(self) -> dict[str, tuple[int, float]]:
        out: dict[str, tuple[int, float]] = {}
        if not self._watch_path.is_dir():
            return out
        try:
            for root, dirs, files in os.walk(self._watch_path):
                depth = str(root).count(os.sep) - str(self._watch_path).count(os.sep)
                if depth >= self._max_depth:
                    dirs[:] = []
                    continue
                for name in files:
                    p = Path(root) / name
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    out[str(p)] = (st.st_size, st.st_mtime)
        except OSError as exc:
            logger.warning("File scan error on %s: %s", self._watch_path, exc)
        return out

    def _scan_once(self) -> None:
        current = self._scan_files()
        # New files.
        for path, (size, mtime) in current.items():
            if path not in self._snapshot:
                self._emit_file_event(path, "file_write", size=size, mtime=mtime)
                continue
            old_size, old_mtime = self._snapshot[path]
            if mtime != old_mtime or size != old_size:
                self._emit_file_event(path, "file_write", size=size, mtime=mtime)
        # Deleted files.
        for path in self._snapshot:
            if path not in current:
                self._emit_file_event(path, "file_delete")
        self._snapshot = current

    def _emit_file_event(
        self, path: str, action: str, size: int | None = None, mtime: float | None = None
    ) -> None:
        source_id = f"file:{path}:{action}:{int(datetime.now(UTC).timestamp() * 1000)}"
        raw_payload: dict[str, Any] = {"activity": action, "path": path}
        if size is not None:
            raw_payload["size"] = size
        if mtime is not None:
            raw_payload["mtime"] = mtime
        self.emit(
            source_id=source_id,
            event_type="file",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload=raw_payload,
            action=action,
            resource=path,
        )

    def record_access(self, path: str, op: str = "file_access", user: str | None = None) -> None:
        """Programmatic API for integration with auditd hooks / test code.

        Emits an event with `op` as the action. If `user` is given, it is
        included in `ingest_metadata` (the agent's own user_id is the default).
        """
        path = str(path)
        metadata: dict[str, Any] = {}
        if user:
            metadata["user_override"] = user
        self.emit(
            source_id=f"file:api:{path}:{op}:{int(datetime.now(UTC).timestamp() * 1000)}",
            event_type="file",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload={"activity": op, "path": path, "source": "auditd_hook"},
            action=op,
            resource=path,
            metadata=metadata,
        )


class ProgrammaticFileCollector(Collector):
    """Cross-platform collector that only supports the programmatic API.

    Useful when you don't want a polling collector (e.g. when auditd is
    forwarding events to a Unix socket that another component reads from,
    or in tests).
    """

    name = "file"

    def __init__(self, config_client: Any):
        super().__init__(config_client)
        self._handler: Callable[[str, str], None] | None = None

    def start(self) -> None:
        self.mark_healthy()
        logger.info("ProgrammaticFileCollector started (no polling)")

    def stop(self) -> None:
        return None

    def set_handler(self, handler: Callable[[str, str], None]) -> None:
        """Receive (path, op) callbacks for every programmatic record_access call."""
        self._handler = handler

    def record_access(self, path: str, op: str = "file_access", user: str | None = None) -> None:
        metadata: dict[str, Any] = {}
        if user:
            metadata["user_override"] = user
        self.emit(
            source_id=f"file:api:{path}:{op}:{int(datetime.now(UTC).timestamp() * 1000)}",
            event_type="file",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload={"activity": op, "path": path, "source": "auditd_hook"},
            action=op,
            resource=path,
            metadata=metadata,
        )
        if self._handler:
            try:
                self._handler(path, op)
            except Exception:  # noqa: BLE001
                logger.exception("File handler raised")


class WindowsFileCollector(Collector):
    """Windows stub. Real impl would consume 4663 Security Event Log."""

    name = "file"

    def __init__(self, config_client: Any):
        super().__init__(config_client)

    def start(self) -> None:
        self.mark_unhealthy("file collector not implemented on Windows")

    def stop(self) -> None:
        return None
