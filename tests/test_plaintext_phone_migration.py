from __future__ import annotations

import json
from datetime import date, datetime
from io import StringIO
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet

from uslugi_parser.catalog import DEFAULT_CATEGORIES
from uslugi_parser.config.settings import SCRAPER_SETTING_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
BASE_REVISION = "20260820_01"
LEGACY_REVISION = "20260826_02"
SETTINGS_REVISION = "20260827_05"
HEAD_REVISION = "20260902_10"
TAXONOMY_SNAPSHOT = json.loads(
    (ROOT / "migrations/data/20260901_yandex_taxonomy.json").read_text(encoding="utf-8")
)


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


def professional_unique_constraints(database_url: str) -> set[tuple[str, ...]]:
    """Вернуть уникальные наборы колонок, защищающие идентичность мастеров."""

    engine = sa.create_engine(database_url)
    try:
        return {
            tuple(str(column) for column in constraint.get("column_names") or [])
            for constraint in sa.inspect(engine).get_unique_constraints("professionals")
        }
    finally:
        engine.dispose()


def professional_identity_state(database_url: str) -> tuple[set[str], int]:
    """Вернуть схему и число сохранённых алиасов исходных ID мастеров."""

    engine = sa.create_engine(database_url)
    try:
        columns = {
            str(column["name"])
            for column in sa.inspect(engine).get_columns("professional_identities")
        }
        with engine.connect() as connection:
            count = int(
                connection.scalar(sa.text("SELECT COUNT(*) FROM professional_identities")) or 0
            )
        return columns, count
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


def settings_schema_state(database_url: str) -> tuple[set[str], dict[str, str]]:
    """Вернуть колонки и начальные пары ключ-значение таблицы settings."""

    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        columns = {str(column["name"]) for column in inspector.get_columns("settings")}
        with engine.connect() as connection:
            rows = connection.execute(sa.text("SELECT `key`, value FROM settings")).all()
        return columns, {str(key): str(value) for key, value in rows}
    finally:
        engine.dispose()


def parser_category_schema_state(
    database_url: str,
) -> tuple[set[str], set[str], list[tuple[str, str, list[str], bool, int]]]:
    """Вернуть схему и упорядоченный снимок категорий парсинга."""

    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        columns = {str(column["name"]) for column in inspector.get_columns("parser_categories")}
        indexes = {
            str(index["name"])
            for index in inspector.get_indexes("parser_categories")
            if index.get("name")
        }
        with engine.connect() as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT c.`key`, c.name, pc.seed_paths, pc.is_active, pc.sort_order "
                    "FROM parser_categories pc "
                    "JOIN categories c ON c.id = pc.category_id "
                    "ORDER BY pc.sort_order, pc.category_id"
                )
            ).all()
        return (
            columns,
            indexes,
            [
                (
                    str(key),
                    str(name),
                    list(json.loads(str(seed_paths))),
                    bool(is_active),
                    int(sort_order),
                )
                for key, name, seed_paths, is_active, sort_order in rows
            ],
        )
    finally:
        engine.dispose()


def taxonomy_schema_state(database_url: str) -> tuple[dict[str, int], int, int]:
    """Вернуть количества справочников, связей и активных целей обхода."""

    engine = sa.create_engine(database_url)
    table_names = (
        "yandex_occupations",
        "yandex_specializations",
        "yandex_services",
        "category_yandex_occupations",
        "category_yandex_specializations",
        "category_yandex_services",
        "parser_category_targets",
    )
    try:
        with engine.connect() as connection:
            counts = {
                table_name: int(
                    connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table_name}")) or 0
                )
                for table_name in table_names
            }
            invalid_urls = int(
                connection.scalar(
                    sa.text(
                        "SELECT COUNT(*) FROM ("
                        "SELECT source_url FROM yandex_occupations UNION ALL "
                        "SELECT source_url FROM yandex_specializations UNION ALL "
                        "SELECT source_url FROM yandex_services"
                        ") AS taxonomy_urls WHERE source_url IS NOT NULL "
                        "AND source_url NOT LIKE 'https://uslugi.yandex.ru/%'"
                    )
                )
                or 0
            )
            unresolved_with_id = int(
                connection.scalar(
                    sa.text(
                        "SELECT COUNT(*) FROM yandex_services "
                        "WHERE verification_status = 'unverified' "
                        "AND (external_id_raw IS NOT NULL OR external_number_id IS NOT NULL "
                        "OR slug IS NOT NULL OR source_url IS NOT NULL)"
                    )
                )
                or 0
            )
        return counts, invalid_urls, unresolved_with_id
    finally:
        engine.dispose()


