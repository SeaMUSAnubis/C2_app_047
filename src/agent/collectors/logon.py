"""Linux logon collector: reads /var/log/wtmp and emits logon/logoff events.

The binary wtmp file is a series of `struct utmp` records. We poll the file
size and read any new records since the last poll. Each new record becomes
one raw log event (action: 'logon' for USER_PROCESS, 'logoff' for DEAD_PROCESS,
or skipped for system events like BOOT_TIME / RUN_LVL).

Implementation notes:
- We do NOT parse wtmp in real-time via inotify (inotify doesn't fire on
  append-only writes from `login`/`logout` until they close the fd).
- Polling every 5 seconds is sufficient for a demo. Lower intervals waste CPU.
- `last_offset` is persisted in the state file so we don't re-emit old events
  across agent restarts.
- The collector tolerates wtmp rotation: if the file shrinks (rotated), we
  reset offset to 0 and read the new file from the start.
- Reading wtmp requires read permission (typically world-readable via
  /var/log/wtmp mode 0664). If the file is unreadable, the collector marks
  itself unhealthy and continues trying.

Security:
- We only emit the username, line (tty), host (if any), and timestamp. We
  do NOT emit the password or any sensitive data.
- The agent's `device_id` and `user_id` are derived from the system, not
  from wtmp. Use `getpass.getuser()` for the running user.
"""

from __future__ import annotations

import logging
import os
import struct
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.collectors.base import Collector

logger = logging.getLogger(__name__)

# struct utmp on 64-bit Linux (glibc). The struct is 384 bytes with 24 bytes
# of padding between ut_host and exit_status (preserved for backward
# compatibility with 32-bit callers).
# Field layout:
#   short ut_type           (2)
#   pid_t ut_pid            (4)
#   char ut_line[32]        (32)
#   char ut_id[4]           (4)
#   char ut_user[32]        (32)
#   char ut_host[256]       (256)
#   <padding>               (24)
#   short e_termination     (2)  - part of struct exit_status
#   short e_exit            (2)
#   <padding>               (2)  - to align ut_session
#   long ut_session         (8)
#   long ut_tv_sec          (8)
#   long ut_tv_usec         (8)
WTMP_RECORD_SIZE = 384
WTMP_FORMAT = "hi32s4s32s256s20xhh2xqqq"
WTMP_TYPES = {
    0: "EMPTY",
    1: "RUN_LVL",
    2: "BOOT_TIME",
    3: "NEW_TIME",
    4: "OLD_TIME",
    5: "INIT_PROCESS",
    6: "LOGIN_PROCESS",
    7: "USER_PROCESS",
    8: "DEAD_PROCESS",
    9: "ACCOUNTING",
}


def _decode(b: bytes) -> str:
    return b.decode("utf-8", errors="replace").rstrip("\x00")


