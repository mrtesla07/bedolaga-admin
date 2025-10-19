"""Simple dictionary-based translations for the admin interface."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

from starlette.requests import Request

DEFAULT_LOCALE = "ru"
FALLBACK_LOCALE = "en"

_MESSAGES: Mapping[str, Mapping[str, str]] = {
    "en": {
        "nav.dashboard": "Dashboard",
        "nav.actions": "Actions",
        "nav.logout": "Logout",
        "nav.overview": "Models overview",
        "layout.subtitle": "Bedolaga admin panel",
        "layout.welcome": "Signed in as {user}",
        "layout.guest": "Guest user",
        "layout.path": "Path: {path}",
        "layout.sqladmin": "SQLAdmin",
        "flash.created": "{model} was created",
        "flash.updated": "{model} was updated",
        "flash.deleted": "{model} was deleted",
        "button.save": "Save",
        "button.cancel": "Cancel",
        "button.delete": "Delete",
        "button.close": "Close",
        "actions.error.unknown.title": "Unknown action",
        "actions.error.unknown.message": "Requested action is not available. Check the submitted values.",
        "actions.error.permission.title": "Permission denied",
        "actions.error.permission.message": "You do not have access to perform this action.",
        "actions.error.api_disabled.title": "Web API is not configured",
        "actions.error.api_disabled.message": "Set WEBAPI_BASE_URL and WEBAPI_API_KEY in .env before using admin actions.",
        "actions.error.csrf.title": "CSRF check failed",
        "actions.error.rate_limit.title": "Too many requests",
        "actions.error.validation.title": "Validation error",
        "actions.error.webapi.title": "Web API error",
        "actions.error.unexpected.title": "Unexpected error",
        "actions.success.generic.title": "Action completed",
        "actions.extend.success.title": "Subscription extended",
        "actions.extend.success.message": "Subscription for user #{user_id} extended by {days} day(s).{extra}",
        "actions.extend.success.extra": " New expiration date: {end_date}.",
        "actions.extend.error.not_found": "Subscription for user #{user_id} was not found.",
        "actions.recharge.success.title": "Balance updated",
        "actions.recharge.success.message": "Balance for user #{user_id} changed by {amount:+.2f} ₽.",
        "actions.recharge.success.balance": " Current balance: {balance:.2f} ₽.",
        "actions.recharge.error.hard_limit": "Amount {amount:.2f} ₽ exceeds hard limit {limit:.2f} ₽.",
        "actions.recharge.error.confirm": "Confirm the amount and reason for the operation.",
        "actions.recharge.default_description": "Manual adjustment",
        "actions.block.success.title": "User status updated",
        "actions.block.success.message": "User #{user_id} status set to {status}.",
        "actions.block.error.mode": "Unknown blocking mode.",
        "actions.block.error.confirm": "Please confirm the blocking operation.",
        "actions.sync.success.title": "Synchronization completed",
        "actions.sync.success.message": "{detail}",
        "actions.sync.error.mode": "Unknown synchronization mode.",
        "actions.sync.detail.to_panel": "Accounts synchronized from the external service to the panel.",
        "actions.sync.detail.from_panel_all": "Accounts exported to the external service.",
        "actions.sync.detail.from_panel_update": "Updated accounts sent to the external service.",
        "actions.sync.detail.sync_statuses": "Subscription statuses synchronized with the external service.",
        "fields.user_id": "User ID",
        "fields.days": "Days",
        "fields.amount": "Amount",
        "fields.description": "Description",
        "fields.mode": "Mode",
        "validation.required": "{field}: value is required.",
        "validation.invalid_integer": "{field}: enter a valid integer.",
        "validation.invalid_amount": "{field}: enter a valid amount.",
        "validation.min_value": "{field}: value must be greater than or equal to {min}.",
        "validation.invalid_choice": "{field}: value is not allowed.",
        "status.blocked": "blocked",
        "status.active": "active",
        "csrf.invalid_format": "Invalid CSRF token format.",
        "csrf.invalid_length": "Invalid CSRF token length.",
        "csrf.invalid_signature": "CSRF token signature mismatch.",
        "csrf.expired": "CSRF token has expired.",
        "csrf.missing": "CSRF token is missing.",
        "rate_limit.exceeded": "Rate limit exceeded. Please try again later.",
        "list.export": "Export",
        "list.actions_button": "Actions",
        "list.delete_selected": "Delete selected items",
        "list.new": "+ New {name}",
        "list.search_placeholder": "Search: {placeholder}",
        "list.search_button": "Search",
        "list.search_reset": "Clear",
        "list.select_all": "Select all",
        "list.select_item": "Select item",
        "list.view": "View",
        "list.edit": "Edit",
        "list.delete": "Delete",
        "list.prev": "Previous",
        "list.next": "Next",
        "list.show": "Show",
        "list.per_page": "{size} / page",
        "list.pagination_info": "Showing {start}–{end} of {total} items",
        "form.error": "Validation error",
        "create.title": "New {name}",
        "create.save_continue": "Save and continue editing",
        "create.save_add": "Save and add another",
        "create.save_new": "Save as new",
        "edit.title": "Edit {name}",
        "details.column": "Field",
        "details.value": "Value",
        "details.back": "Back to list",
        "login.title": "Login to {title}",
        "login.username": "Username",
        "login.password": "Password",
        "login.submit": "Login",
        "modal.confirm_title": "Please confirm",
        "modal.delete_question": "Delete {item}?",
        "modal.confirm": "Confirm",
        "list.export": "Export",
        "list.actions_button": "Actions",
        "list.delete_selected": "Delete selected items",
        "list.new": "+ New {name}",
        "list.search_placeholder": "Search: {placeholder}",
        "list.search_button": "Search",
        "list.search_reset": "Clear",
        "list.select_all": "Select all",
        "list.select_item": "Select item",
        "list.view": "View",
        "list.edit": "Edit",
        "list.delete": "Delete",
        "list.prev": "Previous",
        "list.next": "Next",
        "list.show": "Show",
        "list.per_page": "{size} / page",
        "list.pagination_info": "Showing {start}–{end} of {total} items",
        "form.error": "There was an error",
        "create.title": "New {name}",
        "create.save_continue": "Save and continue editing",
        "create.save_add": "Save and add another",
        "create.save_new": "Save as new",
        "edit.title": "Edit {name}",
        "details.column": "Column",
        "details.value": "Value",
        "details.back": "Go back",
        "login.title": "Login to {title}",
        "login.username": "Username",
        "login.password": "Password",
        "login.submit": "Login",
        "modal.confirm_title": "Please confirm",
        "modal.delete_question": "Delete {item}?",
        "modal.confirm": "Confirm",
    },
    "ru": {
        "nav.dashboard": "Обзор",
        "nav.actions": "Действия web API",
        "nav.logout": "Выход",
        "nav.overview": "Список моделей",
        "layout.subtitle": "Панель управления Bedolaga",
        "layout.welcome": "Вы вошли как {user}",
        "layout.guest": "Гость панели",
        "layout.path": "Маршрут: {path}",
        "layout.sqladmin": "SQLAdmin",
        "flash.created": "Объект {model} создан",
        "flash.updated": "Объект {model} обновлён",
        "flash.deleted": "Объект {model} удалён",
        "button.save": "Сохранить",
        "button.cancel": "Отмена",
        "button.delete": "Удалить",
        "button.close": "Закрыть",
        "actions.error.unknown.title": "Неизвестное действие",
        "actions.error.unknown.message": "Запрошенное действие недоступно. Проверьте переданные значения.",
        "actions.error.permission.title": "Недостаточно прав",
        "actions.error.permission.message": "У вас нет доступа к выполнению этого действия.",
        "actions.error.api_disabled.title": "Web API не настроено",
        "actions.error.api_disabled.message": "Укажите WEBAPI_BASE_URL и WEBAPI_API_KEY в .env перед использованием действий.",
        "actions.error.csrf.title": "CSRF-проверка не пройдена",
        "actions.error.rate_limit.title": "Слишком много запросов",
        "actions.error.validation.title": "Ошибка валидации",
        "actions.error.webapi.title": "Ошибка Web API",
        "actions.error.unexpected.title": "Непредвиденная ошибка",
        "actions.success.generic.title": "Действие выполнено",
        "actions.extend.success.title": "Подписка продлена",
        "actions.extend.success.message": "Подписка пользователя №{user_id} продлена на {days} дн.{extra}",
        "actions.extend.success.extra": " Новая дата окончания: {end_date}.",
        "actions.extend.error.not_found": "Подписка пользователя №{user_id} не найдена.",
        "actions.recharge.success.title": "Баланс обновлён",
        "actions.recharge.success.message": "Баланс пользователя №{user_id} изменён на {amount:+.2f} ₽.",
        "actions.recharge.success.balance": " Текущий баланс: {balance:.2f} ₽.",
        "actions.recharge.error.hard_limit": "Сумма {amount:.2f} ₽ превышает жёсткий лимит {limit:.2f} ₽.",
        "actions.recharge.error.confirm": "Подтвердите сумму и назначение операции.",
        "actions.recharge.default_description": "Ручная корректировка",
        "actions.block.success.title": "Статус пользователя обновлён",
        "actions.block.success.message": "Пользователь №{user_id} переведён в статус {status}.",
        "actions.block.error.mode": "Неизвестный режим блокировки.",
        "actions.block.error.confirm": "Подтвердите операцию блокировки.",
        "actions.sync.success.title": "Синхронизация выполнена",
        "actions.sync.success.message": "{detail}",
        "actions.sync.error.mode": "Неизвестный режим синхронизации.",
        "actions.sync.detail.to_panel": "Учётные записи синхронизированы из внешнего сервиса в панель.",
        "actions.sync.detail.from_panel_all": "Учётные записи выгружены во внешний сервис.",
        "actions.sync.detail.from_panel_update": "Обновлённые записи отправлены во внешний сервис.",
        "actions.sync.detail.sync_statuses": "Статусы подписок синхронизированы с внешним сервисом.",
        "fields.user_id": "ID пользователя",
        "fields.days": "Количество дней",
        "fields.amount": "Сумма",
        "fields.description": "Описание",
        "fields.mode": "Режим",
        "validation.required": "{field}: значение обязательно.",
        "validation.invalid_integer": "{field}: укажите целое число.",
        "validation.invalid_amount": "{field}: укажите корректную сумму.",
        "validation.min_value": "{field}: значение должно быть не меньше {min}.",
        "validation.invalid_choice": "{field}: недопустимое значение.",
        "status.blocked": "заблокирован",
        "status.active": "активен",
        "csrf.invalid_format": "Некорректный формат CSRF-токена.",
        "csrf.invalid_length": "Некорректная длина CSRF-токена.",
        "csrf.invalid_signature": "Подпись CSRF-токена не совпадает.",
        "csrf.expired": "Срок действия CSRF-токена истёк.",
        "csrf.missing": "CSRF-токен отсутствует.",
        "rate_limit.exceeded": "Превышен лимит запросов. Повторите попытку позже.",
        "list.export": "Экспорт",
        "list.actions_button": "Действия",
        "list.delete_selected": "Удалить выбранные",
        "list.new": "+ Новый {name}",
        "list.search_placeholder": "Поиск: {placeholder}",
        "list.search_button": "Найти",
        "list.search_reset": "Очистить",
        "list.select_all": "Выбрать все",
        "list.select_item": "Выбрать запись",
        "list.view": "Просмотр",
        "list.edit": "Редактировать",
        "list.delete": "Удалить",
        "list.prev": "Назад",
        "list.next": "Далее",
        "list.show": "Показать",
        "list.per_page": "{size} / на страницу",
        "list.pagination_info": "Показаны {start}–{end} из {total} записей",
        "form.error": "Ошибка проверки данных",
        "create.title": "Создание {name}",
        "create.save_continue": "Сохранить и продолжить",
        "create.save_add": "Сохранить и создать ещё",
        "create.save_new": "Сохранить как новый",
        "edit.title": "Редактирование {name}",
        "details.column": "Поле",
        "details.value": "Значение",
        "details.back": "Назад к списку",
        "login.title": "Вход в {title}",
        "login.username": "Имя пользователя",
        "login.password": "Пароль",
        "login.submit": "Войти",
        "modal.confirm_title": "Подтвердите действие",
        "modal.delete_question": "Удалить {item}?",
        "modal.confirm": "Подтвердить",
        "form.error": "Возникла ошибка",
        "create.title": "Создание {name}",
        "create.save_continue": "Сохранить и продолжить",
        "create.save_add": "Сохранить и создать ещё",
        "create.save_new": "Сохранить как новый",
        "edit.title": "Редактирование {name}",
        "details.column": "Поле",
        "details.value": "Значение",
        "details.back": "Назад к списку",
        "login.title": "Вход в {title}",
        "login.username": "Имя пользователя",
        "login.password": "Пароль",
        "login.submit": "Войти",
        "modal.confirm_title": "Подтвердите действие",
        "modal.delete_question": "Удалить {item}?",
        "modal.confirm": "Подтвердить",
    },
}


@lru_cache(maxsize=1)
def _resolve_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    lang = locale.split("_")[0].split("-")[0]
    if lang in _MESSAGES:
        return lang
    return DEFAULT_LOCALE


def translate(key: str, *, locale: str | None = None, **kwargs: Any) -> str:
    """Translate key for given locale, with fallback to English."""
    loc = _resolve_locale(locale)
    table = _MESSAGES.get(loc, {})
    template = table.get(key) or _MESSAGES[FALLBACK_LOCALE].get(key) or key
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def t(key: str, **kwargs: Any) -> str:
    """Convenience wrapper using default locale."""
    return translate(key, locale=DEFAULT_LOCALE, **kwargs)


def get_locale(request: Request | None) -> str:
    """Safe helper for templates to fetch locale."""
    if request is None:
        return DEFAULT_LOCALE
    locale = getattr(getattr(request, "state", object()), "locale", None)
    return locale or DEFAULT_LOCALE


def resolve_locale_from_request(request: Request) -> str:
    """Determine locale from query, cookies or Accept-Language header."""
    lang = request.query_params.get("lang") if hasattr(request, "query_params") else None
    if lang:
        return _resolve_locale(lang)

    cookie_lang = request.cookies.get("lang") if hasattr(request, "cookies") else None
    if cookie_lang:
        return _resolve_locale(cookie_lang)

    header = request.headers.get("accept-language", "") if hasattr(request, "headers") else ""
    if header:
        candidates: list[tuple[float, str]] = []
        for raw_part in header.split(","):
            part = raw_part.strip()
            if not part:
                continue
            pieces = part.split(";")
            lang_code = pieces[0]
            quality = 1.0
            if len(pieces) > 1 and pieces[1].startswith("q="):
                try:
                    quality = float(pieces[1][2:])
                except ValueError:
                    quality = 0.0
            candidates.append((quality, lang_code))
        if candidates:
            candidates.sort(reverse=True)
            for _, candidate in candidates:
                resolved = _resolve_locale(candidate)
                if resolved:
                    return resolved

    return DEFAULT_LOCALE
