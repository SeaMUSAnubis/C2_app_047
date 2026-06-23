"""Config client: pulls /api/agents/me/config periodically.

The agent keeps a local copy of the policy + blocklist so collectors can
match without hitting the network. Pulls happen on:
- startup
- every `config_pull_interval` seconds (default 5 minutes)
- on-demand when the caller wants to refresh (used by enroll flow)

Threading: the config cache is read by collectors from any thread, written
by the config puller. We guard with a lock and never modify in place — we
swap the whole dict atomically.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from agent.transport import PermanentError, TransientError, Transport

logger = logging.getLogger(__name__)


@dataclass
class BlocklistEntry:
    pattern: str
    pattern_type: str = "domain"  # domain, url, ip, regex
    category: str | None = None
    reason: str | None = None

    def matches(self, value: str) -> bool:
        """Case-insensitive substring/domain match for 'domain' type.

        For 'domain': exact or suffix match (e.g. pattern "evil.com" matches
        "api.evil.com" and "EVIL.COM" but NOT "notevil.com").
        For 'url'/'ip': case-insensitive substring match.
        For 'regex': full regex match (caller must have validated regex).
        For unknown types: fallback to substring match (conservative).
        """
        if not value:
            return False
        v = value.strip().lower()
        p = self.pattern.strip().lower()
        if self.pattern_type == "domain":
            return v == p or v.endswith("." + p)
        if self.pattern_type in ("url", "ip"):
            return p in v
        if self.pattern_type == "regex":
            import re

            try:
                return re.search(p, value) is not None
            except re.error:
                return False
        # Unknown type — conservative substring match.
        return p in v


@dataclass
class AgentPolicy:
    policy_version: int = 0
    sampling_rate: int = 100  # 1..100, percent
    enabled_collectors: list[str] = field(default_factory=list)
    blocklist: list[BlocklistEntry] = field(default_factory=list)

    def is_collector_enabled(self, name: str) -> bool:
        return name in self.enabled_collectors

    def should_sample(self) -> bool:
        """Return True if the next event should be kept, False to drop.

        With sampling_rate=100, always keep. With sampling_rate=50, keep
        ~50% of events (each call has 50% chance to return True).
        """
        if self.sampling_rate >= 100:
            return True
        if self.sampling_rate <= 0:
            return False
        import random

        return random.randint(1, 100) <= self.sampling_rate


class ConfigClient:
    """Manages a thread-safe local cache of the agent's policy + blocklist."""

    def __init__(self, transport: Transport, pull_interval: float = 300.0):
        self._transport = transport
        self._pull_interval = pull_interval
        self._lock = threading.Lock()
        self._policy = AgentPolicy()
        self._last_pull: float = 0.0
        self._last_error: str | None = None
        self._last_pull_at: str | None = None
        self._server_time: str | None = None

    @property
    def policy(self) -> AgentPolicy:
        with self._lock:
            return self._policy

    @property
    def last_pull_at(self) -> str | None:
        with self._lock:
            return self._last_pull_at

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def is_blocked(self, url_or_domain: str) -> tuple[bool, BlocklistEntry | None]:
        """Check if a URL/domain matches any enabled blocklist pattern.

        Returns (matched, entry). `entry` is the first matching rule.
        """
        with self._lock:
            entries = list(self._policy.blocklist)
        for entry in entries:
            if entry.matches(url_or_domain):
                return True, entry
        return False, None

    def needs_pull(self) -> bool:
        return (time.monotonic() - self._last_pull) >= self._pull_interval

    def pull(self) -> AgentPolicy:
        """Fetch the current config from the server. Returns the new policy.

        Raises:
            TransientError / PermanentError / AuthRevokedError from transport.
        """
        logger.debug("Pulling agent config from %s", self._transport._server_url)
        data = self._transport.get_config()
        new_policy = self._parse(data)
        with self._lock:
            old_version = self._policy.policy_version
            self._policy = new_policy
            self._last_pull = time.monotonic()
            self._last_pull_at = data.get("server_time")
            self._server_time = data.get("server_time")
            self._last_error = None
        if new_policy.policy_version != old_version:
            logger.info(
                "Policy version changed: %d -> %d (collectors=%s, sampling=%d%%, blocklist=%d)",
                old_version, new_policy.policy_version,
                new_policy.enabled_collectors, new_policy.sampling_rate,
                len(new_policy.blocklist),
            )
        return new_policy

    def pull_with_retry(self, max_attempts: int = 3) -> AgentPolicy:
        """Pull config with exponential backoff. Returns cached policy on total failure."""
        import random

        delay = 1.0
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self.pull()
            except TransientError as exc:
                last_exc = exc
                logger.warning(
                    "Config pull attempt %d/%d failed: %s (retry in %.1fs)",
                    attempt, max_attempts, exc, delay,
                )
                time.sleep(delay + random.uniform(0, 0.5))
                delay = min(delay * 2, 30.0)
            except PermanentError:
                raise
        with self._lock:
            self._last_error = str(last_exc) if last_exc else "unknown"
        logger.error("Config pull failed after %d attempts; using cached policy", max_attempts)
        return self._policy

    @staticmethod
    def _parse(data: dict[str, Any]) -> AgentPolicy:
        blocklist_raw = data.get("blocklist") or []
        blocklist: list[BlocklistEntry] = []
        for item in blocklist_raw:
            try:
                blocklist.append(BlocklistEntry(
                    pattern=str(item["pattern"]),
                    pattern_type=str(item.get("pattern_type", "domain")),
                    category=item.get("category"),
                    reason=item.get("reason"),
                ))
            except KeyError:
                continue
        enabled = data.get("enabled_collectors") or []
        return AgentPolicy(
            policy_version=int(data.get("policy_version", 0)),
            sampling_rate=max(1, min(100, int(data.get("sampling_rate", 100)))),
            enabled_collectors=[str(x) for x in enabled],
            blocklist=blocklist,
        )
