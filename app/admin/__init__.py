"""Админ-панель SQLAdmin."""

from app.admin.auth import BedolagaAuthenticationBackend
from app.admin.views import admin_views

__all__ = ["BedolagaAuthenticationBackend", "admin_views"]
