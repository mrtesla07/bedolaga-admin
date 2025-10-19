"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from starlette.middleware.sessions import SessionMiddleware

from sqladmin import Admin

from app.admin import BedolagaAuthenticationBackend, admin_views
from app.core.config import get_settings
from app.core.csrf import CSRFAuthError, issue_csrf, validate_csrf_token
from app.core.permissions import (
    PERM_ACTION_BALANCE,
    PERM_ACTION_BLOCK,
    PERM_ACTION_EXTEND,
    PERM_ACTION_SYNC,
)
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionFactory, engine
from app.models import AdminSecuritySettings, AdminUser, Subscription, UserStatus
from app.services.audit import log_admin_action
from app.services.rate_limiter import RateLimitExceeded, RateLimiter
from app.services.roles import ensure_default_roles
from app.i18n import translate, get_locale
from app.middlewares import LocaleMiddleware
from app.services.webapi import (
    WebAPIConfigurationError,
    WebAPIRequestError,
    get_webapi_client,
    is_webapi_configured,
)

logger = logging.getLogger(__name__)


settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.add_middleware(LocaleMiddleware)
app.state.admin_exists = False

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals['translate'] = translate
templates.env.globals['get_locale'] = get_locale

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.admin_secret_key,
    session_cookie="bedolaga_admin_session",
)


auth_backend = BedolagaAuthenticationBackend(session_factory=AsyncSessionFactory)
admin = Admin(
    app=app,
    engine=engine,
    authentication_backend=auth_backend,
    templates_dir=str(Path(__file__).parent / "templates/sqladmin"),
)

for view in admin_views:
    admin.add_view(view)

