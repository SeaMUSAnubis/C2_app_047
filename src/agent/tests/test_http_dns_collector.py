"""Tests for the DomainCheckCollector and DnsSniffCollector.

We don't require root or real DNS — we test the matching/emit logic and
the queue-driven worker model.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.collectors.http_dns import (
    DnsSniffCollector,
    DomainCheckCollector,
    _HttpBlockMixin,
)
from agent.config_client import AgentPolicy, BlocklistEntry, ConfigClient


def _make_config_client(policy: AgentPolicy) -> ConfigClient:
    transport = MagicMock()
    transport._server_url = "http://test"  # noqa: SLF001
    cc = ConfigClient(transport, pull_interval=60)
    cc._policy = policy  # type: ignore[attr-defined]
    return cc


def _make_policy(entries: list[BlocklistEntry]) -> AgentPolicy:
    return AgentPolicy(
        policy_version=1, sampling_rate=100,
        enabled_collectors=["http"],
        blocklist=entries,
    )


def test_classify_returns_blocked() -> None:
    policy = _make_policy([BlocklistEntry("evil.com", "domain", "malware", "test")])
    cc = _make_config_client(policy)
    mixin = _HttpBlockMixin()
    blocked, info = mixin._classify(cc, "evil.com")
    assert blocked
    assert info is not None
    assert info["pattern"] == "evil.com"
    assert info["category"] == "malware"


def test_classify_returns_not_blocked() -> None:
    policy = _make_policy([BlocklistEntry("evil.com", "domain")])
    cc = _make_config_client(policy)
    mixin = _HttpBlockMixin()
    blocked, info = mixin._classify(cc, "good.com")
    assert not blocked
    assert info is None


def test_classify_handles_empty_blocklist() -> None:
    cc = _make_config_client(_make_policy([]))
    mixin = _HttpBlockMixin()
    blocked, info = mixin._classify(cc, "anything.com")
    assert not blocked
    assert info is None


def test_domain_check_collector_emits_blocked_event() -> None:
    policy = _make_policy([BlocklistEntry("evil.com", "domain", "malware", "blocked")])
    cc = _make_config_client(policy)
    collector = DomainCheckCollector(cc)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    try:
        collector.check_domain("evil.com", source_tag="test")
        # Wait briefly for the worker to drain.
        import time
        deadline = time.time() + 1.0
        while collector.queue_size() > 0 and time.time() < deadline:
            time.sleep(0.05)
        # Force drain by calling _drain (worker polls every 0.5s).
        # Simpler: wait for the worker loop to pick it up.
        time.sleep(0.6)
    finally:
        collector.stop()

    # Filter to just our event.
    our_events = [e for e in events if "evil.com" in str(e)]
    assert len(our_events) >= 1
    sid, payload = our_events[0]
    assert payload["event_type"] == "http"
    assert payload["action"] == "blocked"
    assert payload["raw_payload"]["domain"] == "evil.com"
    assert payload["raw_payload"]["block_pattern"] == "evil.com"


def test_domain_check_collector_emits_allowed_event() -> None:
    policy = _make_policy([BlocklistEntry("evil.com", "domain")])
    cc = _make_config_client(policy)
    collector = DomainCheckCollector(cc)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    try:
        collector.check_domain("good.com", source_tag="test")
        import time
        time.sleep(0.6)
    finally:
        collector.stop()

    our_events = [e for e in events if "good.com" in str(e)]
    assert len(our_events) >= 1
    _, payload = our_events[0]
    assert payload["action"] == "allowed"


def test_domain_check_collector_emits_for_full_url() -> None:
    policy = _make_policy([BlocklistEntry("wikileaks.org", "domain")])
    cc = _make_config_client(policy)
    collector = DomainCheckCollector(cc)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    try:
        collector.check_domain("https://wikileaks.org/some/path", source_tag="browser")
        import time
        time.sleep(0.6)
    finally:
        collector.stop()

    our_events = [e for e in events if "wikileaks.org" in str(e)]
    assert len(our_events) >= 1
    _, payload = our_events[0]
    assert payload["action"] == "blocked"
    assert payload["raw_payload"]["domain"] == "wikileaks.org"
    assert payload["raw_payload"]["url"].startswith("https://wikileaks.org")


def test_domain_check_collector_disabled_collector_emits_nothing() -> None:
    """When http collector is not in enabled_collectors, no event is emitted."""
    policy = AgentPolicy(
        policy_version=1, sampling_rate=100,
        enabled_collectors=[],  # http NOT enabled
        blocklist=[BlocklistEntry("evil.com", "domain")],
    )
    cc = _make_config_client(policy)
    collector = DomainCheckCollector(cc)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    try:
        collector.check_domain("evil.com", source_tag="test")
        import time
        time.sleep(0.6)
    finally:
        collector.stop()

    assert events == []


def test_domain_check_collector_sampling_drops_events() -> None:
    """With sampling_rate=0, all events are dropped."""
    policy = AgentPolicy(
        policy_version=1, sampling_rate=0,  # drop everything
        enabled_collectors=["http"],
        blocklist=[],
    )
    cc = _make_config_client(policy)
    collector = DomainCheckCollector(cc)

    events: list[tuple[str, dict]] = []
    collector.set_sink(lambda sid, payload: events.append((sid, payload)) or True)
    collector.start()
    try:
        for i in range(20):
            collector.check_domain(f"d{i}.com", source_tag="test")
        import time
        time.sleep(0.6)
    finally:
        collector.stop()

    assert events == []


def test_domain_check_collector_handles_empty_value() -> None:
    policy = _make_policy([])
    cc = _make_config_client(policy)
    collector = DomainCheckCollector(cc)
    collector.check_domain("")  # should not raise
    assert collector.queue_size() == 0


def test_domain_check_collector_handles_many_values() -> None:
    policy = _make_policy([])
    cc = _make_config_client(policy)
    collector = DomainCheckCollector(cc)
    for i in range(100):
        collector.check_domain(f"d{i}.com", source_tag="bulk")
    assert collector.queue_size() == 100


def test_dns_sniff_parse_query_extracts_domain() -> None:
    """DNS query: 12-byte header + length-prefixed labels + 0 terminator."""
    # Build a DNS query for "evil.com" type A.
    import struct
    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    question = b"\x04evil\x03com\x00\x00\x01\x00\x01"
    pkt = header + question
    domain = DnsSniffCollector._parse_query(pkt)
    assert domain == "evil.com"


def test_dns_sniff_parse_query_handles_subdomain() -> None:
    import struct
    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    question = b"\x03api\x04evil\x03com\x00\x00\x01\x00\x01"
    pkt = header + question
    domain = DnsSniffCollector._parse_query(pkt)
    assert domain == "api.evil.com"


def test_dns_sniff_parse_query_returns_none_for_too_short() -> None:
    assert DnsSniffCollector._parse_query(b"") is None
    assert DnsSniffCollector._parse_query(b"\x00" * 5) is None


def test_dns_sniff_parse_query_returns_none_for_pointer() -> None:
    """Pointer compression (0xC0 prefix) is rejected."""
    import struct
    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    question = b"\x04evil\x03com\xc0\x0c\x00\x01\x00\x01"
    pkt = header + question
    assert DnsSniffCollector._parse_query(pkt) is None


def test_dns_sniff_parse_query_returns_none_for_malformed() -> None:
    """Length byte exceeds remaining buffer."""
    import struct
    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    question = b"\xffevil"  # 255 bytes requested but only 4 left
    pkt = header + question
    assert DnsSniffCollector._parse_query(pkt) is None


def test_dns_sniff_parse_query_handles_uppercase() -> None:
    """Result should be lowercased."""
    import struct
    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    question = b"\x04EVIL\x03COM\x00\x00\x01\x00\x01"
    pkt = header + question
    assert DnsSniffCollector._parse_query(pkt) == "evil.com"


def test_dns_sniff_collector_marks_unhealthy_without_root() -> None:
    """If not running as root, the collector marks itself unhealthy."""
    import os
    if os.geteuid() == 0:  # noqa: SLF001
        pytest.skip("test requires non-root user")
    policy = _make_policy([])
    cc = _make_config_client(policy)
    c = DnsSniffCollector(cc, listen_port=15353)
    c.start()
    assert not c.is_healthy
    c.stop()
