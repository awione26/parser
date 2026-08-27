from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from uslugi_parser.catalog.categories import DEFAULT_CATEGORIES
from uslugi_parser.config.settings import SCRAPER_SETTING_DEFAULTS
from uslugi_parser.domain import ParsedProfessional, RubricEvidence
from uslugi_parser.infrastructure.database import (
    ParserSetting,
    Professional,
    ProfessionalCategory,
    ProfessionalCategoryRubric,
    ProfessionalRepository,
    make_engine,
    make_session_factory,
)

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        os.getenv("RUN_MYSQL_INTEGRATION") != "1",
        reason="set RUN_MYSQL_INTEGRATION=1 with a disposable MYSQL_TEST_DATABASE_URL",
    ),
]


@contextmanager
def migration_environment(database_url: str):
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def mysql_profile() -> ParsedProfessional:
    return ParsedProfessional(
        source_profile_id="mysql-concurrency-contract",
        profile_url="https://uslugi.yandex.ru/profile/MySqlContract-1",
        full_name="Обезличенный тест",
        phone="+79990000000",
        phone_status="revealed_ui",
        city="Тестоград",
        region="Тестовая область",
        country="Россия",
        age=30,
        age_as_of=date(2026, 8, 20),
        gender="other",
        experience_code=5,
        experience_text="5 лет",
        photo_url=None,
        account_type="person",
    )


def test_mysql_migration_plaintext_concurrent_upsert_and_cascade() -> None:
    database_url = os.getenv("MYSQL_TEST_DATABASE_URL", "")
    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "mysql" or not (parsed_url.database or "").endswith(
        "_test"
    ):
        pytest.fail("MYSQL_TEST_DATABASE_URL must target a disposable MySQL *_test database")

    root = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(root / "migrations"))
    engine = None
    with migration_environment(database_url):
        command.upgrade(alembic_config, "head")
        try:
            command.check(alembic_config)
            engine = make_engine(database_url)
            sessions = make_session_factory(engine)
            with sessions() as session:
                settings = {
                    key: value
                    for key, value in session.execute(
                        select(ParserSetting.key, ParserSetting.value)
                    )
                }
                collation = session.scalar(
                    text(
                        "SELECT table_collation FROM information_schema.tables "
                        "WHERE table_schema = :schema AND table_name = 'settings'"
                    ),
                    {"schema": parsed_url.database},
                )
            assert settings == SCRAPER_SETTING_DEFAULTS
            assert collation == "utf8mb4_bin"

            for invalid_key in ("SCRAPER_UNKNOWN", "scraper_geo"):
                with pytest.raises(DBAPIError):
                    with sessions.begin() as session:
                        session.add(ParserSetting(key=invalid_key, value="invalid"))

            evidence = RubricEvidence(
                level="specialization",
                number_id=1844,
                rubric_id="/contract/plumber",
                seo_id="/contract/plumber",
                name="Обезличенная рубрика",
                experience_code=5,
            )
            barrier = Barrier(2)

            def writer() -> str:
                barrier.wait(timeout=10)
                return ProfessionalRepository(sessions).upsert(
                    mysql_profile(), DEFAULT_CATEGORIES["plumbers"], evidence
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(lambda _: writer(), range(2)))
            assert sorted(outcomes) == ["created", "updated"]

            with sessions() as session:
                professional = session.scalar(select(Professional))
                assert professional is not None
                assert professional.phone == "+79990000000"
                assert session.scalar(select(func.count(Professional.id))) == 1
                assert session.scalar(select(func.count(ProfessionalCategory.professional_id))) == 1
                assert (
                    session.scalar(select(func.count(ProfessionalCategoryRubric.professional_id)))
                    == 1
                )

            with sessions.begin() as session:
                professional = session.scalar(select(Professional))
                assert professional is not None
                session.delete(professional)
            with sessions() as session:
                assert session.scalar(select(func.count(ProfessionalCategory.professional_id))) == 0
                assert (
                    session.scalar(select(func.count(ProfessionalCategoryRubric.professional_id)))
                    == 0
                )
        finally:
            if engine is not None:
                engine.dispose()
            command.downgrade(alembic_config, "20260820_01")
            downgrade_engine = make_engine(database_url)
            try:
                indexes = inspect(downgrade_engine).get_indexes("professional_categories")
                assert not any(
                    index.get("name") == "ix_professional_categories_category_professional"
                    for index in indexes
                )
                assert any(
                    index.get("name") == "category_id"
                    and list(index.get("column_names") or []) == ["category_id"]
                    for index in indexes
                )
            finally:
                downgrade_engine.dispose()
                command.downgrade(alembic_config, "base")
