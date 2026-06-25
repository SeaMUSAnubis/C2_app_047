"""Tests for the Linux logon collector.

We don't require wtmp to be readable — we build a fake wtmp file with
synthesized records. This isolates the parser from the OS.
"""

from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import MagicMock

from agent.collectors.logon import (
    WTMP_FORMAT,
    WTMP_RECORD_SIZE,
    LinuxLogonCollector,
    WindowsLogonCollector,
)
from agent.config_client import AgentPolicy, ConfigClient


def _wtmp_record(
    ut_type: int = 0,
    ut_pid: int = 0,
    line: str = "",
    ut_user: str = "",
    ut_host: str = "",
    tv_sec: int = 0,
) -> bytes:
    """Build a fake wtmp record (384 bytes)."""
    return struct.pack(
        WTMP_FORMAT,
        ut_type, ut_pid,
        line.encode("utf-8")[:32].ljust(32, b"\x00"),
        b"\x00" * 4,  # ut_id
        ut_user.encode("utf-8")[:32].ljust(32, b"\x00"),
        ut_host.encode("utf-8")[:256].ljust(256, b"\x00"),
        0, 0,  # exit_status
        0,  # ut_session
        tv_sec, 0,  # ut_tv_sec, ut_tv_usec
    )


def _make_config_client(enabled: list[str]) -> ConfigClient:
    transport = MagicMock()
    transport._server_url = "http://test"  # noqa: SLF001
    cc = ConfigClient(transport, pull_interval=60)
    cc._policy = AgentPolicy(  # type: ignore[attr-defined]
        policy_version=1, sampling_rate=100,
        enabled_collectors=enabled,
        blocklist=[],
    )
    return cc


def _make_wtmp(path: Path, records: list[bytes]) -> None:
    path.write_bytes(b"".join(records))


def test_logon_collector_parses_user_process(tmp_path: Path) -> None:
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=7, ut_user="acm0001", line="pts/0", tv_sec=1700000000)])
    cc = _make_config_client(["logon"])
    collector = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=60)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    import time
    time.sleep(0.5)
    collector.stop()

    assert len(events) == 1
    sid, payload = events[0]
    assert payload["event_type"] == "logon"
    assert payload["action"] == "logon"
    assert payload["raw_payload"]["username"] == "acm0001"
    assert payload["raw_payload"]["line"] == "pts/0"
    assert payload["user_id"] == "acm0001"


def test_logon_collector_parses_dead_process_as_logoff(tmp_path: Path) -> None:
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=8, ut_user="acm0001", line="pts/0", tv_sec=1700000001)])
    cc = _make_config_client(["logon"])
    collector = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=60)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    import time
    time.sleep(0.5)
    collector.stop()

    assert len(events) == 1
    _, payload = events[0]
    assert payload["action"] == "logoff"


def test_logon_collector_skips_system_events(tmp_path: Path) -> None:
    """Events of type BOOT_TIME, RUN_LVL, etc. should NOT be emitted."""
    wtmp = tmp_path / "wtmp"
    records = [
        _wtmp_record(ut_type=2, ut_user="", tv_sec=1700000000),  # BOOT_TIME
        _wtmp_record(ut_type=1, ut_user="", tv_sec=1700000001),  # RUN_LVL
        _wtmp_record(ut_type=6, ut_user="LOGIN", tv_sec=1700000002),  # LOGIN_PROCESS
        _wtmp_record(ut_type=0, ut_user="", tv_sec=1700000003),  # EMPTY
        _wtmp_record(ut_type=7, ut_user="acm0001", line="pts/0", tv_sec=1700000004),  # real logon
    ]
    _make_wtmp(wtmp, records)
    cc = _make_config_client(["logon"])
    collector = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=60)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    import time
    time.sleep(0.5)
    collector.stop()

    # Only the USER_PROCESS event should be emitted.
    assert len(events) == 1
    assert events[0][1]["raw_payload"]["username"] == "acm0001"


