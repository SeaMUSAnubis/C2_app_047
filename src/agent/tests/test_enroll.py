"""Tests for the agent enrollment flow and CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent.config import AgentConfig
from agent.enroll import enroll
from agent.transport import PermanentError, TransientError


def _config(tmp_path: Path, enrollment_token: str = "o47enr_tok") -> AgentConfig:
    return AgentConfig(
        server_url="http://uebaserver:8000",
        state_path=tmp_path / "state.json",
        enrollment_token=enrollment_token,
    )


def test_enroll_creates_state_file(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "agent-abc123",
            "api_key": "o47ag_secret",
            "policy_version": 1,
            "issued_at": "2026-06-22T10:00:00Z",
        }
        path = enroll(cfg)
    assert path == cfg.state_path
    assert path.is_file()
    # Mode 0600
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_enroll_writes_correct_state(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "agent-xyz",
            "api_key": "o47ag_xyz",
            "policy_version": 1,
            "issued_at": "t",
        }
        enroll(cfg)
    from agent.state import load_state
    s = load_state(cfg.state_path)
    assert s is not None
    assert s.agent_id == "agent-xyz"
    assert s.api_key == "o47ag_xyz"
    assert s.server_url == "http://uebaserver:8000"
    assert s.enrolled_at.endswith("Z")
    assert s.hostname  # non-empty


def test_enroll_uses_resolved_hostname(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cfg.hostname = "WS-EXPLICIT-001"
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "a", "api_key": "k", "policy_version": 1, "issued_at": "t",
        }
        enroll(cfg)
    from agent.state import load_state
    s = load_state(cfg.state_path)
    assert s.hostname == "WS-EXPLICIT-001"


def test_enroll_does_not_auto_set_assigned_user_id(tmp_path: Path) -> None:
    """assigned_user_id is NOT auto-set; admins must pass it explicitly.

    Reason: the users table may not have a row for the local user (e.g. in
    a container running as root, or before the user has been imported
    from LDAP). Auto-setting would cause a FK violation.
    """
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "a", "api_key": "k", "policy_version": 1, "issued_at": "t",
        }
        enroll(cfg)
    args = mock_t.register.call_args.kwargs
    assert args["assigned_user_id"] is None


def test_enroll_uses_hostname_as_default_device_id(tmp_path: Path) -> None:
    """By default we do NOT pass device_id to register, to avoid FK violations
    when the device row doesn't exist yet. The admin can still pass an explicit
    device_id if they've pre-created the device row.
    """
    cfg = _config(tmp_path)
    cfg.hostname = "WS-XYZ"
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "a", "api_key": "k", "policy_version": 1, "issued_at": "t",
        }
        enroll(cfg, device_id=None, assigned_user_id=None)
    args = mock_t.register.call_args.kwargs
    # device_id defaults to None (no auto-create of device rows).
    assert args["device_id"] is None


def test_enroll_uses_explicit_device_id(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "a", "api_key": "k", "policy_version": 1, "issued_at": "t",
        }
        enroll(cfg, device_id="PC-EXPLICIT", assigned_user_id="U-EXPLICIT")
    args = mock_t.register.call_args.kwargs
    assert args["device_id"] == "PC-EXPLICIT"
    assert args["assigned_user_id"] == "U-EXPLICIT"


def test_enroll_calls_register_with_correct_payload(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "a", "api_key": "k", "policy_version": 1, "issued_at": "t",
        }
        enroll(cfg)
    args = mock_t.register.call_args.kwargs
    assert args["enrollment_token"] == "o47enr_tok"
    assert args["hostname"] != ""  # resolved
    assert "os" in args
    assert "os_version" in args


def test_enroll_refuses_when_token_missing(tmp_path: Path) -> None:
    cfg = _config(tmp_path, enrollment_token="")
    cfg.enrollment_token = None
    with pytest.raises(PermanentError):
        enroll(cfg)


def test_enroll_refuses_when_state_exists_without_overwrite(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    # First enrollment.
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "a", "api_key": "k", "policy_version": 1, "issued_at": "t",
        }
        enroll(cfg)
    # Second enrollment without overwrite.
    with pytest.raises(FileExistsError):
        enroll(cfg)


def test_enroll_overwrites_when_requested(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.side_effect = [
            {"agent_id": "a1", "api_key": "k1", "policy_version": 1, "issued_at": "t"},
            {"agent_id": "a2", "api_key": "k2", "policy_version": 1, "issued_at": "t"},
        ]
        enroll(cfg)
        enroll(cfg, overwrite=True)
    from agent.state import load_state
    s = load_state(cfg.state_path)
    assert s is not None
    assert s.agent_id == "a2"
    assert s.api_key == "k2"


def test_enroll_propagates_permanent_error(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.side_effect = PermanentError("Invalid token")
        with pytest.raises(PermanentError):
            enroll(cfg)
    assert not cfg.state_path.exists()


def test_enroll_propagates_transient_error(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.side_effect = TransientError("Network down")
        with pytest.raises(TransientError):
            enroll(cfg)
    assert not cfg.state_path.exists()


def test_enroll_rejects_response_missing_api_key(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "a", "policy_version": 1, "issued_at": "t",
            # missing api_key
        }
        with pytest.raises(PermanentError):
            enroll(cfg)


def test_enroll_closes_transport_on_error(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.side_effect = TransientError("boom")
        with pytest.raises(TransientError):
            enroll(cfg)
    mock_t.close.assert_called_once()


def test_enroll_closes_transport_on_success(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with patch("agent.enroll.Transport") as MockTransport:
        mock_t = MockTransport.return_value
        mock_t.register.return_value = {
            "agent_id": "a", "api_key": "k", "policy_version": 1, "issued_at": "t",
        }
        enroll(cfg)
    mock_t.close.assert_called_once()
