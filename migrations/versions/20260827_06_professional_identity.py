"""Добавить второй уникальный ключ карточки мастера по каноническому URL.

Revision ID: 20260827_06
Revises: 20260827_05
Create Date: 2026-08-27
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260827_06"
down_revision: str | None = "20260827_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASE_URL = "https://uslugi.yandex.ru"
_PRIMARY_KEY_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
_SOURCE_PROFILE_ID_TYPE = sa.String(128).with_variant(
    sa.String(128, collation="NOCASE"),
    "sqlite",
)


def _canonical_profile_url(value: str) -> str:
    """Повторить канонизацию runtime без импорта кода приложения в миграцию."""

    parsed = urlsplit(urljoin(_BASE_URL, value))
    match = re.search(r"/profile/([^/?#]+)", parsed.path)
    if match is None:
        raise RuntimeError(f"cannot canonicalize existing professional URL: {value!r}")
    return urlunsplit(("https", "uslugi.yandex.ru", f"/profile/{match.group(1)}", "", ""))


def _existing_identities(
    connection: sa.Connection,
) -> list[tuple[int, str, str, str, str]]:
    """Прочитать, проверить и подготовить идентичности существующих строк."""

    rows = connection.execute(
        sa.text("SELECT id, source, source_profile_id, profile_url FROM professionals ORDER BY id")
    ).mappings()
    identities: list[tuple[int, str, str, str, str]] = []
    seen_urls: dict[tuple[str, str], int] = {}
    seen_ids: dict[tuple[str, str], int] = {}
    for row in rows:
        source = str(row["source"]).strip().lower()
        source_profile_id = str(row["source_profile_id"]).strip()
        if not source or not source_profile_id:
            raise RuntimeError(
                f"professional {row['id']} has an empty source identity; fix it before migration"
            )
        source_key = (source, source_profile_id)
        previous_source_id = seen_ids.get(source_key)
        if previous_source_id is not None:
            raise RuntimeError(
                "duplicate normalized professional source id found for rows "
                f"{previous_source_id} and {row['id']}; merge them before migration"
            )
        seen_ids[source_key] = int(row["id"])
        canonical_url = _canonical_profile_url(str(row["profile_url"]))
        url_hash = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
        key = (source, url_hash)
        previous_id = seen_urls.get(key)
        if previous_id is not None:
            raise RuntimeError(
                "duplicate canonical professional URL found for rows "
                f"{previous_id} and {row['id']}; merge them before migration"
            )
        seen_urls[key] = int(row["id"])
        identities.append((int(row["id"]), canonical_url, url_hash, source, source_profile_id))
    return identities


def upgrade() -> None:
    """Заполнить URL-хеши и запретить две строки одной карточки источника."""

    if context.is_offline_mode():
        starting_revision = context.get_starting_revision_argument()
        if starting_revision not in (None, "base"):
            raise RuntimeError(
                "revision 20260827_06 cannot canonicalize and validate existing "
                "professional identities in --sql mode; run an online "
                "'alembic upgrade head'"
            )

    migration_context = op.get_context()
    identities: list[tuple[int, str, str, str, str]] = []
    if not migration_context.as_sql:
        # Preflight идёт до DDL: при старых дублях схема останется неизменной.
        identities = _existing_identities(op.get_bind())

    with op.batch_alter_table("professionals") as batch_op:
        batch_op.add_column(sa.Column("profile_url_hash", sa.String(length=64), nullable=True))

    if migration_context.as_sql:
        # Полный base-to-head SQL предназначен для новой пустой базы.
        op.execute("UPDATE professionals SET profile_url_hash = LOWER(SHA2(profile_url, 256))")
    else:
        connection = op.get_bind()
        for row_id, canonical_url, url_hash, source, source_profile_id in identities:
            connection.execute(
                sa.text(
                    "UPDATE professionals SET source = :source, "
                    "source_profile_id = :source_profile_id, profile_url = :profile_url, "
                    "profile_url_hash = :profile_url_hash WHERE id = :id"
                ),
                {
                    "id": row_id,
                    "source": source,
                    "source_profile_id": source_profile_id,
                    "profile_url": canonical_url,
                    "profile_url_hash": url_hash,
                },
            )

    with op.batch_alter_table("professionals") as batch_op:
        batch_op.alter_column(
            "source_profile_id",
            existing_type=sa.String(length=128),
            type_=_SOURCE_PROFILE_ID_TYPE,
            existing_nullable=False,
        )
        batch_op.alter_column(
            "profile_url_hash",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_professional_source_url_hash",
            ["source", "profile_url_hash"],
        )
        batch_op.create_check_constraint(
            "ck_professionals_source_profile_id_not_blank",
            "LENGTH(TRIM(source_profile_id)) > 0",
        )

    op.create_table(
        "professional_identities",
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_profile_id", _SOURCE_PROFILE_ID_TYPE, nullable=False),
        sa.Column("professional_id", _PRIMARY_KEY_TYPE, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["professionals.id"],
            name="fk_professional_identities_professional_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source", "source_profile_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "ix_professional_identities_professional_id",
        "professional_identities",
        ["professional_id"],
        unique=False,
    )
    if not migration_context.as_sql and identities:
        identity_table = sa.table(
            "professional_identities",
            sa.column("source", sa.String(length=64)),
            sa.column("source_profile_id", sa.String(length=128)),
            sa.column("professional_id", _PRIMARY_KEY_TYPE),
        )
        op.bulk_insert(
            identity_table,
            [
                {
                    "source": source,
                    "source_profile_id": source_profile_id,
                    "professional_id": row_id,
                }
                for row_id, _url, _hash, source, source_profile_id in identities
            ],
        )


def downgrade() -> None:
    """Удалить дополнительный ключ URL, сохранив основной source_profile_id."""

    op.drop_table("professional_identities")
    with op.batch_alter_table("professionals") as batch_op:
        batch_op.drop_constraint(
            "ck_professionals_source_profile_id_not_blank",
            type_="check",
        )
        batch_op.drop_constraint("uq_professional_source_url_hash", type_="unique")
        batch_op.drop_column("profile_url_hash")
        batch_op.alter_column(
            "source_profile_id",
            existing_type=_SOURCE_PROFILE_ID_TYPE,
            type_=sa.String(length=128),
            existing_nullable=False,
        )
