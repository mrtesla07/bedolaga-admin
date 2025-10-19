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
from app.models.security import AdminActivityLog, AdminRole, AdminSecuritySettings

__all__ = [
    "AdminUser",
    "AdminRole",
    "AdminSecuritySettings",
    "AdminActivityLog",
    "User",
    "Subscription",
    "Transaction",
    "PromoGroup",
    "UserStatus",
    "SubscriptionStatus",
    "TransactionType",
    "PaymentMethod",
]
