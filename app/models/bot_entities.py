"""Модели сущностей бота для отображения в админке."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserStatus(str, Enum):
    """Статусы пользователя бота."""

    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class SubscriptionStatus(str, Enum):
    """Статусы подписки."""

    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"


class TransactionType(str, Enum):
    """Типы транзакций."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    SUBSCRIPTION_PAYMENT = "subscription_payment"
    REFUND = "refund"
    REFERRAL_REWARD = "referral_reward"


class PaymentMethod(str, Enum):
    """Способы оплаты."""

    TELEGRAM_STARS = "telegram_stars"
    TRIBUTE = "tribute"
    YOOKASSA = "yookassa"
    CRYPTOBOT = "cryptobot"
    MULENPAY = "mulenpay"
    PAL24 = "pal24"
    MANUAL = "manual"


class PromoGroup(Base):
    """Группа промо-акций пользователя."""

    __tablename__ = "promo_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    server_discount_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    traffic_discount_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    device_discount_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="promo_group")

    def __repr__(self) -> str:
        return f"<PromoGroup id={self.id} name={self.name!r}>"


class User(Base):
    """Пользователь бота."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE.value, nullable=False)
    language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)
    balance_kopeks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_promocodes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    has_had_paid_subscription: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    referred_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    referral_code: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    remnawave_uuid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    lifetime_used_traffic_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    auto_promo_group_assigned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_promo_group_threshold_kopeks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_remnawave_sync: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    trojan_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vless_uuid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ss_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    has_made_first_topup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    promo_group_id: Mapped[int] = mapped_column(ForeignKey("promo_groups.id", ondelete="RESTRICT"), nullable=False, index=True)

    promo_group: Mapped[PromoGroup] = relationship("PromoGroup", back_populates="users", lazy="selectin")
    subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        lazy="selectin",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id}>"

    @property
    def balance_rubles(self) -> float:
        return round(self.balance_kopeks / 100, 2)

    @property
    def balance_display(self) -> str:
        return f"{self.balance_rubles:.2f} ₽"

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        name = " ".join(filter(None, parts))
        if name:
            return name
        if self.username:
            return f"@{self.username}"
        return f"ID{self.telegram_id}"

    @property
    def has_active_subscription(self) -> bool:
        return bool(self.subscription and self.subscription.is_active)


class Subscription(Base):
    """Подписка пользователя."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), default=SubscriptionStatus.TRIAL.value, nullable=False)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    traffic_limit_gb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    traffic_used_gb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    subscription_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subscription_crypto_link: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    device_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    connected_squads: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    autopay_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    autopay_days_before: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    remnawave_short_uuid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="subscription", lazy="selectin")

    @property
    def actual_status(self) -> str:
        now = datetime.utcnow()
        if self.status == SubscriptionStatus.DISABLED.value:
            return "disabled"
        if self.end_date <= now:
            return "expired"
        if self.status == SubscriptionStatus.ACTIVE.value:
            return "active"
        if self.status == SubscriptionStatus.TRIAL.value:
            return "trial"
        return self.status

    @property
    def status_display(self) -> str:
        mapping = {
            "expired": "🔴 Истекла",
            "active": "🟢 Активна",
            "trial": "🎯 Тестовая",
            "disabled": "⚫ Отключена",
        }
        return mapping.get(self.actual_status, "❓ Неизвестно")

    @property
    def time_left_display(self) -> str:
        now = datetime.utcnow()
        if self.end_date <= now:
            return "истёк"
        delta = self.end_date - now
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if days > 0:
            return f"{days} дн."
        if hours > 0:
            return f"{hours} ч."
        return f"{minutes} мин."

    @property
    def traffic_used_percent(self) -> float:
        if self.traffic_limit_gb <= 0:
            return 0.0
        return min((self.traffic_used_gb / self.traffic_limit_gb) * 100, 100.0)

    @property
    def traffic_usage_display(self) -> str:
        if self.traffic_limit_gb <= 0:
            return f"{self.traffic_used_gb:.1f} ГБ"
        return f"{self.traffic_used_gb:.1f}/{self.traffic_limit_gb} ГБ ({self.traffic_used_percent:.0f}%)"

    @property
    def is_active(self) -> bool:
        return self.actual_status == "active"

    @property
    def user_display(self) -> str:
        if not self.user:
            return "-"
        return f"{self.user.full_name} ({self.user.telegram_id})"


class Transaction(Base):
    """Финансовая транзакция пользователя."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_kopeks: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="transactions", lazy="selectin")

    @property
    def amount_rubles(self) -> float:
        return round(self.amount_kopeks / 100, 2)

    @property
    def amount_display(self) -> str:
        sign = "-" if self.amount_kopeks < 0 else ""
        return f"{sign}{abs(self.amount_rubles):.2f} ₽"

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} user={self.user_id} amount={self.amount_display}>"

    @property
    def user_display(self) -> str:
        if not self.user:
            return "-"
        return f"{self.user.full_name} ({self.user.telegram_id})"
