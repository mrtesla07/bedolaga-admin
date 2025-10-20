# Bedolaga Admin

Асинхронная админка на FastAPI и SQLAdmin для управления ботом [remnawave-bedolaga-telegram-bot](https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot).

## Возможности

- FastAPI + SQLAdmin + async SQLAlchemy (PostgreSQL).
- Авторизация администраторов, хранение учёток в PostgreSQL.
- Просмотр пользователей, подписок и транзакций в режиме только чтения с фильтрами и вычисляемыми полями.
- Страница `/admin/actions` для управления через web API бота: продление подписок, корректировка баланса, блокировка, синхронизация с RemnaWave.
- Ролевая модель, журнал действий и настройки безопасности (лимиты по сумме, подтверждения, throttling).
- Дашборд `/admin/overview` с агрегатами по пользователям, подпискам и платежам (динамика за 7/30 дней).
- Локализованный интерфейс (`ru`/`en`), тёмная тема, пустые состояния и подсказки в формах SQLAdmin.

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
2. Войдите в `/admin/`, чтобы открыть SQLAdmin (локаль определяется по cookie `lang` или заголовку `Accept-Language`).
3. Дашборд с ключевыми метриками доступен на `/admin/overview`, действия через web API — на `/admin/actions`.

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

## Локализация и UI

- Тексты интерфейса (сообщения, подписи, подсказки форм, пустые состояния) находятся в `app/i18n/messages.py`.
- Для шаблонов доступны макросы `{{ tr('key') }}` и `{{ trf('key', foo='bar') }}`; в Python используйте `translate(...)`.
- Тёмная тема реализована кастомным `app/static/sqladmin.css`; для RTL-сценариев достаточно передать `dir="rtl"` (например, через middleware).
- При добавлении новых полей в формы указывайте подсказки (`form.help.<field>`) рядом с полем в словаре переводов.

## Docker

Для разработки удобнее запускать проект в контейнерах:

1. Скопируйте окружение: `copy .env.example .env` (или `cp .env.example .env`).
2. Отредактируйте .env, указав параметры БД и web API.
3. Запустите `docker compose up --build`.

Подробная инструкция: [docs/docker.md](docs/docker.md).

## Документация

- `docs/roadmap.md` — этапы и статус работ.
- `docs/development.md` — журнал решений и изменений.
- `docs/stage4-plan.md` — текущее развитие UX и локализации.
- `docs/stage2-plan.md` — покрытые сценарии второго этапа (просмотр сущностей, web API).
- `docs/stage3-plan.md` — план по безопасности, ролям и аудиту.

## Статус

Этап 4 (UX и локализация) завершён: дашборд, локализация SQLAdmin, подсказки и пустые состояния доступны. Далее — этап 5 (тестирование и деплой).