def test_logon_collector_skips_reboot_user(tmp_path: Path) -> None:
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=7, ut_user="reboot", line="~", tv_sec=1700000000)])
    cc = _make_config_client(["logon"])
    collector = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=60)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    import time
    time.sleep(0.5)
    collector.stop()
    assert events == []


def test_logon_collector_skips_LOGIN_user(tmp_path: Path) -> None:
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=7, ut_user="LOGIN", line="tty1", tv_sec=1700000000)])
    cc = _make_config_client(["logon"])
    collector = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=60)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    import time
    time.sleep(0.5)
    collector.stop()
    assert events == []


def test_logon_collector_skips_disabled_collector(tmp_path: Path) -> None:
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=7, ut_user="acm0001", line="pts/0", tv_sec=1700000000)])
    cc = _make_config_client([])  # logon NOT enabled
    collector = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=60)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    import time
    time.sleep(0.5)
    collector.stop()
    assert events == []


def test_logon_collector_picks_up_new_records(tmp_path: Path) -> None:
    """After initial scan, appending to wtmp should trigger new events."""
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=7, ut_user="acm0001", line="pts/0", tv_sec=1700000000)])
    cc = _make_config_client(["logon"])
    collector = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=0.1)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    import time
    time.sleep(0.3)  # first scan
    # Append a new record.
    with wtmp.open("ab") as f:
        f.write(_wtmp_record(ut_type=8, ut_user="acm0001", line="pts/0", tv_sec=1700000005))
    time.sleep(0.5)  # second scan
    collector.stop()

    assert len(events) == 2
    assert events[0][1]["action"] == "logon"
    assert events[1][1]["action"] == "logoff"


def test_logon_collector_handles_wtmp_rotation(tmp_path: Path) -> None:
    """If wtmp rotates (size shrinks), reset offset and re-read from new file.

    Real wtmp rotation (e.g. via `logrotate`): the old file is renamed and
    a new one is created with the same path. The new file starts empty
    (size 0) and grows as new logon events occur. We simulate by unlinking
    the file and immediately re-creating it EMPTY, then writing a record
    (the size will grow from 0 to 384, while the collector's offset is 384
    — so size < offset triggers the reset path).
    """
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=7, ut_user="acm0001", line="pts/0", tv_sec=1700000000)])
    cc = _make_config_client(["logon"])
    collector = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=0.1)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    import time
    time.sleep(0.3)
    # Simulate rotation: unlink + recreate EMPTY, then write a record
    # AFTER the collector's first scan sees the empty file (size=0 < offset=384
    # triggers rotation detection).
    wtmp.unlink()
    wtmp.write_bytes(b"")  # empty file = rotated
    time.sleep(0.2)  # let collector see size=0
    # Now append a new record.
    with wtmp.open("ab") as f:
        f.write(_wtmp_record(ut_type=7, ut_user="btr0002", line="pts/1", tv_sec=1700000010))
    time.sleep(0.3)
    collector.stop()

    users = {e[1]["raw_payload"]["username"] for e in events}
    assert "acm0001" in users
    assert "btr0002" in users


def test_logon_collector_marks_unhealthy_when_wtmp_missing(tmp_path: Path) -> None:
    cc = _make_config_client(["logon"])
    collector = LinuxLogonCollector(cc, wtmp_path=tmp_path / "missing", poll_interval=0.1)
    collector.start()
    import time
    time.sleep(0.2)
    assert not collector.is_healthy
    assert "not found" in (collector.last_error or "")
    collector.stop()


