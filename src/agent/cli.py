"""Command-line entry point: `agent <subcommand> [args]`.

Subcommands:
- enroll   : register a new agent (run once per host)
- run      : start the service (foreground; use systemd / NSSM in production)
- version  : print version and exit
- update   : self-update the running binary to the latest release
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from agent import __version__
from agent.config import AgentConfig
from agent.enroll import enroll as enroll_fn
from agent.service import AgentService
from agent.transport import PermanentError, TransientError
from agent.update import DEFAULT_RELEASE_URL, update_binary

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="UEBA endpoint agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="print version and exit")

    p_enroll = sub.add_parser("enroll", help="enroll a new agent (one-time)")
    p_enroll.add_argument("--server-url", required=True)
    p_enroll.add_argument("--enrollment-token", required=True)
    p_enroll.add_argument("--state-path", required=True)
    p_enroll.add_argument("--device-id", default=None)
    p_enroll.add_argument("--assigned-user-id", default=None)
    p_enroll.add_argument("--hostname", default=None)
    p_enroll.add_argument("--no-verify-tls", action="store_true")
    p_enroll.add_argument("--ca-bundle", default=None)
    p_enroll.add_argument("--overwrite", action="store_true")
    p_enroll.add_argument("--log-level", default="INFO")

    p_run = sub.add_parser("run", help="run the agent service in the foreground")
    p_run.add_argument("--server-url", default=None)
    p_run.add_argument("--state-path", default=None)
    p_run.add_argument("--buffer-path", default=None)
    p_run.add_argument("--log-path", default=None)
    p_run.add_argument("--log-level", default=None)
    p_run.add_argument("--no-verify-tls", action="store_true")
    p_run.add_argument("--ca-bundle", default=None)
    p_run.add_argument("--flush-interval", type=float, default=None)
    p_run.add_argument("--flush-batch-max", type=int, default=None)
    p_run.add_argument("--buffer-max-events", type=int, default=None)
    p_run.add_argument("--heartbeat-interval", type=float, default=None)
    p_run.add_argument("--config-pull-interval", type=float, default=None)

    p_update = sub.add_parser("update", help="self-update to the latest release")
    p_update.add_argument(
        "--release-url", default=os.environ.get("UEBA_RELEASE_URL", DEFAULT_RELEASE_URL),
        help="base URL for releases (default: %(default)s)",
    )
    p_update.add_argument(
        "--version", default=os.environ.get("UEBA_VERSION", "latest"),
        help="version to update to (default: latest)",
    )
    p_update.add_argument(
        "--skip-verify", action="store_true",
        help="skip SHA256 check (NOT recommended)",
    )
    p_update.add_argument(
        "--dry-run", action="store_true",
        help="download + verify, but don't replace the running binary",
    )

    return parser


def cmd_version(_: argparse.Namespace) -> int:
    print(f"agent {__version__}")
    return 0


def cmd_enroll(args: argparse.Namespace) -> int:
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
        path = enroll_fn(
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


def _build_run_config(args: argparse.Namespace) -> AgentConfig:
    """Build an AgentConfig for `run`, overlaying CLI args on env defaults."""
    base = AgentConfig()
    return AgentConfig(
        server_url=args.server_url or base.server_url,
        state_path=Path(args.state_path) if args.state_path else base.state_path,
        buffer_path=Path(args.buffer_path) if args.buffer_path else base.buffer_path,
        log_path=Path(args.log_path) if args.log_path else base.log_path,
        log_level=args.log_level or base.log_level,
        verify_tls=not args.no_verify_tls if args.no_verify_tls else base.verify_tls,
        ca_bundle=args.ca_bundle or base.ca_bundle,
        flush_interval=args.flush_interval or base.flush_interval,
        flush_batch_max=args.flush_batch_max or base.flush_batch_max,
        buffer_max_events=args.buffer_max_events or base.buffer_max_events,
        heartbeat_interval=args.heartbeat_interval or base.heartbeat_interval,
        config_pull_interval=args.config_pull_interval or base.config_pull_interval,
    )


def cmd_run(args: argparse.Namespace) -> int:
    config = _build_run_config(args)
    service = AgentService(config)
    return asyncio.run(service.run())


def cmd_update(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    )
    if args.dry_run:
        # Verify the URL is reachable and checksum matches, but don't replace.
        try:
            import tempfile

            from agent.update import (
                _download,
                _parse_sha256sums,
                _sha256_of,
                detect_target,
            )
            os_name, arch = detect_target()
            ext = ".exe" if os_name == "windows" else ""
            binary_name = f"agent-{os_name}-{arch}{ext}"
            with tempfile.TemporaryDirectory(prefix="ueba-agent-dryrun-") as tmp:
                sums = Path(tmp) / "SHA256SUMS"
                new = Path(tmp) / binary_name
                _download(f"{args.release_url}/SHA256SUMS", sums)
                _download(f"{args.release_url}/{binary_name}", new)
                expected = _parse_sha256sums(sums, binary_name)
                actual = _sha256_of(new)
                print(f"  expected SHA256: {expected}")
                print(f"  actual   SHA256: {actual}")
                if expected == actual:
                    print(f"  OK: {binary_name} would update cleanly (current: agent {__version__})")
                    return 0
                print("  MISMATCH — refusing to install")
                return 1
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    try:
        dest, old_v, new_v = update_binary(
            release_url=args.release_url,
            version=args.version,
            skip_verify=args.skip_verify,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Updated: {old_v} -> {new_v} ({dest})")
    if sys.platform in ("win32", "cygwin"):
        print(
            "Windows: the running .exe is held open. The new version was "
            "staged as <bin>.new; it will be swapped on next service start."
        )
    else:
        # Try to restart via the supervisor.
        from agent.update import _restart_service_via_supervisor

        if _restart_service_via_supervisor():
            print("Service restarted under the new binary.")
        else:
            print("Restart the service manually to load the new binary.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        return cmd_version(args)
    if args.command == "enroll":
        return cmd_enroll(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "update":
        return cmd_update(args)
    parser.error(f"unknown command: {args.command}")
    return 1  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
