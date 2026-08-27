"""Replace legacy encrypted phone fields with normalized plaintext phone.

Revision ID: 20260827_03
Revises: 20260826_02
Create Date: 2026-08-27

Existing ciphertext is decrypted in memory and validated before the first DDL
statement. This ordering is intentional: MySQL implicitly commits DDL, so an
invalid or missing legacy key must stop the migration before the schema changes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.engine import Connection

revision: str = "20260827_03"
down_revision: str | None = "20260826_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_KEY_ENV = "LEGACY_PHONE_ENCRYPTION_KEY"
PHONE_PATTERN = re.compile(r"\+[1-9]\d{7,14}\Z")
PHONE_INDEX = "ix_professionals_phone"
LEGACY_HMAC_INDEX = "ix_professionals_phone_hmac"


def _column_names(connection: Connection) -> set[str]:
    return {str(column["name"]) for column in sa.inspect(connection).get_columns("professionals")}


def _index_names(connection: Connection) -> set[str]:
    return {
        str(index["name"])
        for index in sa.inspect(connection).get_indexes("professionals")
        if index.get("name")
    }


def _legacy_fernet(*, required: bool) -> tuple[Fernet | None, bytes | None]:
    configured = os.getenv(LEGACY_KEY_ENV, "").strip()
    if not configured:
        if required:
            raise RuntimeError(f"{LEGACY_KEY_ENV} is required because encrypted phones still exist")
        return None, None

    try:
        encoded = configured.encode("ascii")
        raw_key = base64.urlsafe_b64decode(encoded)
        if len(raw_key) != 32:
            raise ValueError("wrong decoded key length")
        return Fernet(encoded), raw_key
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError(f"{LEGACY_KEY_ENV} is not a valid Fernet key") from exc


def _preflight_upgrade(connection: Connection) -> list[dict[str, object]]:
    rows = (
        connection.execute(
            sa.text(
                "SELECT id, phone_ciphertext FROM professionals "
                "WHERE phone_ciphertext IS NOT NULL ORDER BY id"
            )
        )
        .mappings()
        .all()
    )
    fernet, _ = _legacy_fernet(required=bool(rows))
    if fernet is None:
        return []

    decrypted: list[dict[str, object]] = []
    for row in rows:
        row_id = int(row["id"])
        token = row["phone_ciphertext"]
        try:
            encoded = token.encode("ascii") if isinstance(token, str) else bytes(token)
            phone = fernet.decrypt(encoded).decode("utf-8")
        except (InvalidToken, UnicodeError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"cannot decrypt legacy phone for professionals.id={row_id}"
            ) from exc
        if PHONE_PATTERN.fullmatch(phone) is None:
            raise RuntimeError(f"decrypted phone for professionals.id={row_id} is not normalized")
        decrypted.append({"id": row_id, "phone": phone})
    return decrypted


def _verify_plaintext(connection: Connection, expected_rows: list[dict[str, object]]) -> None:
    if not expected_rows:
        return
    stored = {
        int(row.id): row.phone
        for row in connection.execute(
            sa.text("SELECT id, phone FROM professionals WHERE phone IS NOT NULL")
        )
    }
    for expected in expected_rows:
        row_id = int(expected["id"])
        if stored.get(row_id) != expected["phone"]:
            raise RuntimeError(f"plaintext phone verification failed for professionals.id={row_id}")


def _upgrade_online() -> None:
    connection = op.get_bind()
    columns = _column_names(connection)
    indexes = _index_names(connection)

    has_ciphertext = "phone_ciphertext" in columns
    has_phone = "phone" in columns
    if not has_ciphertext and not has_phone:
        raise RuntimeError("professionals has neither phone nor legacy phone_ciphertext")

    # This is the fail-closed preflight. Do not put DDL above it.
    decrypted = _preflight_upgrade(connection) if has_ciphertext else []

    if not has_phone:
        op.add_column(
            "professionals",
            sa.Column("phone", sa.String(length=32), nullable=True),
        )

    if decrypted:
        connection.execute(
            sa.text("UPDATE professionals SET phone = :phone WHERE id = :id"),
            decrypted,
        )
        _verify_plaintext(connection, decrypted)

    if PHONE_INDEX not in indexes:
        op.create_index(PHONE_INDEX, "professionals", ["phone"])

    # DML has been verified before these destructive DDL operations. Each
    # existence check also makes a retry safe after a partial MySQL DDL commit.
    indexes = _index_names(connection)
    if LEGACY_HMAC_INDEX in indexes:
        op.drop_index(LEGACY_HMAC_INDEX, table_name="professionals")

    columns = _column_names(connection)
    if "phone_hmac" in columns:
        op.drop_column("professionals", "phone_hmac")
    columns = _column_names(connection)
    if "phone_ciphertext" in columns:
        op.drop_column("professionals", "phone_ciphertext")


def _upgrade_offline() -> None:
    starting_revision = context.get_starting_revision_argument()
    if starting_revision not in (None, "base"):
        raise RuntimeError(
            "revision 20260827_03 cannot migrate existing encrypted phones in --sql mode; "
            "run an online 'alembic upgrade head' with LEGACY_PHONE_ENCRYPTION_KEY"
        )

    # A complete base-to-head SQL script targets a new empty database, so there
    # are no ciphertext rows to decrypt. Incremental offline upgrades are refused.
    op.add_column(
        "professionals",
        sa.Column("phone", sa.String(length=32), nullable=True),
    )
    op.create_index(PHONE_INDEX, "professionals", ["phone"])
    op.drop_index(LEGACY_HMAC_INDEX, table_name="professionals")
    op.drop_column("professionals", "phone_hmac")
    op.drop_column("professionals", "phone_ciphertext")


def upgrade() -> None:
    if context.is_offline_mode():
        _upgrade_offline()
        return
    _upgrade_online()


def _preflight_downgrade(
    connection: Connection,
) -> tuple[list[dict[str, object]], Fernet | None]:
    rows = (
        connection.execute(
            sa.text("SELECT id, phone FROM professionals WHERE phone IS NOT NULL ORDER BY id")
        )
        .mappings()
        .all()
    )
    fernet, raw_key = _legacy_fernet(required=bool(rows))
    if fernet is None or raw_key is None:
        return [], None

    hmac_key = hmac.new(
        raw_key,
        b"uslugi-parser/phone-hmac/v1",
        hashlib.sha256,
    ).digest()
    encrypted: list[dict[str, object]] = []
    for row in rows:
        row_id = int(row["id"])
        phone = str(row["phone"])
        if PHONE_PATTERN.fullmatch(phone) is None:
            raise RuntimeError(f"phone for professionals.id={row_id} is not normalized")
        encrypted.append(
            {
                "id": row_id,
                "ciphertext": fernet.encrypt(phone.encode("utf-8")).decode("ascii"),
                "phone_hmac": hmac.new(
                    hmac_key,
                    phone.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest(),
                "phone": phone,
            }
        )
    return encrypted, fernet


def _verify_ciphertext(
    connection: Connection,
    expected_rows: list[dict[str, object]],
    fernet: Fernet | None,
) -> None:
    if not expected_rows:
        return
    if fernet is None:
        raise RuntimeError("legacy Fernet verifier is unavailable")
    stored = {
        int(row.id): row.phone_ciphertext
        for row in connection.execute(
            sa.text(
                "SELECT id, phone_ciphertext FROM professionals WHERE phone_ciphertext IS NOT NULL"
            )
        )
    }
    for expected in expected_rows:
        row_id = int(expected["id"])
        token = stored.get(row_id)
        try:
            encoded = token.encode("ascii") if isinstance(token, str) else bytes(token)
            actual = fernet.decrypt(encoded).decode("utf-8")
        except (InvalidToken, UnicodeError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"legacy ciphertext verification failed for professionals.id={row_id}"
            ) from exc
        if actual != expected["phone"]:
            raise RuntimeError(
                f"legacy ciphertext verification failed for professionals.id={row_id}"
            )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "revision 20260827_03 downgrade requires online mode to encrypt phone data"
        )

    connection = op.get_bind()
    columns = _column_names(connection)
    indexes = _index_names(connection)
    if "phone" not in columns:
        if {"phone_ciphertext", "phone_hmac"}.issubset(columns):
            if LEGACY_HMAC_INDEX not in indexes:
                op.create_index(
                    LEGACY_HMAC_INDEX,
                    "professionals",
                    ["phone_hmac"],
                )
            return
        raise RuntimeError("professionals plaintext phone column is missing")

    # As in upgrade(), complete all fallible crypto work before the first DDL.
    encrypted, fernet = _preflight_downgrade(connection)

    if "phone_ciphertext" not in columns:
        op.add_column(
            "professionals",
            sa.Column("phone_ciphertext", sa.Text(), nullable=True),
        )
    if "phone_hmac" not in columns:
        op.add_column(
            "professionals",
            sa.Column("phone_hmac", sa.String(length=64), nullable=True),
        )

    if encrypted:
        connection.execute(
            sa.text(
                "UPDATE professionals SET phone_ciphertext = :ciphertext, "
                "phone_hmac = :phone_hmac WHERE id = :id"
            ),
            encrypted,
        )
        _verify_ciphertext(connection, encrypted, fernet)

    indexes = _index_names(connection)
    if LEGACY_HMAC_INDEX not in indexes:
        op.create_index(LEGACY_HMAC_INDEX, "professionals", ["phone_hmac"])
    if PHONE_INDEX in indexes:
        op.drop_index(PHONE_INDEX, table_name="professionals")
    op.drop_column("professionals", "phone")
