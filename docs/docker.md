# Docker development environment

This project already ships with a Docker setup that is aimed at day-to-day development.

## Quick start

1. Create the `.env` file if you have not done it yet:
   ```bash
   copy .env.example .env  # PowerShell
   ```
2. Build images and launch the stack:
   ```bash
   docker compose up --build
   ```
3. Open `http://localhost:8000/admin/setup` to create the first admin user.

## How it works

- `docker-compose.yml` starts two services: PostgreSQL (`db`) and the FastAPI application (`app`).
- The application container installs project dependencies once during the build step (`pip install -e .[dev]`).
- The repository root is mounted into `/code` inside the container (`.:/code`), so any file edits on the host are immediately visible to the app.
- `uvicorn --reload` together with the `WATCHFILES_FORCE_POLLING=true` env var enables live reload even on Windows host volumes.

## Typical workflow

- Change code locally → the container reloads automatically.
- Pull updates from git → run `docker compose restart app` (or `docker compose up --build` if dependencies changed).
- Retrieve logs with `docker compose logs -f app`.
- Run one-off commands, e.g. migrations:
  ```bash
  docker compose exec app alembic upgrade head
  ```

You can stop the stack with `docker compose down`. Named volume `postgres-data` keeps the database between restarts.
