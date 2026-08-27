"""Create parser run event log.

Revision ID: 20260827_04
Revises: 20260827_03
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_04"
down_revision: str | None = "20260827_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
pk_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """Создать таблицу жизненного цикла запусков парсера и индекс времени."""

    op.create_table(
        "logs",
        sa.Column("id", pk_type, autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=True),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("resource", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "result IS NULL OR result IN ('success', 'failure')",
            name="ck_logs_result",
        ),
        sa.CheckConstraint(
            "(result IS NULL AND finished_at IS NULL AND error_reason IS NULL) OR "
            "(result = 'success' AND finished_at IS NOT NULL AND error_reason IS NULL) OR "
            "(result = 'failure' AND finished_at IS NOT NULL AND error_reason IS NOT NULL)",
            name="ck_logs_lifecycle",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_logs_started_at", "logs", ["started_at"])
    op.create_index("ix_logs_result_started_at", "logs", ["result", "started_at"])
    op.create_index("ix_logs_resource_started_at", "logs", ["resource", "started_at"])


def downgrade() -> None:
    """Удалить таблицу журнала запусков парсера."""

    op.drop_index("ix_logs_resource_started_at", table_name="logs")
    op.drop_index("ix_logs_result_started_at", table_name="logs")
    op.drop_index("ix_logs_started_at", table_name="logs")
    op.drop_table("logs")
