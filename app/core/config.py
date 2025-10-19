"""Загрузка и доступ к конфигурации приложения."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Bedolaga Admin", validation_alias="APP_NAME")
    debug: bool = Field(default=False, validation_alias="DEBUG")

    admin_secret_key: str = Field(validation_alias="ADMIN_SECRET_KEY")
    access_token_expire_minutes: int = Field(
        default=60,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/bedolaga_admin",
        validation_alias="DATABASE_URL",
    )

    webapi_base_url: str | None = Field(default=None, validation_alias="WEBAPI_BASE_URL")
    webapi_api_key: str | None = Field(default=None, validation_alias="WEBAPI_API_KEY")
    webapi_timeout: float = Field(default=10.0, validation_alias="WEBAPI_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Кэшируемые настройки, чтобы не перечитывать .env."""
    return Settings()
