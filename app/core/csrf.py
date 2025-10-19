"""Simple CSRF token utilities based on HMAC."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request
from starlette.responses import Response

from app.core.config import get_settings


class CSRFAuthError(HTTPException):
    """Raised when CSRF validation fails."""


def _get_secret() -> bytes:
    return get_settings().csrf_secret_key.encode("utf-8")


def _timestamp_now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def generate_csrf_token() -> str:
    """Generate a token: base64(timestamp + randomness + signature)."""
    secret = _get_secret()
    timestamp = _timestamp_now()
    randomness = os.urandom(16)
    payload = timestamp.to_bytes(8, "big") + randomness
    signature = hmac.new(secret, payload, digestmod=hashlib.sha256).digest()
    token_bytes = payload + signature
    return base64.urlsafe_b64encode(token_bytes).decode("utf-8")


def validate_csrf_token(token: str) -> None:
    """Ensure token is valid and not expired."""
    settings = get_settings()
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8"))
    except Exception as exc:
        raise CSRFAuthError(status_code=400, detail="Неверный формат CSRF-токена.") from exc

    if len(raw) != 8 + 16 + 32:
        raise CSRFAuthError(status_code=400, detail="Неверный формат CSRF-токена.")

    payload = raw[:24]
    signature = raw[24:]
    expected_signature = hmac.new(_get_secret(), payload, digestmod=hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise CSRFAuthError(status_code=403, detail="CSRF-проверка не пройдена.")

    timestamp = int.from_bytes(payload[:8], "big")
    issued_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.csrf_token_expire_minutes)
    if datetime.now(tz=timezone.utc) > expires_at:
        raise CSRFAuthError(status_code=400, detail="CSRF-токен истёк.")


def issue_csrf(response: Response) -> str:
    """Generate token and write into cookie."""
    settings = get_settings()
    token = generate_csrf_token()
    response.set_cookie(
        key=settings.csrf_token_cookie,
        value=token,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=settings.csrf_token_expire_minutes * 60,
    )
    return token


def get_csrf_token(request: Request) -> str | None:
    """Fetch token from header or cookie."""
    settings = get_settings()
    header = request.headers.get(settings.csrf_token_header)
    if header:
        return header
    return request.cookies.get(settings.csrf_token_cookie)
