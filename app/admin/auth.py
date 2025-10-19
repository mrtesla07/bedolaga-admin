"""Аутентификация админов для SQLAdmin."""

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.security import verify_password
from app.models import AdminUser


class BedolagaAuthenticationBackend(AuthenticationBackend):
    """Проверка логина/пароля администраторов."""

    def __init__(self, session_factory: Callable[[], AsyncSession], *, session_key: str = "bedolaga_admin") -> None:
        self._session_factory = session_factory
        self._session_key = session_key

    async def login(self, request: Request) -> bool:
        """Авторизация через обычную форму SQLAdmin."""
        form = await request.form()

        email = self._normalize(form.get("username"))
        password = form.get("password")

        if not email or not password:
            return False

        async with self._session_factory() as session:
            user = await self._get_user_by_email(session, email=email)

        if not user or not user.is_active:
            return False

        if not verify_password(password, user.hashed_password):
            return False

        request.session[self._session_key] = str(user.id)
        return True

    async def logout(self, request: Request) -> bool:
        """Очистка сессии при выходе."""
        request.session.pop(self._session_key, None)
        return True

    async def authenticate(self, request: Request) -> bool:
        """Проверка активной сессии."""
        user_id = request.session.get(self._session_key)
        if user_id is None:
            return False

        try:
            user_pk = int(user_id)
        except (TypeError, ValueError):
            request.session.pop(self._session_key, None)
            return False

        async with self._session_factory() as session:
            user = await session.get(AdminUser, user_pk)

        if not user or not user.is_active:
            request.session.pop(self._session_key, None)
            return False

        request.state.admin_user = user
        return True

    @staticmethod
    async def _get_user_by_email(session: AsyncSession, *, email: str) -> AdminUser | None:
        result = await session.execute(select(AdminUser).where(AdminUser.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    def _normalize(value: Any) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None
