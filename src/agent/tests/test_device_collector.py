"""Tests for the device (USB) collector."""

from __future__ import annotations

from unittest.mock import patch

from agent.collectors.device import (
    LinuxDeviceCollector,
    WindowsDeviceCollector,
    _run_lsusb,
)
from agent.config_client import AgentPolicy, ConfigClient


def _make_config_client(policy: AgentPolicy) -> ConfigClient:
    from unittest.mock import MagicMock

    transport = MagicMock()
    cc = ConfigClient(transport, pull_interval=60)
    cc._policy = policy  # type: ignore[attr-defined]
    return cc


def _make_policy(enabled: list[str]) -> AgentPolicy:
    return AgentPolicy(
        policy_version=1, sampling_rate=100,
        enabled_collectors=enabled, blocklist=[],
    )


def _sink(events: list[tuple[str, dict]]):
    def _fn(source_id: str, payload: dict) -> bool:
        events.append((source_id, payload))
        return True
    return _fn


def test_run_lsusb_parses_valid_output() -> None:
    sample = (
        "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub\n"
        "Bus 001 Device 004: ID 0781:5571 SanDisk Corp. Cruzer Blade\n"
        "Bus 002 Device 002: ID 8087:0024 Intel Corp. Integrated Rate Matching Hub\n"
    )
    with patch("shutil.which", return_value="/usr/bin/lsusb"):
        with patch("subprocess.run") as run:
            run.return_value.stdout = sample
            run.return_value.returncode = 0
            devices = _run_lsusb()
    assert len(devices) == 3
    assert devices[1]["id"] == "0781:5571"
    assert devices[1]["desc"] == "SanDisk Corp. Cruzer Blade"
    assert devices[0]["bus"] == "001"
    assert devices[0]["device"] == "001"


def test_run_lsusb_handles_missing_binary() -> None:
    with patch("shutil.which", return_value=None):
        assert _run_lsusb() == []


def test_run_lsusb_handles_nonzero_returncode() -> None:
    with patch("shutil.which", return_value="/usr/bin/lsusb"):
        with patch("subprocess.run") as run:
            run.return_value.stdout = ""
            run.return_value.returncode = 1
            assert _run_lsusb() == []


def test_run_lsusb_handles_timeout() -> None:
    import subprocess

    with patch("shutil.which", return_value="/usr/bin/lsusb"):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("lsusb", 5)):
            assert _run_lsusb() == []


def test_run_lsusb_skips_malformed_lines() -> None:
    sample = "garbage line without ID field\nBus 001 Device 001: ID 1d6b:0002 root hub\n"
    with patch("shutil.which", return_value="/usr/bin/lsusb"):
        with patch("subprocess.run") as run:
            run.return_value.stdout = sample
            run.return_value.returncode = 0
            devices = _run_lsusb()
    assert len(devices) == 1


def test_linux_device_collector_emits_connect_on_new_device() -> None:
    policy = _make_policy(["device"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []

    def fake_run() -> list[dict[str, str]]:
        return [{"id": "0781:5571", "bus": "001", "device": "004", "desc": "SanDisk"}]

    collector = LinuxDeviceCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    with patch.object(LinuxDeviceCollector, "_run_lsusb", staticmethod(fake_run)) if False else patch(
        "agent.collectors.device._run_lsusb", return_value=[]
    ):
        # First scan: empty. No events.
        collector._prev = {}
        # Inject new device.
        new_dev = [{"id": "0781:5571", "bus": "001", "device": "004", "desc": "SanDisk"}]
        with patch("agent.collectors.device._run_lsusb", return_value=new_dev):
            collector._scan_once()
    assert len(events) == 1
    sid, payload = events[0]
    assert payload["event_type"] == "device"
    assert payload["action"] == "connect"
    assert payload["raw_payload"]["usb_id"] == "0781:5571"
    assert payload["raw_payload"]["activity"] == "Connect"
    assert payload["resource"] == "SanDisk"


def test_linux_device_collector_emits_disconnect_on_removal() -> None:
    policy = _make_policy(["device"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxDeviceCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    # Prev had one device; current has none.
    collector._prev = {"0781:5571": {"id": "0781:5571", "bus": "001", "device": "004", "desc": "SanDisk"}}
    with patch("agent.collectors.device._run_lsusb", return_value=[]):
        collector._scan_once()
    assert len(events) == 1
    assert events[0][1]["action"] == "disconnect"


def test_linux_device_collector_no_event_when_unchanged() -> None:
    policy = _make_policy(["device"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxDeviceCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    same = [{"id": "0781:5571", "bus": "001", "device": "004", "desc": "SanDisk"}]
    with patch("agent.collectors.device._run_lsusb", return_value=same):
        collector._prev = {d["id"]: d for d in same}
        collector._scan_once()
    assert events == []


def test_linux_device_collector_start_marks_unhealthy_without_lsusb() -> None:
    policy = _make_policy(["device"])
    cc = _make_config_client(policy)
    collector = LinuxDeviceCollector(cc, poll_interval=0.05)
    with patch("shutil.which", return_value=None):
        collector.start()
    assert not collector.is_healthy
    assert "lsusb" in (collector.last_error or "")


def test_linux_device_collector_start_starts_thread_when_lsusb_available() -> None:
    policy = _make_policy(["device"])
    cc = _make_config_client(policy)
    collector = LinuxDeviceCollector(cc, poll_interval=0.5)
    with patch("shutil.which", return_value="/usr/bin/lsusb"):
        with patch("agent.collectors.device._run_lsusb", return_value=[]):
            collector.start()
            try:
                import time
                time.sleep(0.1)
                assert collector._thread is not None
            finally:
                collector.stop()
    assert collector._thread is None


def test_linux_device_collector_respects_sampling() -> None:
    policy = _make_policy(["device"])
    policy.sampling_rate = 0
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxDeviceCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    collector._prev = {}
    with patch("agent.collectors.device._run_lsusb", return_value=[
        {"id": "0781:5571", "bus": "001", "device": "004", "desc": "SanDisk"},
    ]):
        collector._scan_once()
    assert events == []  # sampling=0 → all dropped


def test_linux_device_collector_disabled_by_policy() -> None:
    policy = _make_policy([])  # device NOT enabled
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxDeviceCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    collector._prev = {}
    with patch("agent.collectors.device._run_lsusb", return_value=[
        {"id": "0781:5571", "bus": "001", "device": "004", "desc": "SanDisk"},
    ]):
        collector._scan_once()
    assert events == []


def test_windows_device_collector_stub_marks_unhealthy() -> None:
    policy = _make_policy(["device"])
    cc = _make_config_client(policy)
    collector = WindowsDeviceCollector(cc)
    collector.start()
    assert not collector.is_healthy