ADMIN_ACTIONS: list[dict[str, Any]] = [
    {
        "key": "extend_subscription",
        "title": "Р СџРЎР‚Р С•Р Т‘Р В»Р С‘РЎвЂљРЎРЉ Р С—Р С•Р Т‘Р С—Р С‘РЎРѓР С”РЎС“",
        "description": "Р СџРЎР‚Р С•Р Т‘Р В»Р ВµР Р†Р В°Р ВµРЎвЂљ РЎвЂљР ВµР С”РЎС“РЎвЂ°РЎС“РЎР‹ Р С—Р С•Р Т‘Р С—Р С‘РЎРѓР С”РЎС“ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ РЎвЂЎР ВµРЎР‚Р ВµР В· web API.",
        "permission": PERM_ACTION_EXTEND,
        "fields": [
            {
                "name": "user_id",
                "label": "ID Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ",
                "type": "number",
                "required": True,
                "min": 1,
                "placeholder": "Р СњР В°Р С—РЎР‚Р С‘Р СР ВµРЎР‚, 102",
            },
            {
                "name": "days",
                "label": "Р С™Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р Т‘Р Р…Р ВµР в„–",
                "type": "number",
                "required": True,
                "min": 1,
                "default": "7",
                "placeholder": "7",
            },
        ],
    },
    {
        "key": "recharge_balance",
        "title": "Р СњР В°РЎвЂЎР С‘РЎРѓР В»Р С‘РЎвЂљРЎРЉ Р В±Р В°Р В»Р В°Р Р…РЎРѓ",
        "description": "Р СњР В°РЎвЂЎР С‘РЎРѓР В»РЎРЏР ВµРЎвЂљ Р С‘Р В»Р С‘ РЎРѓР С—Р С‘РЎРѓРЎвЂ№Р Р†Р В°Р ВµРЎвЂљ Р В±Р В°Р В»Р В°Р Р…РЎРѓ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ РЎРѓ Р С•Р С—РЎвЂ Р С‘Р С•Р Р…Р В°Р В»РЎРЉР Р…Р С•Р в„– Р В·Р В°Р С—Р С‘РЎРѓРЎРЉРЎР‹ Р Р† РЎвЂљРЎР‚Р В°Р Р…Р В·Р В°Р С”РЎвЂ Р С‘Р С‘.",
        "permission": PERM_ACTION_BALANCE,
        "fields": [
            {
                "name": "user_id",
                "label": "ID Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ",
                "type": "number",
                "required": True,
                "min": 1,
                "placeholder": "ID Р Р† РЎвЂљР В°Р В±Р В»Р С‘РЎвЂ Р Вµ users",
            },
            {
                "name": "amount_rub",
                "label": "Р РЋРЎС“Р СР СР В°, РІвЂљР…",
                "type": "number",
                "step": "0.01",
                "required": True,
                "placeholder": "100.00",
            },
            {
                "name": "description",
                "label": "Р С™Р С•Р СР СР ВµР Р…РЎвЂљР В°РЎР‚Р С‘Р в„–",
                "type": "textarea",
                "rows": 3,
                "placeholder": "Р СџРЎР‚Р С‘РЎвЂЎР С‘Р Р…Р В° Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР С‘РЎР‚Р С•Р Р†Р С”Р С‘, Р С—Р С•РЎРЏР Р†Р С‘РЎвЂљРЎРѓРЎРЏ Р Р† Р С•Р С—Р С‘РЎРѓР В°Р Р…Р С‘Р С‘ РЎвЂљРЎР‚Р В°Р Р…Р В·Р В°Р С”РЎвЂ Р С‘Р С‘",
            },
            {
                "name": "create_transaction",
                "label": "Р РЋР С•Р В·Р Т‘Р В°РЎвЂљРЎРЉ Р В·Р В°Р С—Р С‘РЎРѓРЎРЉ Р Р† Р С‘РЎРѓРЎвЂљР С•РЎР‚Р С‘Р С‘ РЎвЂљРЎР‚Р В°Р Р…Р В·Р В°Р С”РЎвЂ Р С‘Р в„–",
                "type": "checkbox",
                "default": True,
            },
        ],
    },
    {
        "key": "block_user",
        "title": "Р С›Р В±Р Р…Р С•Р Р†Р С‘РЎвЂљРЎРЉ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ",
        "description": "Р СџР ВµРЎР‚Р ВµР С”Р В»РЎР‹РЎвЂЎР В°Р ВµРЎвЂљ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ Р СР ВµР В¶Р Т‘РЎС“ Р В°Р С”РЎвЂљР С‘Р Р†Р Р…РЎвЂ№Р С Р С‘ Р В·Р В°Р В±Р В»Р С•Р С”Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р Р…РЎвЂ№Р С.",
        "permission": PERM_ACTION_BLOCK,
        "fields": [
            {
                "name": "user_id",
                "label": "ID Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ",
                "type": "number",
                "required": True,
                "min": 1,
                "placeholder": "ID Р Р† РЎвЂљР В°Р В±Р В»Р С‘РЎвЂ Р Вµ users",
            },
            {
                "name": "mode",
                "label": "Р вЂќР ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р Вµ",
                "type": "select",
                "default": "block",
                "options": [
                    {"value": "block", "label": "Р вЂ”Р В°Р В±Р В»Р С•Р С”Р С‘РЎР‚Р С•Р Р†Р В°РЎвЂљРЎРЉ"},
                    {"value": "unblock", "label": "Р В Р В°Р В·Р В±Р В»Р С•Р С”Р С‘РЎР‚Р С•Р Р†Р В°РЎвЂљРЎРЉ"},
                ],
            },
        ],
    },
    {
        "key": "sync_access",
        "title": "Р РЋР С‘Р Р…РЎвЂ¦РЎР‚Р С•Р Р…Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ РЎРѓ RemnaWave",
        "description": "Р вЂ”Р В°Р С—РЎС“РЎРѓР С”Р В°Р ВµРЎвЂљ РЎРѓР С‘Р Р…РЎвЂ¦РЎР‚Р С•Р Р…Р С‘Р В·Р В°РЎвЂ Р С‘РЎР‹ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ Р СР ВµР В¶Р Т‘РЎС“ Р В±Р С•РЎвЂљР С•Р С Р С‘ RemnaWave Р С—Р В°Р Р…Р ВµР В»РЎРЉРЎР‹.",
        "permission": PERM_ACTION_SYNC,
        "fields": [
            {
                "name": "mode",
                "label": "Р С›Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘РЎРЏ",
                "type": "select",
                "default": "to_panel",
                "options": [
                    {"value": "to_panel", "label": "Р вЂ™РЎвЂ№Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ Р Р† Р С—Р В°Р Р…Р ВµР В»РЎРЉ"},
                    {"value": "from_panel_all", "label": "Р вЂ”Р В°Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ Р С‘Р В· Р С—Р В°Р Р…Р ВµР В»Р С‘ (Р Р†РЎРѓР Вµ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»Р С‘)"},
                    {"value": "from_panel_update", "label": "Р вЂ”Р В°Р С–РЎР‚РЎС“Р В·Р С‘РЎвЂљРЎРЉ Р С‘Р В· Р С—Р В°Р Р…Р ВµР В»Р С‘ (РЎвЂљР С•Р В»РЎРЉР С”Р С• Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘РЎРЏ)"},
                    {"value": "sync_statuses", "label": "Р РЋР С‘Р Р…РЎвЂ¦РЎР‚Р С•Р Р…Р С‘Р В·Р С‘РЎР‚Р С•Р Р†Р В°РЎвЂљРЎРЉ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓРЎвЂ№ Р С—Р С•Р Т‘Р С—Р С‘РЎРѓР С•Р С”"},
                ],
            },
        ],
    },
]

