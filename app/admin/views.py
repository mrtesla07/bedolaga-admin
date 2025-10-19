"""Представления SQLAdmin для администраторов и сущностей бота."""

from __future__ import annotations

from sqladmin import ModelView
from starlette.requests import Request

from app.core.permissions import (
    PERM_ACTION_BALANCE,
    PERM_ACTION_BLOCK,
    PERM_ACTION_EXTEND,
    PERM_ACTION_SYNC,
    PERM_MANAGE_ROLES,
    PERM_MANAGE_USERS,
    PERM_MANAGE_SECURITY,
    PERM_VIEW_AUDIT,
    PERM_VIEW_READONLY,
)
from app.models import (
    AdminActivityLog,
    AdminRole,
    AdminSecuritySettings,
    AdminUser,
    PaymentMethod,
    Subscription,
    SubscriptionStatus,
    Transaction,
    TransactionType,
    User,
    UserStatus,
)

USER_STATUS_CHOICES = [
    (UserStatus.ACTIVE.value, "Активен"),
    (UserStatus.BLOCKED.value, "Заблокирован"),
    (UserStatus.DELETED.value, "Удалён"),
]

SUBSCRIPTION_STATUS_CHOICES = [
    (SubscriptionStatus.TRIAL.value, "Триал"),
    (SubscriptionStatus.ACTIVE.value, "Активна"),
    (SubscriptionStatus.EXPIRED.value, "Истекла"),
    (SubscriptionStatus.DISABLED.value, "Отключена"),
]

TRANSACTION_TYPE_CHOICES = [
    (TransactionType.DEPOSIT.value, "Пополнение"),
    (TransactionType.WITHDRAWAL.value, "Списание"),
    (TransactionType.SUBSCRIPTION_PAYMENT.value, "Оплата подписки"),
    (TransactionType.REFUND.value, "Возврат"),
    (TransactionType.REFERRAL_REWARD.value, "Реферальное вознаграждение"),
]

PAYMENT_METHOD_CHOICES = [
    (PaymentMethod.TELEGRAM_STARS.value, "Telegram Stars"),
    (PaymentMethod.TRIBUTE.value, "Tribute"),
    (PaymentMethod.YOOKASSA.value, "YooKassa"),
    (PaymentMethod.CRYPTOBOT.value, "CryptoBot"),
    (PaymentMethod.MULENPAY.value, "MulenPay"),
    (PaymentMethod.PAL24.value, "Pal24"),
    (PaymentMethod.MANUAL.value, "Ручной"),
]


class ProtectedModelView(ModelView):
    """Базовый класс с проверкой разрешений."""

    required_permissions: set[str] = set()

    def is_accessible(self, request: Request) -> bool:  # type: ignore[override]
        if not self.required_permissions:
            return True
        permissions = getattr(request.state, "admin_permissions", set())
        return permissions.issuperset(self.required_permissions)

    def is_visible(self, request: Request) -> bool:  # type: ignore[override]
        return self.is_accessible(request)


class AdminUserAdmin(ProtectedModelView, model=AdminUser):
    """Управление аккаунтами администраторов."""

    name_plural = "Администраторы"
    icon = "fa-solid fa-user-gear"
    required_permissions = {PERM_MANAGE_USERS}

    can_create = False
    can_delete = False
    form_ajax_refs = {
        "roles": {
            "fields": ("slug", "name"),
        }
    }

    column_list = [
        AdminUser.id,
        AdminUser.email,
        AdminUser.full_name,
        AdminUser.is_active,
        AdminUser.is_superuser,
        "role_slugs",
        AdminUser.created_at,
    ]
    column_searchable_list = [AdminUser.email, AdminUser.full_name]
    column_sortable_list = [AdminUser.id, AdminUser.email, AdminUser.created_at]
    column_labels = {
        AdminUser.email: "Email",
        AdminUser.full_name: "Имя",
        AdminUser.is_active: "Активен",
        AdminUser.is_superuser: "Суперпользователь",
        "role_slugs": "Роли",
        AdminUser.created_at: "Создан",
    }

    form_columns = [
        AdminUser.email,
        AdminUser.full_name,
        AdminUser.is_active,
        AdminUser.is_superuser,
        AdminUser.roles,
    ]
    form_excluded_columns = [AdminUser.hashed_password, AdminUser.activity_logs]
    column_details_list = [
        AdminUser.id,
        AdminUser.email,
        AdminUser.full_name,
        "role_slugs",
        AdminUser.is_active,
        AdminUser.is_superuser,
        AdminUser.created_at,
    ]


