"""Add indexes used by the administration panel.

Revision ID: 20260826_02
Revises: 20260820_01
Create Date: 2026-08-26
"""

from collections.abc import Sequence

from alembic import context, op
from sqlalchemy import inspect

revision: str = "20260826_02"
down_revision: str | None = "20260820_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
_CATEGORY_INDEX = "ix_professional_categories_category_professional"


def _ensure_mysql_category_fk_index() -> None:
    """Восстановить индекс FK category_id перед удалением составного индекса."""

    connection = op.get_bind()
    if connection.dialect.name != "mysql":
        return

    if not context.is_offline_mode():
        indexes = inspect(connection).get_indexes("professional_categories")
        has_replacement = any(
            index.get("name") != _CATEGORY_INDEX
            and list(index.get("column_names") or [])[:1] == ["category_id"]
            for index in indexes
        )
        if has_replacement:
            return

    # На чистой ревизии 01 InnoDB автоматически создаёт именно этот индекс.
    # После upgrade 02 он удаляет его как избыточный и переводит FK на составной.
    op.create_index("category_id", "professional_categories", ["category_id"])


def upgrade() -> None:
    op.create_index(
        "ix_professionals_last_scraped_at",
        "professionals",
        ["last_scraped_at"],
    )
    op.create_index(
        "ix_professionals_location",
        "professionals",
        ["country", "region", "city"],
    )
    op.create_index(
        "ix_professionals_gender_age",
        "professionals",
        ["gender", "age"],
    )
    op.create_index(
        "ix_professionals_experience_code",
        "professionals",
        ["experience_code"],
    )
    op.create_index(
        _CATEGORY_INDEX,
        "professional_categories",
        ["category_id", "professional_id"],
    )


def downgrade() -> None:
    _ensure_mysql_category_fk_index()
    op.drop_index(
        _CATEGORY_INDEX,
        table_name="professional_categories",
    )
    op.drop_index("ix_professionals_experience_code", table_name="professionals")
    op.drop_index("ix_professionals_gender_age", table_name="professionals")
    op.drop_index("ix_professionals_location", table_name="professionals")
    op.drop_index("ix_professionals_last_scraped_at", table_name="professionals")
