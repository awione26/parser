"""Сделать таксономию Яндекса единственным источником целей обхода.

Revision ID: 20260902_10
Revises: 20260901_09
Create Date: 2026-09-02
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from urllib.parse import urlsplit

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260902_10"
down_revision: str | None = "20260901_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATALOG_TABLES = {
    "occupation": (
        "yandex_occupations",
        "category_yandex_occupations",
        "occupation_id",
    ),
    "specialization": (
        "yandex_specializations",
        "category_yandex_specializations",
        "specialization_id",
    ),
    "service": (
        "yandex_services",
        "category_yandex_services",
        "service_id",
    ),
}
_USABLE_STATUSES_SQL = "'confirmed', 'discovered', 'legacy'"
_USABLE_STATUSES = frozenset({"confirmed", "discovered", "legacy"})
_GEO_PATTERN = re.compile(r"^[0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*$")
_SEED_PATTERN = re.compile(
    r"(?:[a-z0-9]+(?:-[a-z0-9]+)*/)*"
    r"[a-z0-9]+(?:-[a-z0-9]+)*--([1-9][0-9]*)$"
)


def _backfill_professional_rubric_levels() -> None:
    """Восстановить уровень legacy-рубрик по точной связи с каталогом."""

    for level, (table_name, mapping_table, mapping_foreign_key) in _CATALOG_TABLES.items():
        other_tables = [values for values in _CATALOG_TABLES.values() if values[0] != table_name]
        ambiguity_guards = " ".join(
            "AND NOT EXISTS ("
            f"SELECT 1 FROM {other_table} AS other_node "
            f"JOIN {other_mapping} AS other_catalog_mapping "
            f"ON other_catalog_mapping.{other_foreign_key} = other_node.id "
            "WHERE other_node.external_number_id = "
            "professional_category_rubrics.source_rubric_number_id "
            "AND other_catalog_mapping.category_id = "
            "professional_category_rubrics.category_id)"
            for other_table, other_mapping, other_foreign_key in other_tables
        )
        op.execute(
            "UPDATE professional_category_rubrics "
            f"SET source_rubric_level = '{level}' "
            "WHERE source_rubric_level IS NULL "
            "AND EXISTS ("
            f"SELECT 1 FROM {table_name} AS catalog_node "
            f"JOIN {mapping_table} AS catalog_mapping "
            f"ON catalog_mapping.{mapping_foreign_key} = catalog_node.id "
            "WHERE catalog_node.external_number_id = "
            "professional_category_rubrics.source_rubric_number_id "
            "AND catalog_mapping.category_id = "
            "professional_category_rubrics.category_id) "
            f"{ambiguity_guards}"
        )


def _canonical_catalog_path(
    slug: object,
    source_url: object,
    rubric_id: object,
) -> str | None:
    """Вернуть путь только для каноничного и безопасного узла яндекс-каталога."""

    if (
        not isinstance(rubric_id, int)
        or isinstance(rubric_id, bool)
        or rubric_id < 1
        or not isinstance(slug, str)
        or not slug
        or slug != slug.strip()
        or not slug.startswith("/")
        or slug.endswith("/")
    ):
        return None
    canonical_path = f"{slug[1:]}--{rubric_id}"
    match = _SEED_PATTERN.fullmatch(canonical_path)
    if match is None or int(match.group(1)) != rubric_id:
        return None
    if not isinstance(source_url, str) or not source_url or source_url != source_url.strip():
        return None
    parsed = urlsplit(source_url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "uslugi.yandex.ru"
        or parsed.query
        or parsed.fragment
    ):
        return None
    parts = parsed.path.split("/")
    if len(parts) >= 3 and not parts[0] and parts[1] == "category":
        source_path = "/".join(parts[2:])
    elif (
        len(parts) >= 4
        and not parts[0]
        and parts[2] == "category"
        and _GEO_PATTERN.fullmatch(parts[1]) is not None
    ):
        source_path = "/".join(parts[3:])
    else:
        return None
    if source_path != canonical_path:
        return None
    return canonical_path


def _disable_unknown_targets() -> None:
    """Выключить legacy-цели без точного уровня внешней таксономии."""

    # Старый UI мог выключить родительскую конфигурацию, но
    # оставить её дочерние цели активными. Сначала переносим это
    # состояние, чтобы новый UI не включил весь скрытый набор одним кликом.
    op.execute(
        "UPDATE parser_category_targets "
        "SET is_active = 0, updated_at = CURRENT_TIMESTAMP "
        "WHERE is_active = 1 AND EXISTS ("
        "SELECT 1 FROM parser_categories AS parser_category "
        "WHERE parser_category.category_id = parser_category_targets.category_id "
        "AND parser_category.is_active = 0)"
    )
    op.execute(
        "UPDATE parser_category_targets "
        "SET is_active = 0, updated_at = CURRENT_TIMESTAMP "
        "WHERE taxonomy_level NOT IN ('occupation', 'specialization', 'service')"
    )


def _disable_invalid_targets_online() -> None:
    """Проверить каждую цель по M:N-связи, slug, URL, ID и relative_path."""

    connection = op.get_bind()
    invalid_ids: set[int] = set()
    for level, (table_name, mapping_table, mapping_foreign_key) in _CATALOG_TABLES.items():
        rows = connection.execute(
            sa.text(
                "SELECT target.id, target.relative_path, "
                "target.source_rubric_number_id, catalog_node.slug, "
                "catalog_node.source_url, catalog_node.verification_status, "
                "catalog_mapping.category_id AS mapped_category_id "
                "FROM parser_category_targets AS target "
                f"LEFT JOIN {table_name} AS catalog_node "
                "ON catalog_node.external_number_id = target.source_rubric_number_id "
                f"LEFT JOIN {mapping_table} AS catalog_mapping "
                "ON catalog_mapping.category_id = target.category_id "
                f"AND catalog_mapping.{mapping_foreign_key} = catalog_node.id "
                f"WHERE target.taxonomy_level = '{level}'"
            )
        )
        for row in rows.mappings():
            canonical_path = _canonical_catalog_path(
                row["slug"],
                row["source_url"],
                row["source_rubric_number_id"],
            )
            if (
                row["mapped_category_id"] is None
                or row["verification_status"] not in _USABLE_STATUSES
                or canonical_path is None
                or row["relative_path"] != canonical_path
            ):
                invalid_ids.add(int(row["id"]))

    targets = sa.table(
        "parser_category_targets",
        sa.column("id", sa.BigInteger()),
        sa.column("is_active", sa.Boolean()),
        sa.column("updated_at", sa.DateTime()),
    )
    ordered_ids = sorted(invalid_ids)
    for offset in range(0, len(ordered_ids), 500):
        op.execute(
            targets.update()
            .where(targets.c.id.in_(ordered_ids[offset : offset + 500]))
            .values(is_active=False, updated_at=sa.func.current_timestamp())
        )


def _disable_invalid_targets_offline() -> None:
    """Выпустить эквивалентную fail-closed проверку в MySQL offline SQL."""

    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("Catalog authority offline migration requires MySQL")
    slug_pattern = (
        r"^/[a-z0-9]+(-[a-z0-9]+)*"
        r"(/[a-z0-9]+(-[a-z0-9]+)*)*$"
    )
    source_pattern = (
        r"^https://uslugi\\.yandex\\.ru/"
        r"([0-9]+-[a-z0-9]+(-[a-z0-9]+)*/)?"
        r"category/[a-z0-9/-]+--[1-9][0-9]*$"
    )
    for level, (table_name, mapping_table, mapping_foreign_key) in _CATALOG_TABLES.items():
        op.execute(
            "UPDATE parser_category_targets "
            "SET is_active = 0, updated_at = CURRENT_TIMESTAMP "
            f"WHERE taxonomy_level = '{level}' AND NOT EXISTS ("
            f"SELECT 1 FROM {table_name} AS catalog_node "
            f"JOIN {mapping_table} AS catalog_mapping "
            f"ON catalog_mapping.{mapping_foreign_key} = catalog_node.id "
            "WHERE catalog_mapping.category_id = parser_category_targets.category_id "
            "AND catalog_node.external_number_id = "
            "parser_category_targets.source_rubric_number_id "
            f"AND catalog_node.verification_status IN ({_USABLE_STATUSES_SQL}) "
            f"AND catalog_node.slug REGEXP '{slug_pattern}' "
            f"AND catalog_node.source_url REGEXP '{source_pattern}' "
            "AND parser_category_targets.relative_path = CONCAT("
            "TRIM(LEADING '/' FROM catalog_node.slug), '--', "
            "catalog_node.external_number_id) "
            "AND SUBSTRING(catalog_node.source_url, "
            "LOCATE('/category/', catalog_node.source_url) + 10) = "
            "parser_category_targets.relative_path)"
        )


def _synchronize_seed_paths() -> None:
    """Обновить legacy JSON-зеркало после fail-closed деактивации целей."""

    if context.is_offline_mode():
        if op.get_bind().dialect.name != "mysql":
            raise RuntimeError("Catalog seed-path sync offline migration requires MySQL")
        op.execute(
            "UPDATE parser_categories AS parser_category "
            "LEFT JOIN ("
            "SELECT category_id, CAST(CONCAT('[', GROUP_CONCAT("
            "JSON_QUOTE(relative_path) ORDER BY sort_order, id SEPARATOR ','), ']') AS JSON) "
            "AS active_seed_paths FROM parser_category_targets "
            "WHERE is_active = 1 GROUP BY category_id"
            ") AS active_targets "
            "ON active_targets.category_id = parser_category.category_id "
            "SET parser_category.seed_paths = COALESCE("
            "active_targets.active_seed_paths, JSON_ARRAY()), "
            "parser_category.updated_at = CURRENT_TIMESTAMP"
        )
        return

    connection = op.get_bind()
    category_ids = [
        int(row[0])
        for row in connection.execute(
            sa.text("SELECT category_id FROM parser_categories ORDER BY category_id")
        )
    ]
    paths_by_category: dict[int, list[str]] = {category_id: [] for category_id in category_ids}
    rows = connection.execute(
        sa.text(
            "SELECT category_id, relative_path FROM parser_category_targets "
            "WHERE is_active = 1 ORDER BY category_id, sort_order, id"
        )
    )
    for category_id, relative_path in rows:
        paths_by_category[int(category_id)].append(str(relative_path))
    for category_id, paths in paths_by_category.items():
        connection.execute(
            sa.text(
                "UPDATE parser_categories SET seed_paths = :seed_paths, "
                "updated_at = CURRENT_TIMESTAMP WHERE category_id = :category_id"
            ),
            {
                "category_id": category_id,
                "seed_paths": json.dumps(paths, ensure_ascii=False),
            },
        )


def _disable_targets_outside_catalog() -> None:
    """Выключить все цели, которые не принадлежат каноничному каталогу."""

    _disable_unknown_targets()
    if context.is_offline_mode():
        _disable_invalid_targets_offline()
    else:
        _disable_invalid_targets_online()
    _synchronize_seed_paths()

    # Конфигурация без единой активной цели не должна блокировать
    # обход остальных валидных строк каталога.
    op.execute(
        "UPDATE parser_categories "
        "SET is_active = 0, updated_at = CURRENT_TIMESTAMP "
        "WHERE is_active = 1 AND NOT EXISTS ("
        "SELECT 1 FROM parser_category_targets AS target "
        "WHERE target.category_id = parser_categories.category_id "
        "AND target.is_active = 1)"
    )


def upgrade() -> None:
    """Обновить legacy-связи и оставить активными только цели из Каталога Яндекса."""

    _backfill_professional_rubric_levels()
    _disable_targets_outside_catalog()
    op.create_index(
        "ix_professional_category_rubrics_catalog",
        "professional_category_rubrics",
        ["source_rubric_level", "source_rubric_number_id", "professional_id"],
        unique=False,
    )


def downgrade() -> None:
    """Удалить индекс, не возвращая заведомо небезопасные цели в активный план."""

    op.drop_index(
        "ix_professional_category_rubrics_catalog",
        table_name="professional_category_rubrics",
    )
