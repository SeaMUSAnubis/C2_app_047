"""Enroll a new agent using a one-time enrollment token.

This is run ONCE per host (typically by the installer). After enrollment,
the state file contains the agent_id + api_key, and subsequent `agent run`
invocations use that.

Usage:
    agent enroll --server-url http://uebaserver:8000 \\
                 --enrollment-token o47enr_xxx \\
                 --state-path /var/lib/ueba-agent/state.json
"""

from __future__ import annotations

import logging
import os
import platform
import socket
import sys
from pathlib import Path

from src.agent.config import AgentConfig
from src.agent.state import (
    clear_state,
    load_state,
    make_enrolled_state,
    save_state,
    state_file_exists,
)
from src.agent.transport import PermanentError, TransientError, Transport

logger = logging.getLogger(__name__)


def _resolve_hostname(override: str | None) -> str:
    if override:
        return override
    try:
        return socket.gethostname() or "unknown"
    except Exception:
        return "unknown"


def _resolve_os_info() -> tuple[str, str]:
    system = platform.system() or "Unknown"
    release = platform.release() or ""
    version = platform.version() or ""
    return system, f"{release} {version}".strip()


def enroll(
    config: AgentConfig,
    *,
    device_id: str | None = None,
    assigned_user_id: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Enroll using the config's enrollment_token. Returns the state file path.

    Raises:
        PermanentError on token rejection or 4xx.
        TransientError on network failure.
        FileExistsError if a state file already exists and overwrite=False.
    """
    if not config.enrollment_token:
        raise PermanentError(
            "Missing --enrollment-token. Ask the admin to issue one via "
            "POST /api/agents/enrollment-tokens."
        )
    if state_file_exists(config.state_path) and not overwrite:
        existing = load_state(config.state_path)
        if existing is not None:
            raise FileExistsError(
                f"State file already exists at {config.state_path} "
                f"(agent_id={existing.agent_id}). "
                f"Use --overwrite to re-enroll, or delete the file first."
            )

    hostname = _resolve_hostname(config.hostname)
    os_name, os_version = _resolve_os_info()
    # We do NOT auto-set device_id or assigned_user_id. Both have FK
    # constraints to the devices/users tables, and most agents enroll
    # BEFORE those rows are created (admin runs the data import script
    # later). Passing None avoids the FK violation. The agent's events
    # are still tagged with the hostname in the payload, so backend
    # normalizers can reconcile once the rows exist.
    # Operators can pass device_id / assigned_user_id explicitly after
    # running the data import.

    logger.info(
        "Enrolling agent: server=%s, hostname=%s, os=%s",
        config.server_url, hostname, os_name,
    )

    transport = Transport(
        server_url=config.server_url,
        api_key="",  # register is unauthenticated
        verify_tls=config.verify_tls,
        ca_bundle=config.ca_bundle,
    )
    try:
        result = transport.register(
            enrollment_token=config.enrollment_token,
            hostname=hostname,
            os=os_name,
            os_version=os_version,
            device_id=device_id,
            assigned_user_id=assigned_user_id,
        )
    finally:
        transport.close()

    api_key = result.get("api_key")
    agent_id = result.get("agent_id")
    if not api_key or not agent_id:
        raise PermanentError(
            f"Server response missing api_key/agent_id: {result}"
        )

    state = make_enrolled_state(
        agent_id=agent_id,
        api_key=api_key,
        server_url=config.server_url,
        hostname=hostname,
    )
    # Clear any leftover state file then write fresh.
    if state_file_exists(config.state_path):
        clear_state(config.state_path)
    save_state(config.state_path, state)
    # Belt and suspenders: ensure mode is 0600 even on platforms that mask it.
    try:
        os.chmod(config.state_path, 0o600)
    except OSError:
        pass

    logger.info("Enrolled successfully. agent_id=%s", agent_id)
    return config.state_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for `agent enroll`."""
    # Lazy import to avoid pulling argparse into the service main.
    import argparse

    parser = argparse.ArgumentParser(prog="agent enroll")
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--enrollment-token", required=True)
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--device-id", default=None)
    parser.add_argument("--assigned-user-id", default=None)
    parser.add_argument("--hostname", default=None)
    parser.add_argument("--no-verify-tls", action="store_true")
    parser.add_argument("--ca-bundle", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = AgentConfig(
        server_url=args.server_url,
        state_path=Path(args.state_path),
        enrollment_token=args.enrollment_token,
        hostname=args.hostname,
        verify_tls=not args.no_verify_tls,
        ca_bundle=args.ca_bundle,
        log_level=args.log_level,
    )
    try:
        path = enroll(
            config,
            device_id=args.device_id,
            assigned_user_id=args.assigned_user_id,
            overwrite=args.overwrite,
        )
    except FileExistsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except PermanentError as exc:
        print(f"ERROR (permanent): {exc}", file=sys.stderr)
        return 3
    except TransientError as exc:
        print(f"ERROR (transient): {exc}", file=sys.stderr)
        return 4
    print(f"Enrolled. State file: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