def test_logon_collector_recovers_from_transient_read_error(tmp_path: Path) -> None:
    """A read error during one scan should not kill the collector.

    We simulate a transient read error by replacing the wtmp file with a
    DIRECTORY of the same name. The collector's `f.open("rb")` will then
    raise `IsADirectoryError` (an OSError subclass), which the run loop
    catches and reports via mark_unhealthy.

    This is more portable than chmod 0o000 (which is bypassed when running
    as root, e.g. inside a container) and represents a realistic failure
    mode (filesystem corruption, manual tampering, mount issues).
    """
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=7, ut_user="acm0001", line="pts/0", tv_sec=1700000000)])
    cc = _make_config_client(["logon"])
    collector = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=0.1)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    import time
    time.sleep(0.3)
    # Append a new record so the file grows (otherwise the scan short-
    # circuits on size <= offset without trying to open).
    with wtmp.open("ab") as f:
        f.write(_wtmp_record(ut_type=7, ut_user="btr0002", line="pts/1", tv_sec=1700000010))
    # Now replace the file with a directory of the same name.
    wtmp.unlink()
    wtmp.mkdir()
    # The next scan will stat OK but open() will fail with IsADirectoryError.
    deadline = time.time() + 1.5
    while collector.is_healthy and time.time() < deadline:
        time.sleep(0.05)
    assert not collector.is_healthy
    assert collector.last_error is not None
    # Cleanup: remove the directory.
    wtmp.rmdir()
    collector.stop()


def test_logon_collector_offset_persists_across_restarts(tmp_path: Path) -> None:
    """The set_offset / get_offset API is used to persist progress."""
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [
        _wtmp_record(ut_type=7, ut_user="u1", line="pts/0", tv_sec=1700000000),
        _wtmp_record(ut_type=8, ut_user="u1", line="pts/0", tv_sec=1700000001),
    ])
    cc = _make_config_client(["logon"])
    c1 = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=0.1)
    c1.set_offset(WTMP_RECORD_SIZE)  # skip first record
    assert c1.get_offset() == WTMP_RECORD_SIZE
    c1.set_offset(0)  # reset
    assert c1.get_offset() == 0


def test_logon_collector_negative_offset_ignored(tmp_path: Path) -> None:
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=7, ut_user="u1", line="pts/0", tv_sec=1700000000)])
    cc = _make_config_client(["logon"])
    c = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=0.1)
    c.set_offset(-1)
    assert c.get_offset() == 0  # not changed
    c.set_offset(100)
    assert c.get_offset() == 100


def test_logon_collector_handles_zero_size_wtmp(tmp_path: Path) -> None:
    wtmp = tmp_path / "wtmp"
    wtmp.write_bytes(b"")
    cc = _make_config_client(["logon"])
    c = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=0.1)

    events: list[tuple[str, dict]] = []
    c.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    c.start()
    import time
    time.sleep(0.3)
    c.stop()
    assert events == []


def test_logon_collector_includes_hostname_in_metadata(tmp_path: Path) -> None:
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [_wtmp_record(ut_type=7, ut_user="acm0001", line="pts/0", tv_sec=1700000000)])
    cc = _make_config_client(["logon"])
    c = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=0.1)

    events: list[tuple[str, dict]] = []
    c.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    c.start()
    import time
    time.sleep(0.3)
    c.stop()

    assert events[0][1]["device_id"]  # non-empty hostname
    assert events[0][1]["ingest_metadata"]["source"] == "wtmp"


def test_windows_logon_collector_is_unhealthy() -> None:
    """The Windows stub must mark itself unhealthy on construction."""
    cc = _make_config_client(["logon"])
    c = WindowsLogonCollector(cc)
    assert not c.is_healthy
    c.start()  # no-op
    c.stop()  # no-op


def test_logon_collector_unique_source_ids_per_record(tmp_path: Path) -> None:
    """The source_id should be different for two logon records on the same line."""
    wtmp = tmp_path / "wtmp"
    _make_wtmp(wtmp, [
        _wtmp_record(ut_type=7, ut_user="u1", line="pts/0", tv_sec=1700000000),
        _wtmp_record(ut_type=7, ut_user="u1", line="pts/0", tv_sec=1700000010),
    ])
    cc = _make_config_client(["logon"])
    c = LinuxLogonCollector(cc, wtmp_path=wtmp, poll_interval=0.1)
    events: list[tuple[str, dict]] = []
    c.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    c.start()
    import time
    time.sleep(0.3)
    c.stop()
    assert len(events) == 2
    assert events[0][0] != events[1][0]
