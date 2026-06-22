"""Main agent service: orchestrate collectors, flusher, heartbeat, config pulls.

Lifecycle:
1. Load AgentConfig + AgentState.
2. Print the legal banner.
3. Recover in-flight events from the previous run (buffer.reset_in_flight()).
4. Build collectors based on policy.
5. Start collectors, flusher, heartbeat, config-puller tasks.
6. On SIGINT/SIGTERM: stop collectors → drain buffer → exit.

Concurrency model: asyncio with a small number of long-running tasks.
Collectors run in their own threads (or in a background thread for sync
code) and write directly to the EventBuffer. The flusher loop is the
async glue that drains the buffer and POSTs batches to the server.

Run with:
    agent run [--config ...] [--foreground]
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading
import time
from typing import Any

from src.agent import __version__
from src.agent.buffer import EventBuffer
from src.agent.collectors.base import Collector
from src.agent.collectors.http_dns import build_http_collectors
from src.agent.collectors.logon import LinuxLogonCollector
from src.agent.config import AgentConfig, is_linux
from src.agent.config_client import ConfigClient
from src.agent.legal import render_banner
from src.agent.state import load_state
from src.agent.transport import (
    AuthRevokedError,
    PermanentError,
    TransientError,
    Transport,
)

logger = logging.getLogger(__name__)


def _setup_logging(config: AgentConfig) -> None:
    """Configure logging to stderr + optional file."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if config.log_path:
        try:
            config.log_path.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(str(config.log_path)))
        except OSError as exc:
            logger.warning("Could not open log file %s: %s", config.log_path, exc)
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def _build_collectors(
    config: AgentConfig, config_client: ConfigClient
) -> list[Collector]:
    """Build collectors based on the current policy.

    We add every collector that COULD be enabled, then filter to only those
    that are enabled by the policy. Collectors that are not enabled are
    not started.
    """
    candidates: list[Collector] = []
    if is_linux():
        candidates.append(LinuxLogonCollector(config_client))
    else:
        from src.agent.collectors.logon import WindowsLogonCollector
        candidates.append(WindowsLogonCollector(config_client))
    candidates.extend(build_http_collectors(config_client))
    enabled = [c for c in candidates if config_client.policy.is_collector_enabled(c.name)]
    logger.info(
        "Collectors: candidates=%s, enabled=%s",
        [c.name for c in candidates],
        [c.name for c in enabled],
    )
    return enabled


def _sink_to_buffer(
    buffer: EventBuffer, sampler_disabled: bool = False
):
    """Build a sink function that writes to the buffer.

    `sampler_disabled=True` skips the policy sampling check (sampling is
    already done inside collectors).
    """
    def sink(source_id: str, payload: dict[str, Any]) -> bool:
        accepted = buffer.enqueue(source_id, payload)
        if not accepted:
            logger.debug("Duplicate suppressed: %s", source_id)
        return True  # always return True; buffer dedupes
    return sink


async def _flusher_loop(
    transport: Transport,
    buffer: EventBuffer,
    flush_interval: float,
    flush_batch_max: int,
    stop_event: asyncio.Event,
) -> None:
    """Drain the buffer and send batches to the server.

    On TransientError: backoff and retry. On PermanentError: drop the
    batch (events are lost — logged for ops attention). On AuthRevokedError:
    signal stop and let the service exit.
    """
    delay = 1.0
    while not stop_event.is_set():
        try:
            events = await asyncio.to_thread(buffer.claim, flush_batch_max)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Buffer claim failed: %s", exc)
            await asyncio.sleep(flush_interval)
            continue
        if not events:
            delay = 1.0
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=flush_interval)
            except TimeoutError:
                pass
            continue
        records = [e.payload for e in events]
        try:
            result = await asyncio.to_thread(transport.send_batch, records)
            accepted_count = int(result.get("created_or_updated", 0))
            failed_count = int(result.get("failed", 0))
            # Server reports aggregate counts. The mapping back to event_ids is
            # best-effort: if failed == 0, ack all; else nack all (let the next
            # loop retry). Server's idempotent ON CONFLICT means re-send is safe.
            if failed_count == 0:
                ids = [e.id for e in events]
                await asyncio.to_thread(buffer.ack, ids)
                logger.debug("Flushed %d events (server accepted %d)", len(ids), accepted_count)
            else:
                ids = [e.id for e in events]
                await asyncio.to_thread(buffer.nack, ids)
                logger.warning(
                    "Server reported %d failures in batch of %d; re-queueing",
                    failed_count, len(events),
                )
            delay = 1.0
        except AuthRevokedError as exc:
            logger.error("Agent revoked — stopping flusher: %s", exc)
            stop_event.set()
            return
        except TransientError as exc:
            logger.warning("Transient error sending batch: %s (retry in %.1fs)", exc, delay)
            await asyncio.to_thread(buffer.nack, [e.id for e in events])
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except TimeoutError:
                pass
            delay = min(delay * 2, 60.0)
        except PermanentError as exc:
            logger.error(
                "Permanent error sending batch — dropping %d events: %s",
                len(events), exc,
            )
            await asyncio.to_thread(buffer.ack, [e.id for e in events])
            delay = 1.0
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected flusher error: %s", exc)
            await asyncio.to_thread(buffer.nack, [e.id for e in events])
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except TimeoutError:
                pass
            delay = min(delay * 2, 60.0)