def category_metadata_state(database_url: str) -> dict[str, tuple[str, str | None]]:
    """Вернуть отображаемые названия и примечания встроенных категорий."""

    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                sa.text("SELECT `key`, name, note FROM categories ORDER BY `key`")
            ).all()
        return {
            str(key): (str(name), None if note is None else str(note)) for key, name, note in rows
        }
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


def professional_rubric_indexes(database_url: str) -> set[str]:
    """Вернуть индексы доказательств рубрик для связи с Каталогом Яндекса."""

    engine = sa.create_engine(database_url)
    try:
        return {
            str(index["name"])
            for index in sa.inspect(engine).get_indexes("professional_category_rubrics")
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
    assert "profile_url_hash" in columns
    assert professional_unique_constraints(database_url) >= {
        ("source", "source_profile_id"),
        ("source", "profile_url_hash"),
    }
    assert professional_identity_state(database_url) == (
        {"source", "source_profile_id", "professional_id", "created_at"},
        0,
    )
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
    setting_columns, setting_rows = settings_schema_state(database_url)
    assert setting_columns == {"key", "value", "created_at", "updated_at"}
    assert setting_rows == SCRAPER_SETTING_DEFAULTS
    parser_columns, parser_indexes, parser_rows = parser_category_schema_state(database_url)
    assert parser_columns == {
        "category_id",
        "seed_paths",
        "is_active",
        "sort_order",
        "created_at",
        "updated_at",
    }
    assert parser_indexes == {"ix_parser_categories_active_order"}
    assert parser_rows == [
        (
            definition.key,
            definition.name,
            list(definition.seed_paths),
            True,
            position * 10,
        )
        for position, definition in enumerate(DEFAULT_CATEGORIES.values(), start=1)
    ]
    taxonomy_counts, invalid_urls, unresolved_with_id = taxonomy_schema_state(database_url)
    assert taxonomy_counts == {
        "yandex_occupations": len(TAXONOMY_SNAPSHOT["yandex_occupations"]),
        "yandex_specializations": len(TAXONOMY_SNAPSHOT["yandex_specializations"]),
        "yandex_services": len(TAXONOMY_SNAPSHOT["yandex_services"]),
        "category_yandex_occupations": sum(
            len(group["occupation_ids"]) for group in TAXONOMY_SNAPSHOT["groups"]
        ),
        "category_yandex_specializations": sum(
            len(group["specialization_ids"]) for group in TAXONOMY_SNAPSHOT["groups"]
        ),
        "category_yandex_services": 171,
        "parser_category_targets": 34,
    }
    assert invalid_urls == 0
    assert unresolved_with_id == 0
    assert category_metadata_state(database_url) == {
        definition.key: (definition.name, definition.note or None)
        for definition in DEFAULT_CATEGORIES.values()
    }
    assert "ix_professional_category_rubrics_catalog" in professional_rubric_indexes(database_url)


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
    assert professional_identity_state(database_url)[1] == 1
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


def test_category_upgrade_preserves_existing_master_id_and_professional_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Синхронизировать master-строку без удаления её ID и исторической связи."""

    database_url = sqlite_url(tmp_path / "category-preservation.sqlite")
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), "20260827_06")
    engine = sa.create_engine(database_url)
    now = datetime(2026, 8, 31, 12, 0, 0)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO categories "
                    "(id, `key`, name, note, created_at, updated_at) VALUES "
                    "(777, 'designers', 'Старое название', 'old', :now, :now)"
                ),
                {"now": now},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO professionals ("
                    "id, source, source_profile_id, profile_url, profile_url_hash, "
                    "phone_status, age_as_of, content_hash, parser_version, "
                    "first_seen_at, last_seen_at, last_scraped_at) VALUES ("
                    "888, 'uslugi.yandex.ru', 'category-preservation', "
                    "'https://uslugi.yandex.ru/profile/Category-1', :url_hash, "
                    "'not_requested', '2026-08-31', :content_hash, '0.1.0', "
                    ":now, :now, :now)"
                ),
                {"url_hash": "a" * 64, "content_hash": "b" * 64, "now": now},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO professional_categories "
                    "(professional_id, category_id, first_seen_at, last_seen_at) "
                    "VALUES (888, 777, :now, :now)"
                ),
                {"now": now},
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_config(), "head")

    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            category = connection.execute(
                sa.text("SELECT id, name FROM categories WHERE `key` = 'designers'")
            ).one()
            config_category_id = connection.scalar(
                sa.text(
                    "SELECT pc.category_id FROM parser_categories pc "
                    "JOIN categories c ON c.id = pc.category_id "
                    "WHERE c.`key` = 'designers'"
                )
            )
            link_count = connection.scalar(
                sa.text(
                    "SELECT COUNT(*) FROM professional_categories "
                    "WHERE professional_id = 888 AND category_id = 777"
                )
            )
            assert connection.scalar(sa.text("SELECT COUNT(*) FROM categories")) == 11
            assert connection.scalar(sa.text("SELECT COUNT(*) FROM parser_categories")) == 11
        assert category == (777, "Дизайнеры")
        assert config_category_id == 777
        assert link_count == 1
    finally:
        engine.dispose()

    command.downgrade(alembic_config(), "20260827_06")
    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        assert "parser_categories" not in inspector.get_table_names()
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT COUNT(*) FROM professional_categories "
                        "WHERE professional_id = 888 AND category_id = 777"
                    )
                )
                == 1
            )
    finally:
        engine.dispose()


def test_taxonomy_upgrade_skips_builtin_category_without_parser_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Не нарушать FK, если администратор ранее удалил встроенную конфигурацию."""

    database_url = sqlite_url(tmp_path / "taxonomy-missing-config.sqlite")
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), "20260831_07")
    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "DELETE FROM parser_categories WHERE category_id = "
                    "(SELECT id FROM categories WHERE `key` = 'designers')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_config(), "head")

    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT COUNT(*) FROM parser_categories")) == 10
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT COUNT(*) FROM parser_category_targets target "
                        "JOIN categories category ON category.id = target.category_id "
                        "WHERE category.`key` = 'designers'"
                    )
                )
                == 0
            )
            assert connection.scalar(sa.text("SELECT COUNT(*) FROM parser_category_targets")) == 33
    finally:
        engine.dispose()


