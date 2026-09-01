"""Синхронизировать названия и описания категорий с новым справочником.

Revision ID: 20260901_09
Revises: 20260901_08
Create Date: 2026-09-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

revision: str = "20260901_09"
down_revision: str | None = "20260901_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRIMARY_KEY_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

_UPDATED_METADATA: tuple[tuple[str, str, str | None], ...] = (
    (
        "designers",
        "Дизайнеры",
        "Точная специализация дизайнеров интерьеров из справочника Яндекса.",
    ),
    (
        "estimators",
        "Сметчики",
        "Специализация проектирования объектов и составления смет.",
    ),
    ("plumbers", "Сантехник", None),
    ("electricians", "Электрик", None),
    ("carpenters", "Плотник", None),
    (
        "furniture_assemblers",
        "Сборщик мебели",
        "Сборка, ремонт и изготовление мебели по приложенному справочнику.",
    ),
    (
        "finishers",
        "Отделочник",
        "Семь подтверждённых отделочных специализаций из справочника Яндекса.",
    ),
    (
        "appliance_repair",
        "Мастер по ремонту бытовой техники",
        "Ремонт и установка бытовой техники по десяти подтверждённым специализациям.",
    ),
    (
        "window_repair",
        "Мастер по ремонту окон",
        "Ремонт и установка окон и балконов по приложенному справочнику.",
    ),
    (
        "locks_and_doors",
        "Мастер по замкам и дверям",
        "Четыре подтверждённые специализации дверей и замков.",
    ),
    (
        "low_voltage",
        "Мастер по слаботочным системам",
        "Слаботочные системы, охрана/СКУД, умный дом и антенны.",
    ),
)

_PREVIOUS_METADATA: tuple[tuple[str, str, str | None], ...] = (
    ("designers", "Дизайнеры", None),
    (
        "estimators",
        "Сметчики",
        "Объединение семи официальных услуг по составлению смет.",
    ),
    ("plumbers", "Сантехник", None),
    ("electricians", "Электрик", None),
    ("carpenters", "Плотник", None),
    (
        "furniture_assemblers",
        "Сборщик мебели",
        "Точные услуги сборки; ремонт и разборка мебели исключены.",
    ),
    (
        "finishers",
        "Отделочник",
        "Allowlist конкретных чистовых, черновых и отделочных услуг.",
    ),
    (
        "appliance_repair",
        "Мастер по ремонту бытовой техники",
        "Только услуги ремонта бытовой техники; установка исключена.",
    ),
    (
        "window_repair",
        "Мастер по ремонту окон",
        "Только ремонтные оконные услуги; балконные работы исключены.",
    ),
    (
        "locks_and_doors",
        "Мастер по замкам и дверям",
        "Allowlist строительных дверей и замков; авто-, сейфовые и гаражные исключены.",
    ),
    ("low_voltage", "Мастер по слаботочным системам", None),
)


def _categories_table() -> sa.TableClause:
    """Описать master-таблицу для переносимого upsert без изменения её ID."""

    return sa.table(
        "categories",
        sa.column("id", _PRIMARY_KEY_TYPE),
        sa.column("key", sa.String(length=64)),
        sa.column("name", sa.String(length=255)),
        sa.column("note", sa.Text()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )


def _sync_metadata(rows: tuple[tuple[str, str, str | None], ...]) -> None:
    """Обновить встроенные строки идемпотентно для MySQL и тестовой SQLite."""

    categories = _categories_table()
    dialect_name = op.get_bind().dialect.name
    for key, name, note in rows:
        values = {
            "key": key,
            "name": name,
            "note": note,
            "created_at": sa.func.current_timestamp(),
            "updated_at": sa.func.current_timestamp(),
        }
        if dialect_name == "mysql":
            statement = mysql_insert(categories).values(**values)
            op.execute(
                statement.on_duplicate_key_update(
                    name=statement.inserted.name,
                    note=statement.inserted.note,
                    updated_at=sa.func.current_timestamp(),
                )
            )
            continue
        if dialect_name == "sqlite":
            statement = sqlite_insert(categories).values(**values)
            op.execute(
                statement.on_conflict_do_update(
                    index_elements=["key"],
                    set_={
                        "name": name,
                        "note": note,
                        "updated_at": sa.func.current_timestamp(),
                    },
                )
            )
            continue
        raise RuntimeError(f"Unsupported category metadata dialect: {dialect_name}")


def upgrade() -> None:
    """Убрать устаревшие описания, противоречащие приложенному справочнику."""

    _sync_metadata(_UPDATED_METADATA)


def downgrade() -> None:
    """Вернуть описания, действовавшие до импорта нового справочника."""

    _sync_metadata(_PREVIOUS_METADATA)
