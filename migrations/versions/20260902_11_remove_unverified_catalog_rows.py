"""Удалить из Яндекс.Каталога строки, не найденные в источнике.

Revision ID: 20260902_11
Revises: 20260902_10
Create Date: 2026-09-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260902_11"
down_revision: str | None = "20260902_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATALOG_TABLES = {
    "occupation": "yandex_occupations",
    "specialization": "yandex_specializations",
    "service": "yandex_services",
}


def _not_found_predicate(alias: str) -> str:
    """Описать legacy-заглушку без raw/number ID, slug и URL источника."""

    return (
        f"{alias}.verification_status = 'unverified' "
        f"AND {alias}.external_id_raw IS NULL "
        f"AND {alias}.external_number_id IS NULL "
        f"AND {alias}.slug IS NULL "
        f"AND {alias}.source_url IS NULL"
    )


def _reference_count_sql(level: str, table_name: str) -> tuple[str, str]:
    """Построить проверки целей обхода и доказательств мастеров для уровня."""

    target_sql = (
        "SELECT COUNT(*) FROM parser_category_targets AS target "
        f"JOIN {table_name} AS catalog_node "
        "ON catalog_node.external_number_id = target.source_rubric_number_id "
        f"AND target.taxonomy_level = '{level}' "
        f"WHERE {_not_found_predicate('catalog_node')}"
    )
    evidence_sql = (
        "SELECT COUNT(*) FROM professional_category_rubrics AS evidence "
        f"JOIN {table_name} AS catalog_node "
        "ON catalog_node.external_number_id = evidence.source_rubric_number_id "
        f"AND (evidence.source_rubric_level = '{level}' "
        "OR evidence.source_rubric_level IS NULL) "
        f"WHERE {_not_found_predicate('catalog_node')}"
    )
    return target_sql, evidence_sql


def _blocking_checks() -> tuple[tuple[str, str], ...]:
    """Вернуть именованные SQL-проверки ссылок, которые нельзя осиротить."""

    checks: list[tuple[str, str]] = []
    for level, table_name in _CATALOG_TABLES.items():
        target_sql, evidence_sql = _reference_count_sql(level, table_name)
        checks.extend(
            (
                (f"{level} parser targets", target_sql),
                (f"{level} professional evidence", evidence_sql),
            )
        )

    # Ненайденные дочерние заглушки удаляются раньше родителей. Блокирует любой
    # дочерний узел, который не входит в точный набор этой очистки.
    checks.extend(
        (
            (
                "preserved services below not-found specializations",
                "SELECT COUNT(*) FROM yandex_services AS service "
                "JOIN yandex_specializations AS specialization "
                "ON specialization.id = service.specialization_id "
                f"WHERE {_not_found_predicate('specialization')} "
                f"AND NOT ({_not_found_predicate('service')})",
            ),
            (
                "preserved specializations below not-found occupations",
                "SELECT COUNT(*) FROM yandex_specializations AS specialization "
                "JOIN yandex_occupations AS occupation "
                "ON occupation.id = specialization.occupation_id "
                f"WHERE {_not_found_predicate('occupation')} "
                f"AND NOT ({_not_found_predicate('specialization')})",
            ),
        )
    )
    return tuple(checks)


def _assert_safe_online() -> None:
    """Остановить online-миграцию до изменений при любой внешней ссылке."""

    connection = op.get_bind()
    blockers: list[str] = []
    for label, statement in _blocking_checks():
        count = int(connection.scalar(sa.text(statement)) or 0)
        if count:
            blockers.append(f"{label}: {count}")
    if blockers:
        raise RuntimeError(
            "Cannot remove unverified Yandex catalog rows; protected references exist: "
            + ", ".join(blockers)
        )


def _assert_safe_offline() -> None:
    """Добавить в MySQL offline SQL проверку, завершающую миграцию ошибкой."""

    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("Unverified catalog cleanup offline migration requires MySQL")

    guard_table = "alembic_unverified_catalog_cleanup_guard"
    count_expression = " + ".join(f"({statement})" for _label, statement in _blocking_checks())
    op.execute(
        f"CREATE TEMPORARY TABLE {guard_table} ("
        "id INTEGER NOT NULL PRIMARY KEY, "
        "blocked_count BIGINT NOT NULL, "
        f"CONSTRAINT ck_{guard_table}_empty CHECK (blocked_count = 0))"
    )
    op.execute(f"INSERT INTO {guard_table} (id, blocked_count) SELECT 1, {count_expression}")
    op.execute(f"DROP TEMPORARY TABLE {guard_table}")


def _delete_unverified_rows() -> None:
    """Удалить M:N-связи и ненайденные узлы снизу вверх по иерархии."""

    for table_name, mapping_table, foreign_key in (
        ("yandex_services", "category_yandex_services", "service_id"),
        (
            "yandex_specializations",
            "category_yandex_specializations",
            "specialization_id",
        ),
        ("yandex_occupations", "category_yandex_occupations", "occupation_id"),
    ):
        op.execute(
            f"DELETE FROM {mapping_table} WHERE {foreign_key} IN ("
            f"SELECT catalog_node.id FROM {table_name} AS catalog_node "
            f"WHERE {_not_found_predicate('catalog_node')})"
        )
        op.execute(f"DELETE FROM {table_name} WHERE {_not_found_predicate(table_name)}")


def upgrade() -> None:
    """Удалить только ненайденные строки, не затрагивая используемый каталог."""

    if context.is_offline_mode():
        _assert_safe_offline()
    else:
        _assert_safe_online()
    _delete_unverified_rows()


def downgrade() -> None:
    """Не восстанавливать предположительные строки без идентификаторов источника.

    Очистка данных намеренно необратима: восстановление snapshot вернуло бы в
    рабочий каталог категории, которые не существуют на сайте Яндекс Услуг.
    """

    pass
