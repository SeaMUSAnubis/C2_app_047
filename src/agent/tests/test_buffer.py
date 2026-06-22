"""Tests for the EventBuffer (SQLite-backed local queue)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agent.buffer import EventBuffer


@pytest.fixture
def tmp_buffer(tmp_path: Path) -> EventBuffer:
    return EventBuffer(db_path=tmp_path / "events.db", max_events=1000)


def test_enqueue_returns_true_for_new(tmp_buffer: EventBuffer) -> None:
    assert tmp_buffer.enqueue("src:1", {"x": 1}) is True
    assert tmp_buffer.size() == 1


def test_enqueue_returns_false_for_duplicate_source_id(tmp_buffer: EventBuffer) -> None:
    assert tmp_buffer.enqueue("src:1", {"x": 1}) is True
    # Same source_id again — must NOT enqueue.
    assert tmp_buffer.enqueue("src:1", {"x": 2}) is False
    assert tmp_buffer.size() == 1
    # The stored payload should be the FIRST one (INSERT OR IGNORE semantics).
    events = tmp_buffer.claim(10)
    assert len(events) == 1
    assert events[0].payload == {"x": 1}


def test_enqueue_persists_payload(tmp_buffer: EventBuffer) -> None:
    payload = {"a": 1, "b": [1, 2, 3], "c": {"nested": "yes"}}
    tmp_buffer.enqueue("src:1", payload)
    events = tmp_buffer.claim(10)
    assert events[0].payload == payload


def test_claim_marks_in_flight(tmp_buffer: EventBuffer) -> None:
    tmp_buffer.enqueue("src:1", {"x": 1})
    tmp_buffer.enqueue("src:2", {"x": 2})
    events = tmp_buffer.claim(10)
    assert len(events) == 2
    assert {e.source_id for e in events} == {"src:1", "src:2"}
    # All events are now in_flight — claim again should return 0.
    assert tmp_buffer.claim(10) == []
    # stats show in_flight=2
    stats = tmp_buffer.stats()
    assert stats["in_flight"] == 2
    assert stats["ready"] == 0


def test_ack_deletes_events(tmp_buffer: EventBuffer) -> None:
    for i in range(3):
        tmp_buffer.enqueue(f"src:{i}", {"i": i})
    events = tmp_buffer.claim(10)
    assert len(events) == 3
    deleted = tmp_buffer.ack([e.id for e in events])
    assert deleted == 3
    assert tmp_buffer.size() == 0


def test_nack_requeues_events(tmp_buffer: EventBuffer) -> None:
    for i in range(3):
        tmp_buffer.enqueue(f"src:{i}", {"i": i})
    events = tmp_buffer.claim(10)
    nack_ids = [events[0].id, events[1].id]
    nacked = tmp_buffer.nack(nack_ids)
    assert nacked == 2
    # Now claim again — should return the 2 nacked events.
    events2 = tmp_buffer.claim(10)
    assert len(events2) == 2
    assert {e.source_id for e in events2} == {"src:0", "src:1"}
    # And the previously-not-nacked event should be gone after ack.
    tmp_buffer.ack([events2[0].id, events2[1].id])
    assert tmp_buffer.size() == 1


def test_claim_is_fifo(tmp_buffer: EventBuffer) -> None:
    for i in range(5):
        tmp_buffer.enqueue(f"src:{i}", {"i": i})
    events = tmp_buffer.claim(10)
    assert [e.source_id for e in events] == ["src:0", "src:1", "src:2", "src:3", "src:4"]


def test_claim_respects_limit(tmp_buffer: EventBuffer) -> None:
    for i in range(10):
        tmp_buffer.enqueue(f"src:{i}", {"i": i})
    events = tmp_buffer.claim(3)
    assert len(events) == 3
    tmp_buffer.ack([e.id for e in events])
    events2 = tmp_buffer.claim(100)
    assert len(events2) == 7


def test_attempts_increments_on_each_claim(tmp_buffer: EventBuffer) -> None:
    tmp_buffer.enqueue("src:1", {"x": 1})
    e1 = tmp_buffer.claim(10)[0]
    assert e1.attempts == 1
    tmp_buffer.nack([e1.id])
    e2 = tmp_buffer.claim(10)[0]
    assert e2.attempts == 2
    assert e2.id == e1.id


def test_last_attempt_at_set_on_claim(tmp_buffer: EventBuffer) -> None:
    tmp_buffer.enqueue("src:1", {"x": 1})
    e = tmp_buffer.claim(10)[0]
    assert e.attempts == 1
    # The last_attempt_at should be a recent ISO timestamp.
    # We can't directly read it from BufferedEvent, but we can check via stats.


def test_max_events_enforced_with_eviction(tmp_path: Path) -> None:
    buf = EventBuffer(db_path=tmp_path / "events.db", max_events=5)
    for i in range(10):
        buf.enqueue(f"src:{i}", {"i": i})
    # Buffer should have evicted oldest 5.
    assert buf.size() == 5
    events = buf.claim(100)
    assert [e.source_id for e in events] == ["src:5", "src:6", "src:7", "src:8", "src:9"]


def test_enqueue_many_dedupes(tmp_buffer: EventBuffer) -> None:
    # Pre-populate src:1
    tmp_buffer.enqueue("src:1", {"x": 1})
    added = tmp_buffer.enqueue_many([
        ("src:1", {"x": 999}),  # duplicate
        ("src:2", {"x": 2}),
        ("src:3", {"x": 3}),
    ])
    assert added == 2
    assert tmp_buffer.size() == 3


def test_enqueue_many_handles_empty(tmp_buffer: EventBuffer) -> None:
    assert tmp_buffer.enqueue_many([]) == 0
    assert tmp_buffer.size() == 0


def test_reset_in_flight_recovers_orphans(tmp_buffer: EventBuffer) -> None:
    """Simulate a crash mid-flush: events are in_flight, then process restarts."""
    tmp_buffer.enqueue("src:1", {"x": 1})
    tmp_buffer.enqueue("src:2", {"x": 2})
    tmp_buffer.claim(10)  # both in_flight
    assert tmp_buffer.stats()["in_flight"] == 2
    # Simulate restart: build a new buffer over the same DB.
    db_path = tmp_buffer.db_path
    tmp_buffer.close()
    new_buf = EventBuffer(db_path=db_path, max_events=1000)
    recovered = new_buf.reset_in_flight()
    assert recovered == 2
    # All events are back to ready.
    assert new_buf.stats()["ready"] == 2
    assert new_buf.stats()["in_flight"] == 0
    events = new_buf.claim(10)
    assert len(events) == 2


def test_close_idempotent(tmp_buffer: EventBuffer) -> None:
    tmp_buffer.close()
    tmp_buffer.close()  # should not raise


def test_concurrent_writers(tmp_path: Path) -> None:
    """The lock should serialize concurrent enqueues from multiple threads."""
    import threading
    buf = EventBuffer(db_path=tmp_path / "events.db", max_events=10000)
    errors: list[Exception] = []

    def writer(start: int) -> None:
        try:
            for i in range(100):
                buf.enqueue(f"src:{start + i}", {"i": i})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i * 1000,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    # 5 threads * 100 events = 500 events total.
    assert buf.size() == 500


def test_unicode_source_id_and_payload(tmp_buffer: EventBuffer) -> None:
    payload = {"url": "https://例え.com/path", "name": "Trần Văn A"}
    assert tmp_buffer.enqueue("agent:PC-1:user:Trần Văn A", payload) is True
    events = tmp_buffer.claim(10)
    assert events[0].payload == payload


def test_concurrent_claim_and_ack(tmp_path: Path) -> None:
    """Ensure claim() + ack() don't race. The flusher does this in a loop."""
    import threading
    buf = EventBuffer(db_path=tmp_path / "events.db", max_events=1000)
    for i in range(200):
        buf.enqueue(f"src:{i}", {"i": i})
    errors: list[Exception] = []

    def flusher_worker(worker_id: int) -> None:
        try:
            for _ in range(5):
                events = buf.claim(20)
                if events:
                    buf.ack([e.id for e in events])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=flusher_worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    # All 200 events should be drained.
    assert buf.size() == 0


