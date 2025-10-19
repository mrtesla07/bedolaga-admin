"""Базовая декларативная модель SQLAlchemy."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Общий базовый класс моделей."""

    repr_cols_num = 2
