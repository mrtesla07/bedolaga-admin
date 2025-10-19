# Bedolaga Admin

Асинхронная админка на FastAPI и SQLAdmin для управления ботом [remnawave-bedolaga-telegram-bot](https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot).

## Возможности

- FastAPI + SQLAdmin + async SQLAlchemy (PostgreSQL).
- Авторизация администраторов, хранение учёток в PostgreSQL.
- Просмотр пользователей, подписок и транзакций в режиме только чтения с фильтрами и вычисляемыми полями.
- Страница `/admin/actions` для управления через web API бота: продление подписок, корректировка баланса, блокировка, синхронизация с RemnaWave.
- Ролевая модель и аудит действий админов (этап 3).

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -U pip
pip install -e .
copy .env.example .env
# отредактируйте .env под своё окружение (БД, web API)
uvicorn app.main:app --reload
```

Первый запуск:

1. Откройте `http://localhost:8000/admin/setup` и создайте администратора.
2. Войдите в `/admin/`, чтобы открыть SQLAdmin.

## Роли и права

Синхронизируйте базовые роли и при необходимости назначьте их администраторам:

```bash
python scripts/init_roles.py --sync
python scripts/init_roles.py --assign admin@example.com superadmin
```

Роли:

- `superadmin` — полный доступ, управление ролями и токенами.
- `manager` — просмотр и безопасные действия (продление, баланс, синхронизация).
- `viewer` — только просмотр данных.

Администратор без ролей, но с флагом `is_superuser`, автоматически получает права `superadmin` (для обратной совместимости).

В SQLAdmin доступен раздел «Настройки безопасности» (только для `superadmin`), где задаются пороги для операций с балансом и правила подтверждения блокировок.

## Настройка web API

Для работы `/admin/actions` укажите параметры web API:

```
WEBAPI_BASE_URL=http://127.0.0.1:9000
WEBAPI_API_KEY=ваш-api-токен
WEBAPI_TIMEOUT_SECONDS=15  # опционально
CSRF_SECRET_KEY=ваш-случайный-seed-для-токенов
```

Токен должен иметь доступ к эндпоинтам `/users`, `/subscriptions`, `/remnawave/*`. Если web API не настроено или нет прав, формы будут отключены и появится предупреждение.

Для защиты форм используется cookie + скрытое поле `_csrf_token`. При необходимости можно переопределить `CSRF_HEADER_NAME`, `CSRF_COOKIE_NAME`, `CSRF_TOKEN_EXPIRE_MINUTES`.

## Документация

- `docs/roadmap.md` — этапы и статус работ.
- `docs/development.md` — журнал решений и изменений.
- `docs/stage2-plan.md` — покрытые сценарии второго этапа (просмотр сущностей, web API).
- `docs/stage3-plan.md` — план по безопасности, ролям и аудиту.

## Статус

Этап 3 (безопасность и роли) в процессе: внедрена модель ролей, журнал действий и CSRF; впереди подтверждения опасных операций и throttling.
