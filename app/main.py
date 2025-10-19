"""Точка входа FastAPI-приложения."""

from pathlib import Path

from fastapi import FastAPI, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from starlette.middleware.sessions import SessionMiddleware

from sqladmin import Admin

from app.admin import BedolagaAuthenticationBackend, admin_views
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionFactory, engine
from app.models import AdminUser


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
