"""Tests for the agent state file (agent_id + api_key persistence)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.agent.state import (
    STATE_FILE_MODE,
    AgentState,
    clear_state,
    load_state,
    make_enrolled_state,
    save_state,
    state_file_exists,
)


def test_state_file_exists(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    assert state_file_exists(p) is False
    p.write_text("{}")
    assert state_file_exists(p) is True


def test_load_state_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_state(tmp_path / "missing.json") is None


def test_load_state_reads_existing_file(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    p.write_text('{"agent_id":"a1","api_key":"k1","server_url":"s","enrolled_at":"t","hostname":"h"}')
    p.chmod(STATE_FILE_MODE)
    s = load_state(p)
    assert s is not None
    assert s.agent_id == "a1"
    assert s.api_key == "k1"


def test_load_state_rejects_world_readable(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    p.write_text('{"agent_id":"a1","api_key":"k1"}')
    p.chmod(0o644)  # group/world readable
    with pytest.raises(PermissionError):
        load_state(p)


def test_load_state_rejects_group_readable(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    p.write_text('{"agent_id":"a1","api_key":"k1"}')
    p.chmod(0o640)  # group readable
    with pytest.raises(PermissionError):
        load_state(p)


def test_save_state_writes_with_mode_0600(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    state = make_enrolled_state("a1", "k1", "http://x", "h")
    save_state(p, state)
    assert p.is_file()
    mode = p.stat().st_mode & 0o777
    assert mode == STATE_FILE_MODE


def test_save_state_creates_parent_dirs(tmp_path: Path) -> None:
    p = tmp_path / "deep" / "nested" / "state.json"
    state = make_enrolled_state("a1", "k1", "http://x", "h")
    save_state(p, state)
    assert p.is_file()


def test_save_state_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If something fails during the write, the final file should not be partial."""
    p = tmp_path / "state.json"
    # First write succeeds.
    save_state(p, make_enrolled_state("a1", "k1", "http://x", "h"))
    first_content = p.read_text()
    # Simulate failure during the second write.
    original_replace = os.replace

    def failing_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        save_state(p, make_enrolled_state("a2", "k2", "http://x", "h"))
    monkeypatch.setattr(os, "replace", original_replace)
    # Original file should still be intact.
    assert p.read_text() == first_content


def test_save_state_overwrites_existing(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    save_state(p, make_enrolled_state("a1", "k1", "http://x", "h"))
    save_state(p, make_enrolled_state("a2", "k2", "http://x", "h"))
    s = load_state(p)
    assert s is not None
    assert s.agent_id == "a2"


def test_clear_state_removes_file(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    save_state(p, make_enrolled_state("a1", "k1", "http://x", "h"))
    assert p.is_file()
    clear_state(p)
    assert not p.exists()


def test_clear_state_noop_when_missing(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    clear_state(p)  # should not raise


def test_make_enrolled_state_has_required_fields() -> None:
    s = make_enrolled_state("a1", "k1", "http://x", "h")
    assert s.agent_id == "a1"
    assert s.api_key == "k1"
    assert s.server_url == "http://x"
    assert s.hostname == "h"
    assert s.enrolled_at.endswith("Z")


def test_state_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    original = make_enrolled_state("a1", "k1", "http://x", "h")
    save_state(p, original)
    loaded = load_state(p)
    assert loaded is not None
    assert loaded.agent_id == original.agent_id
    assert loaded.api_key == original.api_key
    assert loaded.server_url == original.server_url
    assert loaded.hostname == original.hostname


def test_state_to_dict_includes_optional_fields() -> None:
    s = AgentState(
        agent_id="a1", api_key="k1", server_url="s", enrolled_at="t", hostname="h",
        last_heartbeat_at="t2", last_config_pull_at="t3", last_policy_version=2,
        extra={"foo": "bar"},
    )
    d = s.to_dict()
    assert d["last_heartbeat_at"] == "t2"
    assert d["last_policy_version"] == 2
    assert d["extra"] == {"foo": "bar"}


def test_state_from_dict_handles_missing_optional() -> None:
    s = AgentState.from_dict({
        "agent_id": "a1", "api_key": "k1", "server_url": "s",
        "enrolled_at": "t", "hostname": "h",
    })
    assert s.last_heartbeat_at is None
    assert s.last_config_pull_at is None
    assert s.last_policy_version is None
    assert s.extra == {}
