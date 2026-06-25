"""Collector base class.

A Collector is anything that produces RawLogIngest-compatible events.
Lifecycle:
1. The service instantiates collectors based on policy.enabled_collectors.
2. `start()` begins emitting events; events are passed to the sink callback.
3. `stop()` halts emission; clean up OS handles / threads.
4. Errors inside a collector should NOT crash the agent; they should be
   logged and the collector should attempt to restart (or be marked broken).

The collector base class provides:
- A `register_emit` hook to plug a sink (in production, the EventBuffer).
- An `enqueue` helper that applies the sampling rate and blocklist check.
- A `should_run` helper that respects enabled_collectors.
- An abstract `start/stop/health_check` interface.
"""

from __future__ import annotations

import abc
import logging
import socket
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from agent.config_client import ConfigClient

logger = logging.getLogger(__name__)

# Sink signature: sink(source_id, payload_dict) -> bool
# Returns True on success, False if dropped (e.g. sampling).
SinkFn = Callable[[str, dict[str, Any]], bool]


class Collector(abc.ABC):
    """Base class for collectors."""

    name: str = "unknown"

    def __init__(self, config_client: ConfigClient):
        self._config = config_client
        self._sink: SinkFn | None = None
        self._stopped = False
        self._healthy = True
        self._last_error: str | None = None

    def set_sink(self, sink: SinkFn) -> None:
        self._sink = sink

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def is_enabled(self) -> bool:
        return self._config.policy.is_collector_enabled(self.name)

    def emit(
        self,
        source_id: str,
        event_type: str,
        timestamp: str,
        raw_payload: dict[str, Any],
        user_id: str | None = None,
        device_id: str | None = None,
        action: str | None = None,
        resource: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Emit an event to the sink. Returns True if accepted, False if dropped.

        Honors sampling_rate from the policy. The sink is the EventBuffer.enqueue
        function; events rejected by the sink (duplicates) still return True
        (the buffer deduped them).
        """
        if not self._sink:
            logger.warning("Collector %s has no sink; dropping event", self.name)
            return False
        if not self.is_enabled():
            return False
        if not self._config.policy.should_sample():
            return False
        payload = {
            "source_id": source_id,
            "collector_type": "endpoint_agent",
            "event_type": event_type,
            "timestamp": timestamp,
            "user_id": user_id,
            "device_id": device_id,
            "action": action,
            "resource": resource,
            "raw_payload": raw_payload,
            "ingest_metadata": {
                "agent_collector": self.name,
                "agent_hostname": socket.gethostname(),
                "emitted_at": datetime.now(UTC).isoformat(),
                **(metadata or {}),
            },
        }
        try:
            return bool(self._sink(source_id, payload))
        except Exception:
            logger.exception("Sink raised on emit (source_id=%s)", source_id)
            return False

    def mark_unhealthy(self, error: str) -> None:
        self._healthy = False
        self._last_error = error
        logger.error("Collector %s marked unhealthy: %s", self.name, error)

    def mark_healthy(self) -> None:
        self._healthy = True
        self._last_error = None

    @abc.abstractmethod
    def start(self) -> None:
        """Begin emitting events. Must be non-blocking (use threads/async)."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop emitting events. Idempotent. Must complete within a few seconds."""

    def health_check(self) -> bool:
        """Return True if the collector is healthy. Default: self._healthy."""
        return self._healthy
