"""Middleware for resolving request locale."""

from __future__ import annotations

from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.i18n.messages import DEFAULT_LOCALE, resolve_locale_from_request


class LocaleMiddleware(BaseHTTPMiddleware):
    """Stores resolved locale in request.state.locale."""

    def __init__(self, app: ASGIApp, *, default_locale: str = DEFAULT_LOCALE) -> None:
        super().__init__(app)
        self.default_locale = default_locale

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        locale = resolve_locale_from_request(request) or self.default_locale
        request.state.locale = locale
        response = await call_next(request)
        response.headers.setdefault("Content-Language", locale)
        return response