class AdminRoleAdmin(ProtectedModelView, model=AdminRole):
    """Роли администраторов."""

    name = "Роль"
    name_plural = "Роли"
    icon = "fa-solid fa-key"
    required_permissions = {PERM_MANAGE_ROLES}

    column_list = [AdminRole.id, AdminRole.slug, AdminRole.name, AdminRole.description, AdminRole.created_at]
    column_sortable_list = [AdminRole.id, AdminRole.slug, AdminRole.name, AdminRole.created_at]
    column_searchable_list = [AdminRole.slug, AdminRole.name]
    column_labels = {
        AdminRole.slug: "Slug",
        AdminRole.name: "Название",
        AdminRole.description: "Описание",
        AdminRole.created_at: "Создана",
    }
    form_columns = [AdminRole.slug, AdminRole.name, AdminRole.description]


class SecuritySettingsAdmin(ProtectedModelView, model=AdminSecuritySettings):
    """Настройки безопасности."""

    name = "Настройки безопасности"
    name_plural = "Настройки безопасности"
    icon = "fa-solid fa-shield-halved"
    required_permissions = {PERM_MANAGE_SECURITY}

    can_create = False
    can_delete = False

    column_list = [
        AdminSecuritySettings.id,
        AdminSecuritySettings.balance_soft_limit_rub,
        AdminSecuritySettings.balance_hard_limit_rub,
        AdminSecuritySettings.require_balance_confirmation,
        AdminSecuritySettings.require_block_confirmation,
        AdminSecuritySettings.rate_limit_count,
        AdminSecuritySettings.rate_limit_period_seconds,
        AdminSecuritySettings.updated_at,
    ]
    column_labels = {
        AdminSecuritySettings.balance_soft_limit_rub: "Мягкий лимит (₽)",
        AdminSecuritySettings.balance_hard_limit_rub: "Жёсткий лимит (₽)",
        AdminSecuritySettings.require_balance_confirmation: "Требовать подтверждение суммы",
        AdminSecuritySettings.require_block_confirmation: "Требовать подтверждение блокировки",
        AdminSecuritySettings.rate_limit_count: "Макс. операций",
        AdminSecuritySettings.rate_limit_period_seconds: "Окно (сек)",
        AdminSecuritySettings.updated_at: "Обновлено",
    }
    form_columns = [
        AdminSecuritySettings.balance_soft_limit_rub,
        AdminSecuritySettings.balance_hard_limit_rub,
        AdminSecuritySettings.require_balance_confirmation,
        AdminSecuritySettings.require_block_confirmation,
        AdminSecuritySettings.rate_limit_count,
        AdminSecuritySettings.rate_limit_period_seconds,
    ]


class ReadOnlyModelView(ProtectedModelView):
    """Блокировка destructive-операций для данных бота."""

    required_permissions = {PERM_VIEW_READONLY}
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    page_size = 50