def test_taxonomy_upgrade_backfills_custom_parser_category(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Сохранить пользовательские категории при переходе с JSON на targets."""

    database_url = sqlite_url(tmp_path / "taxonomy-custom-config.sqlite")
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), "20260831_07")
    engine = sa.create_engine(database_url)
    now = datetime(2026, 9, 1, 10, 0, 0)
    custom_path = "remont-i-stroitelstvo/polzovatelskaya-rubrika--999999"
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO categories "
                    "(id, `key`, name, note, created_at, updated_at) VALUES "
                    "(999, 'custom_category', 'Пользовательская категория', NULL, :now, :now)"
                ),
                {"now": now},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO parser_categories "
                    "(category_id, seed_paths, is_active, sort_order, created_at, updated_at) "
                    "VALUES (999, :seed_paths, 1, 999, :now, :now)"
                ),
                {"seed_paths": json.dumps([custom_path]), "now": now},
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_config(), "20260901_09")

    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            target = connection.execute(
                sa.text(
                    "SELECT taxonomy_level, source_rubric_number_id, relative_path "
                    "FROM parser_category_targets WHERE category_id = 999"
                )
            ).one()
        assert target == ("unknown", 999999, custom_path)
    finally:
        engine.dispose()


def test_catalog_authority_backfills_evidence_and_disables_legacy_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Сохранить мастера и телефон, но не обходить цель вне Каталога Яндекса."""

    database_url = sqlite_url(tmp_path / "catalog-authority.sqlite")
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), "20260901_09")
    engine = sa.create_engine(database_url)
    now = datetime(2026, 9, 2, 10, 0, 0)
    try:
        with engine.begin() as connection:
            category_id = int(
                connection.scalar(sa.text("SELECT id FROM categories WHERE `key` = 'designers'"))
            )
            estimators_category_id = int(
                connection.scalar(sa.text("SELECT id FROM categories WHERE `key` = 'estimators'"))
            )
            connection.execute(
                sa.text(
                    "INSERT INTO professionals ("
                    "id, source, source_profile_id, profile_url, profile_url_hash, full_name, "
                    "phone, phone_status, age_as_of, content_hash, parser_version, "
                    "first_seen_at, last_seen_at, last_scraped_at) VALUES ("
                    "901, 'uslugi.yandex.ru', 'catalog-migration', "
                    "'https://uslugi.yandex.ru/profile/Catalog-901', :url_hash, 'Test', "
                    "'+79991234567', 'public_profile', '2026-09-02', :content_hash, '0.1.0', "
                    ":now, :now, :now)"
                ),
                {"url_hash": "c" * 64, "content_hash": "d" * 64, "now": now},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO professional_categories "
                    "(professional_id, category_id, first_seen_at, last_seen_at) "
                    "VALUES (901, :category_id, :now, :now)"
                ),
                {"category_id": category_id, "now": now},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO professional_category_rubrics ("
                    "professional_id, category_id, source_rubric_number_id, "
                    "source_rubric_level, source_rubric_name, first_seen_at, last_seen_at) "
                    "VALUES (901, :category_id, 217, NULL, 'Legacy designers', :now, :now)"
                ),
                {"category_id": category_id, "now": now},
            )
            connection.execute(
                sa.text(
                    "UPDATE parser_category_targets SET taxonomy_level = 'unknown', "
                    "source_rubric_number_id = 999999, relative_path = 'legacy--999999' "
                    "WHERE category_id = :category_id"
                ),
                {"category_id": category_id},
            )
            # Старый /cp/categories выключал только родителя,
            # оставляя target активным.
            connection.execute(
                sa.text(
                    "UPDATE parser_categories SET is_active = 0 WHERE category_id = :category_id"
                ),
                {"category_id": estimators_category_id},
            )
            connection.execute(
                sa.text(
                    "UPDATE parser_category_targets SET relative_path = 'wrong--1844' "
                    "WHERE source_rubric_number_id = 1844"
                )
            )
            connection.execute(
                sa.text(
                    "UPDATE yandex_specializations SET source_url = NULL "
                    "WHERE external_number_id = 2007"
                )
            )
            connection.execute(
                sa.text(
                    "UPDATE yandex_specializations "
                    "SET source_url = 'https://evil.example/category/carpenter--5788' "
                    "WHERE external_number_id = 5788"
                )
            )
            connection.execute(
                sa.text(
                    "DELETE FROM category_yandex_specializations "
                    "WHERE specialization_id = ("
                    "SELECT id FROM yandex_specializations WHERE external_number_id = 1708)"
                )
            )
            connection.execute(
                sa.text(
                    "UPDATE yandex_specializations SET source_url = "
                    "'https://uslugi.yandex.ru/category/"
                    "remont-i-stroitelstvo/slabotochnye-sistemy--5784' "
                    "WHERE external_number_id = 5784"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(alembic_config(), "head")

    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert (
                connection.scalar(sa.text("SELECT phone FROM professionals WHERE id = 901"))
                == "+79991234567"
            )
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT source_rubric_level FROM professional_category_rubrics "
                        "WHERE professional_id = 901"
                    )
                )
                == "occupation"
            )
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT is_active FROM parser_category_targets "
                        "WHERE source_rubric_number_id = 999999"
                    )
                )
                == 0
            )
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT is_active FROM parser_categories WHERE category_id = "
                        "(SELECT id FROM categories WHERE `key` = 'designers')"
                    )
                )
                == 0
            )
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT COUNT(*) FROM parser_category_targets "
                        "WHERE category_id = :category_id AND is_active = 1"
                    ),
                    {"category_id": estimators_category_id},
                )
                == 0
            )
            invalid_catalog_targets = int(
                connection.scalar(
                    sa.text(
                        "SELECT COUNT(*) FROM parser_category_targets "
                        "WHERE source_rubric_number_id IN (1844, 2007, 5788, 1708) "
                        "AND is_active = 0"
                    )
                )
                or 0
            )
            assert invalid_catalog_targets == 4
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT is_active FROM parser_category_targets "
                        "WHERE source_rubric_number_id = 5784"
                    )
                )
                == 1
            )
            designers_seed_paths = connection.scalar(
                sa.text(
                    "SELECT seed_paths FROM parser_categories WHERE category_id = :category_id"
                ),
                {"category_id": category_id},
            )
            estimators_seed_paths = connection.scalar(
                sa.text(
                    "SELECT seed_paths FROM parser_categories WHERE category_id = :category_id"
                ),
                {"category_id": estimators_category_id},
            )
            plumbers_seed_paths = connection.scalar(
                sa.text(
                    "SELECT seed_paths FROM parser_categories WHERE category_id = "
                    "(SELECT id FROM categories WHERE `key` = 'plumbers')"
                )
            )
            assert json.loads(str(designers_seed_paths)) == []
            assert json.loads(str(estimators_seed_paths)) == []
            assert json.loads(str(plumbers_seed_paths)) == [
                "remont-i-stroitelstvo/vodosnabzhenie-i-kanalizatsiya--1367"
            ]
        assert "ix_professional_category_rubrics_catalog" in professional_rubric_indexes(
            database_url
        )
    finally:
        engine.dispose()

    command.downgrade(alembic_config(), "20260901_09")
    assert "ix_professional_category_rubrics_catalog" not in professional_rubric_indexes(
        database_url
    )


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
    assert ":param_" not in sql
    assert "ADD COLUMN phone VARCHAR(32)" in sql
    assert "CREATE INDEX ix_professionals_phone ON professionals (phone)" in sql
    assert "DROP COLUMN phone_ciphertext" in sql
    assert "DROP COLUMN phone_hmac" in sql
    assert "CREATE TABLE logs" in sql
    assert "resource VARCHAR(255) NOT NULL" in sql
    assert "CREATE INDEX ix_logs_result_started_at ON logs (result, started_at)" in sql
    assert "CREATE INDEX ix_logs_resource_started_at ON logs (resource, started_at)" in sql
    assert "CREATE TABLE settings" in sql
    assert "CONSTRAINT ck_settings_known_key CHECK" in sql
    assert ")CHARSET=utf8mb4 COLLATE utf8mb4_bin" in sql
    assert sql.count("INSERT INTO settings") == len(SCRAPER_SETTING_DEFAULTS)
    assert "ADD COLUMN profile_url_hash VARCHAR(64)" in sql
    assert "CONSTRAINT uq_professional_source_url_hash UNIQUE" in sql
    assert "CONSTRAINT ck_professionals_source_profile_id_not_blank CHECK" in sql
    assert "CREATE TABLE professional_identities" in sql
    assert "fk_professional_identities_professional_id" in sql
    assert "CREATE TABLE parser_categories" in sql
    assert "fk_parser_categories_category_id" in sql
    assert "CREATE INDEX ix_parser_categories_active_order" in sql
    # Ревизия 07 создаёт master-строки, а 09 повторно синхронизирует их описания.
    assert sql.count("INSERT INTO categories") == len(DEFAULT_CATEGORIES) * 2
    assert sql.count("INSERT INTO parser_categories") == len(DEFAULT_CATEGORIES)
    assert "CREATE TABLE yandex_occupations" in sql
    assert "CREATE TABLE yandex_specializations" in sql
    assert "CREATE TABLE yandex_services" in sql
    assert "CREATE TABLE parser_category_targets" in sql
    assert "CREATE TABLE category_yandex_services" in sql
    assert "yabs.yandex.ru" not in sql