class ActionValidationError(ValueError):
    """Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р Р†Р В°Р В»Р С‘Р Т‘Р В°РЎвЂ Р С‘Р С‘ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎРЏ."""


def _get_action_meta(action_key: str) -> dict[str, Any] | None:
    return next((item for item in ADMIN_ACTIONS if item["key"] == action_key), None)


def _require_int(value: str | None, *, label: str, min_value: int | None = None) -> int:
    if value is None or str(value).strip() == "":
        raise ActionValidationError(f"{label}: РЎС“Р С”Р В°Р В¶Р С‘РЎвЂљР Вµ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘Р Вµ.")
    try:
        number = int(str(value).strip())
    except ValueError as exc:
        raise ActionValidationError(f"{label}: Р С•Р В¶Р С‘Р Т‘Р В°Р ВµРЎвЂљРЎРѓРЎРЏ РЎвЂ Р ВµР В»Р С•Р Вµ РЎвЂЎР С‘РЎРѓР В»Р С•.") from exc
    if min_value is not None and number < min_value:
        raise ActionValidationError(f"{label}: Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘Р Вµ Р Т‘Р С•Р В»Р В¶Р Р…Р С• Р В±РЎвЂ№РЎвЂљРЎРЉ Р Р…Р Вµ Р СР ВµР Р…РЎРЉРЎв‚¬Р Вµ {min_value}.")
    return number


def _format_sync_message(response: dict[str, Any], default: str) -> str:
    detail = response.get("detail") or default
    data = response.get("data") or response.get("stats")
    if isinstance(data, dict) and data:
        pairs = ", ".join(f"{key}: {value}" for key, value in data.items())
        return f"{detail} ({pairs})"
    return detail


def _get_permissions(request: Request) -> set[str]:
    """Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ Р СР Р…Р С•Р В¶Р ВµРЎРѓРЎвЂљР Р†Р С• РЎР‚Р В°Р В·РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р С‘Р в„– РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР С–Р С• Р В°Р Т‘Р СР С‘Р Р…Р С‘РЎРѓРЎвЂљРЎР‚Р В°РЎвЂљР С•РЎР‚Р В°."""
    perms = getattr(request.state, "admin_permissions", set())
    return set(perms)


def _build_allowed_actions(permissions: set[str]) -> dict[str, bool]:
    """Р РЋР С•Р В·Р Т‘Р В°РЎвЂРЎвЂљ Р С”Р В°РЎР‚РЎвЂљРЎС“ Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…РЎвЂ№РЎвЂ¦ Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р в„–."""
    allowed: dict[str, bool] = {}
    for action in ADMIN_ACTIONS:
        required = action.get("permission")
        allowed[action["key"]] = required is None or required in permissions
    return allowed



async def _ensure_security_settings() -> None:
    async with AsyncSessionFactory() as session:
        settings = await session.get(AdminSecuritySettings, 1)
        if settings is None:
            session.add(AdminSecuritySettings(id=1))
            await session.commit()


async def _get_security_settings() -> AdminSecuritySettings:
    async with AsyncSessionFactory() as session:
        settings = await session.get(AdminSecuritySettings, 1)
        if settings is None:
            settings = AdminSecuritySettings(id=1)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


def _parse_amount_rubles(value: str | None) -> tuple[int, Decimal]:
    if value is None or not str(value).strip():
        raise ActionValidationError("Р РЋРЎС“Р СР СР В°: РЎС“Р С”Р В°Р В¶Р С‘РЎвЂљР Вµ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘Р Вµ.")
    normalized = str(value).replace(",", ".").strip()
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ActionValidationError("Р РЋРЎС“Р СР СР В°: Р Р…Р ВµР С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№Р в„– РЎвЂћР С•РЎР‚Р СР В°РЎвЂљ.") from exc
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount == 0:
        raise ActionValidationError("Р РЋРЎС“Р СР СР В° Р Т‘Р С•Р В»Р В¶Р Р…Р В° Р С•РЎвЂљР В»Р С‘РЎвЂЎР В°РЎвЂљРЎРЉРЎРѓРЎРЏ Р С•РЎвЂљ Р Р…РЎС“Р В»РЎРЏ.")
    kopeks = int(amount * 100)
    return kopeks, amount


