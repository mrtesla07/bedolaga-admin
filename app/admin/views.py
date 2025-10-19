"""Определение представлений SQLAdmin."""

from sqladmin import ModelView

from app.models import AdminUser


class AdminUserAdmin(ModelView, model=AdminUser):
    """CRUD для администраторов."""

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

    can_create = False  # создание через отдельный скрипт для контроля хешей


admin_views = [AdminUserAdmin]
