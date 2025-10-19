"""Утилита для создания первого администратора."""

import argparse
import asyncio

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import AsyncSessionFactory
from app.models import AdminUser


async def create_admin(email: str, password: str, full_name: str | None, superuser: bool) -> None:
    """Создаёт администратора, если такой email не занят."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(AdminUser).where(AdminUser.email == email))
        if result.scalar_one_or_none():
            raise SystemExit("Пользователь с таким email уже существует.")

        user = AdminUser(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_superuser=superuser,
        )

        session.add(user)
        await session.commit()

    print(f"Администратор {email} создан.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Создание администратора для Bedolaga Admin")
    parser.add_argument("--email", required=True, help="Email администратора")
    parser.add_argument("--password", required=True, help="Пароль администратора")
    parser.add_argument("--full-name", dest="full_name", help="Полное имя (опционально)")
    parser.add_argument("--superuser", action="store_true", help="Сделать суперпользователем")

    args = parser.parse_args()
    asyncio.run(create_admin(**vars(args)))


if __name__ == "__main__":
    main()