class BotUserAdmin(ReadOnlyModelView, model=User):
    """Просмотр пользователей бота."""

    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"

    column_list = [
        User.id,
        User.telegram_id,
        "full_name",
        User.status,
        "balance_display",
        User.has_had_paid_subscription,
        User.has_active_subscription,
        User.language,
        User.created_at,
        User.last_activity,
    ]
    column_searchable_list = [
        User.telegram_id,
        User.username,
        User.first_name,
        User.last_name,
        User.referral_code,
        User.remnawave_uuid,
    ]
    column_sortable_list = [
        User.id,
        User.telegram_id,
        User.created_at,
        User.last_activity,
        User.balance_kopeks,
    ]
    column_filters = [
        User.status,
        User.language,
        User.has_had_paid_subscription,
        User.has_made_first_topup,
    ]
    column_labels = {
        User.telegram_id: "Telegram ID",
        "full_name": "Имя",
        User.status: "Статус",
        "balance_display": "Баланс",
        User.has_had_paid_subscription: "Были платные подписки",
        User.has_active_subscription: "Активная подписка",
        User.language: "Язык",
        User.created_at: "Создан",
        User.last_activity: "Последняя активность",
    }
    column_details_list = [
        User.id,
        User.telegram_id,
        User.username,
        User.first_name,
        User.last_name,
        User.status,
        User.language,
        "balance_display",
        User.balance_kopeks,
        User.used_promocodes,
        User.has_had_paid_subscription,
        User.has_active_subscription,
        User.promo_group_id,
        User.remnawave_uuid,
        User.last_remnawave_sync,
        User.created_at,
        User.updated_at,
        User.last_activity,
        User.auto_promo_group_assigned,
        User.auto_promo_group_threshold_kopeks,
        User.lifetime_used_traffic_bytes,
    ]
    column_choices = {
        User.status: USER_STATUS_CHOICES,
    }


class SubscriptionAdmin(ReadOnlyModelView, model=Subscription):
    """Просмотр подписок."""

    name = "Подписка"
    name_plural = "Подписки"
    icon = "fa-solid fa-clock-rotate-left"
    required_permissions = ReadOnlyModelView.required_permissions

    column_list = [
        Subscription.id,
        Subscription.user_id,
        "user_display",
        Subscription.status,
        "status_display",
        Subscription.is_trial,
        Subscription.autopay_enabled,
        Subscription.start_date,
        Subscription.end_date,
        "time_left_display",
        "traffic_usage_display",
    ]
    column_sortable_list = [
        Subscription.id,
        Subscription.user_id,
        Subscription.start_date,
        Subscription.end_date,
        Subscription.status,
    ]
    column_searchable_list = [Subscription.user_id, Subscription.remnawave_short_uuid]
    column_filters = [
        Subscription.status,
        Subscription.is_trial,
        Subscription.autopay_enabled,
    ]
    column_labels = {
        Subscription.user_id: "ID пользователя",
        "user_display": "Пользователь",
        Subscription.status: "Статус",
        "status_display": "Описание статуса",
        Subscription.is_trial: "Триал",
        Subscription.autopay_enabled: "Автоплатёж",
        Subscription.start_date: "Начало",
        Subscription.end_date: "Завершение",
        "time_left_display": "Осталось",
        "traffic_usage_display": "Трафик",
    }
    column_details_list = [
        Subscription.id,
        Subscription.user_id,
        "user_display",
        Subscription.status,
        Subscription.is_trial,
        Subscription.start_date,
        Subscription.end_date,
        Subscription.traffic_limit_gb,
        Subscription.traffic_used_gb,
        "traffic_usage_display",
        Subscription.device_limit,
        Subscription.connected_squads,
        Subscription.autopay_enabled,
        Subscription.autopay_days_before,
        Subscription.subscription_url,
        Subscription.subscription_crypto_link,
        Subscription.remnawave_short_uuid,
        Subscription.created_at,
        Subscription.updated_at,
    ]
    column_choices = {
        Subscription.status: SUBSCRIPTION_STATUS_CHOICES,
    }


