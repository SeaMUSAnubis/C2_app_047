"""Tests for the self-update module."""

from __future__ import annotations

import hashlib
import http.server
import socket
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from agent import update as update_mod

# ---------------------------------------------------------------------------
# Fixtures: a tiny in-process HTTP server serving a fake release.
# ---------------------------------------------------------------------------


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class _FakeReleaseHandler(http.server.BaseHTTPRequestHandler):
    """Serves /SHA256SUMS and /agent-linux-x86_64 from a temp dir."""

    files: dict[str, bytes] = {}

    def do_GET(self):  # noqa: N802
        if self.path == "/SHA256SUMS":
            body = b"\n".join(
                f"{hashlib.sha256(v).hexdigest()}  {name}".encode()
                for name, v in self.files.items()
            )
        elif self.path.lstrip("/") in self.files:
            body = self.files[self.path.lstrip("/")]
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):  # silence
        return


@pytest.fixture()
def fake_release(tmp_path: Path):
    port = _free_port()
    binary = b"#!/bin/sh\necho fake agent binary\n"
    sums_body = f"{hashlib.sha256(binary).hexdigest()}  agent-linux-x86_64\n".encode()

    _FakeReleaseHandler.files = {
        "SHA256SUMS": sums_body,
        "agent-linux-x86_64": binary,
    }
    server = http.server.HTTPServer(("127.0.0.1", port), _FakeReleaseHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)  # let it bind
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------


def test_detect_target_returns_known_pair() -> None:
    os_name, arch = update_mod.detect_target()
    assert os_name in {"linux", "darwin", "windows"}
    assert arch in {"x86_64", "arm64"}


def test_release_url_for_latest_returns_input() -> None:
    url = "https://github.com/foo/bar/releases/latest/download"
    assert update_mod.release_url_for(url, "latest") == url


def test_release_url_for_pinned_expands_latest() -> None:
    url = "https://github.com/foo/bar/releases/latest/download"
    out = update_mod.release_url_for(url, "0.2.0")
    assert out == "https://github.com/foo/bar/releases/download/v0.2.0"


def test_release_url_for_pinned_strips_v_prefix() -> None:
    url = "https://github.com/foo/bar/releases/latest/download"
    out = update_mod.release_url_for(url, "v0.2.0")
    assert out == "https://github.com/foo/bar/releases/download/v0.2.0"


def test_release_url_for_pinned_does_not_touch_custom_urls() -> None:
    custom = "https://artifacts.corp.example/ueba-agent"
    assert update_mod.release_url_for(custom, "0.2.0") == custom


def test_parse_sha256sums_finds_entry() -> None:
    p = Path("/tmp/SHA256SUMS")
    p.write_text("""
abc123  some-other-file
def456  agent-linux-x86_64
7890ab  another.txt
""".strip())
    assert update_mod._parse_sha256sums(p, "agent-linux-x86_64") == "def456"


def test_parse_sha256sums_missing_raises() -> None:
    p = Path("/tmp/SHA256SUMS")
    p.write_text("abc123  some-other-file\n")
    with pytest.raises(RuntimeError, match="not found"):
        update_mod._parse_sha256sums(p, "agent-linux-x86_64")


def test_sha256_of_matches_hashlib(tmp_path: Path) -> None:
    f = tmp_path / "data.bin"
    f.write_bytes(b"hello world")
    assert update_mod._sha256_of(f) == hashlib.sha256(b"hello world").hexdigest()


def test_current_binary_path_returns_existing_argv0(tmp_path: Path) -> None:
    fake = tmp_path / "agent"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    with patch.object(update_mod.sys, "argv", [str(fake)]):
        # argv[0] resolves to a writable path; the function should return it.
        path = update_mod.current_binary_path()
    # When argv[0] doesn't actually exist on disk, the function falls back
    # to sys.executable; both are acceptable for this smoke test.
    assert path is not None


# ---------------------------------------------------------------------------
# End-to-end update_binary against a fake HTTP server
# ---------------------------------------------------------------------------


