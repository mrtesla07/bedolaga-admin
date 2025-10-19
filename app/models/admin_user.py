"""Модель администратора."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.security import admin_user_roles

if TYPE_CHECKING:  # pragma: no cover
    from app.models.security import AdminActivityLog, AdminRole


class AdminUser(Base):
    """Администраторы админ-панели."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    roles: Mapped[list["AdminRole"]] = relationship(
        "AdminRole",
        secondary=admin_user_roles,
        back_populates="users",
        lazy="selectin",
    )

    activity_logs: Mapped[list["AdminActivityLog"]] = relationship(
        "AdminActivityLog",
        back_populates="admin",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AdminUser email={self.email!r}>"

    @property
    def role_slugs(self) -> str:
        if self.roles:
            return ", ".join(sorted(role.slug for role in self.roles))
        return "—"
