"""РўРѕС‡РєР° РІС…РѕРґР° FastAPI-РїСЂРёР»РѕР¶РµРЅРёСЏ."""

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
from app.i18n import translate
from app.services.webapi import (
    WebAPIConfigurationError,
    WebAPIRequestError,
    get_webapi_client,
    is_webapi_configured,
)

logger = logging.getLogger(__name__)


settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.state.admin_exists = False

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals['translate'] = translate

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
        "title": "РџСЂРѕРґР»РёС‚СЊ РїРѕРґРїРёСЃРєСѓ",
        "description": "РџСЂРѕРґР»РµРІР°РµС‚ С‚РµРєСѓС‰СѓСЋ РїРѕРґРїРёСЃРєСѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ С‡РµСЂРµР· web API.",
        "permission": PERM_ACTION_EXTEND,
        "fields": [
            {
                "name": "user_id",
                "label": "ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ",
                "type": "number",
                "required": True,
                "min": 1,
                "placeholder": "РќР°РїСЂРёРјРµСЂ, 102",
            },
            {
                "name": "days",
                "label": "РљРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№",
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
        "title": "РќР°С‡РёСЃР»РёС‚СЊ Р±Р°Р»Р°РЅСЃ",
        "description": "РќР°С‡РёСЃР»СЏРµС‚ РёР»Рё СЃРїРёСЃС‹РІР°РµС‚ Р±Р°Р»Р°РЅСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ СЃ РѕРїС†РёРѕРЅР°Р»СЊРЅРѕР№ Р·Р°РїРёСЃСЊСЋ РІ С‚СЂР°РЅР·Р°РєС†РёРё.",
        "permission": PERM_ACTION_BALANCE,
        "fields": [
            {
                "name": "user_id",
                "label": "ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ",
                "type": "number",
                "required": True,
                "min": 1,
                "placeholder": "ID РІ С‚Р°Р±Р»РёС†Рµ users",
            },
            {
                "name": "amount_rub",
                "label": "РЎСѓРјРјР°, в‚Ѕ",
                "type": "number",
                "step": "0.01",
                "required": True,
                "placeholder": "100.00",
            },
            {
                "name": "description",
                "label": "РљРѕРјРјРµРЅС‚Р°СЂРёР№",
                "type": "textarea",
                "rows": 3,
                "placeholder": "РџСЂРёС‡РёРЅР° РєРѕСЂСЂРµРєС‚РёСЂРѕРІРєРё, РїРѕСЏРІРёС‚СЃСЏ РІ РѕРїРёСЃР°РЅРёРё С‚СЂР°РЅР·Р°РєС†РёРё",
            },
            {
                "name": "create_transaction",
                "label": "РЎРѕР·РґР°С‚СЊ Р·Р°РїРёСЃСЊ РІ РёСЃС‚РѕСЂРёРё С‚СЂР°РЅР·Р°РєС†РёР№",
                "type": "checkbox",
                "default": True,
            },
        ],
    },
    {
        "key": "block_user",
        "title": "РћР±РЅРѕРІРёС‚СЊ СЃС‚Р°С‚СѓСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ",
        "description": "РџРµСЂРµРєР»СЋС‡Р°РµС‚ СЃС‚Р°С‚СѓСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РјРµР¶РґСѓ Р°РєС‚РёРІРЅС‹Рј Рё Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅРЅС‹Рј.",
        "permission": PERM_ACTION_BLOCK,
        "fields": [
            {
                "name": "user_id",
                "label": "ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ",
                "type": "number",
                "required": True,
                "min": 1,
                "placeholder": "ID РІ С‚Р°Р±Р»РёС†Рµ users",
            },
            {
                "name": "mode",
                "label": "Р”РµР№СЃС‚РІРёРµ",
                "type": "select",
                "default": "block",
                "options": [
                    {"value": "block", "label": "Р—Р°Р±Р»РѕРєРёСЂРѕРІР°С‚СЊ"},
                    {"value": "unblock", "label": "Р Р°Р·Р±Р»РѕРєРёСЂРѕРІР°С‚СЊ"},
                ],
            },
        ],
    },
    {
        "key": "sync_access",
        "title": "РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ СЃ RemnaWave",
        "description": "Р—Р°РїСѓСЃРєР°РµС‚ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёСЋ РґР°РЅРЅС‹С… РјРµР¶РґСѓ Р±РѕС‚РѕРј Рё RemnaWave РїР°РЅРµР»СЊСЋ.",
        "permission": PERM_ACTION_SYNC,
        "fields": [
            {
                "name": "mode",
                "label": "РћРїРµСЂР°С†РёСЏ",
                "type": "select",
                "default": "to_panel",
                "options": [
                    {"value": "to_panel", "label": "Р’С‹РіСЂСѓР·РёС‚СЊ РґР°РЅРЅС‹Рµ РІ РїР°РЅРµР»СЊ"},
                    {"value": "from_panel_all", "label": "Р—Р°РіСЂСѓР·РёС‚СЊ РёР· РїР°РЅРµР»Рё (РІСЃРµ РїРѕР»СЊР·РѕРІР°С‚РµР»Рё)"},
                    {"value": "from_panel_update", "label": "Р—Р°РіСЂСѓР·РёС‚СЊ РёР· РїР°РЅРµР»Рё (С‚РѕР»СЊРєРѕ РѕР±РЅРѕРІР»РµРЅРёСЏ)"},
                    {"value": "sync_statuses", "label": "РЎРёРЅС…СЂРѕРЅРёР·РёСЂРѕРІР°С‚СЊ СЃС‚Р°С‚СѓСЃС‹ РїРѕРґРїРёСЃРѕРє"},
                ],
            },
        ],
    },
]

