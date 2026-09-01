"""Добавить нормализованный справочник категорий Яндекс Услуг.

Revision ID: 20260901_08
Revises: 20260831_07
Create Date: 2026-09-01
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_08"
down_revision: str | None = "20260831_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRIMARY_KEY_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "20260901_yandex_taxonomy.json"
_VERIFICATION_CHECK = "verification_status IN ('confirmed', 'discovered', 'legacy', 'unverified')"


def _snapshot() -> dict[str, Any]:
    """Прочитать неизменяемый снимок приложенного справочника этой ревизии."""

    payload = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("groups"), list):
        raise RuntimeError("Invalid Yandex taxonomy migration snapshot")
    return payload


def _create_source_table(
    name: str,
    *,
    parent: tuple[str, str] | None = None,
) -> None:
    """Создать таблицу одного уровня внешней таксономии с необязательным родителем."""

    columns: list[sa.Column[Any]] = [
        sa.Column("id", _PRIMARY_KEY_TYPE, autoincrement=True, nullable=False),
    ]
    if parent is not None:
        parent_column, parent_table = parent
        columns.append(sa.Column(parent_column, _PRIMARY_KEY_TYPE, nullable=True))
    columns.extend(
        [
            sa.Column("external_id_raw", sa.String(length=255), nullable=True),
            sa.Column("external_number_id", sa.Integer(), nullable=True),
            sa.Column("slug", sa.String(length=512), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("source_url", sa.String(length=1024), nullable=True),
            sa.Column("verification_status", sa.String(length=16), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.CheckConstraint(
                _VERIFICATION_CHECK,
                name=f"ck_{name}_verification_status",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "external_number_id",
                name=f"uq_{name}_external_number_id",
            ),
        ]
    )
    if parent is not None:
        parent_column, parent_table = parent
        columns.append(
            sa.ForeignKeyConstraint(
                [parent_column],
                [f"{parent_table}.id"],
                name=f"fk_{name}_{parent_column}",
                ondelete="RESTRICT",
            )
        )
    op.create_table(
        name,
        *columns,
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(f"ix_{name}_name", name, ["name"], unique=False)
    if parent is not None:
        op.create_index(f"ix_{name}_{parent[0]}", name, [parent[0]], unique=False)


def _create_mapping_table(
    name: str,
    *,
    foreign_column: str,
    foreign_table: str,
) -> None:
    """Создать M:N связь внутренней группы с одним уровнем Яндекс-каталога."""

    op.create_table(
        name,
        sa.Column("category_id", _PRIMARY_KEY_TYPE, nullable=False),
        sa.Column(foreign_column, _PRIMARY_KEY_TYPE, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("sort_order >= 0", name=f"ck_{name}_sort_order"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=f"fk_{name}_category_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [foreign_column],
            [f"{foreign_table}.id"],
            name=f"fk_{name}_{foreign_column}",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("category_id", foreign_column),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        f"ix_{name}_{foreign_column}",
        name,
        [foreign_column, "category_id"],
        unique=False,
    )


def _taxonomy_table(name: str, *, parent_column: str | None = None) -> sa.TableClause:
    """Описать минимальный набор колонок таблицы для bulk insert снимка."""

    columns = [
        sa.column("id", _PRIMARY_KEY_TYPE),
    ]
    if parent_column is not None:
        columns.append(sa.column(parent_column, _PRIMARY_KEY_TYPE))
    columns.extend(
        [
            sa.column("external_id_raw", sa.String(length=255)),
            sa.column("external_number_id", sa.Integer()),
            sa.column("slug", sa.String(length=512)),
            sa.column("name", sa.String(length=255)),
            sa.column("source_url", sa.String(length=1024)),
            sa.column("verification_status", sa.String(length=16)),
        ]
    )
    return sa.table(name, *columns)


def _backfill_legacy_targets() -> None:
    """Перенести JSON-пути всех существующих конфигураций в нормализованные цели.

    Пользовательские категории могли быть добавлены до этой ревизии, поэтому
    нельзя ограничиваться одиннадцатью встроенными группами из снимка.
    Выражения выполняются как SQL, чтобы полный offline-скрипт Alembic оставался
    пригодным для развёртывания MySQL.
    """

    dialect_name = op.get_bind().dialect.name
    if dialect_name == "mysql":
        op.execute(
            sa.text(
                """
                INSERT INTO parser_category_targets (
                    category_id, taxonomy_level, source_rubric_number_id,
                    relative_path, is_active, sort_order, created_at, updated_at
                )
                SELECT
                    parser_category.category_id,
                    'unknown',
                    CAST(SUBSTRING_INDEX(seed.relative_path, '--', -1) AS UNSIGNED),
                    seed.relative_path,
                    1,
                    seed.seed_order * 10,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM parser_categories AS parser_category
                JOIN JSON_TABLE(
                    parser_category.seed_paths,
                    '$[*]' COLUMNS (
                        seed_order FOR ORDINALITY,
                        relative_path VARCHAR(512) PATH '$'
                    )
                ) AS seed ON TRUE
                """
            )
        )
        return

    if dialect_name == "sqlite":
        op.execute(
            sa.text(
                """
                INSERT INTO parser_category_targets (
                    category_id, taxonomy_level, source_rubric_number_id,
                    relative_path, is_active, sort_order, created_at, updated_at
                )
                SELECT
                    parser_category.category_id,
                    'unknown',
                    CAST(substr(seed.value, instr(seed.value, '--') + 2) AS INTEGER),
                    seed.value,
                    1,
                    (CAST(seed.key AS INTEGER) + 1) * 10,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM parser_categories AS parser_category
                JOIN json_each(parser_category.seed_paths) AS seed ON 1 = 1
                """
            )
        )
        return

    raise RuntimeError(f"Unsupported taxonomy migration dialect: {dialect_name}")


def _seed_snapshot(payload: dict[str, Any]) -> None:
    """Заполнить внешние уровни, связи групп и проверенные цели обхода."""

    for table_name, parent_column in (
        ("yandex_occupations", None),
        ("yandex_specializations", "occupation_id"),
        ("yandex_services", "specialization_id"),
    ):
        rows = payload[table_name]
        if rows:
            op.bulk_insert(
                _taxonomy_table(table_name, parent_column=parent_column),
                rows,
            )

    categories = sa.table(
        "categories",
        sa.column("id", _PRIMARY_KEY_TYPE),
        sa.column("key", sa.String(length=64)),
    )
    mappings = (
        (
            "category_yandex_occupations",
            "occupation_id",
            "occupation_ids",
        ),
        (
            "category_yandex_specializations",
            "specialization_id",
            "specialization_ids",
        ),
        ("category_yandex_services", "service_id", "service_ids"),
    )
    for group in payload["groups"]:
        category_key = group["category_key"]
        for table_name, foreign_column, manifest_key in mappings:
            mapping = sa.table(
                table_name,
                sa.column("category_id", _PRIMARY_KEY_TYPE),
                sa.column(foreign_column, _PRIMARY_KEY_TYPE),
                sa.column("sort_order", sa.Integer()),
            )
            for position, foreign_id in enumerate(group[manifest_key], start=1):
                source = sa.select(
                    categories.c.id,
                    sa.literal(int(foreign_id)),
                    sa.literal(position * 10),
                ).where(categories.c.key == category_key)
                op.execute(
                    mapping.insert().from_select(
                        ["category_id", foreign_column, "sort_order"],
                        source,
                    )
                )

        targets = group["crawl_targets"]
        parser_targets = sa.table(
            "parser_category_targets",
            sa.column("category_id", _PRIMARY_KEY_TYPE),
            sa.column("taxonomy_level", sa.String(length=16)),
            sa.column("source_rubric_number_id", sa.Integer()),
            sa.column("relative_path", sa.String(length=512)),
            sa.column("is_active", sa.Boolean()),
            sa.column("sort_order", sa.Integer()),
            sa.column("created_at", sa.DateTime()),
            sa.column("updated_at", sa.DateTime()),
        )
        parser_categories = sa.table(
            "parser_categories",
            sa.column("category_id", _PRIMARY_KEY_TYPE),
            sa.column("seed_paths", sa.JSON()),
        )
        configured_category = (
            sa.select(parser_categories.c.category_id)
            .select_from(
                parser_categories.join(
                    categories,
                    categories.c.id == parser_categories.c.category_id,
                )
            )
            .where(categories.c.key == category_key)
        )
        op.execute(
            parser_targets.delete().where(
                parser_targets.c.category_id == configured_category.scalar_subquery()
            )
        )
        for position, target in enumerate(targets, start=1):
            source = (
                sa.select(
                    parser_categories.c.category_id,
                    sa.literal(target["taxonomy_level"]),
                    sa.literal(int(target["source_rubric_number_id"])),
                    sa.literal(target["relative_path"]),
                    sa.true(),
                    sa.literal(position * 10),
                    sa.func.current_timestamp(),
                    sa.func.current_timestamp(),
                )
                .select_from(
                    parser_categories.join(
                        categories,
                        categories.c.id == parser_categories.c.category_id,
                    )
                )
                .where(categories.c.key == category_key)
            )
            op.execute(
                parser_targets.insert().from_select(
                    [
                        "category_id",
                        "taxonomy_level",
                        "source_rubric_number_id",
                        "relative_path",
                        "is_active",
                        "sort_order",
                        "created_at",
                        "updated_at",
                    ],
                    source,
                )
            )

        seed_paths = [target["relative_path"] for target in targets]
        op.execute(
            parser_categories.update()
            .where(
                parser_categories.c.category_id
                == sa.select(categories.c.id)
                .where(categories.c.key == category_key)
                .scalar_subquery()
            )
            .values(
                seed_paths=sa.literal(
                    json.dumps(seed_paths, ensure_ascii=False),
                    type_=sa.Text(),
                )
            )
        )


def upgrade() -> None:
    """Создать и заполнить справочник, затем нормализовать цели обхода парсера."""

    op.add_column(
        "professional_category_rubrics",
        sa.Column("source_rubric_level", sa.String(length=16), nullable=True),
    )
    _create_source_table("yandex_occupations")
    _create_source_table(
        "yandex_specializations",
        parent=("occupation_id", "yandex_occupations"),
    )
    _create_source_table(
        "yandex_services",
        parent=("specialization_id", "yandex_specializations"),
    )
    _create_mapping_table(
        "category_yandex_occupations",
        foreign_column="occupation_id",
        foreign_table="yandex_occupations",
    )
    _create_mapping_table(
        "category_yandex_specializations",
        foreign_column="specialization_id",
        foreign_table="yandex_specializations",
    )
    _create_mapping_table(
        "category_yandex_services",
        foreign_column="service_id",
        foreign_table="yandex_services",
    )
    op.create_table(
        "parser_category_targets",
        sa.Column("id", _PRIMARY_KEY_TYPE, autoincrement=True, nullable=False),
        sa.Column("category_id", _PRIMARY_KEY_TYPE, nullable=False),
        sa.Column("taxonomy_level", sa.String(length=16), nullable=False),
        sa.Column("source_rubric_number_id", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.String(length=512), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "taxonomy_level IN ('occupation', 'specialization', 'service', 'unknown')",
            name="ck_parser_category_targets_level",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_parser_category_targets_sort_order",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["parser_categories.category_id"],
            name="fk_parser_category_targets_category_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "category_id",
            "source_rubric_number_id",
            name="uq_parser_category_targets_category_rubric",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_bin",
    )
    op.create_index(
        "ix_parser_category_targets_category_order",
        "parser_category_targets",
        ["category_id", "is_active", "sort_order", "id"],
        unique=False,
    )
    _backfill_legacy_targets()
    _seed_snapshot(_snapshot())


def downgrade() -> None:
    """Удалить внешний справочник и вернуть legacy JSON-пути ревизии 07."""

    payload = _snapshot()
    categories = sa.table(
        "categories",
        sa.column("id", _PRIMARY_KEY_TYPE),
        sa.column("key", sa.String(length=64)),
    )
    parser_categories = sa.table(
        "parser_categories",
        sa.column("category_id", _PRIMARY_KEY_TYPE),
        sa.column("seed_paths", sa.JSON()),
    )
    for group in payload["groups"]:
        op.execute(
            parser_categories.update()
            .where(
                parser_categories.c.category_id
                == sa.select(categories.c.id)
                .where(categories.c.key == group["category_key"])
                .scalar_subquery()
            )
            .values(
                seed_paths=sa.literal(
                    json.dumps(group["legacy_seed_paths"], ensure_ascii=False),
                    type_=sa.Text(),
                )
            )
        )

    op.drop_index(
        "ix_parser_category_targets_category_order",
        table_name="parser_category_targets",
    )
    op.drop_table("parser_category_targets")
    op.drop_index(
        "ix_category_yandex_services_service_id",
        table_name="category_yandex_services",
    )
    op.drop_table("category_yandex_services")
    op.drop_index(
        "ix_category_yandex_specializations_specialization_id",
        table_name="category_yandex_specializations",
    )
    op.drop_table("category_yandex_specializations")
    op.drop_index(
        "ix_category_yandex_occupations_occupation_id",
        table_name="category_yandex_occupations",
    )
    op.drop_table("category_yandex_occupations")
    op.drop_index("ix_yandex_services_specialization_id", table_name="yandex_services")
    op.drop_index("ix_yandex_services_name", table_name="yandex_services")
    op.drop_table("yandex_services")
    op.drop_index(
        "ix_yandex_specializations_occupation_id",
        table_name="yandex_specializations",
    )
    op.drop_index("ix_yandex_specializations_name", table_name="yandex_specializations")
    op.drop_table("yandex_specializations")
    op.drop_index("ix_yandex_occupations_name", table_name="yandex_occupations")
    op.drop_table("yandex_occupations")
    op.drop_column("professional_category_rubrics", "source_rubric_level")
