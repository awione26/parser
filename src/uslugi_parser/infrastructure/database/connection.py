"""Создание SQLAlchemy-подключения и фабрики сессий."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Создать SQLAlchemy Engine с проверкой и обновлением соединений пула."""

    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Создать фабрику сессий без истечения ORM-атрибутов после commit."""

    return sessionmaker(bind=engine, expire_on_commit=False)
