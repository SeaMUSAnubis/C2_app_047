"""Tests for the config client + blocklist matching + sampling."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from src.agent.config_client import (
    AgentPolicy,
    BlocklistEntry,
    ConfigClient,
)
from src.agent.transport import PermanentError, TransientError


@pytest.fixture
def mock_transport() -> MagicMock:
    t = MagicMock()
    t._server_url = "http://test"  # noqa: SLF001
    return t


def _make_transport_with_data(data: dict) -> MagicMock:
    t = MagicMock()
    t._server_url = "http://test"  # noqa: SLF001
    t.get_config.return_value = data
    return t


def test_blocklist_domain_exact_match() -> None:
    e = BlocklistEntry(pattern="evil.com", pattern_type="domain")
    assert e.matches("evil.com")
    assert e.matches("EVIL.COM")  # case-insensitive
    assert not e.matches("notevil.com")
    assert not e.matches("")


def test_blocklist_domain_subdomain_match() -> None:
    e = BlocklistEntry(pattern="evil.com", pattern_type="domain")
    assert e.matches("api.evil.com")
    assert e.matches("deep.nested.evil.com")
    assert not e.matches("evil.company.com")  # not a subdomain of evil.com


def test_blocklist_url_substring_match() -> None:
    e = BlocklistEntry(pattern="malware.exe", pattern_type="url")
    assert e.matches("http://bad.com/malware.exe")
    assert e.matches("https://safe.com/MALWARE.EXE")
    assert not e.matches("http://safe.com/safe.exe")


def test_blocklist_ip_substring_match() -> None:
    e = BlocklistEntry(pattern="192.168.1.100", pattern_type="ip")
    assert e.matches("192.168.1.100")
    assert e.matches("Client 192.168.1.100 connected")
    assert not e.matches("192.168.1.1")


def test_blocklist_regex_match() -> None:
    e = BlocklistEntry(pattern=r"job.*search", pattern_type="regex")
    assert e.matches("indeed.com/job-search")
    assert e.matches("monster.com/job_search")
    assert not e.matches("github.com/jobs")


def test_blocklist_invalid_regex_does_not_match() -> None:
    e = BlocklistEntry(pattern=r"[invalid(", pattern_type="regex")
    # Malformed regex must not raise, just return False.
    assert e.matches("anything") is False


def test_blocklist_empty_value() -> None:
    e = BlocklistEntry(pattern="evil.com", pattern_type="domain")
    assert e.matches("") is False
    assert e.matches("   ") is False


def test_blocklist_strips_whitespace() -> None:
    e = BlocklistEntry(pattern="  evil.com  ", pattern_type="domain")
    assert e.matches("evil.com")
    assert e.matches("api.evil.com")


def test_blocklist_unknown_pattern_type_substring() -> None:
    """Unknown pattern types fall back to substring match."""
    e = BlocklistEntry(pattern="foo", pattern_type="unknown")
    assert e.matches("foobar")


def test_policy_default_sampling_keeps_all() -> None:
    p = AgentPolicy(sampling_rate=100)
    for _ in range(100):
        assert p.should_sample() is True


def test_policy_zero_sampling_drops_all() -> None:
    p = AgentPolicy(sampling_rate=0)
    for _ in range(100):
        assert p.should_sample() is False


def test_policy_sampling_rate_50_is_roughly_50_percent() -> None:
    p = AgentPolicy(sampling_rate=50)
    kept = sum(1 for _ in range(10_000) if p.should_sample())
    # Allow 5% tolerance.
    assert 4500 < kept < 5500, f"expected ~5000 kept, got {kept}"


def test_policy_sampling_rate_clamps_to_range() -> None:
    """The AgentPolicy dataclass itself does not clamp; the ConfigClient
    parser does. Verify the parser clamps server-supplied values to [1, 100]."""
    transport = _make_transport_with_data({
        "policy_version": 1,
        "sampling_rate": 200,  # out of range
        "enabled_collectors": [], "blocklist": [],
    })
    cc = ConfigClient(transport, pull_interval=60)
    p = cc.pull()
    assert p.sampling_rate == 100

    transport2 = _make_transport_with_data({
        "policy_version": 1,
        "sampling_rate": -5,  # out of range
        "enabled_collectors": [], "blocklist": [],
    })
    cc2 = ConfigClient(transport2, pull_interval=60)
    p2 = cc2.pull()
    assert p2.sampling_rate == 1


def test_policy_collector_enabled() -> None:
    p = AgentPolicy(enabled_collectors=["logon", "http"])
    assert p.is_collector_enabled("logon")
    assert p.is_collector_enabled("http")
    assert not p.is_collector_enabled("file")


def test_config_client_starts_with_defaults() -> None:
    transport = _make_transport_with_data({})
    cc = ConfigClient(transport)
    # Default policy is empty until first pull.
    assert cc.policy.policy_version == 0
    assert cc.policy.sampling_rate == 100
    assert cc.policy.blocklist == []


def test_config_client_pull_parses_server_response(mock_transport: MagicMock) -> None:
    mock_transport.get_config.return_value = {
        "policy_version": 5,
        "sampling_rate": 75,
        "enabled_collectors": ["logon", "http"],
        "blocklist": [
            {"pattern": "evil.com", "pattern_type": "domain",
             "category": "malware", "reason": "test"},
            {"pattern": "10.0.0.1", "pattern_type": "ip", "category": "internal"},
        ],
        "server_time": "2026-06-22T10:00:00Z",
    }
    cc = ConfigClient(mock_transport, pull_interval=60)
    p = cc.pull()
    assert p.policy_version == 5
    assert p.sampling_rate == 75
    assert p.enabled_collectors == ["logon", "http"]
    assert len(p.blocklist) == 2
    assert p.blocklist[0].pattern == "evil.com"
    assert p.blocklist[0].category == "malware"


def test_config_client_pull_skips_invalid_blocklist_entries(mock_transport: MagicMock) -> None:
    mock_transport.get_config.return_value = {
        "policy_version": 1, "sampling_rate": 100,
        "enabled_collectors": [],
        "blocklist": [
            {"pattern": "good.com", "pattern_type": "domain"},
            {"missing": "pattern"},  # no 'pattern' key — skipped
            {"pattern": "another.com"},  # no pattern_type — defaults to domain
        ],
    }
    cc = ConfigClient(mock_transport, pull_interval=60)
    p = cc.pull()
    assert len(p.blocklist) == 2
    assert p.blocklist[0].pattern == "good.com"
    assert p.blocklist[1].pattern_type == "domain"


def test_config_client_is_blocked_checks_policy() -> None:
    transport = _make_transport_with_data({
        "policy_version": 1, "sampling_rate": 100,
        "enabled_collectors": [],
        "blocklist": [
            {"pattern": "blocked.com", "pattern_type": "domain"},
        ],
    })
    cc = ConfigClient(transport, pull_interval=60)
    cc.pull()
    blocked, entry = cc.is_blocked("blocked.com")
    assert blocked
    assert entry is not None
    assert entry.pattern == "blocked.com"

    blocked, entry = cc.is_blocked("allowed.com")
    assert not blocked
    assert entry is None


def test_config_client_is_blocked_returns_first_match() -> None:
    transport = _make_transport_with_data({
        "policy_version": 1, "sampling_rate": 100,
        "enabled_collectors": [],
        "blocklist": [
            {"pattern": "first.com", "pattern_type": "domain"},
            {"pattern": "first.com", "pattern_type": "domain", "category": "dup"},
        ],
    })
    cc = ConfigClient(transport, pull_interval=60)
    cc.pull()
    blocked, entry = cc.is_blocked("first.com")
    assert blocked
    assert entry.category is None  # first match wins


def test_config_client_needs_pull_based_on_interval() -> None:
    cc = ConfigClient(MagicMock(), pull_interval=0.05)
    assert cc.needs_pull() is True
    # Simulate a pull.
    cc._last_pull = time.monotonic()  # noqa: SLF001
    assert cc.needs_pull() is False
    time.sleep(0.06)
    assert cc.needs_pull() is True


def test_config_client_pull_with_retry_eventually_succeeds() -> None:
    transport = MagicMock()
    transport._server_url = "http://test"  # noqa: SLF001
    call_count = {"n": 0}

    def flaky_get_config() -> dict:
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise TransientError("transient")
        return {
            "policy_version": 1, "sampling_rate": 100,
            "enabled_collectors": [], "blocklist": [],
        }

    transport.get_config.side_effect = flaky_get_config
    cc = ConfigClient(transport, pull_interval=60)
    p = cc.pull_with_retry(max_attempts=5)
    assert p.policy_version == 1
    assert call_count["n"] == 3


def test_config_client_pull_with_retry_returns_cached_on_total_failure() -> None:
    transport = MagicMock()
    transport._server_url = "http://test"  # noqa: SLF001
    transport.get_config.side_effect = TransientError("always fails")
    cc = ConfigClient(transport, pull_interval=60)
    p = cc.pull_with_retry(max_attempts=2)
    # Default empty policy.
    assert p.policy_version == 0
    assert cc.last_error is not None


def test_config_client_pull_with_retry_propagates_permanent() -> None:
    transport = MagicMock()
    transport._server_url = "http://test"  # noqa: SLF001
    transport.get_config.side_effect = PermanentError("bad request")
    cc = ConfigClient(transport, pull_interval=60)
    with pytest.raises(PermanentError):
        cc.pull_with_retry(max_attempts=3)


def test_config_client_pull_detects_policy_version_change() -> None:
    transport = MagicMock()
    transport._server_url = "http://test"  # noqa: SLF001
    responses = [
        {"policy_version": 1, "sampling_rate": 100,
         "enabled_collectors": ["logon"], "blocklist": []},
        {"policy_version": 2, "sampling_rate": 75,
         "enabled_collectors": ["logon", "http"], "blocklist": []},
    ]
    transport.get_config.side_effect = responses
    cc = ConfigClient(transport, pull_interval=60)
    p1 = cc.pull()
    assert p1.policy_version == 1
    p2 = cc.pull()
    assert p2.policy_version == 2
    assert p2.sampling_rate == 75


def test_config_client_thread_safe_reads() -> None:
    transport = _make_transport_with_data({
        "policy_version": 1, "sampling_rate": 100,
        "enabled_collectors": [], "blocklist": [
            {"pattern": "evil.com", "pattern_type": "domain"},
        ],
    })
    cc = ConfigClient(transport, pull_interval=60)
    cc.pull()
    errors: list[Exception] = []

    def reader() -> None:
        try:
            for _ in range(100):
                cc.is_blocked("evil.com")
                _ = cc.policy
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def writer() -> None:
        try:
            for _ in range(50):
                cc.pull()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=reader),
        threading.Thread(target=writer),
        threading.Thread(target=reader),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors


def test_config_client_last_pull_at_set_after_pull() -> None:
    transport = _make_transport_with_data({
        "policy_version": 1, "sampling_rate": 100,
        "enabled_collectors": [], "blocklist": [],
        "server_time": "2026-06-22T10:00:00Z",
    })
    cc = ConfigClient(transport, pull_interval=60)
    assert cc.last_pull_at is None
    cc.pull()
    assert cc.last_pull_at == "2026-06-22T10:00:00Z"


def test_config_client_missing_sampling_rate_defaults_to_100() -> None:
    transport = _make_transport_with_data({
        "policy_version": 1,
        "enabled_collectors": [], "blocklist": [],
        # no sampling_rate
    })
    cc = ConfigClient(transport, pull_interval=60)
    p = cc.pull()
    assert p.sampling_rate == 100


def test_config_client_missing_blocklist_defaults_to_empty() -> None:
    transport = _make_transport_with_data({
        "policy_version": 1, "sampling_rate": 100,
        "enabled_collectors": [],
    })
    cc = ConfigClient(transport, pull_interval=60)
    p = cc.pull()
    assert p.blocklist == []


def test_config_client_missing_enabled_collectors_defaults_to_empty() -> None:
    transport = _make_transport_with_data({
        "policy_version": 1, "sampling_rate": 100,
        "blocklist": [],
    })
    cc = ConfigClient(transport, pull_interval=60)
    p = cc.pull()
    assert p.enabled_collectors == []