class ActionValidationError(ValueError):
    """РћС€РёР±РєР° РІР°Р»РёРґР°С†РёРё РґР°РЅРЅС‹С… РґРµР№СЃС‚РІРёСЏ."""


def _get_action_meta(action_key: str) -> dict[str, Any] | None:
    return next((item for item in ADMIN_ACTIONS if item["key"] == action_key), None)


def _require_int(value: str | None, *, label: str, min_value: int | None = None) -> int:
    if value is None or str(value).strip() == "":
        raise ActionValidationError(f"{label}: СѓРєР°Р¶РёС‚Рµ Р·РЅР°С‡РµРЅРёРµ.")
    try:
        number = int(str(value).strip())
    except ValueError as exc:
        raise ActionValidationError(f"{label}: РѕР¶РёРґР°РµС‚СЃСЏ С†РµР»РѕРµ С‡РёСЃР»Рѕ.") from exc
    if min_value is not None and number < min_value:
        raise ActionValidationError(f"{label}: Р·РЅР°С‡РµРЅРёРµ РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ РЅРµ РјРµРЅСЊС€Рµ {min_value}.")
    return number


def _format_sync_message(response: dict[str, Any], default: str) -> str:
    detail = response.get("detail") or default
    data = response.get("data") or response.get("stats")
    if isinstance(data, dict) and data:
        pairs = ", ".join(f"{key}: {value}" for key, value in data.items())
        return f"{detail} ({pairs})"
    return detail


