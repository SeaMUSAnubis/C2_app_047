"""Process spawn collector.

Linux implementation: every `poll_interval` seconds, walk `/proc` to get the
list of running PIDs, compare to the previous snapshot, and emit a `process`
event for each new PID. We read `/proc/<pid>/comm` (process name) and
`/proc/<pid>/cmdline` (full command line) for context.

Limitations:
- Polling is coarse (a process that starts and exits between two polls is
  missed). For higher fidelity, use a real audit/exec tracer (auditd, eBPF).
- We do not emit events for the kthreadd / kworker / systemd / sshd / etc.
  long-lived daemons because we seed the snapshot at start.
- The collector requires read access to /proc (which is world-readable by
  default on most Linux distros).

Windows: stub. Real impl would use Event 4688 (with auditing enabled) or
ETW `Microsoft-Windows-Kernel-Process`.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.collectors.base import Collector

logger = logging.getLogger(__name__)


def _read_proc(pid: int) -> dict[str, str] | None:
    """Read /proc/<pid>/comm and /proc/<pid>/cmdline. Returns None if gone."""
    try:
        comm = (Path("/proc") / str(pid) / "comm").read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, FileNotFoundError):
        return None
    try:
        cmdline = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\x00", b" ").decode(
            "utf-8", errors="replace"
        ).strip()
    except (OSError, FileNotFoundError):
        cmdline = ""
    return {"comm": comm, "cmdline": cmdline}


def _list_pids() -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    proc = Path("/proc")
    if not proc.is_dir():
        return out
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        info = _read_proc(pid)
        if info is None:
            continue
        out[pid] = info
    return out


class LinuxProcessCollector(Collector):
    """Poll /proc for new processes; emit `process` event for each new PID."""

    name = "process"

    def __init__(self, config_client: Any, poll_interval: float = 5.0):
        super().__init__(config_client)
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._prev: dict[int, dict[str, str]] = {}

    def start(self) -> None:
        if self._thread is not None:
            return
        if not Path("/proc").is_dir():
            self.mark_unhealthy("/proc not mounted")
            return
        self._stop.clear()
        # Seed with the current PID set so we don't fire on every daemon
        # already running at startup.
        self._prev = _list_pids()
        self._thread = threading.Thread(
            target=self._run, name="process-collector", daemon=True
        )
        self._thread.start()
        logger.info("LinuxProcessCollector started (poll=%.1fs)", self._poll_interval)

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

    def _scan_once(self) -> None:
        current = _list_pids()
        for pid, info in current.items():
            if pid in self._prev:
                continue
            self._emit(pid, info)
        # We track PIDs that exit too, but only if they appeared AFTER startup
        # (i.e. were ever "new"). This prevents unbounded growth of prev.
        self._prev = {pid: info for pid, info in current.items() if pid in self._prev or pid in current}

    def _emit(self, pid: int, info: dict[str, str]) -> None:
        comm = info.get("comm", "")
        cmdline = info.get("cmdline", "")
        source_id = f"process:{pid}:{int(datetime.now(UTC).timestamp() * 1000)}"
        self.emit(
            source_id=source_id,
            event_type="process",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload={
                "activity": "spawn",
                "pid": pid,
                "process_name": comm,
                "cmdline": cmdline,
            },
            action="spawn",
            resource=comm or cmdline or f"pid:{pid}",
            metadata={"pid": pid},
        )


class ProgrammaticProcessCollector(Collector):
    """Cross-platform collector that only supports programmatic process events.

    Useful when auditd/execve-tracer is feeding events to a separate channel
    and you want to forward them via this agent.
    """

    name = "process"

    def __init__(self, config_client: Any):
        super().__init__(config_client)

    def start(self) -> None:
        self.mark_healthy()
        logger.info("ProgrammaticProcessCollector started (no polling)")

    def stop(self) -> None:
        return None

    def record_spawn(
        self,
        pid: int,
        process_name: str,
        cmdline: str = "",
        user: str | None = None,
    ) -> None:
        source_id = f"process:api:{pid}:{int(datetime.now(UTC).timestamp() * 1000)}"
        metadata: dict[str, Any] = {"pid": pid}
        if user:
            metadata["user_override"] = user
        self.emit(
            source_id=source_id,
            event_type="process",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload={
                "activity": "spawn",
                "pid": pid,
                "process_name": process_name,
                "cmdline": cmdline,
                "source": "exec_audit",
            },
            action="spawn",
            resource=process_name or f"pid:{pid}",
            metadata=metadata,
        )


class WindowsProcessCollector(Collector):
    """Windows stub. Real impl would consume 4688 Security Event Log."""

    name = "process"

    def __init__(self, config_client: Any):
        super().__init__(config_client)

    def start(self) -> None:
        self.mark_unhealthy("process collector not implemented on Windows")

    def stop(self) -> None:
        return None