def _is_checked(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"on", "true", "1", "yes"}
    return bool(value)


async def _execute_action(
    action_key: str,
    form: Dict[str, Any],
    security_settings: AdminSecuritySettings,
) -> dict[str, Any]:
    client = get_webapi_client()

    if action_key == "extend_subscription":
        user_id = _require_int(form.get("user_id"), label="ID Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ", min_value=1)
        days = _require_int(form.get("days"), label="Р С™Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р Т‘Р Р…Р ВµР в„–", min_value=1)

        async with AsyncSessionFactory() as session:
            result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalar_one_or_none()

        if not subscription:
            raise ActionValidationError("Р Р€ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ Р Р…Р ВµРЎвЂљ Р В°Р С”РЎвЂљР С‘Р Р†Р Р…Р С•Р в„– Р С—Р С•Р Т‘Р С—Р С‘РЎРѓР С”Р С‘.")

        response = await client.extend_subscription(subscription.id, days)
        end_date = response.get("end_date")

        message = f"Р СџР С•Р Т‘Р С—Р С‘РЎРѓР С”Р В° Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ {user_id} Р С—РЎР‚Р С•Р Т‘Р В»Р ВµР Р…Р В° Р Р…Р В° {days} Р Т‘Р Р…."
        if end_date:
            message += f" Р СњР С•Р Р†Р В°РЎРЏ Р Т‘Р В°РЎвЂљР В° Р С•Р С”Р С•Р Р…РЎвЂЎР В°Р Р…Р С‘РЎРЏ: {end_date}."

        return {
            "status": "success",
            "title": "Р СџР С•Р Т‘Р С—Р С‘РЎРѓР С”Р В° Р С—РЎР‚Р С•Р Т‘Р В»Р ВµР Р…Р В°",
            "message": message,
            "response": response,
            "_audit": {
                "target_type": "subscription",
                "target_id": str(subscription.id),
                "payload": {
                    "input": {"user_id": user_id, "days": days},
                    "response": response,
                },
            },
        }

    if action_key == "recharge_balance":
        user_id = _require_int(form.get("user_id"), label="ID Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ", min_value=1)
        amount_kopeks, amount = _parse_amount_rubles(form.get("amount_rub"))
        description = (form.get("description") or "Р С™Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР С‘РЎР‚Р С•Р Р†Р С”Р В° РЎвЂЎР ВµРЎР‚Р ВµР В· Р В°Р Т‘Р СР С‘Р Р…Р С”РЎС“").strip()
        create_transaction = _is_checked(form.get("create_transaction"))

        amount_abs = abs(amount)
        soft_limit = Decimal(security_settings.balance_soft_limit_rub or 0)
        hard_limit = Decimal(security_settings.balance_hard_limit_rub or 0)
        confirmation_checked = _is_checked(form.get("confirm_amount"))

        if hard_limit > 0 and amount_abs > hard_limit:
            raise ActionValidationError(
                f"Р РЋРЎС“Р СР СР В° {amount_abs:.2f} РІвЂљР… Р С—РЎР‚Р ВµР Р†РЎвЂ№РЎв‚¬Р В°Р ВµРЎвЂљ Р В¶РЎвЂРЎРѓРЎвЂљР С”Р С‘Р в„– Р В»Р С‘Р СР С‘РЎвЂљ {hard_limit:.2f} РІвЂљР…."
            )

        if (
            security_settings.require_balance_confirmation
            and soft_limit > 0
            and amount_abs > soft_limit
            and not confirmation_checked
        ):
            raise ActionValidationError(
                "Р СџР С•Р Т‘РЎвЂљР Р†Р ВµРЎР‚Р Т‘Р С‘РЎвЂљР Вµ Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…Р С‘Р Вµ Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘Р С‘, Р С•РЎвЂљР СР ВµРЎвЂљР С‘Р Р† РЎвЂЎР ВµР С”Р В±Р С•Р С”РЎРѓ Р С—Р С•Р Т‘РЎвЂљР Р†Р ВµРЎР‚Р В¶Р Т‘Р ВµР Р…Р С‘РЎРЏ."
            )

        response = await client.update_balance(
            user_id,
            amount_kopeks,
            description=description,
            create_transaction=create_transaction,
        )

        balance_rubles = response.get("balance_rubles")
        if balance_rubles is None and "balance_kopeks" in response:
            try:
                balance_rubles = Decimal(response["balance_kopeks"]) / 100
            except (InvalidOperation, TypeError):
                balance_rubles = None

        message = f"Р вЂР В°Р В»Р В°Р Р…РЎРѓ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ {user_id} РЎРѓР С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР С‘РЎР‚Р С•Р Р†Р В°Р Р… Р Р…Р В° {amount:+.2f} РІвЂљР…."
        if balance_rubles is not None:
            message += f" Р СћР ВµР С”РЎС“РЎвЂ°Р С‘Р в„– Р В±Р В°Р В»Р В°Р Р…РЎРѓ: {Decimal(str(balance_rubles)):.2f} РІвЂљР…."

        return {
            "status": "success",
            "title": "Р вЂР В°Р В»Р В°Р Р…РЎРѓ Р С•Р В±Р Р…Р С•Р Р†Р В»РЎвЂР Р…",
            "message": message,
            "response": response,
            "_audit": {
                "target_type": "user",
                "target_id": str(user_id),
                "payload": {
                    "input": {
                        "amount_kopeks": amount_kopeks,
                        "amount_rub": f"{amount:.2f}",
                        "description": description,
                        "create_transaction": create_transaction,
                        "confirmed": confirmation_checked,
                    },
                    "response": response,
                    "limits": {
                        "soft_limit_rub": security_settings.balance_soft_limit_rub,
                        "hard_limit_rub": security_settings.balance_hard_limit_rub,
                    },
                },
            },
        }

    if action_key == "block_user":
        user_id = _require_int(form.get("user_id"), label="ID Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ", min_value=1)
        mode = str(form.get("mode") or "block").lower()
        if mode not in {"block", "unblock"}:
            raise ActionValidationError("Р вЂ™РЎвЂ№Р В±Р ВµРЎР‚Р С‘РЎвЂљР Вµ Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…Р С•Р Вµ Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р Вµ Р Т‘Р В»РЎРЏ Р С‘Р В·Р СР ВµР Р…Р ВµР Р…Р С‘РЎРЏ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР В°.")

        confirmation_checked = _is_checked(form.get("confirm_block"))
        if security_settings.require_block_confirmation and not confirmation_checked:
            raise ActionValidationError("Р СџР С•Р Т‘РЎвЂљР Р†Р ВµРЎР‚Р Т‘Р С‘РЎвЂљР Вµ Р В±Р В»Р С•Р С”Р С‘РЎР‚Р С•Р Р†Р С”РЎС“, Р С•РЎвЂљР СР ВµРЎвЂљР С‘Р Р† РЎвЂЎР ВµР С”Р В±Р С•Р С”РЎРѓ.")

        status_value = UserStatus.BLOCKED.value if mode == "block" else UserStatus.ACTIVE.value
        response = await client.update_user_status(user_id, status_value)
        new_status = response.get("status", status_value)

        action_text = "Р В·Р В°Р В±Р В»Р С•Р С”Р С‘РЎР‚Р С•Р Р†Р В°Р Р…" if mode == "block" else "РЎР‚Р В°Р В·Р В±Р В»Р С•Р С”Р С‘РЎР‚Р С•Р Р†Р В°Р Р…"
        message = (
            f"Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ {user_id} Р С•Р В±Р Р…Р С•Р Р†Р В»РЎвЂР Р… ({new_status}). "
            f"Р СџР С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЉ {action_text}."
        )

        return {
            "status": "success",
            "title": "Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ Р С•Р В±Р Р…Р С•Р Р†Р В»РЎвЂР Р…",
            "message": message,
            "response": response,
            "_audit": {
                "target_type": "user",
                "target_id": str(user_id),
                "payload": {
                    "input": {"mode": mode, "status": status_value, "confirmed": confirmation_checked},
                    "response": response,
                },
            },
        }

    if action_key == "sync_access":
        mode = str(form.get("mode") or "to_panel").lower()
        if mode == "to_panel":
            response = await client.sync_to_panel()
            message = _format_sync_message(response, "Р вЂ™РЎвЂ№Р С–РЎР‚РЎС“Р В·Р С”Р В° Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ Р Р† RemnaWave Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…Р В°.")
        elif mode == "from_panel_all":
            response = await client.sync_from_panel("all")
            message = _format_sync_message(response, "Р вЂ”Р В°Р С–РЎР‚РЎС“Р В·Р С”Р В° Р Р†РЎРѓР ВµРЎвЂ¦ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»Р ВµР в„– Р С‘Р В· RemnaWave Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬Р ВµР Р…Р В°.")
        elif mode == "from_panel_update":
            response = await client.sync_from_panel("update_only")
            message = _format_sync_message(response, "Р СџР С•Р В»РЎС“РЎвЂЎР ВµР Р…РЎвЂ№ Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘РЎРЏ Р С‘Р В· RemnaWave.")
        elif mode == "sync_statuses":
            response = await client.sync_subscription_statuses()
            message = _format_sync_message(response, "Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓРЎвЂ№ Р С—Р С•Р Т‘Р С—Р С‘РЎРѓР С•Р С” РЎРѓР С‘Р Р…РЎвЂ¦РЎР‚Р С•Р Р…Р С‘Р В·Р С‘РЎР‚Р С•Р Р†Р В°Р Р…РЎвЂ№.")
        else:
            raise ActionValidationError("Р СњР ВµР С‘Р В·Р Р†Р ВµРЎРѓРЎвЂљР Р…РЎвЂ№Р в„– РЎР‚Р ВµР В¶Р С‘Р С РЎРѓР С‘Р Р…РЎвЂ¦РЎР‚Р С•Р Р…Р С‘Р В·Р В°РЎвЂ Р С‘Р С‘.")

        return {
            "status": "success",
            "title": "Р РЋР С‘Р Р…РЎвЂ¦РЎР‚Р С•Р Р…Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ Р В·Р В°Р С—РЎС“РЎвЂ°Р ВµР Р…Р В°",
            "message": message,
            "response": response,
            "_audit": {
                "target_type": "remnawave_sync",
                "target_id": mode,
                "payload": {
                    "input": {"mode": mode},
                    "response": response,
                },
            },
        }

    raise ActionValidationError("Р СњР ВµР С‘Р В·Р Р†Р ВµРЎРѓРЎвЂљР Р…Р С•Р Вµ Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р Вµ.")



