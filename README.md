# Bedolaga Admin

Асинхронная админка на FastAPI и SQLAdmin для управления ботом [remnawave-bedolaga-telegram-bot](https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot).

## Возможности

- FastAPI + SQLAdmin + async SQLAlchemy (PostgreSQL).
- Авторизация администраторов, хранение учётных записей в БД.
- Таблицы пользователей, подписок и транзакций в режиме только чтения с фильтрами и вычисляемыми полями.
- Страница `/admin/actions` для управления через web API бота:
  - продление подписки;
  - начисление/списание баланса;
  - блокировка/разблокировка пользователя;
  - синхронизация с RemnaWave (выгрузка/загрузка/обновление статусов).

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
2. Войдите в `/admin/`, чтобы получить доступ к SQLAdmin.

## Настройка web API бота

Для работы действий на странице `/admin/actions` укажите переменные окружения:

```
WEBAPI_BASE_URL=http://127.0.0.1:9000   # адрес web API бота
WEBAPI_API_KEY=ваш-api-токен
WEBAPI_TIMEOUT_SECONDS=15               # (опционально) таймаут HTTP-запросов
```

Токен должен иметь права на необходимые эндпоинты (`/users`, `/subscriptions`, `/remnawave/...`). Если значения отсутствуют, формы будут отображены в режиме "только чтение" с предупреждением.

## Документация

- `docs/roadmap.md` — этапы и статус работ.
- `docs/development.md` — журнал решений и изменений.
- `docs/stage2-plan.md` — план и покрытые сценарии второго этапа.

## Статус

Этап 2: просмотр сущностей и базовые действия через web API — **в процессе развития**, ключевые операции реализованы.