def _get_permissions(request: Request) -> set[str]:
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ РјРЅРѕР¶РµСЃС‚РІРѕ СЂР°Р·СЂРµС€РµРЅРёР№ С‚РµРєСѓС‰РµРіРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°."""
    perms = getattr(request.state, "admin_permissions", set())
    return set(perms)


def _build_allowed_actions(permissions: set[str]) -> dict[str, bool]:
    """РЎРѕР·РґР°С‘С‚ РєР°СЂС‚Сѓ РґРѕСЃС‚СѓРїРЅС‹С… РґРµР№СЃС‚РІРёР№."""
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
        raise ActionValidationError("РЎСѓРјРјР°: СѓРєР°Р¶РёС‚Рµ Р·РЅР°С‡РµРЅРёРµ.")
    normalized = str(value).replace(",", ".").strip()
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ActionValidationError("РЎСѓРјРјР°: РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ С„РѕСЂРјР°С‚.") from exc
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount == 0:
        raise ActionValidationError("РЎСѓРјРјР° РґРѕР»Р¶РЅР° РѕС‚Р»РёС‡Р°С‚СЊСЃСЏ РѕС‚ РЅСѓР»СЏ.")
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
        user_id = _require_int(form.get("user_id"), label="ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ", min_value=1)
        days = _require_int(form.get("days"), label="РљРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№", min_value=1)

        async with AsyncSessionFactory() as session:
            result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalar_one_or_none()

        if not subscription:
            raise ActionValidationError("РЈ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РЅРµС‚ Р°РєС‚РёРІРЅРѕР№ РїРѕРґРїРёСЃРєРё.")

        response = await client.extend_subscription(subscription.id, days)
        end_date = response.get("end_date")

        message = f"РџРѕРґРїРёСЃРєР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {user_id} РїСЂРѕРґР»РµРЅР° РЅР° {days} РґРЅ."
        if end_date:
            message += f" РќРѕРІР°СЏ РґР°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ: {end_date}."

        return {
            "status": "success",
            "title": "РџРѕРґРїРёСЃРєР° РїСЂРѕРґР»РµРЅР°",
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
        user_id = _require_int(form.get("user_id"), label="ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ", min_value=1)
        amount_kopeks, amount = _parse_amount_rubles(form.get("amount_rub"))
        description = (form.get("description") or "РљРѕСЂСЂРµРєС‚РёСЂРѕРІРєР° С‡РµСЂРµР· Р°РґРјРёРЅРєСѓ").strip()
        create_transaction = _is_checked(form.get("create_transaction"))

        amount_abs = abs(amount)
        soft_limit = Decimal(security_settings.balance_soft_limit_rub or 0)
        hard_limit = Decimal(security_settings.balance_hard_limit_rub or 0)
        confirmation_checked = _is_checked(form.get("confirm_amount"))

        if hard_limit > 0 and amount_abs > hard_limit:
            raise ActionValidationError(
                f"РЎСѓРјРјР° {amount_abs:.2f} в‚Ѕ РїСЂРµРІС‹С€Р°РµС‚ Р¶С‘СЃС‚РєРёР№ Р»РёРјРёС‚ {hard_limit:.2f} в‚Ѕ."
            )

        if (
            security_settings.require_balance_confirmation
            and soft_limit > 0
            and amount_abs > soft_limit
            and not confirmation_checked
        ):
            raise ActionValidationError(
                "РџРѕРґС‚РІРµСЂРґРёС‚Рµ РІС‹РїРѕР»РЅРµРЅРёРµ РѕРїРµСЂР°С†РёРё, РѕС‚РјРµС‚РёРІ С‡РµРєР±РѕРєСЃ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ."
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

        message = f"Р‘Р°Р»Р°РЅСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {user_id} СЃРєРѕСЂСЂРµРєС‚РёСЂРѕРІР°РЅ РЅР° {amount:+.2f} в‚Ѕ."
        if balance_rubles is not None:
            message += f" РўРµРєСѓС‰РёР№ Р±Р°Р»Р°РЅСЃ: {Decimal(str(balance_rubles)):.2f} в‚Ѕ."

        return {
            "status": "success",
            "title": "Р‘Р°Р»Р°РЅСЃ РѕР±РЅРѕРІР»С‘РЅ",
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
        user_id = _require_int(form.get("user_id"), label="ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ", min_value=1)
        mode = str(form.get("mode") or "block").lower()
        if mode not in {"block", "unblock"}:
            raise ActionValidationError("Р’С‹Р±РµСЂРёС‚Рµ РєРѕСЂСЂРµРєС‚РЅРѕРµ РґРµР№СЃС‚РІРёРµ РґР»СЏ РёР·РјРµРЅРµРЅРёСЏ СЃС‚Р°С‚СѓСЃР°.")

        confirmation_checked = _is_checked(form.get("confirm_block"))
        if security_settings.require_block_confirmation and not confirmation_checked:
            raise ActionValidationError("РџРѕРґС‚РІРµСЂРґРёС‚Рµ Р±Р»РѕРєРёСЂРѕРІРєСѓ, РѕС‚РјРµС‚РёРІ С‡РµРєР±РѕРєСЃ.")

        status_value = UserStatus.BLOCKED.value if mode == "block" else UserStatus.ACTIVE.value
        response = await client.update_user_status(user_id, status_value)
        new_status = response.get("status", status_value)

        action_text = "Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ" if mode == "block" else "СЂР°Р·Р±Р»РѕРєРёСЂРѕРІР°РЅ"
        message = (
            f"РЎС‚Р°С‚СѓСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {user_id} РѕР±РЅРѕРІР»С‘РЅ ({new_status}). "
            f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {action_text}."
        )

        return {
            "status": "success",
            "title": "РЎС‚Р°С‚СѓСЃ РѕР±РЅРѕРІР»С‘РЅ",
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
            message = _format_sync_message(response, "Р’С‹РіСЂСѓР·РєР° РґР°РЅРЅС‹С… РІ RemnaWave РІС‹РїРѕР»РЅРµРЅР°.")
        elif mode == "from_panel_all":
            response = await client.sync_from_panel("all")
            message = _format_sync_message(response, "Р—Р°РіСЂСѓР·РєР° РІСЃРµС… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РёР· RemnaWave Р·Р°РІРµСЂС€РµРЅР°.")
        elif mode == "from_panel_update":
            response = await client.sync_from_panel("update_only")
            message = _format_sync_message(response, "РџРѕР»СѓС‡РµРЅС‹ РѕР±РЅРѕРІР»РµРЅРёСЏ РёР· RemnaWave.")
        elif mode == "sync_statuses":
            response = await client.sync_subscription_statuses()
            message = _format_sync_message(response, "РЎС‚Р°С‚СѓСЃС‹ РїРѕРґРїРёСЃРѕРє СЃРёРЅС…СЂРѕРЅРёР·РёСЂРѕРІР°РЅС‹.")
        else:
            raise ActionValidationError("РќРµРёР·РІРµСЃС‚РЅС‹Р№ СЂРµР¶РёРј СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё.")

        return {
            "status": "success",
            "title": "РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ Р·Р°РїСѓС‰РµРЅР°",
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

    raise ActionValidationError("РќРµРёР·РІРµСЃС‚РЅРѕРµ РґРµР№СЃС‚РІРёРµ.")



@app.get("/admin/actions", include_in_schema=False)
async def admin_actions_page(
    request: Request,
    current_admin: AdminUser = Depends(get_current_admin),
):
    """РЎС‚СЂР°РЅРёС†Р° РґРµР№СЃС‚РІРёР№ web API."""
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
    """РћР±СЂР°Р±Р°С‚С‹РІР°РµС‚ Р·Р°РїСѓСЃРє РґРµР№СЃС‚РІРёР№ web API."""
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
            "title": "РќРµРёР·РІРµСЃС‚РЅРѕРµ РґРµР№СЃС‚РІРёРµ",
            "message": "Р’С‹Р±СЂР°РЅРЅРѕРµ РґРµР№СЃС‚РІРёРµ РЅРµ СЂР°СЃРїРѕР·РЅР°РЅРѕ. РћР±РЅРѕРІРёС‚Рµ СЃС‚СЂР°РЅРёС†Сѓ Рё РїРѕРїСЂРѕР±СѓР№С‚Рµ СЃРЅРѕРІР°.",
        }
    elif action_meta.get("permission") and action_meta["permission"] not in permissions:
        result = {
            "status": "error",
            "title": "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ",
            "message": "РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РЅР° РІС‹РїРѕР»РЅРµРЅРёРµ СЌС‚РѕРіРѕ РґРµР№СЃС‚РІРёСЏ.",
        }
        audit_meta = {"payload": {"form": form_values.get(action_key, {}), "reason": "permission_denied"}}
    elif not api_configured:
        result = {
            "status": "error",
            "title": "Web API РЅРµ РЅР°СЃС‚СЂРѕРµРЅРѕ",
            "message": "РЈРєР°Р¶РёС‚Рµ WEBAPI_BASE_URL Рё WEBAPI_API_KEY РІ .env, Р·Р°С‚РµРј РїРµСЂРµР·Р°РїСѓСЃС‚РёС‚Рµ РїСЂРёР»РѕР¶РµРЅРёРµ.",
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
                raise CSRFAuthError(status_code=400, detail="CSRF-С‚РѕРєРµРЅ РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚.")
            validate_csrf_token(token)
            payload_form = form_values.setdefault(action_key, {})
            result = await _execute_action(action_key, payload_form, security_settings)
        except CSRFAuthError as exc:
            result = {
                "status": "error",
                "title": "CSRF-РїСЂРѕРІРµСЂРєР° РЅРµ РїСЂРѕР№РґРµРЅР°",
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
                "title": "РЎР»РёС€РєРѕРј РјРЅРѕРіРѕ Р·Р°РїСЂРѕСЃРѕРІ",
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
                "title": "РћС€РёР±РєР° РІР°Р»РёРґР°С†РёРё",
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
                "title": "Web API РЅРµРґРѕСЃС‚СѓРїРЅРѕ",
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
                "title": "Web API РѕС‚РІРµС‚РёР»Рѕ РѕС€РёР±РєРѕР№",
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
            logger.exception("РќРµ СѓРґР°Р»РѕСЃСЊ РІС‹РїРѕР»РЅРёС‚СЊ РґРµР№СЃС‚РІРёРµ %s", action_key)
            result = {
                "status": "error",
                "title": "РќРµРїСЂРµРґРІРёРґРµРЅРЅР°СЏ РѕС€РёР±РєР°",
                "message": f"Р—Р°РїСЂРѕСЃ РЅРµ РІС‹РїРѕР»РЅРµРЅ: {exc}",
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
    """РџСЂРѕСЃС‚РµР№С€РёР№ СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РїСЂРѕРІРµСЂРєРё СЃРѕСЃС‚РѕСЏРЅРёСЏ РїСЂРёР»РѕР¶РµРЅРёСЏ."""
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    """РЎРѕР·РґР°С‘Рј С‚Р°Р±Р»РёС†С‹ Рё РїРѕРґРіРѕС‚Р°РІР»РёРІР°РµРј РґР°РЅРЅС‹Рµ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.admin_exists = await _admin_account_exists()
    await ensure_default_roles()
    await _ensure_security_settings()
    app.state.rate_limiter = RateLimiter()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """РљРѕСЂСЂРµРєС‚РЅРѕ Р·Р°РєСЂС‹РІР°РµРј СЃРѕРµРґРёРЅРµРЅРёСЏ СЃ Р±Р°Р·РѕР№."""
    await engine.dispose()