@app.get("/admin/actions", include_in_schema=False)
async def admin_actions_page(
    request: Request,
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Р РЋРЎвЂљРЎР‚Р В°Р Р…Р С‘РЎвЂ Р В° Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р в„– web API."""
    await _ensure_security_settings()
    permissions = _get_permissions(request)
    security_settings = await _get_security_settings()
    api_configured = is_webapi_configured()
    context: Dict[str, Any] = {
        "request": request,
        "admin": current_admin,
        "actions": ADMIN_ACTIONS,
        "result": None,
        "api_configured": api_configured,
        "permissions": sorted(permissions),
        "allowed_actions": _build_allowed_actions(permissions),
        "form_values": {},
        "submitted_action": None,
        "csrf_token": "",
        "security_settings": security_settings,
    }
    response = templates.TemplateResponse("actions.html", context)
    context["csrf_token"] = issue_csrf(response)
    return response


@app.post("/admin/actions", include_in_schema=False)
async def admin_actions_submit(
    request: Request,
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Р С›Р В±РЎР‚Р В°Р В±Р В°РЎвЂљРЎвЂ№Р Р†Р В°Р ВµРЎвЂљ Р В·Р В°Р С—РЎС“РЎРѓР С” Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р в„– web API."""
    await _ensure_security_settings()
    form = await request.form()
    action_key = str(form.get("action") or "")
    action_meta = _get_action_meta(action_key)
    permissions = _get_permissions(request)
    allowed_actions = _build_allowed_actions(permissions)
    api_configured = is_webapi_configured()
    security_settings = await _get_security_settings()
    roles = getattr(request.state, "admin_roles", set())
    rate_limiter: RateLimiter | None = getattr(request.app.state, "rate_limiter", None)

    form_values: Dict[str, Dict[str, Any]] = {}
    if action_meta:
        collected: Dict[str, Any] = {}
        for field in action_meta.get("fields", []):
            name = field.get("name")
            if not name:
                continue
            if field.get("type") == "checkbox":
                collected[name] = "on" if form.get(name) else ""
            else:
                collected[name] = form.get(name) or ""
        if collected:
            form_values[action_key] = collected

        extras: Dict[str, Any] = {}
        if action_key == "recharge_balance":
            extras["confirm_amount"] = "on" if form.get("confirm_amount") else ""
        if action_key == "block_user":
            extras["confirm_block"] = "on" if form.get("confirm_block") else ""
        if extras:
            form_values.setdefault(action_key, {}).update(extras)

    audit_meta: dict[str, Any] | None = None

    if not action_meta:
        result = {
            "status": "error",
            "title": "Р СњР ВµР С‘Р В·Р Р†Р ВµРЎРѓРЎвЂљР Р…Р С•Р Вµ Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р Вµ",
            "message": "Р вЂ™РЎвЂ№Р В±РЎР‚Р В°Р Р…Р Р…Р С•Р Вµ Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р Вµ Р Р…Р Вµ РЎР‚Р В°РЎРѓР С—Р С•Р В·Р Р…Р В°Р Р…Р С•. Р С›Р В±Р Р…Р С•Р Р†Р С‘РЎвЂљР Вµ РЎРѓРЎвЂљРЎР‚Р В°Р Р…Р С‘РЎвЂ РЎС“ Р С‘ Р С—Р С•Р С—РЎР‚Р С•Р В±РЎС“Р в„–РЎвЂљР Вµ РЎРѓР Р…Р С•Р Р†Р В°.",
        }
    elif action_meta.get("permission") and action_meta["permission"] not in permissions:
        result = {
            "status": "error",
            "title": "Р СњР ВµР Т‘Р С•РЎРѓРЎвЂљР В°РЎвЂљР С•РЎвЂЎР Р…Р С• Р С—РЎР‚Р В°Р Р†",
            "message": "Р Р€ Р Р†Р В°РЎРѓ Р Р…Р ВµРЎвЂљ Р С—РЎР‚Р В°Р Р† Р Р…Р В° Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…Р С‘Р Вµ РЎРЊРЎвЂљР С•Р С–Р С• Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎРЏ.",
        }
        audit_meta = {"payload": {"form": form_values.get(action_key, {}), "reason": "permission_denied"}}
    elif not api_configured:
        result = {
            "status": "error",
            "title": "Web API Р Р…Р Вµ Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р ВµР Р…Р С•",
            "message": "Р Р€Р С”Р В°Р В¶Р С‘РЎвЂљР Вµ WEBAPI_BASE_URL Р С‘ WEBAPI_API_KEY Р Р† .env, Р В·Р В°РЎвЂљР ВµР С Р С—Р ВµРЎР‚Р ВµР В·Р В°Р С—РЎС“РЎРѓРЎвЂљР С‘РЎвЂљР Вµ Р С—РЎР‚Р С‘Р В»Р С•Р В¶Р ВµР Р…Р С‘Р Вµ.",
        }
        audit_meta = {"payload": {"reason": "webapi_not_configured"}}
    else:
        try:
            if rate_limiter and security_settings.rate_limit_count > 0 and security_settings.rate_limit_period_seconds > 0 and "superadmin" not in roles:
                rate_limiter.hit(
                    (current_admin.id, action_key),
                    limit=security_settings.rate_limit_count,
                    period=security_settings.rate_limit_period_seconds,
                )

            token = form.get("_csrf_token") or request.headers.get(settings.csrf_token_header)
            if not token:
                raise CSRFAuthError(status_code=400, detail="CSRF-РЎвЂљР С•Р С”Р ВµР Р… Р С•РЎвЂљРЎРѓРЎС“РЎвЂљРЎРѓРЎвЂљР Р†РЎС“Р ВµРЎвЂљ.")
            validate_csrf_token(token)
            payload_form = form_values.setdefault(action_key, {})
            result = await _execute_action(action_key, payload_form, security_settings)
        except CSRFAuthError as exc:
            result = {
                "status": "error",
                "title": "CSRF-Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° Р Р…Р Вµ Р С—РЎР‚Р С•Р в„–Р Т‘Р ВµР Р…Р В°",
                "message": exc.detail,
            }
            audit_meta = {
                "payload": {
                    "form": form_values.get(action_key, {}),
                    "error": "csrf_failed",
                }
            }
        except RateLimitExceeded as exc:
            result = {
                "status": "error",
                "title": "Р РЋР В»Р С‘РЎв‚¬Р С”Р С•Р С Р СР Р…Р С•Р С–Р С• Р В·Р В°Р С—РЎР‚Р С•РЎРѓР С•Р Р†",
                "message": exc.detail,
            }
            audit_meta = {
                "payload": {
                    "form": form_values.get(action_key, {}),
                    "error": "rate_limit",
                }
            }
        except ActionValidationError as exc:
            result = {
                "status": "error",
                "title": "Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р Р†Р В°Р В»Р С‘Р Т‘Р В°РЎвЂ Р С‘Р С‘",
                "message": str(exc),
            }
            audit_meta = {
                "payload": {
                    "form": form_values.get(action_key, {}),
                    "error": "validation",
                }
            }
        except WebAPIConfigurationError as exc:
            result = {
                "status": "error",
                "title": "Web API Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р С•",
                "message": str(exc),
            }
            audit_meta = {
                "payload": {
                    "form": form_values.get(action_key, {}),
                    "error": "webapi_configuration",
                }
            }
        except WebAPIRequestError as exc:
            detail = str(exc)
            if exc.status_code:
                detail = f"{detail} (HTTP {exc.status_code})"
            result = {
                "status": "error",
                "title": "Web API Р С•РЎвЂљР Р†Р ВµРЎвЂљР С‘Р В»Р С• Р С•РЎв‚¬Р С‘Р В±Р С”Р С•Р в„–",
                "message": detail,
            }
            audit_meta = {
                "payload": {
                    "form": form_values.get(action_key, {}),
                    "error": "webapi_response",
                    "response": getattr(exc, "payload", None),
                }
            }
        except Exception as exc:  # pragma: no cover
            logger.exception("Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р С‘РЎвЂљРЎРЉ Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р Вµ %s", action_key)
            result = {
                "status": "error",
                "title": "Р СњР ВµР С—РЎР‚Р ВµР Т‘Р Р†Р С‘Р Т‘Р ВµР Р…Р Р…Р В°РЎРЏ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°",
                "message": f"Р вЂ”Р В°Р С—РЎР‚Р С•РЎРѓ Р Р…Р Вµ Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…: {exc}",
            }
            audit_meta = {
                "payload": {
                    "form": form_values.get(action_key, {}),
                    "error": "unexpected_exception",
                }
            }
        else:
            audit_meta = result.pop("_audit", None)

    if action_meta and action_key:
        log_payload = None
        target_type = None
        target_id = None
        if audit_meta:
            target_type = audit_meta.get("target_type") or None
            target_id = audit_meta.get("target_id") or None
            log_payload = audit_meta.get("payload")
        if log_payload is None:
            log_payload = form_values.get(action_key)
        if log_payload is not None and not isinstance(log_payload, dict):
            log_payload = {"value": str(log_payload)}

        await log_admin_action(
            admin_id=current_admin.id,
            action=action_key,
            status=result.get("status", "error"),
            message=result.get("message"),
            target_type=target_type,
            target_id=target_id,
            payload=log_payload if isinstance(log_payload, dict) else None,
            request=request,
        )

    context: Dict[str, Any] = {
        "request": request,
        "admin": current_admin,
        "actions": ADMIN_ACTIONS,
        "result": result,
        "api_configured": api_configured,
        "permissions": sorted(permissions),
        "allowed_actions": allowed_actions,
        "form_values": form_values,
        "submitted_action": action_key if action_meta else None,
        "csrf_token": "",
        "security_settings": security_settings,
    }
    response = templates.TemplateResponse(
        "actions.html",
        context,
        status_code=status.HTTP_200_OK,
    )
    context["csrf_token"] = issue_csrf(response)
    return response


@app.get("/health", tags=["monitoring"])
async def healthcheck() -> dict[str, str]:
    """Р СџРЎР‚Р С•РЎРѓРЎвЂљР ВµР в„–РЎв‚¬Р С‘Р в„– РЎРЊР Р…Р Т‘Р С—Р С•Р С‘Р Р…РЎвЂљ Р Т‘Р В»РЎРЏ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р С‘ РЎРѓР С•РЎРѓРЎвЂљР С•РЎРЏР Р…Р С‘РЎРЏ Р С—РЎР‚Р С‘Р В»Р С•Р В¶Р ВµР Р…Р С‘РЎРЏ."""
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    """Р РЋР С•Р В·Р Т‘Р В°РЎвЂР С РЎвЂљР В°Р В±Р В»Р С‘РЎвЂ РЎвЂ№ Р С‘ Р С—Р С•Р Т‘Р С–Р С•РЎвЂљР В°Р Р†Р В»Р С‘Р Р†Р В°Р ВµР С Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ Р С—Р С• РЎС“Р СР С•Р В»РЎвЂЎР В°Р Р…Р С‘РЎР‹."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.admin_exists = await _admin_account_exists()
    await ensure_default_roles()
    await _ensure_security_settings()
    app.state.rate_limiter = RateLimiter()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Р С™Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…Р С• Р В·Р В°Р С”РЎР‚РЎвЂ№Р Р†Р В°Р ВµР С РЎРѓР С•Р ВµР Т‘Р С‘Р Р…Р ВµР Р…Р С‘РЎРЏ РЎРѓ Р В±Р В°Р В·Р С•Р в„–."""
    await engine.dispose()
