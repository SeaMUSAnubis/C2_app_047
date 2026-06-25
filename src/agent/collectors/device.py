"""Device (USB) collector.

Linux implementation: periodically invoke `lsusb` and diff the output against
the previous snapshot. New device entries → emit `device` event with
action=connect. Entries that disappeared → action=disconnect.

Windows implementation: stub (would require WMI / `win32com` or ETW to
implement; not in scope for Phase 4 demo). Marked unhealthy on start.

The collector's `name` attribute (`"device"`) is what the policy uses to
enable/disable it via `enabled_collectors`.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from datetime import UTC, datetime
from typing import Any

from agent.collectors.base import Collector

logger = logging.getLogger(__name__)


def _run_lsusb() -> list[dict[str, str]]:
    """Return a snapshot of USB devices as a list of {bus, device, id, desc}.

    Empty list if `lsusb` is not installed or fails. The id is the canonical
    `vendor:product` hex pair (e.g. "0781:5571"); the desc is the human
    description (e.g. "SanDisk Corp. Cruzer Blade").
    """
    binary = shutil.which("lsusb")
    if not binary:
        return []
    try:
        proc = subprocess.run(  # noqa: S603 — input is constant
            [binary],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("lsusb execution failed: %s", exc)
        return []
    if proc.returncode != 0:
        return []
    devices: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        # Format: "Bus 001 Device 004: ID 0781:5571 SanDisk Corp. Cruzer Blade"
        # The "ID" token is always preceded by ": " (the end of "Device NNN:").
        # This avoids false positives from lines that happen to contain the
        # word "ID" elsewhere (e.g. "without ID field" in help text).
        if ": ID " not in line:
            continue
        try:
            prefix, rest = line.split(": ID ", 1)
            parts = prefix.strip().split()
            bus = parts[1] if len(parts) >= 2 else "?"
            device = parts[3].rstrip(":") if len(parts) >= 4 else "?"
            id_and_desc = rest.strip().split(maxsplit=1)
            usb_id = id_and_desc[0]
            desc = id_and_desc[1] if len(id_and_desc) > 1 else ""
            devices.append({"bus": bus, "device": device, "id": usb_id, "desc": desc})
        except (ValueError, IndexError):
            continue
    return devices


class LinuxDeviceCollector(Collector):
    """Poll `lsusb` and emit connect/disconnect events."""

    name = "device"

    def __init__(self, config_client: Any, poll_interval: float = 10.0):
        super().__init__(config_client)
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._prev: dict[str, dict[str, str]] = {}

    def start(self) -> None:
        if self._thread is not None:
            return
        if shutil.which("lsusb") is None:
            self.mark_unhealthy("lsusb not installed")
            return
        self._stop.clear()
        # Seed with the initial state so we don't emit events for devices
        # that were already connected when the agent started.
        self._prev = {d["id"]: d for d in _run_lsusb()}
        self._thread = threading.Thread(
            target=self._run, name="device-collector", daemon=True
        )
        self._thread.start()
        logger.info("LinuxDeviceCollector started (poll=%.1fs)", self._poll_interval)

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
        current = {d["id"]: d for d in _run_lsusb()}
        # New devices = in current but not prev.
        for usb_id, dev in current.items():
            if usb_id not in self._prev:
                self._emit(usb_id, "connect", dev)
        # Removed devices = in prev but not current.
        for usb_id, dev in self._prev.items():
            if usb_id not in current:
                self._emit(usb_id, "disconnect", dev)
        self._prev = current

    def _emit(self, usb_id: str, action: str, dev: dict[str, str]) -> None:
        source_id = f"device:{usb_id}:{action}:{int(datetime.now(UTC).timestamp() * 1000)}"
        self.emit(
            source_id=source_id,
            event_type="device",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload={
                "activity": "Connect" if action == "connect" else "Disconnect",
                "usb_id": usb_id,
                "bus": dev.get("bus"),
                "device": dev.get("device"),
                "product": dev.get("desc"),
            },
            action=action,
            resource=dev.get("desc") or usb_id,
        )


class WindowsDeviceCollector(Collector):
    """Windows stub. Real impl would use WMI Win32_USBHub events."""

    name = "device"

    def __init__(self, config_client: Any):
        super().__init__(config_client)

    def start(self) -> None:
        self.mark_unhealthy("device collector not implemented on Windows")

    def stop(self) -> None:
        return None
