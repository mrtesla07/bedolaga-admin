"""Simple dictionary-based translations for the admin interface."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

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
