# Bedolaga Admin

Веб-админка на базе FastAPI и SQLAdmin для управления ботом [remnawave-bedolaga-telegram-bot](https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot).

- FastAPI + Starlette + SQLAdmin.
- Async SQLAlchemy и PostgreSQL.
- Авторизация администраторов, хранение пользователей в БД.
- Готова к дальнейшей интеграции с API бота.
- Просмотр пользователей, подписок и транзакций бота в режиме только чтения.
- Черновые действия веб-API (страница `/admin/actions`) с описанием будущих операций.

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e .
copy .env.example .env
# отредактируйте .env под своё окружение
uvicorn app.main:app --reload
```

После запуска откройте `http://localhost:8000/admin/setup`, заполните форму и создайте первого администратора. Возможность первичной регистрации будет автоматически отключена после создания учётной записи. При необходимости дополнительного суперпользователя используйте `scripts/create_admin.py`.

Для локальной разработки PostgreSQL можно поднять через `docker-compose.yml`.

## Документация

- `docs/roadmap.md` — этапы разработки.
- `docs/development.md` — заметки о ходе работ и ключевых решениях.

## Статус

Этап 1: базовая админка с авторизацией и CRUD по админам — **в процессе**.