def test_identity_upgrade_rejects_existing_duplicate_canonical_urls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Не включать новый unique key, пока старые логические дубли не объединены."""

    database_url = sqlite_url(tmp_path / "duplicate-identities.sqlite")
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), SETTINGS_REVISION)
    engine = sa.create_engine(database_url)
    now = datetime(2026, 8, 27, 12, 0, 0)
    try:
        with engine.begin() as connection:
            for row_id, source_profile_id, profile_url in (
                (1, "stable-a", "https://uslugi.yandex.ru/profile/Same-1?from=search"),
                (2, "stable-b", "https://uslugi.yandex.ru/profile/Same-1#reviews"),
            ):
                connection.execute(
                    sa.text(
                        "INSERT INTO professionals ("
                        "id, source, source_profile_id, profile_url, phone_status, age_as_of, "
                        "content_hash, parser_version, first_seen_at, last_seen_at, "
                        "last_scraped_at) VALUES ("
                        ":id, 'uslugi.yandex.ru', :source_profile_id, :profile_url, "
                        "'not_requested', '2026-08-27', :content_hash, '0.1.0', :now, :now, :now)"
                    ),
                    {
                        "id": row_id,
                        "source_profile_id": source_profile_id,
                        "profile_url": profile_url,
                        "content_hash": str(row_id) * 64,
                        "now": now,
                    },
                )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="duplicate canonical professional URL"):
        command.upgrade(alembic_config(), "head")

    columns, _indexes, version = schema_state(database_url)
    assert "profile_url_hash" not in columns
    assert version == SETTINGS_REVISION


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


def test_identity_incremental_offline_sql_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Не обходить preflight идентичности через incremental --sql."""

    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://uslugi:test@127.0.0.1:3306/uslugi?charset=utf8mb4",
    )

    with pytest.raises(RuntimeError, match="cannot canonicalize and validate"):
        command.upgrade(
            alembic_config(output_buffer=StringIO()),
            f"{SETTINGS_REVISION}:head",
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
