"""Утилиты для работы с ролями администраторов."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory
from app.models import AdminRole

# slug, name, description
DEFAULT_ROLES: Sequence[tuple[str, str, str]] = (
    ("superadmin", "Суперадмин", "Полный доступ, управление ролями и настройками безопасности."),
    ("manager", "Менеджер", "Просмотр данных и безопасные действия: продление, баланс, синхронизация."),
    ("viewer", "Наблюдатель", "Только чтение данных в панели."),
)


async def _sync_roles(session: AsyncSession, *, roles: Sequence[tuple[str, str, str]] = DEFAULT_ROLES) -> None:
    """Создаёт или обновляет базовые роли в рамках переданной сессии."""
    for slug, name, description in roles:
        result = await session.execute(select(AdminRole).where(AdminRole.slug == slug))
        role = result.scalar_one_or_none()
        if role:
            role.name = name
            role.description = description
        else:
            session.add(AdminRole(slug=slug, name=name, description=description))


async def ensure_default_roles() -> None:
    """Гарантирует наличие стандартных ролей в базе."""
    async with AsyncSessionFactory() as session:
        await _sync_roles(session)
        await session.commit()


async def sync_roles_with_session(session: AsyncSession) -> None:
    """Переиспользуемая функция для внешних сервисов/CLI."""
    await _sync_roles(session)
