"""Создать хранилище редактируемых настроек парсера.

Revision ID: 20260827_05
Revises: 20260827_04
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_05"
down_revision: str | None = "20260827_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_SETTINGS: tuple[tuple[str, str], ...] = (
    (
        "SCRAPER_USER_AGENT",
        "CompanyName-UslugiParser/0.1 (+mailto:parser-owner@example.com)",
    ),
    ("SCRAPER_GEO", "213-moscow"),
    ("SCRAPER_RESPECT_ROBOTS", "true"),
    ("SCRAPER_MIN_DELAY_SECONDS", "2.0"),
    ("SCRAPER_MAX_DELAY_SECONDS", "5.0"),
    ("SCRAPER_TIMEOUT_SECONDS", "30.0"),
    ("SCRAPER_MAX_RETRIES", "3"),
    ("SCRAPER_COLLECT_PHONE", "false"),
    ("SCRAPER_PHONE_HEADLESS", "true"),
    ("SCRAPER_PHONE_TIMEOUT_SECONDS", "15.0"),
    ("SCRAPER_INCLUDE_ORGANIZATIONS", "false"),
)


def _allowed_keys_constraint() -> str:
    """Сформировать CHECK, не позволяющий хранить посторонние ключи настроек."""

    values = ", ".join(f"'{key}'" for key, _value in DEFAULT_SETTINGS)
    # Backticks подходят MySQL и SQLite и защищают зарезервированное слово KEY.
    return f"`key` IN ({values})"


def upgrade() -> None:
    """Создать таблицу и заполнить её одиннадцатью безопасными значениями по умолчанию."""

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
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
        sa.CheckConstraint(_allowed_keys_constraint(), name="ck_settings_known_key"),
        sa.PrimaryKeyConstraint("key"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    settings_table = sa.table(
        "settings",
        sa.column("key", sa.String(length=64)),
        sa.column("value", sa.Text()),
    )
    op.bulk_insert(
        settings_table,
        [{"key": key, "value": value} for key, value in DEFAULT_SETTINGS],
    )


def downgrade() -> None:
    """Удалить таблицу настроек вместе с её начальными значениями."""

    op.drop_table("settings")
