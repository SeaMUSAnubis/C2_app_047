from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import HTTPException, status

from src.config import settings

JWT_ALGORITHM = "HS256"


def hash_password(password: str, *, salt: str | None = None) -> str:
    password_salt = salt or base64.urlsafe_b64encode(os.urandom(16)).decode("ascii")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), password_salt.encode("utf-8"), 120_000)
    return f"{password_salt}${base64.urlsafe_b64encode(digest).decode('ascii')}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, expected_digest = password_hash.split("$", 1)
    except ValueError:
        return False
    candidate = hash_password(password, salt=salt).split("$", 1)[1]
    return hmac.compare_digest(candidate, expected_digest)


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> tuple[str, int]:
    expires_in = (expires_minutes or settings.jwt_expires_minutes) * 60
    now = int(time.time())
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {"sub": subject, "role": role, "iat": now, "exp": now + expires_in}
    signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}", expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature = token.split(".")
    except ValueError as exc:
        raise _credentials_error() from exc

    signing_input = f"{header_b64}.{payload_b64}"
    if not hmac.compare_digest(signature, _sign(signing_input)):
        raise _credentials_error()

    try:
        header = _b64_decode_json(header_b64)
        payload = _b64_decode_json(payload_b64)
    except (ValueError, json.JSONDecodeError) as exc:
        raise _credentials_error() from exc

    if header.get("alg") != JWT_ALGORITHM:
        raise _credentials_error()
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload


def _b64_json(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _b64_decode_json(value: str) -> dict[str, Any]:
    padded = value + ("=" * (-len(value) % 4))
    return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))


def _sign(signing_input: str) -> str:
    digest = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
