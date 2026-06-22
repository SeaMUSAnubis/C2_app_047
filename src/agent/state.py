"""Persistent agent state (agent_id + api_key + metadata).

Stored as JSON with file mode 0600. Loaded once at startup, written whenever
the agent enrolls successfully or re-enrolls.

Security notes:
- The state file contains the plaintext api_key. Mode 0600 ensures only the
  agent's user can read it. Root-owned if the agent runs as root.
- We never log the api_key or the full state file content.
- The state file is a regular file (not a symlink target) to prevent TOCTOU.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_FILE_MODE = 0o600


@dataclass
class AgentState:
    agent_id: str
    api_key: str
    server_url: str
    enrolled_at: str
    hostname: str
    last_heartbeat_at: str | None = None
    last_config_pull_at: str | None = None
    last_policy_version: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentState:
        return cls(
            agent_id=str(data["agent_id"]),
            api_key=str(data["api_key"]),
            server_url=str(data["server_url"]),
            enrolled_at=str(data["enrolled_at"]),
            hostname=str(data["hostname"]),
            last_heartbeat_at=data.get("last_heartbeat_at"),
            last_config_pull_at=data.get("last_config_pull_at"),
            last_policy_version=data.get("last_policy_version"),
            extra=data.get("extra", {}) or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def state_file_exists(path: Path) -> bool:
    return path.is_file()


def load_state(path: Path) -> AgentState | None:
    """Read the state file. Returns None if missing or invalid.

    Raises:
        PermissionError: if the file is group/world readable (security check).
    """
    if not path.is_file():
        return None
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise PermissionError(
            f"State file {path} is readable by group/world (mode={oct(mode)}). "
            f"Refusing to read. Run: chmod 600 {path}"
        )
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return AgentState.from_dict(data)


def save_state(path: Path, state: AgentState) -> None:
    """Atomically write the state file with mode 0600.

    Atomic write: write to a temp file in the same directory, fsync, rename.
    This prevents partial writes if the process is killed mid-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, STATE_FILE_MODE)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def clear_state(path: Path) -> None:
    if path.is_file():
        path.unlink()


def make_enrolled_state(
    agent_id: str, api_key: str, server_url: str, hostname: str
) -> AgentState:
    return AgentState(
        agent_id=agent_id,
        api_key=api_key,
        server_url=server_url,
        enrolled_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        hostname=hostname,
    )
