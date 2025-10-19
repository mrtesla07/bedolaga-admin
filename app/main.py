"""Точка входа FastAPI-приложения."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
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
from app.models import AdminUser, Subscription, UserStatus
from app.services.audit import log_admin_action
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
)

for view in admin_views:
    admin.add_view(view)

ADMIN_ACTIONS: list[dict[str, Any]] = [
    {
        "key": "extend_subscription",
        "title": "Продлить подписку",
        "description": "Продлевает текущую подписку пользователя через web API.",
        "permission": PERM_ACTION_EXTEND,
        "fields": [
            {
                "name": "user_id",
                "label": "ID пользователя",
                "type": "number",
                "required": True,
                "min": 1,
                "placeholder": "Например, 102",
            },
            {
                "name": "days",
                "label": "Количество дней",
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
        "title": "Начислить баланс",
        "description": "Начисляет или списывает баланс пользователя с опциональной записью в транзакции.",
        "permission": PERM_ACTION_BALANCE,
        "fields": [
            {
                "name": "user_id",
                "label": "ID пользователя",
                "type": "number",
                "required": True,
                "min": 1,
                "placeholder": "ID в таблице users",
            },
            {
                "name": "amount_rub",
                "label": "Сумма, ₽",
                "type": "number",
                "step": "0.01",
                "required": True,
                "placeholder": "100.00",
            },
            {
                "name": "description",
                "label": "Комментарий",
                "type": "textarea",
                "rows": 3,
                "placeholder": "Причина корректировки, появится в описании транзакции",
            },
            {
                "name": "create_transaction",
                "label": "Создать запись в истории транзакций",
                "type": "checkbox",
                "default": True,
            },
        ],
    },
    {
        "key": "block_user",
        "title": "Обновить статус пользователя",
        "description": "Переключает статус пользователя между активным и заблокированным.",
        "permission": PERM_ACTION_BLOCK,
        "fields": [
            {
                "name": "user_id",
                "label": "ID пользователя",
                "type": "number",
                "required": True,
                "min": 1,
                "placeholder": "ID в таблице users",
            },
            {
                "name": "mode",
                "label": "Действие",
                "type": "select",
                "default": "block",
                "options": [
                    {"value": "block", "label": "Заблокировать"},
                    {"value": "unblock", "label": "Разблокировать"},
                ],
            },
        ],
    },
    {
        "key": "sync_access",
        "title": "Синхронизация с RemnaWave",
        "description": "Запускает синхронизацию данных между ботом и RemnaWave панелью.",
        "permission": PERM_ACTION_SYNC,
        "fields": [
            {
                "name": "mode",
                "label": "Операция",
                "type": "select",
                "default": "to_panel",
                "options": [
                    {"value": "to_panel", "label": "Выгрузить данные в панель"},
                    {"value": "from_panel_all", "label": "Загрузить из панели (все пользователи)"},
                    {"value": "from_panel_update", "label": "Загрузить из панели (только обновления)"},
                    {"value": "sync_statuses", "label": "Синхронизировать статусы подписок"},
                ],
            },
        ],
    },
]

class ActionValidationError(ValueError):
    """Ошибка валидации данных действия."""


def _get_action_meta(action_key: str) -> dict[str, Any] | None:
    return next((item for item in ADMIN_ACTIONS if item["key"] == action_key), None)


def _require_int(value: str | None, *, label: str, min_value: int | None = None) -> int:
    if value is None or str(value).strip() == "":
        raise ActionValidationError(f"{label}: укажите значение.")
    try:
        number = int(str(value).strip())
    except ValueError as exc:
        raise ActionValidationError(f"{label}: ожидается целое число.") from exc
    if min_value is not None and number < min_value:
        raise ActionValidationError(f"{label}: значение должно быть не меньше {min_value}.")
    return number


def _format_sync_message(response: dict[str, Any], default: str) -> str:
    detail = response.get("detail") or default
    data = response.get("data") or response.get("stats")
    if isinstance(data, dict) and data:
        pairs = ", ".join(f"{key}: {value}" for key, value in data.items())
        return f"{detail} ({pairs})"
    return detail


def _get_permissions(request: Request) -> set[str]:
    """Возвращает множество разрешений текущего администратора."""
    perms = getattr(request.state, "admin_permissions", set())
    return set(perms)


def _build_allowed_actions(permissions: set[str]) -> dict[str, bool]:
    """Создаёт карту доступных действий."""
    allowed: dict[str, bool] = {}
    for action in ADMIN_ACTIONS:
        required = action.get("permission")
        allowed[action["key"]] = required is None or required in permissions
    return allowed


def _parse_amount_rubles(value: str | None) -> tuple[int, Decimal]:
    if value is None or not str(value).strip():
        raise ActionValidationError("Сумма: укажите значение.")
    normalized = str(value).replace(",", ".").strip()
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ActionValidationError("Сумма: некорректный формат.") from exc
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount == 0:
        raise ActionValidationError("Сумма должна отличаться от нуля.")
    kopeks = int(amount * 100)
    return kopeks, amount


def _is_checked(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"on", "true", "1", "yes"}
    return bool(value)


async def _execute_action(action_key: str, form: Dict[str, Any]) -> dict[str, Any]:
    client = get_webapi_client()

    if action_key == "extend_subscription":
        user_id = _require_int(form.get("user_id"), label="ID пользователя", min_value=1)
        days = _require_int(form.get("days"), label="Количество дней", min_value=1)

        async with AsyncSessionFactory() as session:
            result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalar_one_or_none()

        if not subscription:
            raise ActionValidationError("У пользователя нет подписки или она не найдена.")

        response = await client.extend_subscription(subscription.id, days)
        end_date = response.get("end_date")

        message = f"Подписка пользователя {user_id} продлена на {days} дн."
        if end_date:
            message += f" Новая дата окончания: {end_date}."

        return {
            "status": "success",
            "title": "Подписка продлена",
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
        user_id = _require_int(form.get("user_id"), label="ID пользователя", min_value=1)
        amount_kopeks, amount = _parse_amount_rubles(form.get("amount_rub"))
        description = (form.get("description") or "Корректировка через админку").strip()
        create_transaction = _is_checked(form.get("create_transaction"))

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

        message = f"Баланс пользователя {user_id} скорректирован на {amount:+.2f} ₽."
        if balance_rubles is not None:
            message += f" Текущий баланс: {Decimal(str(balance_rubles)):.2f} ₽."

        return {
            "status": "success",
            "title": "Баланс обновлён",
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
                    },
                    "response": response,
                },
            },
        }

    if action_key == "block_user":
        user_id = _require_int(form.get("user_id"), label="ID пользователя", min_value=1)
        mode = str(form.get("mode") or "block").lower()
        if mode not in {"block", "unblock"}:
            raise ActionValidationError("Выберите действие для изменения статуса.")

        status_value = UserStatus.BLOCKED.value if mode == "block" else UserStatus.ACTIVE.value
        response = await client.update_user_status(user_id, status_value)
        new_status = response.get("status", status_value)

        action_text = "заблокирован" if mode == "block" else "разблокирован"
        message = f"Статус пользователя {user_id} обновлён ({new_status}). Пользователь {action_text}."

        return {
            "status": "success",
            "title": "Статус обновлён",
            "message": message,
            "response": response,
            "_audit": {
                "target_type": "user",
                "target_id": str(user_id),
                "payload": {
                    "input": {"mode": mode, "status": status_value},
                    "response": response,
                },
            },
        }

    if action_key == "sync_access":
        mode = str(form.get("mode") or "to_panel").lower()
        if mode == "to_panel":
            response = await client.sync_to_panel()
            message = _format_sync_message(response, "Выгрузка данных в RemnaWave выполнена.")
        elif mode == "from_panel_all":
            response = await client.sync_from_panel("all")
            message = _format_sync_message(response, "Загрузка всех пользователей из RemnaWave завершена.")
        elif mode == "from_panel_update":
            response = await client.sync_from_panel("update_only")
            message = _format_sync_message(response, "Получены обновления из RemnaWave.")
    elif mode == "sync_statuses":
        response = await client.sync_subscription_statuses()
        message = _format_sync_message(response, "Статусы подписок синхронизированы.")
    else:
        raise ActionValidationError("Неизвестный режим синхронизации.")

    return {
        "status": "success",
        "title": "Синхронизация запущена",
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

    raise ActionValidationError("Неизвестное действие.")


async def _admin_account_exists() -> bool:
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(func.count()).select_from(AdminUser))
        return (result.scalar_one() or 0) > 0


@app.middleware("http")
async def enforce_admin_setup(request: Request, call_next):
    """Переадресует на страницу создания администратора, если учётки ещё нет."""
    path = request.url.path
    if (
        path.startswith("/admin")
        and not path.startswith("/admin/setup")
        and not path.startswith("/admin/static")
        and not getattr(app.state, "admin_exists", False)
    ):
        return RedirectResponse(url="/admin/setup", status_code=status.HTTP_303_SEE_OTHER)

    return await call_next(request)


@app.get("/admin/setup", include_in_schema=False)
async def admin_setup_form(request: Request):
    """Форма первичного создания администратора."""
    if getattr(app.state, "admin_exists", False):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "setup.html",
        {"request": request, "errors": [], "form": {}},
    )


@app.post("/admin/setup", include_in_schema=False)
async def admin_setup_submit(
    request: Request,
    email: str = Form(...),
    full_name: str | None = Form(None),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    """Обрабатывает создание первого администратора."""
    if getattr(app.state, "admin_exists", False):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    email_normalized = email.strip().lower()
    full_name_normalized = full_name.strip() if full_name else None

    errors: list[str] = []
    form_state = {
        "email": email_normalized,
        "full_name": full_name_normalized or "",
    }

    if not email_normalized:
        errors.append("Введите корректный адрес электронной почты.")

    if len(password) < 8:
        errors.append("Пароль должен содержать не менее 8 символов.")

    if password != password_confirm:
        errors.append("Пароли не совпадают.")

    async with AsyncSessionFactory() as session:
        if not errors:
            result = await session.execute(select(AdminUser).where(AdminUser.email == email_normalized))
            if result.scalar_one_or_none():
                errors.append("Администратор с такой почтой уже существует.")

        if errors:
            return templates.TemplateResponse(
                "setup.html",
                {"request": request, "errors": errors, "form": form_state},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = AdminUser(
            email=email_normalized,
            full_name=full_name_normalized,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        await session.commit()

    app.state.admin_exists = True
    return RedirectResponse(url="/admin/login?setup=done", status_code=status.HTTP_303_SEE_OTHER)


async def get_current_admin(request: Request) -> AdminUser:
    """Проверяет авторизацию администратора для кастомных маршрутов."""
    user_id = request.session.get(auth_backend.session_key)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"},
        )

    try:
        admin_id = int(user_id)
    except (TypeError, ValueError):
        request.session.pop(auth_backend.session_key, None)
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"},
        )

    async with AsyncSessionFactory() as session:
        admin_user = await session.get(AdminUser, admin_id)

    if not admin_user or not admin_user.is_active:
        request.session.pop(auth_backend.session_key, None)
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"},
        )

    return admin_user


@app.get("/admin/actions", include_in_schema=False)
async def admin_actions_page(
    request: Request,
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Страница действий web API."""
    permissions = _get_permissions(request)
    context: Dict[str, Any] = {
        "request": request,
        "admin": current_admin,
        "actions": ADMIN_ACTIONS,
        "result": None,
        "api_configured": is_webapi_configured(),
        "permissions": sorted(permissions),
        "allowed_actions": _build_allowed_actions(permissions),
        "form_values": {},
        "submitted_action": None,
        "csrf_token": "",
    }
    response = templates.TemplateResponse("actions.html", context)
    context["csrf_token"] = issue_csrf(response)
    return response


