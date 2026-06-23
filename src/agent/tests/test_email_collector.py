"""Tests for the email collector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.collectors.email import (
    EmailCollector,
    IMAPPollerEmailCollector,
    _redact_subject,
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


def test_redact_subject_hashes_to_16_chars() -> None:
    h = _redact_subject("Confidential: M&A plans Q3")
    assert h is not None
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


def test_redact_subject_stable_for_same_input() -> None:
    h1 = _redact_subject("foo")
    h2 = _redact_subject("foo")
    assert h1 == h2


def test_redact_subject_different_for_different_input() -> None:
    assert _redact_subject("foo") != _redact_subject("bar")


def test_redact_subject_none_returns_none() -> None:
    assert _redact_subject(None) is None


def test_email_collector_emit_email_send() -> None:
    policy = _make_policy(["email"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = EmailCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_email(
        op="email_send", from_="alice@corp", to="bob@external.com",
        subject="Hi there", size=2048, attachments=0,
    )
    assert len(events) == 1
    sid, payload = events[0]
    assert payload["event_type"] == "email"
    assert payload["action"] == "email_send"
    assert payload["resource"] == "bob@external.com"
    assert payload["raw_payload"]["from"] == "alice@corp"
    assert payload["raw_payload"]["to"] == "bob@external.com"
    assert payload["raw_payload"]["size"] == 2048
    assert payload["raw_payload"]["subject_hash"] is not None
    assert "Hi there" not in str(payload)  # body NEVER in payload


def test_email_collector_unknown_op_clamps_to_email_send() -> None:
    policy = _make_policy(["email"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = EmailCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_email(op="some_unknown_op", from_="a", to="b")
    assert events[0][1]["action"] == "email_send"


def test_email_collector_email_read_uses_sender_as_resource() -> None:
    policy = _make_policy(["email"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = EmailCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_email(op="email_read", from_="newsletter@example", to="me@corp")
    assert events[0][1]["action"] == "email_read"
    # For reads, resource is sender.
    assert events[0][1]["resource"] == "newsletter@example"


def test_email_collector_user_override_metadata() -> None:
    policy = _make_policy(["email"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = EmailCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_email(op="email_send", from_="a", to="b", user="alice")
    assert events[0][1]["ingest_metadata"]["user_override"] == "alice"


def test_email_collector_disabled_by_policy() -> None:
    policy = _make_policy([])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = EmailCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    collector.record_email(op="email_send", from_="a", to="b")
    assert events == []


def test_email_collector_thread_safe_concurrent_calls() -> None:
    import threading
    policy = _make_policy(["email"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = EmailCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()

    def fire():
        for _ in range(20):
            collector.record_email(op="email_send", from_="a", to="b")

    threads = [threading.Thread(target=fire) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(events) == 100
    assert collector.emitted_count == 100


def test_email_collector_subject_never_in_payload() -> None:
    policy = _make_policy(["email"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = EmailCollector(cc)
    collector.set_sink(_sink(events))
    collector.start()
    secret = "TOP_SECRET_ACQUISITION_PLANS_2030"
    collector.record_email(op="email_send", from_="a", to="b", subject=secret)
    raw = str(events[0])
    assert secret not in raw


def test_imap_poller_email_collector_start_marks_unhealthy_without_creds() -> None:
    policy = _make_policy(["email"])
    cc = _make_config_client(policy)
    collector = IMAPPollerEmailCollector(cc, imap_host=None)
    collector.start()
    assert not collector.is_healthy


def test_imap_poller_email_collector_start_starts_thread_with_creds() -> None:
    policy = _make_policy(["email"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = IMAPPollerEmailCollector(
        cc, imap_host="imap.example.com", imap_user="u", imap_password="p", poll_interval=0.5,
    )
    collector.set_sink(_sink(events))

    class FakeIMAP:
        def __init__(self, host, port):
            self.host = host
            self.port = port
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def login(self, user, pw):
            return ("OK", [b""])
        def select(self, box, readonly=False):
            return ("OK", [b""])
        def uid(self, command, *args):
            if command == "SEARCH":
                return ("OK", [b""])
            return ("OK", [])

    with patch("imaplib.IMAP4_SSL", FakeIMAP):
        collector.start()
        try:
            import time
            time.sleep(0.1)
            assert collector._thread is not None
        finally:
            collector.stop()
    assert collector._thread is None


def test_imap_poller_email_collector_poll_emits_event_for_new_mail() -> None:
    policy = _make_policy(["email"])
    cc = _make_config_client(policy)
    events: list[tuple[str, dict]] = []
    collector = IMAPPollerEmailCollector(
        cc, imap_host="imap.example.com", imap_user="u", imap_password="p",
    )
    collector.set_sink(_sink(events))

    class FakeIMAP:
        poll_count = {"n": 0}
        def __init__(self, host, port): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def login(self, *a, **k): return ("OK", [b""])
        def select(self, *a, **k): return ("OK", [b""])
        def uid(self, command, *args):
            if command == "SEARCH":
                FakeIMAP.poll_count["n"] += 1
                # First poll: baseline (no event). Second poll: new mail arrived.
                if FakeIMAP.poll_count["n"] == 1:
                    return ("OK", [b"100"])
                return ("OK", [b"100 101"])
            if command == "FETCH":
                return ("OK", [(b"1 (RFC822.SIZE 1234)", b"ignored")])
            return ("OK", [])

    FakeIMAP.poll_count["n"] = 0
    with patch("imaplib.IMAP4_SSL", FakeIMAP):
        # First call: baseline → no event
        collector._poll_once()
        assert events == []
        # Second call: new mail → 1 event
        collector._poll_once()
    assert len(events) == 1
    assert events[0][1]["event_type"] == "email"
    assert events[0][1]["action"] == "email_read"
    assert events[0][1]["raw_payload"]["size"] == 1234
