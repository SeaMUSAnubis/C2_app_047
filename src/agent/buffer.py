"""Local SQLite buffer for events waiting to be sent to the server.

Design:
- One row per event. `source_id` is unique — collectors may emit duplicates
  on retry; the buffer silently dedupes.
- Two queues coexist in the same table:
  * `state = 0`  → ready to send
  * `state = 1`  → in-flight (claimed by a flusher, will be deleted on success
                   or re-queued on failure)
- One row per event lets us atomically claim + delete on success, and
  re-queue on failure. No in-memory queue means a crash mid-flush does not
  lose the in-flight batch: the next flush picks them up again.
- The buffer enforces `max_events` by evicting the oldest rows first.

Threading: all access goes through `_lock` so multiple threads (e.g. collectors
running in `to_thread`) cannot race with the flusher.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    state INTEGER NOT NULL DEFAULT 0,    -- 0=ready, 1=in_flight
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_state_id ON events(state, id);
"""


@dataclass
class BufferedEvent:
    id: int
    source_id: str
    payload: dict[str, Any]
    attempts: int = 0


class EventBuffer:
    """Persistent FIFO queue for events awaiting server delivery."""

    def __init__(self, db_path: Path, max_events: int = 100_000):
        self.db_path = db_path
        self.max_events = max_events
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,  # autocommit, we manage transactions explicitly
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        assert self._conn is not None, "Buffer closed"
        with self._lock:
            conn = self._conn
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------------
    # Producer API (called by collectors)
    # ------------------------------------------------------------------

    def enqueue(self, source_id: str, payload: dict[str, Any]) -> bool:
        """Add an event. Returns False if source_id is a duplicate."""
        now = datetime.now(UTC).isoformat()
        try:
            with self._tx() as conn:
                conn.execute(
                    """
                    INSERT INTO events (source_id, payload_json, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (source_id, json.dumps(payload, sort_keys=True), now),
                )
                # Enforce max_events: evict oldest if over limit.
                row = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()
                count = int(row["c"]) if row else 0
                if count > self.max_events:
                    overflow = count - self.max_events
                    conn.execute(
                        """
                        DELETE FROM events WHERE id IN (
                            SELECT id FROM events ORDER BY id ASC LIMIT ?
                        )
                        """,
                        (overflow,),
                    )
            return True
        except sqlite3.IntegrityError:
            return False

    def enqueue_many(self, items: list[tuple[str, dict[str, Any]]]) -> int:
        """Bulk enqueue. Returns count of NEW rows added (excluding duplicates)."""
        if not items:
            return 0
        now = datetime.now(UTC).isoformat()
        rows = [
            (source_id, json.dumps(payload, sort_keys=True), now)
            for source_id, payload in items
        ]
        with self._tx() as conn:
            before = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
            conn.executemany(
                """
                INSERT OR IGNORE INTO events (source_id, payload_json, created_at)
                VALUES (?, ?, ?)
                """,
                rows,
            )
            after = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
            added = after - before
            # Evict overflow.
            if after > self.max_events:
                overflow = after - self.max_events
                conn.execute(
                    """
                    DELETE FROM events WHERE id IN (
                        SELECT id FROM events ORDER BY id ASC LIMIT ?
                    )
                    """,
                    (overflow,),
                )
        return int(added)

    def size(self) -> int:
        with self._lock:
            assert self._conn is not None
            row = self._conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()
        return int(row["c"]) if row else 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            assert self._conn is not None
            total = self._conn.execute(
                "SELECT COUNT(*) AS c FROM events"
            ).fetchone()["c"]
            in_flight = self._conn.execute(
                "SELECT COUNT(*) AS c FROM events WHERE state = 1"
            ).fetchone()["c"]
        return {"total": int(total), "in_flight": int(in_flight), "ready": int(total) - int(in_flight)}

    # ------------------------------------------------------------------
    # Consumer API (called by the flusher)
    # ------------------------------------------------------------------

    def claim(self, limit: int) -> list[BufferedEvent]:
        """Claim up to `limit` ready events and mark them in_flight.

        The events are returned in FIFO order. They will be deleted on a
        subsequent ack() call, or put back on nack().

        Implementation: UPDATE first (mark in_flight + bump attempts), then
        SELECT to read the post-UPDATE state. The BufferedEvent's `attempts`
        field reflects the value AFTER this claim.
        """
        with self._tx() as conn:
            # Find candidate ids in FIFO order.
            id_rows = conn.execute(
                """
                SELECT id FROM events WHERE state = 0
                ORDER BY id ASC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            if not id_rows:
                return []
            ids = [r["id"] for r in id_rows]
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE events SET state = 1, attempts = attempts + 1, "
                f"last_attempt_at = ? WHERE id IN ({placeholders})",
                [datetime.now(UTC).isoformat(), *ids],
            )
            # Re-read so the returned BufferedEvent reflects the new attempts.
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                f"SELECT id, source_id, payload_json, attempts "
                f"FROM events WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        return [
            BufferedEvent(
                id=r["id"],
                source_id=r["source_id"],
                payload=json.loads(r["payload_json"]),
                attempts=r["attempts"],
            )
            for r in rows
        ]

    def ack(self, event_ids: list[int]) -> int:
        """Delete the given event ids (successfully sent). Returns count deleted."""
        if not event_ids:
            return 0
        with self._tx() as conn:
            placeholders = ",".join("?" * len(event_ids))
            cur = conn.execute(
                f"DELETE FROM events WHERE id IN ({placeholders})",
                event_ids,
            )
        return int(cur.rowcount or 0)

    def nack(self, event_ids: list[int]) -> int:
        """Re-queue in_flight events back to ready (send failed). Returns count."""
        if not event_ids:
            return 0
        with self._tx() as conn:
            placeholders = ",".join("?" * len(event_ids))
            cur = conn.execute(
                f"UPDATE events SET state = 0 WHERE id IN ({placeholders})",
                event_ids,
            )
        return int(cur.rowcount or 0)

    def reset_in_flight(self) -> int:
        """Recover any events that were in_flight when the previous process died.

        Returns count of events re-queued. Call once at startup.
        """
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE events SET state = 0, last_attempt_at = ? WHERE state = 1",
                (datetime.now(UTC).isoformat(),),
            )
        return int(cur.rowcount or 0)
