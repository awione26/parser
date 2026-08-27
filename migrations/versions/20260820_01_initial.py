"""Initial professionals and categories schema.

Revision ID: 20260820_01
Revises:
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
pk_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", pk_type, autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_table(
        "professionals",
        sa.Column("id", pk_type, autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_profile_id", sa.String(length=128), nullable=False),
        sa.Column("profile_url", sa.String(length=1024), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("phone_ciphertext", sa.Text(), nullable=True),
        sa.Column("phone_hmac", sa.String(length=64), nullable=True),
        sa.Column("phone_status", sa.String(length=32), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("region", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("age", sa.SmallInteger(), nullable=True),
        sa.Column("age_as_of", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(length=16), nullable=True),
        sa.Column("experience_code", sa.SmallInteger(), nullable=True),
        sa.Column("experience_text", sa.String(length=64), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("account_type", sa.String(length=32), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_scraped_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_profile_id", name="uq_professional_source_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_professionals_phone_hmac", "professionals", ["phone_hmac"])
    op.create_table(
        "professional_categories",
        sa.Column("professional_id", pk_type, nullable=False),
        sa.Column("category_id", pk_type, nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("professional_id", "category_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_table(
        "professional_category_rubrics",
        sa.Column("professional_id", pk_type, nullable=False),
        sa.Column("category_id", pk_type, nullable=False),
        sa.Column("source_rubric_number_id", sa.Integer(), nullable=False),
        sa.Column("source_rubric_id", sa.String(length=255), nullable=True),
        sa.Column("source_rubric_seo_id", sa.String(length=255), nullable=True),
        sa.Column("source_rubric_name", sa.String(length=255), nullable=True),
        sa.Column("experience_code", sa.SmallInteger(), nullable=True),
        sa.Column("experience_text", sa.String(length=64), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["professional_id", "category_id"],
            [
                "professional_categories.professional_id",
                "professional_categories.category_id",
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("professional_id", "category_id", "source_rubric_number_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    op.drop_table("professional_category_rubrics")
    op.drop_table("professional_categories")
    op.drop_table("professionals")
    op.drop_table("categories")