class TransactionAdmin(ReadOnlyModelView, model=Transaction):
    """Просмотр транзакций."""

    name = "Транзакция"
    name_plural = "Транзакции"
    icon = "fa-solid fa-money-check"
    required_permissions = ReadOnlyModelView.required_permissions
    column_default_sort = (Transaction.created_at, True)

    column_list = [
        Transaction.id,
        Transaction.user_id,
        "user_display",
        Transaction.type,
        Transaction.payment_method,
        "amount_display",
        Transaction.is_completed,
        Transaction.created_at,
        Transaction.completed_at,
    ]
    column_searchable_list = [
        Transaction.user_id,
        Transaction.external_id,
        Transaction.description,
    ]
    column_sortable_list = [
        Transaction.id,
        Transaction.user_id,
        Transaction.created_at,
        Transaction.amount_kopeks,
        Transaction.is_completed,
    ]
    column_filters = [
        Transaction.type,
        Transaction.payment_method,
        Transaction.is_completed,
    ]
    column_labels = {
        Transaction.user_id: "ID пользователя",
        "user_display": "Пользователь",
        Transaction.type: "Тип",
        Transaction.payment_method: "Способ оплаты",
        "amount_display": "Сумма",
        Transaction.is_completed: "Завершена",
        Transaction.created_at: "Создана",
        Transaction.completed_at: "Завершена в",
        Transaction.external_id: "Внешний ID",
    }
    column_details_list = [
        Transaction.id,
        Transaction.user_id,
        "user_display",
        Transaction.type,
        Transaction.payment_method,
        Transaction.description,
        Transaction.external_id,
        "amount_display",
        Transaction.amount_kopeks,
        Transaction.is_completed,
        Transaction.created_at,
        Transaction.completed_at,
    ]
    column_choices = {
        Transaction.type: TRANSACTION_TYPE_CHOICES,
        Transaction.payment_method: PAYMENT_METHOD_CHOICES,
    }


class AdminActivityLogAdmin(ReadOnlyModelView, model=AdminActivityLog):
    """Журнал действий администраторов."""

    name = "Журнал действий"
    name_plural = "Журнал действий"
    icon = "fa-solid fa-clipboard-list"
    required_permissions = {PERM_VIEW_AUDIT}
    page_size = 100

    column_list = [
        AdminActivityLog.id,
        AdminActivityLog.created_at,
        AdminActivityLog.admin_id,
        "admin_email",
        AdminActivityLog.action,
        AdminActivityLog.status,
        AdminActivityLog.target_type,
        AdminActivityLog.target_id,
    ]
    column_sortable_list = [
        AdminActivityLog.id,
        AdminActivityLog.created_at,
        AdminActivityLog.status,
        AdminActivityLog.target_type,
    ]
    column_filters = [
        AdminActivityLog.status,
        AdminActivityLog.action,
        AdminActivityLog.target_type,
    ]
    column_searchable_list = [
        AdminActivityLog.action,
        AdminActivityLog.message,
        AdminActivityLog.ip_address,
        AdminActivityLog.user_agent,
    ]
    column_labels = {
        AdminActivityLog.created_at: "Дата",
        AdminActivityLog.admin_id: "ID администратора",
        "admin_email": "Email администратора",
        AdminActivityLog.action: "Действие",
        AdminActivityLog.status: "Статус",
        AdminActivityLog.target_type: "Тип объекта",
        AdminActivityLog.target_id: "ID объекта",
        AdminActivityLog.message: "Сообщение",
        AdminActivityLog.ip_address: "IP",
        AdminActivityLog.user_agent: "User-Agent",
    }
    column_details_list = [
        AdminActivityLog.id,
        AdminActivityLog.created_at,
        AdminActivityLog.admin_id,
        "admin_email",
        AdminActivityLog.action,
        AdminActivityLog.status,
        AdminActivityLog.target_type,
        AdminActivityLog.target_id,
        AdminActivityLog.message,
        AdminActivityLog.payload_json,
        AdminActivityLog.ip_address,
        AdminActivityLog.user_agent,
    ]


admin_views = [
    AdminUserAdmin,
    AdminRoleAdmin,
    SecuritySettingsAdmin,
    BotUserAdmin,
    SubscriptionAdmin,
    TransactionAdmin,
    AdminActivityLogAdmin,
]
