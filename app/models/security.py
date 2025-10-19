"""Модели безопасности: роли админов и журнал действий."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.admin_user import AdminUser


admin_user_roles = Table(
    "admin_user_roles",
    Base.metadata,
    Column("admin_id", ForeignKey("admin_users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("admin_roles.id", ondelete="CASCADE"), primary_key=True),
)


class AdminRole(Base):
    """Роли администраторов."""

    __tablename__ = "admin_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    users: Mapped[list["AdminUser"]] = relationship(
        "AdminUser",
        secondary=admin_user_roles,
        back_populates="roles",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AdminRole slug={self.slug!r}>"


class AdminActivityLog(Base):
    """Журнал действий администраторов."""

    __tablename__ = "admin_activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        back_populates="activity_logs",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<AdminActivityLog action={self.action!r} status={self.status!r}>"

    @property
    def admin_email(self) -> str:
        admin = getattr(self, "admin", None)
        if admin and admin.email:
            return admin.email
        return "—"
