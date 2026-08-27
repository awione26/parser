from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from uslugi_parser.config.database import database_url_from_env
from uslugi_parser.infrastructure.database.models import Base

load_dotenv()
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = database_url_from_env()
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

target_metadata = Base.metadata
managed_tables = frozenset(target_metadata.tables)


def include_parser_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Ограничить autogenerate таблицами, которыми управляет Alembic парсера.

    Laravel хранит свои таблицы в той же MySQL. Без этого фильтра `alembic check`
    ошибочно предлагает удалить таблицы админки как посторонние.
    """

    del name, reflected, compare_to
    if type_ == "table":
        return getattr(object_, "name", None) in managed_tables

    table = getattr(object_, "table", None)
    return table is None or getattr(table, "name", None) in managed_tables


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_parser_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_parser_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
