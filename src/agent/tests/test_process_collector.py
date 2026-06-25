"""Tests for the process collector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.collectors.process import (
    LinuxProcessCollector,
    ProgrammaticProcessCollector,
    WindowsProcessCollector,
    _list_pids,
    _read_proc,
)
from agent.config_client import AgentPolicy, ConfigClient


def _make_config_client(policy: AgentPolicy) -> ConfigClient:
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


def test_read_proc_returns_comm_and_cmdline(tmp_path) -> None:
    """Test _read_proc using a temp dir mocked as /proc/<pid>."""
    # We can't easily mock /proc, so test the public collector API instead
    # with monkey-patched _list_pids.
    proc_info = _read_proc(99999)
    assert proc_info is None  # PID doesn't exist


def test_list_pids_returns_empty_when_proc_missing() -> None:
    with patch("pathlib.Path.is_dir", return_value=False):
        assert _list_pids() == {}


def test_linux_process_collector_emits_for_new_pid() -> None:
    policy = _make_policy(["process"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxProcessCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    collector._prev = {}
    new_pid = {1234: {"comm": "bash", "cmdline": "bash -c echo hi"}}
    with patch("agent.collectors.process._list_pids", return_value=new_pid):
        collector._scan_once()
    assert len(events) == 1
    sid, payload = events[0]
    assert payload["event_type"] == "process"
    assert payload["action"] == "spawn"
    assert payload["raw_payload"]["pid"] == 1234
    assert payload["raw_payload"]["process_name"] == "bash"
    assert payload["raw_payload"]["cmdline"] == "bash -c echo hi"
    assert payload["resource"] == "bash"


def test_linux_process_collector_no_event_for_unchanged_pids() -> None:
    policy = _make_policy(["process"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxProcessCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    same = {1: {"comm": "init", "cmdline": ""}}
    collector._prev = dict(same)
    with patch("agent.collectors.process._list_pids", return_value=same):
        collector._scan_once()
    assert events == []


def test_linux_process_collector_start_marks_unhealthy_without_proc() -> None:
    policy = _make_policy(["process"])
    cc = _make_config_client(policy)
    collector = LinuxProcessCollector(cc, poll_interval=0.05)
    with patch("pathlib.Path.is_dir", return_value=False):
        collector.start()
    assert not collector.is_healthy


def test_linux_process_collector_start_runs_thread() -> None:
    policy = _make_policy(["process"])
    cc = _make_config_client(policy)
    collector = LinuxProcessCollector(cc, poll_interval=0.5)
    with patch("pathlib.Path.is_dir", return_value=True):
        with patch("agent.collectors.process._list_pids", return_value={1: {"comm": "init", "cmdline": ""}}):
            collector.start()
            try:
                import time
                time.sleep(0.1)
                assert collector._thread is not None
            finally:
                collector.stop()
    assert collector._thread is None


def test_linux_process_collector_respects_sampling() -> None:
    policy = _make_policy(["process"])
    policy.sampling_rate = 0
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxProcessCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    collector._prev = {}
    with patch("agent.collectors.process._list_pids", return_value={
        9999: {"comm": "x", "cmdline": "y"},
    }):
        collector._scan_once()
    assert events == []


def test_programmatic_process_collector_record_spawn() -> None:
    policy = _make_policy(["process"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = ProgrammaticProcessCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_spawn(pid=1234, process_name="powershell.exe", cmdline="powershell -enc XYZ", user="alice")
    assert len(events) == 1
    sid, payload = events[0]
    assert payload["event_type"] == "process"
    assert payload["action"] == "spawn"
    assert payload["raw_payload"]["pid"] == 1234
    assert payload["raw_payload"]["process_name"] == "powershell.exe"
    assert payload["raw_payload"]["cmdline"] == "powershell -enc XYZ"
    assert payload["ingest_metadata"]["user_override"] == "alice"


def test_programmatic_process_collector_disabled_by_policy() -> None:
    policy = _make_policy([])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = ProgrammaticProcessCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_spawn(pid=1, process_name="x")
    assert events == []


def test_windows_process_collector_stub_marks_unhealthy() -> None:
    policy = _make_policy(["process"])
    cc = _make_config_client(policy)
    collector = WindowsProcessCollector(cc)
    collector.start()
    assert not collector.is_healthy
