"""HTTP / DNS block collector.

Two collector variants in this module:

1. `DomainCheckCollector` — programmatic collector: tests or other components
   call `check_domain(domain, url=None)` and the collector emits an `http`
   event with action `allowed` or `blocked`. Useful for:
   - testing the blocklist logic without a real DNS packet capture
   - integration with browser extensions that know the full URL
   - in-app hooks for HTTP libraries

2. `DnsSniffCollector` (Linux, requires root) — listens on a raw socket for
   DNS queries to UDP/53 and emits one event per query. Requires either
   `setcap cap_net_raw,cap_net_bind_service=+ep` on the python binary, or
   running the agent as root. Marked as advanced; not active by default.

For Windows, the Windows HTTP collector (WFP / ETW-based) is not implemented
in Phase 2. We rely on DomainCheckCollector being driven by browser
extensions or other integrations.

The DNS collector and the domain-check collector share the same emit logic,
factored into a helper.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
from datetime import UTC, datetime
from typing import Any

from agent.collectors.base import Collector

logger = logging.getLogger(__name__)


class _HttpBlockMixin:
    """Shared block-check + emit logic for HTTP / DNS collectors."""

    @staticmethod
    def _classify(config_client: Any, value: str) -> tuple[bool, dict[str, Any] | None]:
        """Return (blocked, block_info) for a domain or URL."""
        is_blocked, entry = config_client.is_blocked(value)
        if not is_blocked or entry is None:
            return False, None
        return True, {
            "pattern": entry.pattern,
            "pattern_type": entry.pattern_type,
            "category": entry.category,
            "reason": entry.reason,
        }

    def _emit_http(
        self,
        source_id: str,
        value: str,
        *,
        user_id: str | None,
        device_id: str | None,
        action: str,
        block_info: dict[str, Any] | None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        url = value if value.startswith(("http://", "https://")) else value
        domain = value
        # Lightweight URL → domain extraction without urllib.
        for prefix in ("https://", "http://"):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
                break
        if "/" in domain:
            domain = domain.split("/", 1)[0]
        if domain.startswith("www."):
            domain = domain[4:]
        raw_payload: dict[str, Any] = {
            "url": url,
            "domain": domain,
            "action": action,
        }
        if block_info:
            raw_payload.update({
                "block_pattern": block_info["pattern"],
                "block_category": block_info.get("category"),
                "block_reason": block_info.get("reason"),
            })
        return self.emit(  # type: ignore[attr-defined]
            source_id=source_id,
            event_type="http",
            timestamp=datetime.now(UTC).isoformat(),
            raw_payload=raw_payload,
            user_id=user_id,
            device_id=device_id,
            action=action,
            resource=url,
            metadata={
                "source": metadata.get("source", "agent") if metadata else "agent",
                **(metadata or {}),
            },
        )


class DomainCheckCollector(_HttpBlockMixin, Collector):
    """Programmatic HTTP collector. The service drives it via `check_domain`.

    Used by:
    - Tests (no real DNS required)
    - Browser extensions that push the URL to the agent via a local socket
    - Any in-app code that wants to evaluate a URL against the blocklist
    """

    name = "http"

    def __init__(self, config_client: Any):
        super().__init__(config_client)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._hostname = ""
        self._running_user = ""
        self._queue: list[tuple[str, str, str | None]] = []  # (value, source_tag, user_id)
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._hostname = socket.gethostname()
        try:
            import getpass
            self._running_user = getpass.getuser()
        except Exception:
            self._running_user = ""
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="http-domain-check", daemon=True
        )
        self._thread.start()
        logger.info("DomainCheckCollector started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def check_domain(
        self, value: str, user_id: str | None = None,
        source_tag: str = "manual",
    ) -> None:
        """Queue a value (domain or URL) for blocklist evaluation.

        Non-blocking. The collector's worker thread picks the value up and
        emits the corresponding event.
        """
        if not value:
            return
        with self._lock:
            self._queue.append((value, source_tag, user_id or self._running_user or None))

    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    def _drain(self) -> list[tuple[str, str, str | None]]:
        with self._lock:
            items = self._queue[:]
            self._queue.clear()
        return items

    def _run(self) -> None:
        while not self._stop.is_set():
            items = self._drain()
            if not items:
                self._stop.wait(0.5)
                continue
            for value, source_tag, user_id in items:
                try:
                    self._evaluate(value, user_id, source_tag)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("HTTP evaluation failed for %r: %s", value, exc)


class _BaseEvaluateMixin(_HttpBlockMixin):
    """Provides the _evaluate method used by DomainCheckCollector worker."""

    def _evaluate(self, value: str, user_id: str | None, source_tag: str) -> None:
        # Extract the domain from a URL for blocklist matching. URLs like
        # "https://wikileaks.org/path" would otherwise fail a domain-suffix
        # match against "wikileaks.org".
        match_value = value
        for prefix in ("https://", "http://"):
            if match_value.startswith(prefix):
                match_value = match_value[len(prefix):]
                break
        if "/" in match_value:
            match_value = match_value.split("/", 1)[0]
        if match_value.startswith("www."):
            match_value = match_value[4:]
        is_blocked, block_info = self._classify(self._config, match_value)  # type: ignore[attr-defined]
        action = "blocked" if is_blocked else "allowed"
        # Source id: tag the source so we can dedupe across the network stack.
        # In production, the caller would also include a process pid / uid.
        source_id = (
            f"agent:{self._hostname}:http:{source_tag}:{value}:{int(datetime.now(UTC).timestamp() * 1000)}"
        )
        self._emit_http(
            source_id=source_id,
            value=value,
            user_id=user_id,
            device_id=self._hostname,
            action=action,
            block_info=block_info,
            metadata={"source": source_tag},
        )


# Attach the _evaluate method to DomainCheckCollector.
DomainCheckCollector._evaluate = _BaseEvaluateMixin._evaluate  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# DNS sniff collector (Linux, requires root) — Phase 2 advanced
# ---------------------------------------------------------------------------


class DnsSniffCollector(_HttpBlockMixin, Collector):
    """Listen on UDP/53 and emit one event per DNS query.

    Requires:
    - Linux
    - root or `setcap cap_net_raw,cap_net_bind_service=+ep` on the python
      binary
    - iptables rule: iptables -t nat -A OUTPUT -p udp --dport 53
        -j REDIRECT --to-ports 5353
      (and similar for IPv6) to redirect system DNS to this listener.
      The agent will NOT set this rule automatically — that's an operator
      task. Without the redirect, this collector captures nothing.

    This collector is marked advanced and is not started unless explicitly
    enabled in the agent config. It uses `dnspython` if available, falling
    back to a minimal manual parser.
    """

    name = "http_dns_sniff"

    def __init__(
        self, config_client: Any, listen_port: int = 5353,
        poll_interval: float = 1.0,
    ):
        super().__init__(config_client)
        self._port = listen_port
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._hostname = ""

    def start(self) -> None:
        if os.geteuid() != 0:  # type: ignore[attr-defined, no-any-return]
            self.mark_unhealthy("DnsSniffCollector requires root")
            return
        if self._thread is not None:
            return
        self._hostname = socket.gethostname()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="dns-sniff", daemon=True
        )
        self._thread.start()
        logger.info("DnsSniffCollector started on port %d", self._port)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", self._port))
        except OSError as exc:
            self.mark_unhealthy(f"bind port {self._port} failed: {exc}")
            sock.close()
            return
        sock.settimeout(1.0)
        self.mark_healthy()
        while not self._stop.is_set():
            try:
                data, addr = sock.recvfrom(4096)
            except TimeoutError:
                continue
            except OSError as exc:
                self.mark_unhealthy(f"recvfrom: {exc}")
                break
            try:
                domain = self._parse_query(data)
            except Exception:  # noqa: BLE001
                continue
            if not domain:
                continue
            is_blocked, block_info = self._classify(self._config, domain)
            action = "blocked" if is_blocked else "allowed"
            source_id = f"agent:{self._hostname}:dns:{domain}:{int(datetime.now(UTC).timestamp() * 1000)}"
            self._emit_http(
                source_id=source_id,
                value=domain,
                user_id=None,
                device_id=self._hostname,
                action=action,
                block_info=block_info,
                metadata={"source": "dns_sniff", "client_ip": addr[0] if addr else None},
            )
        sock.close()

    @staticmethod
    def _parse_query(data: bytes) -> str | None:
        """Parse a DNS query and return the queried domain (lowercased).

        DNS header: 12 bytes. Question starts at offset 12, sequence of
        length-prefixed labels (each label: 1 byte length + N bytes data,
        terminated by a zero-length label).
        """
        if len(data) < 12:
            return None
        i = 12
        labels: list[str] = []
        # Defensive: cap iterations to prevent infinite loops on malformed input.
        for _ in range(128):
            if i >= len(data):
                return None
            ln = data[i]
            if ln == 0:
                break
            if ln & 0xC0:  # pointer (compression) — skip for queries
                return None
            i += 1
            if i + ln > len(data):
                return None
            labels.append(data[i:i + ln].decode("utf-8", errors="replace"))
            i += ln
        return ".".join(labels).lower() if labels else None


def build_http_collectors(config_client: Any) -> list[Collector]:
    """Factory: build the HTTP collector(s) that should run for this policy."""
    collectors: list[Collector] = []
    if config_client.policy.is_collector_enabled("http"):
        collectors.append(DomainCheckCollector(config_client))
    if config_client.policy.is_collector_enabled("http_dns_sniff"):
        from agent.config import is_linux
        if is_linux():
            collectors.append(DnsSniffCollector(config_client))
    return collectors
