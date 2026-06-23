"""Tests for the HTTP transport.

We mock httpx.Client via monkeypatch to avoid hitting the network. The tests
verify:
- Request URL/headers/body shape
- Status code classification (2xx success, 4xx permanent, 5xx transient, 401/403 auth)
- Network error → TransientError
- JSON decode error on 2xx → PermanentError
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from agent.transport import (
    AuthRevokedError,
    PermanentError,
    TransientError,
    Transport,
)


class _MockResponse:
    def __init__(self, status_code: int, json_data: Any = None, text: str = ""):
        self.status_code = status_code
        self._json = json_data
        self.text = text or (str(json_data) if json_data is not None else "")

    def json(self) -> Any:
        if self._json is not None:
            return self._json
        raise ValueError("not json")


@pytest.fixture
def transport() -> Transport:
    t = Transport(
        server_url="http://uebaserver:8000",
        api_key="o47ag_testkey",
        verify_tls=False,
    )
    yield t
    t.close()


def _patch_client(transport: Transport, mock_client: MagicMock) -> None:
    transport._client = mock_client  # type: ignore[attr-defined]


def test_send_batch_posts_to_batch_endpoint(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(200, {"created_or_updated": 2, "failed": 0, "errors": []})
    _patch_client(transport, client)

    records = [
        {"source_id": "s:1", "collector_type": "endpoint_agent",
         "event_type": "logon", "timestamp": "2026-06-22T10:00:00Z"},
        {"source_id": "s:2", "collector_type": "endpoint_agent",
         "event_type": "logon", "timestamp": "2026-06-22T10:00:01Z"},
    ]
    result = transport.send_batch(records)

    client.post.assert_called_once()
    called_url = client.post.call_args[0][0]
    assert called_url == "http://uebaserver:8000/api/raw-logs/batch"
    called_body = client.post.call_args[1]["json"]
    assert called_body == {"records": records}
    assert result["created_or_updated"] == 2


def test_send_batch_sends_api_key_header(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(200, {"created_or_updated": 0, "failed": 0, "errors": []})
    _patch_client(transport, client)

    transport.send_batch([])
    headers = client.post.call_args[1]["headers"]
    assert headers["X-API-Key"] == "o47ag_testkey"
    assert "User-Agent" in headers


def test_send_batch_classifies_2xx_as_success(transport: Transport) -> None:
    for code in (200, 201, 202, 204):
        client = MagicMock()
        client.post.return_value = _MockResponse(code, {"created_or_updated": 0, "failed": 0, "errors": []})
        _patch_client(transport, client)
        result = transport.send_batch([])
        assert result["created_or_updated"] == 0


def test_send_batch_401_raises_auth_revoked(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(401, {"detail": "Invalid API key"})
    _patch_client(transport, client)
    with pytest.raises(AuthRevokedError):
        transport.send_batch([])


def test_send_batch_403_raises_auth_revoked(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(403, {"detail": "Agent revoked"})
    _patch_client(transport, client)
    with pytest.raises(AuthRevokedError):
        transport.send_batch([])


def test_send_batch_429_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(429, {"detail": "rate limited"})
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.send_batch([])


def test_send_batch_500_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(500, {"detail": "server error"})
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.send_batch([])


def test_send_batch_502_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(502, {"detail": "bad gateway"})
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.send_batch([])


def test_send_batch_400_raises_permanent(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(400, {"detail": "bad request"})
    _patch_client(transport, client)
    with pytest.raises(PermanentError):
        transport.send_batch([])


def test_send_batch_404_raises_permanent(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(404, {"detail": "not found"})
    _patch_client(transport, client)
    with pytest.raises(PermanentError):
        transport.send_batch([])


def test_send_batch_network_error_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.side_effect = httpx.ConnectError("connection refused")
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.send_batch([])


def test_send_batch_timeout_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.side_effect = httpx.ReadTimeout("read timeout")
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.send_batch([])


def test_send_batch_invalid_json_response_raises_permanent(transport: Transport) -> None:
    """If server returns 2xx but not parseable JSON, treat as permanent."""
    bad = MagicMock()
    bad.status_code = 200
    bad.text = "not json"
    bad.json.side_effect = json.JSONDecodeError("not json", "not json", 0)
    client = MagicMock()
    client.post.return_value = bad
    _patch_client(transport, client)
    with pytest.raises(PermanentError):
        transport.send_batch([])


def test_send_single_posts_to_ingest_endpoint(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(201, {
        "id": 42, "source_id": "s:1", "created_at": "t", "collector_type": "endpoint_agent",
        "event_type": "logon", "timestamp": "t", "user_id": None, "device_id": None,
        "raw_payload": {}, "ingest_metadata": {},
    })
    _patch_client(transport, client)

    record = {"source_id": "s:1", "collector_type": "endpoint_agent",
              "event_type": "logon", "timestamp": "t"}
    result = transport.send_single(record)

    assert result["id"] == 42
    assert client.post.call_args[0][0] == "http://uebaserver:8000/api/raw-logs/ingest"


def test_heartbeat_posts_to_heartbeat_endpoint(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(200, {
        "status": "active", "policy_version": 1, "last_heartbeat": "t",
    })
    _patch_client(transport, client)

    result = transport.heartbeat({"buffer_size": 10})
    assert result["status"] == "active"
    assert client.post.call_args[0][0] == "http://uebaserver:8000/api/agents/heartbeat"
    assert client.post.call_args[1]["json"] == {"metrics": {"buffer_size": 10}}


def test_get_config_calls_me_config(transport: Transport) -> None:
    client = MagicMock()
    client.get.return_value = _MockResponse(200, {
        "policy_version": 1, "sampling_rate": 100, "enabled_collectors": ["logon"],
        "blocklist": [], "server_time": "t",
    })
    _patch_client(transport, client)

    result = transport.get_config()
    assert result["policy_version"] == 1
    assert client.get.call_args[0][0] == "http://uebaserver:8000/api/agents/me/config"


def test_register_success(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(201, {
        "agent_id": "agent-abc", "api_key": "o47ag_xyz", "policy_version": 1, "issued_at": "t",
    })
    _patch_client(transport, client)

    result = transport.register(
        enrollment_token="o47enr_t", hostname="WS-001", os="Linux",
    )
    assert result["agent_id"] == "agent-abc"
    # The X-API-Key header is explicitly cleared for the public register endpoint.
    headers = client.post.call_args[1]["headers"]
    assert headers["X-API-Key"] == ""
    body = client.post.call_args[1]["json"]
    assert body["enrollment_token"] == "o47enr_t"
    assert body["hostname"] == "WS-001"


def test_register_rejected_by_server_raises_permanent(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(400, {"detail": "Invalid enrollment token"})
    _patch_client(transport, client)
    with pytest.raises(PermanentError):
        transport.register(enrollment_token="bad", hostname="WS")


def test_register_500_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(500, {"detail": "server error"})
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.register(enrollment_token="t", hostname="WS")


def test_register_network_error_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.side_effect = httpx.ConnectError("refused")
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.register(enrollment_token="t", hostname="WS")


def test_strips_trailing_slash_from_server_url() -> None:
    t = Transport(
        server_url="http://uebaserver:8000/",
        api_key="k",
        verify_tls=False,
    )
    try:
        assert t._server_url == "http://uebaserver:8000"  # type: ignore[attr-defined]
    finally:
        t.close()


def test_send_batch_handles_503_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.return_value = _MockResponse(503, {"detail": "unavailable"})
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.send_batch([])


def test_send_batch_400_with_partial_accepted_raises_permanent(transport: Transport) -> None:
    """Server returns 400 — this is a bad request. We should NOT retry."""
    client = MagicMock()
    client.post.return_value = _MockResponse(400, {"detail": "Invalid timestamp format"})
    _patch_client(transport, client)
    with pytest.raises(PermanentError):
        transport.send_batch([])


def test_heartbeat_network_error_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.side_effect = httpx.ConnectError("refused")
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.heartbeat()


def test_get_config_network_error_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.get.side_effect = httpx.ConnectError("refused")
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.get_config()


def test_send_single_network_error_raises_transient(transport: Transport) -> None:
    client = MagicMock()
    client.post.side_effect = httpx.ConnectTimeout("timeout")
    _patch_client(transport, client)
    with pytest.raises(TransientError):
        transport.send_single({"source_id": "s"})


def test_verify_tls_disabled_in_test_transport() -> None:
    """When verify_tls=False, the client constructs without error and uses
    the unsecured transport path. We don't introspect httpx internals; we
    only verify the call doesn't raise."""
    t = Transport(server_url="http://x", api_key="k", verify_tls=False)
    try:
        # Confirm the headers carry the X-API-Key.
        assert t._default_headers["X-API-Key"] == "k"  # type: ignore[attr-defined]
    finally:
        t.close()


def test_auth_revoked_is_permanent_subclass() -> None:
    """AuthRevokedError must inherit from PermanentError so callers can catch it."""
    assert issubclass(AuthRevokedError, PermanentError)
    assert issubclass(AuthRevokedError, Exception)


def test_transport_close_is_idempotent() -> None:
    t = Transport(server_url="http://x", api_key="k", verify_tls=False)
    t.close()
    t.close()  # must not raise
