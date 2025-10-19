"""Сервис для логирования действий администраторов."""

from __future__ import annotations

import json
import logging
from typing import Any

from starlette.requests import Request

from app.db.session import AsyncSessionFactory
from app.models import AdminActivityLog

logger = logging.getLogger(__name__)


async def log_admin_action(
    *,
    admin_id: int | None,
    action: str,
    status: str,
    message: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Сохраняет запись в журнале действий."""
    try:
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("User-Agent") if request else None

        payload_json: dict[str, Any] | None = None
        if payload is not None:
            try:
                # Преобразуем в json-friendly структуру
                json.dumps(payload)
                payload_json = payload
            except (TypeError, ValueError):
                payload_json = {"raw": str(payload)}

        async with AsyncSessionFactory() as session:
            entry = AdminActivityLog(
                admin_id=admin_id,
                action=action,
                status=status,
                message=message,
                target_type=target_type,
                target_id=target_id,
                payload_json=payload_json,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(entry)
            await session.commit()
    except Exception:  # pragma: no cover - логирование не должно падать
        logger.exception("Не удалось записать действие администратора: %s", action)
