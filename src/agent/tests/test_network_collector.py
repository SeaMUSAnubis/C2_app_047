"""Tests for the network collector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.collectors.network import (
    LinuxNetworkCollector,
    ProgrammaticNetworkCollector,
    WindowsNetworkCollector,
    _parse_addr,
    _read_proc_net,
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


def test_parse_addr_ipv4() -> None:
    # 127.0.0.1:0EBB in /proc/net/tcp is hex 0100007F:0EBB
    ip, port = _parse_addr("0100007F:0EBB")
    assert ip == "127.0.0.1"
    assert port == 3771


def test_parse_addr_port_443() -> None:
    ip, port = _parse_addr("0100007F:01BB")
    assert port == 443


def test_parse_addr_invalid_returns_zero() -> None:
    ip, port = _parse_addr("garbage")
    assert ip == "0.0.0.0"
    assert port == 0


def test_parse_addr_empty() -> None:
    assert _parse_addr("") == ("0.0.0.0", 0)


def test_read_proc_net_parses_established_only() -> None:
    sample = """\
  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 0100007F:0EBB 0100007F:C000 01 00000000:00000000 00:00000000 00000000  1000        0 12345 1 ...
   1: 00000000:0050 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 22222 2 ...
   2: 0100007F:9C40 0100007F:0EBB 06 00000000:00000000 00:00000000 00000000  1000        0 33333 3 ...
"""
    with patch("pathlib.Path.is_file", return_value=True):
        with patch("pathlib.Path.read_text", return_value=sample):
            conns = _read_proc_net("tcp")
    # Only the ESTABLISHED (01) state entry is included.
    assert len(conns) == 1
    local_ip, local_port, remote_ip, remote_port = next(iter(conns))
    assert local_ip == "127.0.0.1"
    assert local_port == 3771
    assert remote_port == 49152  # 0xC000


def test_read_proc_net_skips_empty_remote() -> None:
    sample = """\
  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 0100007F:0EBB 00000000:0000 01 00000000:00000000 00:00000000 00000000  1000        0 12345 1 ...
"""
    with patch("pathlib.Path.is_file", return_value=True):
        with patch("pathlib.Path.read_text", return_value=sample):
            assert _read_proc_net("tcp") == set()


def test_read_proc_net_handles_missing_file() -> None:
    with patch("pathlib.Path.is_file", return_value=False):
        assert _read_proc_net("nonexistent") == set()


def test_linux_network_collector_emits_for_new_connection() -> None:
    policy = _make_policy(["network"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxNetworkCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    collector._prev = set()
    new = {("127.0.0.1", 50000, "8.8.8.8", 443)}
    with patch("agent.collectors.network._read_proc_net_all", return_value=new):
        collector._scan_once()
    assert len(events) == 1
    sid, payload = events[0]
    assert payload["event_type"] == "network"
    assert payload["action"] == "connection"
    assert payload["raw_payload"]["src_ip"] == "127.0.0.1"
    assert payload["raw_payload"]["src_port"] == 50000
    assert payload["raw_payload"]["dst_ip"] == "8.8.8.8"
    assert payload["raw_payload"]["dst_port"] == 443
    assert payload["resource"] == "8.8.8.8:443"


def test_linux_network_collector_no_event_for_unchanged_conns() -> None:
    policy = _make_policy(["network"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxNetworkCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    same = {("127.0.0.1", 50000, "8.8.8.8", 443)}
    collector._prev = set(same)
    with patch("agent.collectors.network._read_proc_net_all", return_value=same):
        collector._scan_once()
    assert events == []


def test_linux_network_collector_start_marks_unhealthy_without_proc_net() -> None:
    policy = _make_policy(["network"])
    cc = _make_config_client(policy)
    collector = LinuxNetworkCollector(cc, poll_interval=0.05)
    with patch("pathlib.Path.is_dir", return_value=False):
        collector.start()
    assert not collector.is_healthy


def test_linux_network_collector_start_runs_thread() -> None:
    policy = _make_policy(["network"])
    cc = _make_config_client(policy)
    collector = LinuxNetworkCollector(cc, poll_interval=0.5)
    with patch("pathlib.Path.is_dir", return_value=True):
        with patch("agent.collectors.network._read_proc_net_all", return_value=set()):
            collector.start()
            try:
                import time
                time.sleep(0.1)
                assert collector._thread is not None
            finally:
                collector.stop()
    assert collector._thread is None


def test_linux_network_collector_respects_sampling() -> None:
    policy = _make_policy(["network"])
    policy.sampling_rate = 0
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = LinuxNetworkCollector(cc, poll_interval=0.05)
    collector.set_sink(_sink(events))
    collector._prev = set()
    with patch("agent.collectors.network._read_proc_net_all", return_value={
        ("127.0.0.1", 1, "1.1.1.1", 443),
    }):
        collector._scan_once()
    assert events == []


def test_programmatic_network_collector_record_connection() -> None:
    policy = _make_policy(["network"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = ProgrammaticNetworkCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_connection("10.0.0.5", 55555, "evil.com", 443, protocol="tcp")
    assert len(events) == 1
    sid, payload = events[0]
    assert payload["event_type"] == "network"
    assert payload["action"] == "connection"
    assert payload["raw_payload"]["src_ip"] == "10.0.0.5"
    assert payload["raw_payload"]["dst_ip"] == "evil.com"
    assert payload["raw_payload"]["dst_port"] == 443
    assert payload["raw_payload"]["protocol"] == "tcp"


def test_programmatic_network_collector_disabled_by_policy() -> None:
    policy = _make_policy([])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = ProgrammaticNetworkCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_connection("1.1.1.1", 1, "2.2.2.2", 80)
    assert events == []


def test_windows_network_collector_stub_marks_unhealthy() -> None:
    policy = _make_policy(["network"])
    cc = _make_config_client(policy)
    collector = WindowsNetworkCollector(cc)
    collector.start()
    assert not collector.is_healthy