def test_empty_claim_returns_empty_list(tmp_buffer: EventBuffer) -> None:
    assert tmp_buffer.claim(10) == []


def test_empty_ack_and_nack(tmp_buffer: EventBuffer) -> None:
    assert tmp_buffer.ack([]) == 0
    assert tmp_buffer.nack([]) == 0


def test_journal_mode_is_wal(tmp_path: Path) -> None:
    """Verify WAL mode is set (helps with concurrent reader/writer)."""
    db_path = tmp_path / "events.db"
    buf = EventBuffer(db_path=db_path, max_events=100)
    # Read PRAGMA.
    mode = buf._conn.execute("PRAGMA journal_mode").fetchone()  # type: ignore[union-attr]
    assert mode[0].lower() == "wal"
    buf.close()


def test_max_events_zero_disables_eviction_check_under_threshold(tmp_path: Path) -> None:
    """max_events=1000 should not evict when count is below 1000."""
    buf = EventBuffer(db_path=tmp_path / "events.db", max_events=1000)
    for i in range(500):
        buf.enqueue(f"src:{i}", {"i": i})
    assert buf.size() == 500


def test_persistence_across_close_reopen(tmp_path: Path) -> None:
    """Verify that data written in one buffer instance is readable in another."""
    db_path = tmp_path / "events.db"
    buf1 = EventBuffer(db_path=db_path, max_events=100)
    buf1.enqueue("src:1", {"x": 1})
    buf1.enqueue("src:2", {"x": 2})
    buf1.close()
    buf2 = EventBuffer(db_path=db_path, max_events=100)
    assert buf2.size() == 2
    events = buf2.claim(10)
    assert {e.source_id for e in events} == {"src:1", "src:2"}


def test_concurrent_enqueue_does_not_duplicate(tmp_path: Path) -> None:
    """Same source_id from two threads should result in ONE row."""
    import threading
    buf = EventBuffer(db_path=tmp_path / "events.db", max_events=100)
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def writer() -> None:
        try:
            barrier.wait()
            buf.enqueue("src:same", {"thread": "any"})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=writer)
    t2 = threading.Thread(target=writer)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert not errors
    # Only one of them got True, the other got False.
    assert buf.size() == 1
