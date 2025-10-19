"""Скрипт для инициализации ролей администраторов."""

import argparse
import asyncio
from typing import Sequence

from sqlalchemy import select

from app.db.session import AsyncSessionFactory
from app.models import AdminRole, AdminUser

DEFAULT_ROLES: Sequence[tuple[str, str, str]] = (
    ("superadmin", "Суперадмин", "Полный доступ, управление ролями и токенами."),
    ("manager", "Менеджер", "Просмотр данных и безопасные действия с ботом."),
    ("viewer", "Наблюдатель", "Только просмотр данных."),
)


async def sync_roles() -> None:
    async with AsyncSessionFactory() as session:
        for slug, name, description in DEFAULT_ROLES:
            result = await session.execute(select(AdminRole).where(AdminRole.slug == slug))
            role = result.scalar_one_or_none()
            if role:
                role.name = name
                role.description = description
            else:
                session.add(AdminRole(slug=slug, name=name, description=description))
        await session.commit()


async def assign_role(email: str, slug: str) -> None:
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(AdminUser).where(AdminUser.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise SystemExit(f"Администратор с email {email!r} не найден.")

        role_result = await session.execute(select(AdminRole).where(AdminRole.slug == slug))
        role = role_result.scalar_one_or_none()
        if not role:
            raise SystemExit(f"Роль {slug!r} не найдена. Сначала выполните синхронизацию ролей.")

        if role not in user.roles:
            user.roles.append(role)
            await session.commit()
            print(f"Роль {slug} назначена пользователю {email}.")
        else:
            print(f"У пользователя {email} уже есть роль {slug}.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Инициализация ролей для админки.")
    parser.add_argument("--sync", action="store_true", help="Создать или обновить базовые роли.")
    parser.add_argument("--assign", nargs=2, metavar=("EMAIL", "ROLE"), help="Назначить роль пользователю.")
    args = parser.parse_args()

    if args.sync:
        await sync_roles()
        print("Роли синхронизированы.")

    if args.assign:
        email, role_slug = args.assign
        await assign_role(email, role_slug)

    if not args.sync and not args.assign:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
