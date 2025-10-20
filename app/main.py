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
from app.services.overview import get_overview_metrics
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
    """Raised when admin action validation fails."""


def _t(locale: str, key: str, **kwargs: Any) -> str:
    """Translate helper using provided locale."""
    return translate(key, locale=locale, **kwargs)



def _get_action_meta(action_key: str) -> dict[str, Any] | None:
    return next((item for item in ADMIN_ACTIONS if item["key"] == action_key), None)


def _require_int(value: Any, *, locale: str, field_key: str, min_value: int | None = None) -> int:
    field_label = _t(locale, field_key)
    text_value = str(value).strip() if value is not None else ""
    if not text_value:
        raise ActionValidationError(_t(locale, "validation.required", field=field_label))
    try:
        number = int(text_value)
    except ValueError as exc:
        raise ActionValidationError(_t(locale, "validation.invalid_integer", field=field_label)) from exc
    if min_value is not None and number < min_value:
        raise ActionValidationError(
            _t(locale, "validation.min_value", field=field_label, min=min_value)
        )
    return number


def _parse_amount_rubles(value: Any, *, locale: str) -> tuple[int, Decimal]:
    field_label = _t(locale, "fields.amount")
    text_value = str(value or "").replace(",", ".").strip()
    if not text_value:
        raise ActionValidationError(_t(locale, "validation.required", field=field_label))
    try:
        amount = Decimal(text_value)
    except (InvalidOperation, ValueError) as exc:
        raise ActionValidationError(_t(locale, "validation.invalid_amount", field=field_label)) from exc
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    amount_kopeks = int(amount * 100)
    return amount_kopeks, amount


def _is_checked(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"on", "true", "1", "yes"}
    return bool(value)


