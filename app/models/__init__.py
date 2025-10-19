"""Импорт моделей для регистрации в SQLAdmin."""

from app.models.admin_user import AdminUser
from app.models.bot_entities import (
    PaymentMethod,
    PromoGroup,
    Subscription,
    SubscriptionStatus,
    Transaction,
    TransactionType,
    User,
    UserStatus,
)

__all__ = [
    "AdminUser",
    "User",
    "Subscription",
    "Transaction",
    "PromoGroup",
    "UserStatus",
    "SubscriptionStatus",
    "TransactionType",
    "PaymentMethod",
]
