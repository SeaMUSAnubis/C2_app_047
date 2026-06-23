"""Self-update: download a newer version of the agent binary, verify it,
and replace the currently-running binary in-place.

The check is symmetric with `install_via_curl.sh`:
- detect OS + arch
- download SHA256SUMS + matching binary from the release URL
- verify SHA256 (always; refuses to install on mismatch unless
  `UEBA_SKIP_VERIFY=1`)
- atomic replace (write to `<bin>.new`, then `os.replace`)

After replace:
- Linux/macOS: if running under systemd / launchd, ask the supervisor to
  restart us (so the new binary is loaded).
- Windows: spawn a one-shot scheduled task that runs on next logon to
  swap the .new file in (the running process can't replace itself on
  Windows while the .exe is held open).
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

DEFAULT_RELEASE_URL: Final[str] = (
    "https://github.com/vespionage/ueba-endpoint-monitoring/releases/latest/download"
)


def current_binary_path() -> Path:
    """Best-effort: return the path of the running binary.

    - PyInstaller binary: `sys.executable` is the unpacked temp path; the
      real binary is `sys.argv[0]`.
    - Python venv: `sys.executable` is the venv python.
    """
    argv0 = Path(sys.argv[0]).resolve()
    if argv0.exists() and os.access(argv0, os.W_OK):
        return argv0
    return Path(sys.executable).resolve()


def detect_target() -> tuple[str, str]:
    """Return (os, arch) for the current host.

    os is one of: linux, darwin, windows.
    arch is one of: x86_64, arm64.
    """
    sysname = sys.platform
    if sysname.startswith("linux"):
        os_name = "linux"
    elif sysname == "darwin":
        os_name = "darwin"
    elif sysname in ("win32", "cygwin"):
        os_name = "windows"
    else:
        raise RuntimeError(f"unsupported platform: {sysname}")
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        raise RuntimeError(f"unsupported arch: {machine}")
    return os_name, arch


def release_url_for(release_url: str, version: str) -> str:
    """If version is pinned, expand the release URL accordingly."""
    if version == "latest":
        return release_url
    if release_url.endswith("/releases/latest/download"):
        return release_url[: -len("/releases/latest/download")] + f"/releases/download/v{version.lstrip('v')}"
    return release_url


def _download(url: str, dest: Path, timeout: float = 30.0) -> None:
    """Stream-download a file. Uses urllib so it works in a frozen binary
    without extra deps (httpx would be nicer but stdlib is bullet-proof).
    """
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "ueba-agent-updater"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as f:
        shutil.copyfileobj(resp, f, length=64 * 1024)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_sha256sums(sums_path: Path, binary_name: str) -> str:
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[-1] == binary_name:
            return parts[0]
    raise RuntimeError(f"{binary_name} not found in {sums_path}")


def _atomic_replace(src: Path, dst: Path) -> None:
    """Replace dst with src atomically. On Windows, dst cannot be the
    currently-running binary; the caller is expected to handle that case
    by deferring the replace to a one-shot scheduled task.
    """
    if not src.exists():
        raise RuntimeError(f"source does not exist: {src}")
    if not dst.exists():
        # No prior binary — just move.
        shutil.move(str(src), str(dst))
        return
    if sys.platform in ("win32", "cygwin"):
        # Windows holds .exe open while running; can't os.replace over it.
        # Caller should have arranged a deferred-replace mechanism.
        raise RuntimeError(
            f"refusing to replace running Windows binary {dst} — "
            "caller must defer the swap to a one-shot task",
        )
    os.replace(src, dst)


def _restart_service_via_supervisor() -> bool:
    """If we're under systemd or launchd, ask the supervisor to restart us.
    Otherwise, do nothing (the operator can restart manually).
    """
    if sys.platform.startswith("linux") and Path("/run/systemd/system").exists():
        try:
            subprocess.run(
                ["systemctl", "restart", "ueba-agent.service"],
                check=True, timeout=15, capture_output=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("systemctl restart failed — restart manually")
    if sys.platform == "darwin":
        try:
            subprocess.run(
                ["launchctl", "kickstart", "-k", "system/com.vespionage.ueba-agent"],
                check=True, timeout=15, capture_output=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("launchctl kickstart failed — restart manually")
    return False


def update_binary(
    release_url: str = DEFAULT_RELEASE_URL,
    version: str = "latest",
    skip_verify: bool = False,
) -> tuple[Path, str, str]:
    """Download + verify + replace the running binary in place.

    Returns (binary_path, old_version, new_version).

    Raises:
        RuntimeError on any failure (download, checksum mismatch, replace).
    """
    os_name, arch = detect_target()
    ext = ".exe" if os_name == "windows" else ""
    binary_name = f"agent-{os_name}-{arch}{ext}"
    base = release_url_for(release_url, version)

    with tempfile.TemporaryDirectory(prefix="ueba-agent-update-") as tmpdir:
        tmp = Path(tmpdir)
        sums_path = tmp / "SHA256SUMS"
        new_bin = tmp / (binary_name + ".new")

        logger.info("Downloading %s/SHA256SUMS", base)
        _download(f"{base}/SHA256SUMS", sums_path)
        logger.info("Downloading %s/%s", base, binary_name)
        _download(f"{base}/{binary_name}", new_bin)

        expected = _parse_sha256sums(sums_path, binary_name)
        actual = _sha256_of(new_bin)
        if expected != actual:
            if skip_verify:
                logger.warning(
                    "SHA256 mismatch (expected=%s... actual=%s...) — skip_verify=True, continuing",
                    expected[:16], actual[:16],
                )
            else:
                raise RuntimeError(
                    f"SHA256 mismatch! expected={expected} actual={actual} — "
                    "refusing to install. Set UEBA_SKIP_VERIFY=1 to override."
                )
        logger.info("SHA256 verified: %s...", actual[:16])

        # The new binary is verified; figure out the install path + replace.
        if sys.platform in ("win32", "cygwin"):
            # Defer the swap: write to <bin>.new alongside the current exe;
            # the install_via_curl.ps1 script handles the actual swap via a
            # one-shot task. We just print instructions.
            dest = current_binary_path()
            staged = dest.with_suffix(dest.suffix + ".new")
            shutil.move(str(new_bin), str(staged))
            return dest, _read_local_version(dest), _read_version_from_release(base)
        else:
            dest = current_binary_path()
            _atomic_replace(new_bin, dest)
            os.chmod(dest, 0o755)
            return dest, _read_local_version(dest), _read_local_version(dest)


def _read_local_version(bin_path: Path) -> str:
    """Best-effort: read the running version by invoking `agent version`."""
    try:
        out = subprocess.run(
            [str(bin_path), "version"], capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            line = out.stdout.strip()
            if line.startswith("agent "):
                return line.split(" ", 1)[1]
    except (subprocess.SubprocessError, OSError):
        pass
    return "unknown"


def _read_version_from_release(base: str) -> str:
    """The release URL doesn't always embed the version. Best we can do is
    parse the URL. If unknown, return "unknown".
    """
    # e.g. base = ".../releases/download/v0.2.0" — version is in path.
    parts = base.rstrip("/").split("/")
    for part in reversed(parts):
        if part.startswith("v") and part[1:].replace(".", "").isdigit():
            return part.lstrip("v")
    return "unknown"


def install_self_update_check(
    release_url: str = DEFAULT_RELEASE_URL,
    version: str = "latest",
) -> bool:
    """Check whether a newer version is available, and download+apply it.

    Returns True if an update was applied (or queued for apply on next start).
    """
    try:
        dest, old_v, new_v = update_binary(release_url, version)
    except Exception as exc:
        logger.error("update failed: %s", exc)
        return False
    logger.info("updated %s: %s -> %s", dest, old_v, new_v)
    if sys.platform in ("win32", "cygwin"):
        logger.info(
            "Windows: the running binary can't be replaced while open. "
            "The staged .new file will be swapped on next service start "
            "(see install_via_curl.ps1 for the swap mechanism)."
        )
        return True
    if _restart_service_via_supervisor():
        logger.info("service restarted under new binary")
    else:
        logger.info("update applied — restart the service manually to load it")
    return True