async def _execute_action(
    action_key: str,
    form: Dict[str, Any],
    security_settings: AdminSecuritySettings,
    locale: str,
) -> dict[str, Any]:
    client = get_webapi_client()

    if action_key == "extend_subscription":
        user_id = _require_int(form.get("user_id"), locale=locale, field_key="fields.user_id", min_value=1)
        days = _require_int(form.get("days"), locale=locale, field_key="fields.days", min_value=1)

        async with AsyncSessionFactory() as session:
            result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalar_one_or_none()

        if not subscription:
            raise ActionValidationError(_t(locale, "actions.extend.error.not_found", user_id=user_id))

        response = await client.extend_subscription(subscription.id, days)
        end_date = response.get("end_date")
        extra = ""
        if end_date:
            extra = _t(locale, "actions.extend.success.extra", end_date=end_date)

        return {
            "status": "success",
            "title": _t(locale, "actions.extend.success.title"),
            "message": _t(locale, "actions.extend.success.message", user_id=user_id, days=days, extra=extra),
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
        user_id = _require_int(form.get("user_id"), locale=locale, field_key="fields.user_id", min_value=1)
        amount_kopeks, amount = _parse_amount_rubles(form.get("amount_rub"), locale=locale)
        description = (form.get("description") or _t(locale, "actions.recharge.default_description")).strip()
        create_transaction = _is_checked(form.get("create_transaction"))

        amount_abs = abs(amount)
        soft_limit = Decimal(security_settings.balance_soft_limit_rub or 0)
        hard_limit = Decimal(security_settings.balance_hard_limit_rub or 0)
        confirmation_checked = _is_checked(form.get("confirm_amount"))

        if hard_limit > 0 and amount_abs > hard_limit:
            raise ActionValidationError(
                _t(locale, "actions.recharge.error.hard_limit", amount=amount_abs, limit=hard_limit)
            )

        if (
            security_settings.require_balance_confirmation
            and soft_limit > 0
            and amount_abs > soft_limit
            and not confirmation_checked
        ):
            raise ActionValidationError(_t(locale, "actions.recharge.error.confirm"))

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

        message = _t(locale, "actions.recharge.success.message", user_id=user_id, amount=amount)
        if balance_rubles is not None:
            message += _t(locale, "actions.recharge.success.balance", balance=Decimal(str(balance_rubles)))

        return {
            "status": "success",
            "title": _t(locale, "actions.recharge.success.title"),
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
        user_id = _require_int(form.get("user_id"), locale=locale, field_key="fields.user_id", min_value=1)
        mode = str(form.get("mode") or "block").lower()
        if mode not in {"block", "unblock"}:
            raise ActionValidationError(_t(locale, "actions.block.error.mode"))

        confirmation_checked = _is_checked(form.get("confirm_block"))
        if security_settings.require_block_confirmation and not confirmation_checked:
            raise ActionValidationError(_t(locale, "actions.block.error.confirm"))

        status_value = UserStatus.BLOCKED.value if mode == "block" else UserStatus.ACTIVE.value
        response = await client.update_user_status(user_id, status_value)
        new_status = response.get("status", status_value)
        status_key = f"status.{str(new_status).lower()}"
        status_label = translate(status_key, locale=locale)
        if status_label == status_key:
            status_label = str(new_status)

        return {
            "status": "success",
            "title": _t(locale, "actions.block.success.title"),
            "message": _t(locale, "actions.block.success.message", user_id=user_id, status=status_label),
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
        detail_keys = {
            "to_panel": "actions.sync.detail.to_panel",
            "from_panel_all": "actions.sync.detail.from_panel_all",
            "from_panel_update": "actions.sync.detail.from_panel_update",
            "sync_statuses": "actions.sync.detail.sync_statuses",
        }
        if mode not in detail_keys:
            raise ActionValidationError(_t(locale, "actions.sync.error.mode"))

        if mode == "to_panel":
            response = await client.sync_to_panel()
        elif mode == "from_panel_all":
            response = await client.sync_from_panel("all")
        elif mode == "from_panel_update":
            response = await client.sync_from_panel("update_only")
        else:  # mode == "sync_statuses"
            response = await client.sync_subscription_statuses()

        detail_message = _format_sync_message(locale, response, detail_keys[mode])

        return {
            "status": "success",
            "title": _t(locale, "actions.sync.success.title"),
            "message": _t(locale, "actions.sync.success.message", detail=detail_message),
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

    raise ActionValidationError(_t(locale, "actions.error.unknown.message"))


def _format_sync_message(locale: str, response: dict[str, Any], detail_key: str) -> str:
    detail = response.get("detail") or _t(locale, detail_key)
    data = response.get("data") or response.get("stats")
    if isinstance(data, dict) and data:
        pairs = ", ".join(f"{key}: {value}" for key, value in data.items())
        return f"{detail} ({pairs})"
    return detail


def _get_permissions(request: Request) -> set[str]:
    """Return permissions granted to the current admin user."""
    perms = getattr(request.state, "admin_permissions", set())
    return set(perms)


def _build_allowed_actions(permissions: set[str]) -> dict[str, bool]:
    """Create a map of available actions based on permissions."""
    allowed: dict[str, bool] = {}
    for action in ADMIN_ACTIONS:
        required = action.get("permission")
        allowed[action["key"]] = required is None or required in permissions
    return allowed


async def get_current_admin(request: Request) -> AdminUser:
    """Dependency enforcing авторизацию администратора."""
    user = getattr(request.state, "admin_user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@app.get("/admin/overview", name="admin:overview")
async def admin_overview(
    request: Request,
    current_admin: AdminUser = Depends(get_current_admin),
) -> Any:
    """Обзорная страница админки с основными метриками."""
    locale = get_locale(request)
    metrics = await get_overview_metrics()
    context: Dict[str, Any] = {
        "request": request,
        "admin": current_admin,
        "title": translate("overview.title", locale=locale),
        "subtitle": translate("overview.subtitle", locale=locale),
        "metrics": metrics,
    }
    return templates.TemplateResponse("overview.html", context, status_code=status.HTTP_200_OK)


async def admin_actions_submit(
    request: Request,
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Execute admin actions via web API."""
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
    locale = get_locale(request)

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
            "title": _t(locale, "actions.error.unknown.title"),
            "message": _t(locale, "actions.error.unknown.message"),
        }
    elif action_meta.get("permission") and action_meta["permission"] not in permissions:
        result = {
            "status": "error",
            "title": _t(locale, "actions.error.permission.title"),
            "message": _t(locale, "actions.error.permission.message"),
        }
        audit_meta = {"payload": {"form": form_values.get(action_key, {}), "reason": "permission_denied"}}
    elif not api_configured:
        result = {
            "status": "error",
            "title": _t(locale, "actions.error.api_disabled.title"),
            "message": _t(locale, "actions.error.api_disabled.message"),
        }
        audit_meta = {"payload": {"reason": "webapi_not_configured"}}
    else:
        try:
            if (
                rate_limiter
                and security_settings.rate_limit_count > 0
                and security_settings.rate_limit_period_seconds > 0
                and "superadmin" not in roles
            ):
                rate_limiter.hit(
                    (current_admin.id, action_key),
                    limit=security_settings.rate_limit_count,
                    period=security_settings.rate_limit_period_seconds,
                )

            token = form.get("_csrf_token") or request.headers.get(settings.csrf_token_header)
            if not token:
                raise CSRFAuthError(status_code=400, detail={"code": "csrf.missing"})
            validate_csrf_token(token)
            payload_form = form_values.setdefault(action_key, {})
            result = await _execute_action(action_key, payload_form, security_settings, locale)
        except CSRFAuthError as exc:
            code = "csrf.invalid_format"
            if isinstance(exc.detail, dict):
                code = exc.detail.get("code", code)
            result = {
                "status": "error",
                "title": _t(locale, "actions.error.csrf.title"),
                "message": translate(code, locale=locale),
            }
            audit_meta = {
                "payload": {
                    "form": form_values.get(action_key, {}),
                    "error": "csrf_failed",
                    "code": code,
                }
            }
        except RateLimitExceeded as exc:
            code = "rate_limit.exceeded"
            if isinstance(exc.detail, dict):
                code = exc.detail.get("code", code)
            result = {
                "status": "error",
                "title": _t(locale, "actions.error.rate_limit.title"),
                "message": translate(code, locale=locale),
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
                "title": _t(locale, "actions.error.validation.title"),
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
                "title": _t(locale, "actions.error.webapi.title"),
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
                "title": _t(locale, "actions.error.webapi.title"),
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
            logger.exception("Unexpected error while executing action %s", action_key)
            result = {
                "status": "error",
                "title": _t(locale, "actions.error.unexpected.title"),
                "message": str(exc),
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
