"""Представления SQLAdmin для админов и сущностей бота."""

from sqladmin import ModelView

from app.models import (
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


class AdminUserAdmin(ModelView, model=AdminUser):
    """CRUD для администраторов панели."""

    name_plural = "Администраторы"

    column_list = [AdminUser.id, AdminUser.email, AdminUser.is_active, AdminUser.is_superuser, AdminUser.created_at]
    column_searchable_list = [AdminUser.email, AdminUser.full_name]
    column_sortable_list = [AdminUser.id, AdminUser.email, AdminUser.created_at]
    column_labels = {
        AdminUser.email: "Email",
        AdminUser.full_name: "Имя",
        AdminUser.is_active: "Активен",
        AdminUser.is_superuser: "Суперпользователь",
        AdminUser.created_at: "Создан",
    }

    form_columns = [
        AdminUser.email,
        AdminUser.full_name,
        AdminUser.is_active,
        AdminUser.is_superuser,
    ]

    form_excluded_columns = [AdminUser.hashed_password]

    can_create = False  # создание только через setup/скрипт


class ReadOnlyModelView(ModelView):
    """Блокировка destructive-операций для данных бота."""

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
        "status_display": "Отображение статуса",
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


admin_views = [
    AdminUserAdmin,
    BotUserAdmin,
    SubscriptionAdmin,
    TransactionAdmin,
]
