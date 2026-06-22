"""HTTP transport to the UEBA backend.

Responsibilities:
- Send /api/raw-logs/batch (drained from the local buffer)
- Send /api/agents/heartbeat periodically
- Pull /api/agents/me/config

Failure handling:
- Network errors (ConnectError, ReadTimeout, etc.) → raise TransportError
- HTTP 5xx → raise TransientError (caller should retry with backoff)
- HTTP 4xx → raise PermanentError (caller should NOT retry; ack the events
  to avoid an infinite loop, log the failure for investigation)
- HTTP 2xx (incl. 201) → success

The transport does NOT itself implement retry/backoff. The caller (flusher
loop) catches TransientError, applies backoff, and re-tries.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TransportError(Exception):
    """Base class for transport errors."""


class TransientError(TransportError):
    """5xx or network error — safe to retry."""


class PermanentError(TransportError):
    """4xx (except 429) — do NOT retry; the request will never succeed."""


class AuthRevokedError(PermanentError):
    """The agent's API key is invalid or the agent is revoked. Stop sending."""


@dataclass
class BatchResult:
    accepted_ids: list[int]
    failed_ids: list[int]
    errors: list[dict[str, Any]]

    @property
    def all_accepted(self) -> bool:
        return not self.failed_ids


def _classify_response(response: httpx.Response) -> None:
    """Raise the appropriate exception based on status code.

    Rules:
    - 2xx (including 201, 200) → no exception
    - 401 or 403 → AuthRevokedError
    - 429 (rate limit) or 5xx → TransientError
    - other 4xx → PermanentError
    """
    status = response.status_code
    if 200 <= status < 300:
        return
    if status in (401, 403):
        raise AuthRevokedError(
            f"Auth failure {status}: {response.text[:200]}"
        )
    if status == 429 or 500 <= status < 600:
        raise TransientError(
            f"Transient error {status}: {response.text[:200]}"
        )
    raise PermanentError(
        f"Permanent error {status}: {response.text[:200]}"
    )


class Transport:
    """Thin wrapper around httpx.Client. Stateless across calls."""

    def __init__(
        self,
        server_url: str,
        api_key: str,
        timeout: float = 30.0,
        verify_tls: bool = True,
        ca_bundle: str | None = None,
        user_agent: str = "ueba-agent/0.1.0",
    ):
        self._server_url = server_url.rstrip("/")
        self._api_key = api_key
        self._user_agent = user_agent
        verify_param: bool | str = verify_tls
        if ca_bundle:
            verify_param = ca_bundle
        self._client = httpx.Client(
            timeout=timeout,
            verify=verify_param,
        )
        self._default_headers: dict[str, str] = {
            "X-API-Key": api_key,
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    def _headers(self) -> dict[str, str]:
        return dict(self._default_headers)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Transport:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def send_batch(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """POST /api/raw-logs/batch. Returns the result dict on success.

        Records are sent verbatim (the server validates each as RawLogIngest).
        Raises TransientError/PermanentError/AuthRevokedError on failure.
        """
        url = f"{self._server_url}/api/raw-logs/batch"
        try:
            response = self._client.post(
                url,
                json={"records": records},
                headers=self._headers(),
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout,
                httpx.RemoteProtocolError) as exc:
            raise TransientError(f"Network error: {exc}") from exc
        _classify_response(response)
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise PermanentError(
                f"Server returned non-JSON 2xx: {response.text[:200]}"
            ) from exc

    def send_single(self, record: dict[str, Any]) -> dict[str, Any]:
        """POST /api/raw-logs/ingest."""
        url = f"{self._server_url}/api/raw-logs/ingest"
        try:
            response = self._client.post(url, json=record, headers=self._headers())
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout,
                httpx.RemoteProtocolError) as exc:
            raise TransientError(f"Network error: {exc}") from exc
        _classify_response(response)
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise PermanentError(
                f"Server returned non-JSON 2xx: {response.text[:200]}"
            ) from exc

    def heartbeat(self, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST /api/agents/heartbeat."""
        url = f"{self._server_url}/api/agents/heartbeat"
        try:
            response = self._client.post(
                url, json={"metrics": metrics or {}}, headers=self._headers()
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout,
                httpx.RemoteProtocolError) as exc:
            raise TransientError(f"Network error: {exc}") from exc
        _classify_response(response)
        return response.json()

    def get_config(self) -> dict[str, Any]:
        """GET /api/agents/me/config. Returns the policy + blocklist dict."""
        url = f"{self._server_url}/api/agents/me/config"
        try:
            response = self._client.get(url, headers=self._headers())
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout,
                httpx.RemoteProtocolError) as exc:
            raise TransientError(f"Network error: {exc}") from exc
        _classify_response(response)
        return response.json()

    def register(
        self, enrollment_token: str, hostname: str,
        os: str | None = None, os_version: str | None = None,
        device_id: str | None = None, assigned_user_id: str | None = None,
    ) -> dict[str, Any]:
        """POST /api/agents/register. Returns {agent_id, api_key, ...}.

        This is a PUBLIC endpoint (no X-API-Key auth). It is also a one-shot
        call — if the request fails partway, the operator must retry with the
        same enrollment token (which becomes single-use on success).
        """
        url = f"{self._server_url}/api/agents/register"
        # Register is a public endpoint — explicitly clear the X-API-Key.
        headers = self._headers()
        headers["X-API-Key"] = ""
        try:
            response = self._client.post(
                url,
                json={
                    "enrollment_token": enrollment_token,
                    "hostname": hostname,
                    "os": os,
                    "os_version": os_version,
                    "device_id": device_id,
                    "assigned_user_id": assigned_user_id,
                },
                headers=headers,
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout,
                httpx.RemoteProtocolError) as exc:
            raise TransientError(f"Network error: {exc}") from exc
        # Register uses different error semantics:
        # 400 (invalid token) → PermanentError
        # 201 → success
        if 200 <= response.status_code < 300:
            try:
                return response.json()
            except json.JSONDecodeError as exc:
                raise PermanentError(
                    f"Server returned non-JSON 2xx: {response.text[:200]}"
                ) from exc
        if response.status_code == 400:
            raise PermanentError(
                f"Registration rejected: {response.json().get('detail', response.text)}"
            )
        if 500 <= response.status_code < 600:
            raise TransientError(
                f"Transient error {response.status_code}: {response.text[:200]}"
            )
        raise PermanentError(
            f"Registration failed: {response.status_code} {response.text[:200]}"
        )