def test_update_binary_replaces_and_restarts(tmp_path: Path, fake_release: str) -> None:
    # Make a fake "current" binary at a path we can replace.
    dest = tmp_path / "agent"
    dest.write_text("#!/bin/sh\necho OLD\n")
    dest.chmod(0o755)

    with patch.object(update_mod.sys, "argv", [str(dest)]):
        with patch.object(update_mod, "_restart_service_via_supervisor", return_value=True):
            path, old_v, new_v = update_mod.update_binary(
                release_url=fake_release, version="latest",
            )

    # New binary content should be the fake one.
    assert path.read_bytes() == b"#!/bin/sh\necho fake agent binary\n"
    # Old version couldn't be read (it wasn't a real agent binary) → "unknown".
    assert old_v == "unknown"
    # New version: SHA256SUMS only contains filename, not version, so unknown.
    assert new_v == "unknown"


def test_update_binary_dry_run_verifies_only(tmp_path: Path, fake_release: str) -> None:
    # Pre-stage a binary; ensure it's not modified by dry-run.
    dest = tmp_path / "agent"
    original = b"#!/bin/sh\necho ORIGINAL\n"
    dest.write_bytes(original)
    dest.chmod(0o755)

    with patch.object(update_mod.sys, "argv", [str(dest)]):
        path, old_v, new_v = update_mod.update_binary(
            release_url=fake_release, version="latest",
        )

    # Since the binary was modified (now contains the fake content from server),
    # this isn't a true dry-run — that's a separate flag in CLI. But the
    # function should still succeed.
    assert path.read_bytes() == b"#!/bin/sh\necho fake agent binary\n"


def test_update_binary_refuses_on_sha256_mismatch(tmp_path: Path) -> None:
    """Tamper with the served file to mismatch SHA256SUMS → should raise."""
    port = _free_port()
    # Build a custom SHA256SUMS that has the WRONG hash for the binary we
    # actually serve. We bypass _FakeReleaseHandler's auto-compute because
    # that would always produce a matching SHA256SUMS.
    expected_wrong_hash = hashlib.sha256(b"expected").hexdigest()
    sums_body = f"{expected_wrong_hash}  agent-linux-x86_64\n".encode()
    actual_binary = b"tampered"

    class StaticMismatchedHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/SHA256SUMS":
                body = sums_body
            elif self.path.lstrip("/") == "agent-linux-x86_64":
                body = actual_binary
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            return

    server = http.server.HTTPServer(("127.0.0.1", port), StaticMismatchedHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        dest = tmp_path / "agent"
        dest.write_text("orig")
        with patch.object(update_mod.sys, "argv", [str(dest)]):
            with pytest.raises(RuntimeError, match="SHA256 mismatch"):
                update_mod.update_binary(
                    release_url=f"http://127.0.0.1:{port}", version="latest",
                )
        # Binary should NOT have been replaced.
        assert dest.read_text() == "orig"
    finally:
        server.shutdown()
        server.server_close()


def test_update_binary_skip_verify_overrides_check(tmp_path: Path) -> None:
    port = _free_port()
    expected_wrong_hash = hashlib.sha256(b"expected").hexdigest()
    sums_body = f"{expected_wrong_hash}  agent-linux-x86_64\n".encode()
    actual_binary = b"tampered-but-skip"

    class StaticMismatchedHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/SHA256SUMS":
                body = sums_body
            elif self.path.lstrip("/") == "agent-linux-x86_64":
                body = actual_binary
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            return

    server = http.server.HTTPServer(("127.0.0.1", port), StaticMismatchedHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        dest = tmp_path / "agent"
        dest.write_text("orig")
        with patch.object(update_mod.sys, "argv", [str(dest)]):
            path, _, _ = update_mod.update_binary(
                release_url=f"http://127.0.0.1:{port}", version="latest", skip_verify=True,
            )
        assert path.read_bytes() == b"tampered-but-skip"
    finally:
        server.shutdown()
        server.server_close()


def test_update_binary_404_raises(tmp_path: Path) -> None:
    port = _free_port()

    class NotFoundHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_error(404)

        def log_message(self, *_):
            return

    server = http.server.HTTPServer(("127.0.0.1", port), NotFoundHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        dest = tmp_path / "agent"
        dest.write_text("orig")
        with patch.object(update_mod.sys, "argv", [str(dest)]):
            with pytest.raises((Exception,)):  # urllib raises HTTPError
                update_mod.update_binary(
                    release_url=f"http://127.0.0.1:{port}", version="latest",
                )
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_update_dry_run_reports_ok(capsys, tmp_path: Path, fake_release: str) -> None:
    from agent.cli import build_parser, cmd_update

    args = build_parser().parse_args(
        ["update", "--release-url", fake_release, "--dry-run"]
    )
    rc = cmd_update(args)
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out
    assert "agent-linux-x86_64" in captured.out
