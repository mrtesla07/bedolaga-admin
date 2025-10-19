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