@app.post("/admin/actions", include_in_schema=False)
async def admin_actions_submit(
    request: Request,
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Обрабатывает запуск действий web API."""
    form = await request.form()
    action_key = str(form.get("action") or "")
    action_meta = _get_action_meta(action_key)
    form_values: Dict[str, Dict[str, Any]] = {}
    permissions = _get_permissions(request)
    allowed_actions = _build_allowed_actions(permissions)
    api_configured = is_webapi_configured()

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
        form_values[action_key] = collected

    audit_meta: dict[str, Any] | None = None

    if not action_meta:
        result = {
            "status": "error",
            "title": "Неизвестное действие",
            "message": "Выбранное действие не распознано. Обновите страницу и попробуйте снова.",
        }
    elif action_meta.get("permission") and action_meta["permission"] not in permissions:
        result = {
            "status": "error",
            "title": "Недостаточно прав",
            "message": "У вас нет прав на выполнение этого действия.",
        }
        form_snapshot = form_values.get(action_key, {})
        audit_meta = {"payload": {"form": form_snapshot, "reason": "permission_denied"}}
    elif not api_configured:
        result = {
            "status": "error",
            "title": "Web API не настроено",
            "message": "Укажите WEBAPI_BASE_URL и WEBAPI_API_KEY в .env, затем перезапустите приложение.",
        }
        audit_meta = {"payload": {"reason": "webapi_not_configured"}}
    else:
        try:
            token = form.get("_csrf_token") or request.headers.get(settings.csrf_token_header)
            if not token:
                raise CSRFAuthError(status_code=400, detail="CSRF-токен отсутствует.")
            validate_csrf_token(token)
            result = await _execute_action(action_key, form_values[action_key])
        except CSRFAuthError as exc:
            result = {
                "status": "error",
                "title": "CSRF-проверка не пройдена",
                "message": exc.detail,
            }
            audit_meta = {
                "payload": {
                    "form": form_values.get(action_key, {}),
                    "error": "csrf_failed",
                }
            }
        except ActionValidationError as exc:
            result = {
                "status": "error",
                "title": "Ошибка валидации",
                "message": str(exc),
            }
            audit_meta = {"payload": {"form": form_values.get(action_key, {}), "error": "validation"}}
        except WebAPIConfigurationError as exc:
            result = {
                "status": "error",
                "title": "Web API недоступно",
                "message": str(exc),
            }
            audit_meta = {"payload": {"form": form_values.get(action_key, {}), "error": "webapi_configuration"}}
        except WebAPIRequestError as exc:
            detail = str(exc)
            if exc.status_code:
                detail = f"{detail} (HTTP {exc.status_code})"
            result = {
                "status": "error",
                "title": "Web API ответило ошибкой",
                "message": detail,
            }
            audit_meta = {
                "payload": {
                    "form": form_values.get(action_key, {}),
                    "error": "webapi_response",
                    "response": getattr(exc, "payload", None),
                }
            }
        except Exception as exc:  # pragma: no cover - защита от непредвиденных ошибок
            logger.exception("Не удалось выполнить действие %s", action_key)
            result = {
                "status": "error",
                "title": "Непредвиденная ошибка",
                "message": f"Запрос не выполнен: {exc}",
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
    """Простейший эндпоинт для проверки состояния приложения."""
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    """Создаём таблицы и проверяем, есть ли уже администраторы."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.admin_exists = await _admin_account_exists()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Корректно закрываем соединения с базой."""
    await engine.dispose()
