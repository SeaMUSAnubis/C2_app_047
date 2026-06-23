"""Tests for the file collector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from agent.collectors.file import (
    LinuxFileCollector,
    ProgrammaticFileCollector,
    WindowsFileCollector,
)
from agent.config_client import AgentPolicy, ConfigClient


def _make_config_client(policy: AgentPolicy) -> ConfigClient:
    transport = MagicMock()
    cc = ConfigClient(transport, pull_interval=60)
    cc._policy = policy  # type: ignore[attr-defined]
    return cc


def _make_policy(enabled: list[str], sampling: int = 100) -> AgentPolicy:
    return AgentPolicy(
        policy_version=1, sampling_rate=sampling,
        enabled_collectors=enabled, blocklist=[],
    )


def _sink(events: list[tuple[str, dict]]):
    def _fn(source_id: str, payload: dict) -> bool:
        events.append((source_id, payload))
        return True
    return _fn


def test_linux_file_collector_emits_for_new_file(tmp_path: Path) -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxFileCollector(cc, watch_path=str(tmp_path), poll_interval=0.05)
    collector.set_sink(_sink(events))
    # Empty initial state, then add a file.
    collector._snapshot = {}
    (tmp_path / "secret.txt").write_text("hello")
    collector._scan_once()
    assert len(events) == 1
    sid, payload = events[0]
    assert payload["event_type"] == "file"
    assert payload["action"] == "file_write"
    assert payload["raw_payload"]["path"].endswith("secret.txt")


def test_linux_file_collector_emits_for_modified_file(tmp_path: Path) -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxFileCollector(cc, watch_path=str(tmp_path), poll_interval=0.05)
    collector.set_sink(_sink(events))
    f = tmp_path / "data.bin"
    f.write_text("v1")
    stat = f.stat()
    collector._snapshot = {str(f): (stat.st_size, stat.st_mtime)}
    f.write_text("v2-longer")
    collector._scan_once()
    assert len(events) == 1
    assert events[0][1]["action"] == "file_write"


def test_linux_file_collector_emits_for_deleted_file(tmp_path: Path) -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxFileCollector(cc, watch_path=str(tmp_path), poll_interval=0.05)
    collector.set_sink(_sink(events))
    f = tmp_path / "will_be_gone.txt"
    f.write_text("x")
    stat = f.stat()
    collector._snapshot = {str(f): (stat.st_size, stat.st_mtime)}
    f.unlink()
    collector._scan_once()
    assert len(events) == 1
    assert events[0][1]["action"] == "file_delete"


def test_linux_file_collector_no_event_when_unchanged(tmp_path: Path) -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxFileCollector(cc, watch_path=str(tmp_path), poll_interval=0.05)
    collector.set_sink(_sink(events))
    f = tmp_path / "static.txt"
    f.write_text("hello")
    stat = f.stat()
    collector._snapshot = {str(f): (stat.st_size, stat.st_mtime)}
    collector._scan_once()
    assert events == []


def test_linux_file_collector_start_marks_unhealthy_when_path_missing(tmp_path: Path) -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    collector = LinuxFileCollector(cc, watch_path=str(tmp_path / "nonexistent"), poll_interval=0.05)
    collector.start()
    assert not collector.is_healthy
    assert "not a directory" in (collector.last_error or "").lower()


def test_linux_file_collector_respects_max_depth(tmp_path: Path) -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    collector = LinuxFileCollector(
        cc, watch_path=str(tmp_path), poll_interval=0.05, max_depth=1
    )
    # Create file at depth 3 (should be skipped).
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "deep.txt").write_text("x")
    snapshot = collector._scan_files()
    assert all("a/b/c" not in p for p in snapshot)


def test_programmatic_file_collector_record_access_emits_event() -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = ProgrammaticFileCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_access("/home/user/secret.docx", op="file_access", user="alice")
    assert len(events) == 1
    sid, payload = events[0]
    assert payload["event_type"] == "file"
    assert payload["action"] == "file_access"
    assert payload["resource"] == "/home/user/secret.docx"
    assert payload["ingest_metadata"]["user_override"] == "alice"


def test_programmatic_file_collector_handler_called() -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    collector = ProgrammaticFileCollector(cc)
    events: list[tuple[str, dict]] = []
    collector.set_sink(_sink(events))
    received: list[tuple[str, str]] = []
    collector.set_handler(lambda p, op: received.append((p, op)))
    collector.start()
    collector.record_access("/foo", op="file_copy")
    assert received == [("/foo", "file_copy")]


def test_programmatic_file_collector_disabled_by_policy_drops_events() -> None:
    policy = _make_policy([])  # file NOT enabled
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = ProgrammaticFileCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_access("/foo", op="file_access")
    assert events == []


def test_programmatic_file_collector_handler_exception_does_not_propagate() -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = ProgrammaticFileCollector(cc)
    collector.set_sink(_sink(events))
    collector.set_handler(lambda p, op: (_ for _ in ()).throw(RuntimeError("boom")))
    collector.start()
    # Should not raise even though handler raises.
    collector.record_access("/foo", op="file_access")
    assert len(events) == 1


def test_windows_file_collector_stub_marks_unhealthy() -> None:
    policy = _make_policy(["file"])
    cc = _make_config_client(policy)
    collector = WindowsFileCollector(cc)
    collector.start()
    assert not collector.is_healthy
