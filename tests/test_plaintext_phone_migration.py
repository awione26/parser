from __future__ import annotations

from datetime import date, datetime
from io import StringIO
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
BASE_REVISION = "20260820_01"
LEGACY_REVISION = "20260826_02"
HEAD_REVISION = "20260827_04"


def alembic_config(*, output_buffer: StringIO | None = None) -> Config:
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output_buffer)
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return config


def sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path}"


def insert_legacy_profile(database_url: str, ciphertext: str) -> None:
    engine = sa.create_engine(database_url)
    now = datetime(2026, 8, 27, 12, 0, 0)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO professionals (
                        source, source_profile_id, profile_url, full_name,
                        phone_ciphertext, phone_hmac, phone_status,
                        age_as_of, content_hash, parser_version,
                        first_seen_at, last_seen_at, last_scraped_at
                    ) VALUES (
                        :source, :source_profile_id, :profile_url, :full_name,
                        :phone_ciphertext, :phone_hmac, :phone_status,
                        :age_as_of, :content_hash, :parser_version,
                        :first_seen_at, :last_seen_at, :last_scraped_at
                    )
                    """
                ),
                {
                    "source": "uslugi.yandex.ru",
                    "source_profile_id": "legacy-profile",
                    "profile_url": "https://uslugi.yandex.ru/profile/Legacy-1",
                    "full_name": "Legacy Test",
                    "phone_ciphertext": ciphertext,
                    "phone_hmac": "0" * 64,
                    "phone_status": "revealed_ui",
                    "age_as_of": date(2026, 8, 27),
                    "content_hash": "1" * 64,
                    "parser_version": "0.1.0",
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "last_scraped_at": now,
                },
            )
    finally:
        engine.dispose()


def schema_state(database_url: str) -> tuple[set[str], set[str], str]:
    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        columns = {str(column["name"]) for column in inspector.get_columns("professionals")}
        indexes = {
            str(index["name"])
            for index in inspector.get_indexes("professionals")
            if index.get("name")
        }
        with engine.connect() as connection:
            version = str(connection.scalar(sa.text("SELECT version_num FROM alembic_version")))
        return columns, indexes, version
    finally:
        engine.dispose()


def log_schema_state(database_url: str) -> tuple[set[str], set[str]]:
    """Вернуть колонки и индексы созданной Alembic таблицы logs."""

    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        columns = {str(column["name"]) for column in inspector.get_columns("logs")}
        indexes = {
            str(index["name"]) for index in inspector.get_indexes("logs") if index.get("name")
        }
        return columns, indexes
    finally:
        engine.dispose()


def professional_category_indexes(database_url: str) -> set[str]:
    """Вернуть имена индексов таблицы связей мастеров и категорий."""

    engine = sa.create_engine(database_url)
    try:
        return {
            str(index["name"])
            for index in sa.inspect(engine).get_indexes("professional_categories")
            if index.get("name")
        }
    finally:
        engine.dispose()


def test_admin_index_revision_downgrades_to_base_on_sqlite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = sqlite_url(tmp_path / "index-downgrade.sqlite")
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), LEGACY_REVISION)

    assert "ix_professional_categories_category_professional" in professional_category_indexes(
        database_url
    )

    command.downgrade(alembic_config(), BASE_REVISION)

    assert "ix_professional_categories_category_professional" not in professional_category_indexes(
        database_url
    )
    assert schema_state(database_url)[2] == BASE_REVISION


def test_admin_index_offline_mysql_downgrade_restores_fk_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = StringIO()
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://uslugi:test@127.0.0.1:3306/uslugi?charset=utf8mb4",
    )

    command.downgrade(
        alembic_config(output_buffer=output),
        f"{LEGACY_REVISION}:{BASE_REVISION}",
        sql=True,
    )

    sql = output.getvalue()
    create_position = sql.index("CREATE INDEX category_id ON professional_categories (category_id)")
    drop_position = sql.index(
        "DROP INDEX ix_professional_categories_category_professional ON professional_categories"
    )
    assert create_position < drop_position


def test_fresh_upgrade_creates_plaintext_schema_without_legacy_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = sqlite_url(tmp_path / "fresh.sqlite")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("LEGACY_PHONE_ENCRYPTION_KEY", raising=False)

    command.upgrade(alembic_config(), "head")

    columns, indexes, version = schema_state(database_url)
    assert "phone" in columns
    assert "phone_ciphertext" not in columns
    assert "phone_hmac" not in columns
    assert "ix_professionals_phone" in indexes
    assert version == HEAD_REVISION
    log_columns, log_indexes = log_schema_state(database_url)
    assert log_columns == {
        "id",
        "started_at",
        "finished_at",
        "result",
        "error_reason",
        "resource",
    }
    assert log_indexes == {
        "ix_logs_started_at",
        "ix_logs_result_started_at",
        "ix_logs_resource_started_at",
    }


def test_upgrade_decrypts_legacy_phone_then_drops_legacy_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = sqlite_url(tmp_path / "legacy.sqlite")
    key = Fernet.generate_key()
    phone = "+79991234567"
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), LEGACY_REVISION)
    insert_legacy_profile(
        database_url,
        Fernet(key).encrypt(phone.encode("utf-8")).decode("ascii"),
    )
    monkeypatch.setenv("LEGACY_PHONE_ENCRYPTION_KEY", key.decode("ascii"))

    command.upgrade(alembic_config(), "head")

    columns, indexes, version = schema_state(database_url)
    assert "phone" in columns
    assert "phone_ciphertext" not in columns
    assert "phone_hmac" not in columns
    assert "ix_professionals_phone" in indexes
    assert version == HEAD_REVISION
    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT phone FROM professionals")) == phone
    finally:
        engine.dispose()

    command.downgrade(alembic_config(), LEGACY_REVISION)
    columns, indexes, version = schema_state(database_url)
    assert "phone" not in columns
    assert "phone_ciphertext" in columns
    assert "phone_hmac" in columns
    assert "ix_professionals_phone_hmac" in indexes
    assert version == LEGACY_REVISION
    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            ciphertext = connection.scalar(sa.text("SELECT phone_ciphertext FROM professionals"))
        assert Fernet(key).decrypt(str(ciphertext).encode("ascii")).decode("utf-8") == phone
    finally:
        engine.dispose()


def test_upgrade_fails_before_ddl_when_legacy_key_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = sqlite_url(tmp_path / "missing-key.sqlite")
    key = Fernet.generate_key()
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), LEGACY_REVISION)
    insert_legacy_profile(
        database_url,
        Fernet(key).encrypt(b"+79991234567").decode("ascii"),
    )
    monkeypatch.delenv("LEGACY_PHONE_ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="LEGACY_PHONE_ENCRYPTION_KEY is required"):
        command.upgrade(alembic_config(), "head")

    columns, indexes, version = schema_state(database_url)
    assert "phone" not in columns
    assert "phone_ciphertext" in columns
    assert "phone_hmac" in columns
    assert "ix_professionals_phone_hmac" in indexes
    assert version == LEGACY_REVISION


def test_upgrade_fails_before_ddl_for_invalid_ciphertext(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = sqlite_url(tmp_path / "invalid-token.sqlite")
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), LEGACY_REVISION)
    insert_legacy_profile(database_url, "not-a-valid-fernet-token")
    monkeypatch.setenv(
        "LEGACY_PHONE_ENCRYPTION_KEY",
        Fernet.generate_key().decode("ascii"),
    )

    with pytest.raises(RuntimeError, match="cannot decrypt legacy phone"):
        command.upgrade(alembic_config(), "head")

    columns, _, version = schema_state(database_url)
    assert "phone" not in columns
    assert "phone_ciphertext" in columns
    assert version == LEGACY_REVISION


def test_full_offline_sql_contains_plaintext_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    output = StringIO()
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://uslugi:test@127.0.0.1:3306/uslugi?charset=utf8mb4",
    )

    command.upgrade(alembic_config(output_buffer=output), "head", sql=True)

    sql = output.getvalue()
    assert "ADD COLUMN phone VARCHAR(32)" in sql
    assert "CREATE INDEX ix_professionals_phone ON professionals (phone)" in sql
    assert "DROP COLUMN phone_ciphertext" in sql
    assert "DROP COLUMN phone_hmac" in sql
    assert "CREATE TABLE logs" in sql
    assert "resource VARCHAR(255) NOT NULL" in sql
    assert "CREATE INDEX ix_logs_result_started_at ON logs (result, started_at)" in sql
    assert "CREATE INDEX ix_logs_resource_started_at ON logs (resource, started_at)" in sql


def test_incremental_offline_sql_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://uslugi:test@127.0.0.1:3306/uslugi?charset=utf8mb4",
    )

    with pytest.raises(RuntimeError, match="cannot migrate existing encrypted phones"):
        command.upgrade(
            alembic_config(output_buffer=StringIO()),
            f"{LEGACY_REVISION}:head",
            sql=True,
        )


def test_alembic_check_ignores_tables_owned_by_laravel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Не считать таблицы админки изменениями схемы Python-парсера."""

    database_url = sqlite_url(tmp_path / "shared-schema.sqlite")
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), "head")

    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, login VARCHAR(255) NOT NULL)")
            )
    finally:
        engine.dispose()

    command.check(alembic_config())