class LinuxLogonCollector(Collector):
    name = "logon"

    def __init__(
        self,
        config_client: Any,
        wtmp_path: Path = Path("/var/log/wtmp"),
        poll_interval: float = 5.0,
    ):
        super().__init__(config_client)
        self._wtmp_path = Path(wtmp_path)
        self._poll_interval = poll_interval
        self._offset = 0
        self._last_inode: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._hostname = ""

    def start(self) -> None:
        if self._thread is not None:
            return
        if not self._wtmp_path.is_file():
            self.mark_unhealthy(f"wtmp not found: {self._wtmp_path}")
            return
        self._hostname = os.uname().nodename
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="logon-collector", daemon=True
        )
        self._thread.start()
        logger.info("LinuxLogonCollector started (wtmp=%s)", self._wtmp_path)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def set_offset(self, offset: int) -> None:
        """Called by the service to restore offset across restarts."""
        if offset >= 0:
            self._offset = offset

    def get_offset(self) -> int:
        return self._offset

    def _run(self) -> None:
        consecutive_errors = 0
        while not self._stop.is_set():
            try:
                n = self._scan_once()
                if n:
                    logger.debug("Emitted %d logon/logoff events", n)
                self.mark_healthy()
                consecutive_errors = 0
            except OSError as exc:
                self.mark_unhealthy(f"wtmp read error: {exc}")
                consecutive_errors += 1
            except Exception as exc:  # noqa: BLE001
                self.mark_unhealthy(f"unexpected error: {exc}")
                consecutive_errors += 1
            # Exponential backoff on persistent errors (cap at 60s).
            wait = self._poll_interval
            if consecutive_errors > 0:
                wait = min(60.0, self._poll_interval * (2 ** min(consecutive_errors, 4)))
            self._stop.wait(wait)

    def _scan_once(self) -> int:
        """Read any new wtmp records. Returns count emitted."""
        try:
            stat = self._wtmp_path.stat()
        except OSError as exc:
            raise OSError(f"stat wtmp: {exc}") from exc
        current_size = stat.st_size
        current_inode = stat.st_ino

        # Handle rotation: detect either by size shrink or inode change.
        if self._last_inode is not None and current_inode != self._last_inode:
            logger.info(
                "wtmp rotated (inode %d -> %d), resetting offset",
                self._last_inode, current_inode,
            )
            self._offset = 0
        elif current_size < self._offset:
            logger.info("wtmp shrank (size %d < offset %d), resetting",
                        current_size, self._offset)
            self._offset = 0
        self._last_inode = current_inode

        if current_size <= self._offset:
            return 0

        emitted = 0
        with self._wtmp_path.open("rb") as f:
            f.seek(self._offset)
            chunk_size = WTMP_RECORD_SIZE * 64
            while True:
                buf = f.read(chunk_size)
                if not buf:
                    break
                # Process whole records only; ignore trailing partial record.
                usable = (len(buf) // WTMP_RECORD_SIZE) * WTMP_RECORD_SIZE
                for i in range(0, usable, WTMP_RECORD_SIZE):
                    rec = buf[i:i + WTMP_RECORD_SIZE]
                    rec_offset = self._offset + i
                    if self._emit_record(rec, rec_offset):
                        emitted += 1
                self._offset += usable
                if len(buf) < chunk_size:
                    break
        return emitted

    def _emit_record(self, rec: bytes, rec_offset: int = 0) -> bool:
        try:
            (ut_type, ut_pid, ut_line, ut_id, ut_user, ut_host,
             _e_term, _e_exit, _ut_session, tv_sec, _tv_usec) = struct.unpack(
                WTMP_FORMAT, rec
            )
        except struct.error:
            return False
        type_name = WTMP_TYPES.get(ut_type, f"TYPE_{ut_type}")
        line = _decode(ut_line)
        user = _decode(ut_user)
        host = _decode(ut_host)
        # We emit only USER_PROCESS (logon) and DEAD_PROCESS (logoff).
        if ut_type == 7:  # USER_PROCESS
            action = "logon"
        elif ut_type == 8:  # DEAD_PROCESS
            action = "logoff"
        else:
            return False
        if not user or user == "LOGIN" or user == "reboot":
            return False
        try:
            timestamp = datetime.fromtimestamp(tv_sec, UTC).isoformat()
        except (OSError, ValueError, OverflowError):
            timestamp = datetime.now(UTC).isoformat()
        # Compose a stable source_id: wtmp inode + record byte offset.
        # The caller passes rec_offset, so each record gets a unique source_id.
        # The inode changes when the file is rotated, producing fresh source_ids.
        try:
            inode = self._wtmp_path.stat().st_ino
        except OSError:
            inode = 0
        source_id = f"agent:{self._hostname}:wtmp:{inode}:{rec_offset}"
        return self.emit(
            source_id=source_id,
            event_type="logon",
            timestamp=timestamp,
            raw_payload={
                "action": action,
                "username": user,
                "line": line,
                "host": host,
                "pid": int(ut_pid),
                "wtmp_type": type_name,
            },
            user_id=user,
            device_id=self._hostname,
            action=action,
            resource=line,
            metadata={"source": "wtmp", "wtmp_inode": int(inode)},
        )


# ---------------------------------------------------------------------------
# Windows stub: not implemented in Phase 2. Use WMI or `pywin32` later.
# ---------------------------------------------------------------------------


class WindowsLogonCollector(Collector):
    name = "logon"

    def __init__(self, config_client: Any):
        super().__init__(config_client)
        self.mark_unhealthy("Windows logon collector not yet implemented")

    def start(self) -> None:  # noqa: D401
        return

    def stop(self) -> None:  # noqa: D401
        return
