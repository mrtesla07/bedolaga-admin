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
    # explicit query parameter has the highest priority
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
