"""Network connection collector.

Linux implementation: poll `/proc/net/tcp` and `/proc/net/udp` for new
established connections, emit a `network` event for each new (local,
remote) tuple. We track the previous state so we only fire on new
connections, not on every poll.

Limitations:
- We only see connections, not packets. Polling every 5s is sufficient for
  most UEBA scenarios (a connection that opens and closes in <5s is rare).
- We do not capture payload; only metadata (local, remote, state).
- Listening sockets are not emitted (state == 0A in /proc/net/tcp).

Windows: stub. Real impl would use ETW `Microsoft-Windows-Kernel-Network`
or WFP.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.collectors.base import Collector

logger = logging.getLogger(__name__)


# /proc/net/tcp state field values. ESTABLISHED = 01.
ESTABLISHED_STATE = "01"


def _parse_addr(hex_addr: str) -> tuple[str, int]:
    """Convert /proc/net/{tcp,udp} hex addr:port to (ip, port)."""
    if not hex_addr or ":" not in hex_addr:
        return "0.0.0.0", 0
    ip_hex, port_hex = hex_addr.split(":", 1)
    # IPv4 in hex is little-endian (each byte reversed).
    try:
        ip_bytes = bytes.fromhex(ip_hex)
        ip = ".".join(str(b) for b in reversed(ip_bytes))
    except ValueError:
        ip = "0.0.0.0"
    try:
        port = int(port_hex, 16)
    except ValueError:
        port = 0
    return ip, port


def _read_proc_net(filename: str) -> set[tuple[str, int, str, int]]:
    """Return set of (local_ip, local_port, remote_ip, remote_port) tuples
    in ESTABLISHED state from /proc/net/<filename."""
    path = Path("/proc/net") / filename
    if not path.is_file():
        return set()
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return set()
    out: set[tuple[str, int, str, int]] = set()
    for line in lines[1:]:  # skip header
        parts = line.split()
        if len(parts) < 4:
            continue
        if parts[3] != ESTABLISHED_STATE:
            continue
        local_ip, local_port = _parse_addr(parts[1])
        remote_ip, remote_port = _parse_addr(parts[2])
        # Skip empty remotes (shouldn't happen for ESTABLISHED).
        if remote_ip == "0.0.0.0" and remote_port == 0:
            continue
        out.add((local_ip, local_port, remote_ip, remote_port))
    return out


def _read_proc_net_all() -> set[tuple[str, int, str, int]]:
    """Read both /proc/net/tcp (IPv4) and /proc/net/tcp6 (IPv6) ESTABLISHED."""
    out = _read_proc_net("tcp")
    out |= _read_proc_net("tcp6")
    return out


class LinuxNetworkCollector(Collector):
    """Poll /proc/net/tcp for new connections; emit network events."""

    name = "network"

    def __init__(self, config_client: Any, poll_interval: float = 5.0):
        super().__init__(config_client)
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._prev: set[tuple[str, int, str, int]] = set()

    def start(self) -> None:
        if self._thread is not None:
            return
        if not Path("/proc/net").is_dir():
            self.mark_unhealthy("/proc/net not available")
            return
        self._stop.clear()
        # Seed with current connections (do not emit on startup).
        self._prev = _read_proc_net_all()
        self._thread = threading.Thread(
            target=self._run, name="network-collector", daemon=True
        )
        self._thread.start()
        logger.info("LinuxNetworkCollector started (poll=%.1fs)", self._poll_interval)

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
        current = _read_proc_net_all()
        new_conns = current - self._prev
        for local_ip, local_port, remote_ip, remote_port in sorted(new_conns):
            self._emit(local_ip, local_port, remote_ip, remote_port)
        self._prev = current

    def _emit(self, local_ip: str, local_port: int, remote_ip: str, remote_port: int) -> None:
        source_id = (
            f"network:{local_ip}:{local_port}:{remote_ip}:{remote_port}:"
            f"{int(datetime.now(UTC).timestamp() * 1000)}"
        )
        self.emit(
            source_id=source_id,
            event_type="network",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload={
                "activity": "connection",
                "src_ip": local_ip,
                "src_port": local_port,
                "dst_ip": remote_ip,
                "dst_port": remote_port,
                "protocol": "tcp",
            },
            action="connection",
            resource=f"{remote_ip}:{remote_port}",
        )


class ProgrammaticNetworkCollector(Collector):
    """Cross-platform collector that only supports programmatic connection events."""

    name = "network"

    def __init__(self, config_client: Any):
        super().__init__(config_client)

    def start(self) -> None:
        self.mark_healthy()
        logger.info("ProgrammaticNetworkCollector started (no polling)")

    def stop(self) -> None:
        return None

    def record_connection(
        self,
        local_ip: str,
        local_port: int,
        remote_ip: str,
        remote_port: int,
        protocol: str = "tcp",
    ) -> None:
        source_id = (
            f"network:api:{local_ip}:{local_port}:{remote_ip}:{remote_port}:"
            f"{int(datetime.now(UTC).timestamp() * 1000)}"
        )
        self.emit(
            source_id=source_id,
            event_type="network",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload={
                "activity": "connection",
                "src_ip": local_ip,
                "src_port": local_port,
                "dst_ip": remote_ip,
                "dst_port": remote_port,
                "protocol": protocol,
                "source": "auditd_or_etw",
            },
            action="connection",
            resource=f"{remote_ip}:{remote_port}",
        )


class WindowsNetworkCollector(Collector):
    """Windows stub. Real impl would consume ETW Kernel-Network events."""

    name = "network"

    def __init__(self, config_client: Any):
        super().__init__(config_client)

    def start(self) -> None:
        self.mark_unhealthy("network collector not implemented on Windows")

    def stop(self) -> None:
        return None
