"""Клиент для вызова web API бота."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class WebAPIError(RuntimeError):
    """Базовая ошибка web API."""


class WebAPIConfigurationError(WebAPIError):
    """API недоступно из-за некорректной конфигурации."""


class WebAPIRequestError(WebAPIError):
    """API вернуло ошибку."""

    def __init__(self, message: str, *, status_code: int, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class WebAPIClient:
    """Асинхронный httpx-клиент с авторизацией по токену."""

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def extend_subscription(self, subscription_id: int, days: int) -> dict[str, Any]:
        payload = {"days": days}
        return await self._request("POST", f"/subscriptions/{subscription_id}/extend", json=payload)

    async def update_balance(
        self,
        user_id: int,
        amount_kopeks: int,
        *,
        description: str,
        create_transaction: bool,
    ) -> dict[str, Any]:
        payload = {
            "amount_kopeks": amount_kopeks,
            "description": description,
            "create_transaction": create_transaction,
        }
        return await self._request("POST", f"/users/{user_id}/balance", json=payload)

    async def update_user_status(self, user_id: int, status_value: str) -> dict[str, Any]:
        payload = {"status": status_value}
        return await self._request("PATCH", f"/users/{user_id}", json=payload)

    async def sync_to_panel(self) -> dict[str, Any]:
        return await self._request("POST", "/remnawave/sync/to-panel")

    async def sync_from_panel(self, mode: str = "all") -> dict[str, Any]:
        payload = {"mode": mode}
        return await self._request("POST", "/remnawave/sync/from-panel", json=payload)

    async def sync_subscription_statuses(self) -> dict[str, Any]:
        return await self._request("POST", "/remnawave/sync/subscriptions/statuses")

    async def _request(self, method: str, path: str, *, json: Any | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path if path.startswith("/") else f"/{path}"
        headers = {"X-API-Key": self.api_key}

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=headers,
        ) as client:
            try:
                response = await client.request(method, url, json=json, params=params)
            except httpx.RequestError as exc:
                logger.exception("Ошибка сети при обращении к web API %s %s", method, url)
                raise WebAPIRequestError(
                    f"Проблема с подключением к web API: {exc}",
                    status_code=0,
                ) from exc

        data = _extract_response_data(response)

        if response.is_error:
            detail = _extract_error_message(data) or response.text or "Неизвестная ошибка web API"
            raise WebAPIRequestError(detail, status_code=response.status_code, payload=data)

        return data


def _extract_response_data(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"data": data}
    except ValueError:
        return {"raw": response.text}


def _extract_error_message(data: dict[str, Any]) -> str | None:
    if "detail" in data:
        detail = data["detail"]
        if isinstance(detail, str):
            return detail
        if isinstance(detail, dict) and "message" in detail:
            return str(detail["message"])
        return str(detail)
    if "error" in data:
        return str(data["error"])
    return None


def is_webapi_configured() -> bool:
    """Проверяет наличие базовой конфигурации."""
    settings = get_settings()
    return bool(settings.webapi_base_url and settings.webapi_api_key)


def get_webapi_client() -> WebAPIClient:
    """Возвращает сконфигурированный клиент или кидает ошибку конфигурации."""
    settings = get_settings()
    if not settings.webapi_base_url or not settings.webapi_api_key:
        raise WebAPIConfigurationError("WEBAPI_BASE_URL или WEBAPI_API_KEY не заданы.")

    timeout = max(settings.webapi_timeout, 1.0)

    return WebAPIClient(
        base_url=settings.webapi_base_url,
        api_key=settings.webapi_api_key,
        timeout=timeout,
    )
