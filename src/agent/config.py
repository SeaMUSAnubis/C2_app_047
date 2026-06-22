"""Agent configuration loaded from env vars and CLI args.

Precedence: CLI > env > default. Sensitive values (api_key) are loaded from
the state file, NOT from env, to avoid leaking them through process listings.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path("/var/lib/ueba-agent/state.json")
DEFAULT_BUFFER_PATH = Path("/var/lib/ueba-agent/buffer.db")
DEFAULT_LOG_PATH = Path("/var/log/ueba-agent/agent.log")

HEARTBEAT_INTERVAL_SECONDS = 60
CONFIG_PULL_INTERVAL_SECONDS = 300
FLUSH_INTERVAL_SECONDS = 10
FLUSH_BATCH_MAX = 500
BUFFER_MAX_EVENTS = 100_000


@dataclass
class AgentConfig:
    """Runtime configuration for the agent. All fields have safe defaults."""

    server_url: str = "http://localhost:8000"
    state_path: Path = field(default_factory=lambda: Path(os.environ.get(
        "AGENT_STATE_PATH", str(DEFAULT_STATE_PATH))))
    buffer_path: Path = field(default_factory=lambda: Path(os.environ.get(
        "AGENT_BUFFER_PATH", str(DEFAULT_BUFFER_PATH))))
    log_path: Path = field(default_factory=lambda: Path(os.environ.get(
        "AGENT_LOG_PATH", str(DEFAULT_LOG_PATH))))
    log_level: str = os.environ.get("AGENT_LOG_LEVEL", "INFO")
    enrollment_token: str | None = None
    api_key: str | None = None
    agent_id: str | None = None
    hostname: str | None = None
    flush_interval: float = FLUSH_INTERVAL_SECONDS
    flush_batch_max: int = FLUSH_BATCH_MAX
    buffer_max_events: int = BUFFER_MAX_EVENTS
    heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS
    config_pull_interval: float = CONFIG_PULL_INTERVAL_SECONDS
    verify_tls: bool = True
    ca_bundle: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_args(cls, argv: list[str] | None = None) -> AgentConfig:
        """Parse CLI + env into AgentConfig. Does NOT validate connectivity."""
        parser = argparse.ArgumentParser(
            prog="ueba-agent",
            description="UEBA endpoint agent (collect + send activity logs)",
        )
        parser.add_argument(
            "--server-url",
            default=os.environ.get("AGENT_SERVER_URL", "http://localhost:8000"),
            help="Backend base URL (default: %(default)s)",
        )
        parser.add_argument(
            "--state-path",
            default=os.environ.get("AGENT_STATE_PATH", str(DEFAULT_STATE_PATH)),
            help="Path to the agent state JSON (agent_id + api_key)",
        )
        parser.add_argument(
            "--buffer-path",
            default=os.environ.get("AGENT_BUFFER_PATH", str(DEFAULT_BUFFER_PATH)),
            help="Path to the local SQLite buffer",
        )
        parser.add_argument(
            "--log-path",
            default=os.environ.get("AGENT_LOG_PATH", str(DEFAULT_LOG_PATH)),
            help="Path to the agent log file",
        )
        parser.add_argument(
            "--log-level",
            default=os.environ.get("AGENT_LOG_LEVEL", "INFO"),
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        )
        parser.add_argument(
            "--enrollment-token",
            default=os.environ.get("AGENT_ENROLLMENT_TOKEN"),
            help="One-time enrollment token (issued by admin)",
        )
        parser.add_argument(
            "--hostname",
            default=None,
            help="Override hostname (default: socket.gethostname())",
        )
        parser.add_argument(
            "--no-verify-tls",
            action="store_true",
            default=os.environ.get("AGENT_VERIFY_TLS", "1") == "0",
            help="Disable TLS certificate verification (debug only)",
        )
        parser.add_argument(
            "--ca-bundle",
            default=os.environ.get("AGENT_CA_BUNDLE"),
            help="Path to custom CA bundle for server verification",
        )
        parser.add_argument(
            "--flush-interval",
            type=float,
            default=float(os.environ.get("AGENT_FLUSH_INTERVAL", FLUSH_INTERVAL_SECONDS)),
            help="Seconds between buffer flushes",
        )
        parser.add_argument(
            "--flush-batch-max",
            type=int,
            default=int(os.environ.get("AGENT_FLUSH_BATCH_MAX", FLUSH_BATCH_MAX)),
            help="Max events per flush call",
        )
        parser.add_argument(
            "--buffer-max-events",
            type=int,
            default=int(os.environ.get("AGENT_BUFFER_MAX_EVENTS", BUFFER_MAX_EVENTS)),
            help="Max events kept in the SQLite buffer (oldest evicted first)",
        )
        parser.add_argument(
            "--heartbeat-interval",
            type=float,
            default=float(os.environ.get("AGENT_HEARTBEAT_INTERVAL",
                                         HEARTBEAT_INTERVAL_SECONDS)),
            help="Seconds between heartbeats",
        )
        parser.add_argument(
            "--config-pull-interval",
            type=float,
            default=float(os.environ.get("AGENT_CONFIG_PULL_INTERVAL",
                                         CONFIG_PULL_INTERVAL_SECONDS)),
            help="Seconds between config pulls",
        )
        args = parser.parse_args(argv)
        return cls(
            server_url=args.server_url.rstrip("/"),
            state_path=Path(args.state_path),
            buffer_path=Path(args.buffer_path),
            log_path=Path(args.log_path),
            log_level=args.log_level,
            enrollment_token=args.enrollment_token,
            hostname=args.hostname,
            flush_interval=args.flush_interval,
            flush_batch_max=args.flush_batch_max,
            buffer_max_events=args.buffer_max_events,
            heartbeat_interval=args.heartbeat_interval,
            config_pull_interval=args.config_pull_interval,
            verify_tls=not args.no_verify_tls,
            ca_bundle=args.ca_bundle,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "server_url": self.server_url,
            "state_path": str(self.state_path),
            "buffer_path": str(self.buffer_path),
            "log_path": str(self.log_path),
            "log_level": self.log_level,
            "flush_interval": self.flush_interval,
            "flush_batch_max": self.flush_batch_max,
            "buffer_max_events": self.buffer_max_events,
            "heartbeat_interval": self.heartbeat_interval,
            "config_pull_interval": self.config_pull_interval,
            "verify_tls": self.verify_tls,
            "ca_bundle": self.ca_bundle,
        }


def is_root() -> bool:
    """Check if running as root. Used for wtmp reading and DNS sinkhole."""
    try:
        return os.geteuid() == 0  # type: ignore[attr-defined, no-any-return]
    except AttributeError:
        return False  # Windows


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_linux() -> bool:
    return sys.platform.startswith("linux")