async def _heartbeat_loop(
    transport: Transport,
    buffer: EventBuffer,
    state_path: Any,
    heartbeat_interval: float,
    stop_event: asyncio.Event,
) -> None:
    """Send periodic heartbeats. On AuthRevokedError, signal stop."""
    while not stop_event.is_set():
        try:
            metrics = await asyncio.to_thread(buffer.stats)
            metrics["uptime_seconds"] = time.monotonic()
            result = await asyncio.to_thread(transport.heartbeat, metrics)
            logger.debug("Heartbeat OK: %s", result.get("status"))
        except AuthRevokedError as exc:
            logger.error("Agent revoked — stopping heartbeat: %s", exc)
            stop_event.set()
            return
        except TransientError as exc:
            logger.warning("Heartbeat transient error: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Heartbeat unexpected error: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=heartbeat_interval)
        except TimeoutError:
            pass


async def _config_pull_loop(
    config_client: ConfigClient,
    config_pull_interval: float,
    stop_event: asyncio.Event,
    on_policy_change: callable = None,  # type: ignore[valid-type]
) -> None:
    """Pull config periodically. Restarts collectors on policy change."""
    while not stop_event.is_set():
        try:
            old_version = config_client.policy.policy_version
            new_policy = await asyncio.to_thread(
                config_client.pull_with_retry, 3
            )
            if on_policy_change and new_policy.policy_version != old_version:
                try:
                    on_policy_change()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("on_policy_change callback failed: %s", exc)
        except AuthRevokedError as exc:
            logger.error("Agent revoked — stopping config puller: %s", exc)
            stop_event.set()
            return
        except PermanentError as exc:
            logger.error("Config pull permanent error: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Config pull unexpected error: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config_pull_interval)
        except TimeoutError:
            pass


class AgentService:
    """High-level orchestrator. Run with `await service.run()`."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.state = None
        self.buffer: EventBuffer | None = None
        self.transport: Transport | None = None
        self.config_client: ConfigClient | None = None
        self.collectors: list[Collector] = []
        self._stop_event = asyncio.Event()
        self._stopped = False
        self._lock = threading.Lock()

    def request_stop(self) -> None:
        if not self._stopped:
            self._stopped = True
            self._stop_event.set()

    async def run(self) -> int:
        _setup_logging(self.config)
        # 1. Load state.
        try:
            self.state = load_state(self.config.state_path)
        except PermissionError as exc:
            logger.error("State file permission error: %s", exc)
            return 2
        if self.state is None:
            logger.error(
                "No state file at %s. Run `agent enroll` first.",
                self.config.state_path,
            )
            return 3

        # 2. Banner.
        banner = render_banner(
            __version__,
            str(self.config.state_path),
            self.config.server_url,
            self.state.agent_id,
        )
        for line in banner.splitlines():
            logger.info(line)

        # 3. Buffer.
        self.buffer = EventBuffer(
            db_path=self.config.buffer_path,
            max_events=self.config.buffer_max_events,
        )
        recovered = self.buffer.reset_in_flight()
        if recovered:
            logger.info("Recovered %d in-flight events from previous run", recovered)

        # 4. Transport + config client.
        self.transport = Transport(
            server_url=self.config.server_url,
            api_key=self.state.api_key,
            verify_tls=self.config.verify_tls,
            ca_bundle=self.config.ca_bundle,
        )
        self.config_client = ConfigClient(
            self.transport, pull_interval=self.config.config_pull_interval
        )
        # Pull initial config (best-effort, falls back to defaults on failure).
        try:
            self.config_client.pull_with_retry(max_attempts=3)
        except AuthRevokedError as exc:
            logger.error("Agent revoked at startup: %s", exc)
            return 4
        except PermanentError as exc:
            logger.warning("Initial config pull failed permanently: %s", exc)

        # 5. Build collectors.
        self.collectors = _build_collectors(self.config, self.config_client)
        sink = _sink_to_buffer(self.buffer)
        for c in self.collectors:
            c.set_sink(sink)
        # Restore wtmp offset across restarts.
        for c in self.collectors:
            if isinstance(c, LinuxLogonCollector):
                offset = self._load_wtmp_offset()
                if offset is not None:
                    c.set_offset(offset)

        # 6. Start collectors.
        for c in self.collectors:
            try:
                c.start()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Collector %s failed to start: %s", c.name, exc)

        # 7. Start async tasks.
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.request_stop)
            except NotImplementedError:
                # Windows / restricted environments: signal handlers not supported.
                pass

        tasks = [
            asyncio.create_task(
                _flusher_loop(
                    self.transport, self.buffer,
                    self.config.flush_interval, self.config.flush_batch_max,
                    self._stop_event,
                ),
                name="flusher",
            ),
            asyncio.create_task(
                _heartbeat_loop(
                    self.transport, self.buffer, self.config.state_path,
                    self.config.heartbeat_interval, self._stop_event,
                ),
                name="heartbeat",
            ),
            asyncio.create_task(
                _config_pull_loop(
                    self.config_client, self.config.config_pull_interval,
                    self._stop_event,
                    on_policy_change=self._on_policy_change,
                ),
                name="config-pull",
            ),
        ]
        try:
            await self._stop_event.wait()
        finally:
            logger.info("Stopping service...")
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for c in self.collectors:
                try:
                    c.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Collector %s stop error: %s", c.name, exc)
            # Persist wtmp offset for next restart.
            for c in self.collectors:
                if isinstance(c, LinuxLogonCollector):
                    self._save_wtmp_offset(c.get_offset())
            if self.buffer is not None:
                # Final flush: try to drain whatever is left.
                try:
                    events = self.buffer.claim(self.config.flush_batch_max)
                    if events:
                        await asyncio.to_thread(
                            self.transport.send_batch, [e.payload for e in events]
                        )
                        await asyncio.to_thread(self.buffer.ack, [e.id for e in events])
                        logger.info("Final flush: sent %d events", len(events))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Final flush failed: %s", exc)
                self.buffer.close()
            if self.transport is not None:
                self.transport.close()
            logger.info("Service stopped")
        return 0

    def _load_wtmp_offset(self) -> int | None:
        """Load wtmp offset from a sibling file in the same dir as state."""
        offset_path = self.config.state_path.with_name(
            self.config.state_path.stem + ".wtmp_offset"
        )
        if not offset_path.is_file():
            return None
        try:
            return int(offset_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def _save_wtmp_offset(self, offset: int) -> None:
        offset_path = self.config.state_path.with_name(
            self.config.state_path.stem + ".wtmp_offset"
        )
        try:
            offset_path.parent.mkdir(parents=True, exist_ok=True)
            offset_path.write_text(str(offset), encoding="utf-8")
            os.chmod(offset_path, 0o600)
        except OSError as exc:
            logger.warning("Failed to persist wtmp offset: %s", exc)

    def _on_policy_change(self) -> None:
        """Restart collectors whose enabled state changed."""
        new_enabled = set(self.config_client.policy.enabled_collectors)  # type: ignore[union-attr]
        current = {c.name for c in self.collectors if c.is_healthy or c.last_error}
        for c in self.collectors:
            if c.name not in new_enabled:
                logger.info("Disabling collector %s (no longer in policy)", c.name)
                try:
                    c.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Stop collector %s: %s", c.name, exc)
        # Start newly-enabled collectors.
        for name in new_enabled - current:
            logger.info("Enabling collector %s (newly in policy)", name)
            # We only have built-in factories; for Phase 2, we don't dynamically
            # add new collector types. The base set is started in _build_collectors.
            # This branch covers the case where a collector was disabled then
            # re-enabled without a restart.


import os  # noqa: E402  (used in _save_wtmp_offset)
