from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.exc import IntegrityError

from uslugi_parser.catalog.categories import DEFAULT_CATEGORIES
from uslugi_parser.domain import ParsedProfessional, RubricEvidence
from uslugi_parser.infrastructure.database import (
    Base,
    IdentityConflictError,
    ParserSetting,
    ParserSettingRepository,
    Professional,
    ProfessionalCategory,
    ProfessionalCategoryRubric,
    ProfessionalIdentity,
    ProfessionalRepository,
    make_session_factory,
)


def make_profile(*, phone: str | None, phone_status: str) -> ParsedProfessional:
    return ParsedProfessional(
        source_profile_id="123",
        profile_url="https://uslugi.yandex.ru/profile/Test-123",
        full_name="Тестовый Мастер",
        phone=phone,
        phone_status=phone_status,
        city="Тестоград",
        region="Тестовая область",
        country="Россия",
        age=30,
        age_as_of=date(2026, 8, 20),
        gender="female",
        experience_code=5,
        experience_text="5 лет",
        photo_url="https://example.test/photo.jpg",
        account_type="person",
    )


def test_repository_upsert_and_category_links() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    repository = ProfessionalRepository(sessions)
    plumber_evidence = RubricEvidence(
        level="specialization",
        number_id=1844,
        rubric_id="/internal/plumber",
        seo_id="/canonical/plumber",
        name="Сантехнические работы",
        experience_code=5,
    )

    assert (
        repository.upsert(
            make_profile(phone="+79991234567", phone_status="revealed_ui"),
            DEFAULT_CATEGORIES["plumbers"],
            plumber_evidence,
        )
        == "created"
    )
    assert (
        repository.upsert(
            make_profile(phone=None, phone_status="not_requested"),
            DEFAULT_CATEGORIES["electricians"],
        )
        == "updated"
    )

    with sessions() as session:
        professional = session.scalar(select(Professional))
        assert professional is not None
        assert professional.phone == "+79991234567"
        assert professional.phone_status == "revealed_ui"
        assert session.query(ProfessionalCategory).count() == 2
        assert session.query(ProfessionalCategoryRubric).count() == 1

    repository.upsert(
        make_profile(phone=None, phone_status="reveal_failed"),
        DEFAULT_CATEGORIES["plumbers"],
        RubricEvidence(
            level="service",
            number_id=9999,
            rubric_id="9999",
            seo_id="/another-service",
            name="Другая услуга",
            experience_code=2,
        ),
    )
    with sessions() as session:
        professional = session.scalar(select(Professional))
        assert professional is not None
        assert professional.phone == "+79991234567"
        assert session.query(ProfessionalCategoryRubric).count() == 2

    repository.upsert(
        make_profile(phone=None, phone_status="not_public"),
        DEFAULT_CATEGORIES["plumbers"],
    )
    with sessions() as session:
        professional = session.scalar(select(Professional))
        assert professional is not None
        assert professional.phone is None
        assert professional.phone_status == "not_public"


def test_repository_normalizes_phone_before_plaintext_storage() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    repository = ProfessionalRepository(sessions)

    repository.upsert(
        make_profile(phone="8 (999) 123-45-67", phone_status="public_profile"),
        DEFAULT_CATEGORIES["plumbers"],
    )

    with sessions() as session:
        professional = session.scalar(select(Professional))
        assert professional is not None
        assert professional.phone == "+79991234567"


def test_repository_rejects_phone_that_cannot_be_normalized() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    repository = ProfessionalRepository(make_session_factory(engine))

    with pytest.raises(ValueError, match="cannot be normalized"):
        repository.upsert(
            make_profile(phone="internal-id", phone_status="public_profile"),
            DEFAULT_CATEGORIES["plumbers"],
        )


def test_repository_retries_a_unique_constraint_race(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    repository = ProfessionalRepository(make_session_factory(engine))
    original = repository._upsert_once
    calls = 0

    def flaky_upsert(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise IntegrityError("insert", {}, RuntimeError("simulated race"))
        return original(*args, **kwargs)

    monkeypatch.setattr(repository, "_upsert_once", flaky_upsert)
    assert (
        repository.upsert(
            make_profile(phone=None, phone_status="not_requested"),
            DEFAULT_CATEGORIES["plumbers"],
        )
        == "created"
    )
    assert calls == 2


def test_repository_deduplicates_changed_source_id_by_canonical_url() -> None:
    """Сохранить одну строку при смене id у того же канонического URL."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    repository = ProfessionalRepository(sessions)
    base_profile = make_profile(phone=None, phone_status="not_requested")

    first = replace(
        base_profile,
        source_profile_id="old-stable-id",
        profile_url="https://uslugi.yandex.ru/profile/Test-123?from=search#reviews",
    )
    second = replace(
        base_profile,
        source_profile_id="new-stable-id",
        profile_url="https://uslugi.yandex.ru/profile/Test-123?utm_source=repeat",
    )

    assert repository.upsert(first, DEFAULT_CATEGORIES["plumbers"]) == "created"
    assert repository.upsert(second, DEFAULT_CATEGORIES["electricians"]) == "updated"

    with sessions() as session:
        professional = session.scalar(select(Professional))
        assert professional is not None
        assert professional.source_profile_id == "old-stable-id"
        assert professional.profile_url == "https://uslugi.yandex.ru/profile/Test-123"
        assert session.query(Professional).count() == 1
        assert session.query(ProfessionalIdentity).count() == 2
        assert session.query(ProfessionalCategory).count() == 2


def test_repository_remembers_all_source_id_aliases_after_url_changes() -> None:
    """Не создать дубль после последовательной смены и ID, и URL профиля."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    repository = ProfessionalRepository(sessions)
    profile = make_profile(phone=None, phone_status="not_requested")

    for source_profile_id, profile_url in (
        ("stable-a", "https://uslugi.yandex.ru/profile/Master-X"),
        ("stable-b", "https://uslugi.yandex.ru/profile/Master-X"),
        ("stable-a", "https://uslugi.yandex.ru/profile/Master-Y"),
        ("stable-b", "https://uslugi.yandex.ru/profile/Master-Z"),
        ("STABLE-B", "https://uslugi.yandex.ru/profile/Master-W"),
    ):
        repository.upsert(
            replace(
                profile,
                source_profile_id=source_profile_id,
                profile_url=profile_url,
            ),
            DEFAULT_CATEGORIES["plumbers"],
        )

    with sessions() as session:
        professional = session.scalar(select(Professional))
        assert professional is not None
        assert professional.profile_url == "https://uslugi.yandex.ru/profile/Master-W"
        assert session.query(Professional).count() == 1
        assert session.query(ProfessionalIdentity).count() == 2


def test_repository_repeated_profile_preserves_one_row_and_first_seen() -> None:
    """Повторный парсинг обновляет существующую строку, не создавая новую."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    repository = ProfessionalRepository(sessions)
    profile = make_profile(phone=None, phone_status="not_requested")

    assert repository.upsert(profile, DEFAULT_CATEGORIES["plumbers"]) == "created"
    with sessions() as session:
        original = session.scalar(select(Professional))
        assert original is not None
        original_id = original.id
        original_first_seen = original.first_seen_at

    assert repository.upsert(profile, DEFAULT_CATEGORIES["plumbers"]) == "updated"
    with sessions() as session:
        repeated = session.scalar(select(Professional))
        assert repeated is not None
        assert repeated.id == original_id
        assert repeated.first_seen_at == original_first_seen
        assert session.query(Professional).count() == 1
        assert session.query(ProfessionalCategory).count() == 1


def test_repository_does_not_merge_distinct_ids_by_name_or_phone() -> None:
    """Не считать тёзок или общий телефон достаточными признаками одного мастера."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    repository = ProfessionalRepository(sessions)
    profile = make_profile(phone="+79991234567", phone_status="public_profile")

    repository.upsert(
        replace(
            profile,
            source_profile_id="stable-a",
            profile_url="https://uslugi.yandex.ru/profile/Master-A-1",
        ),
        DEFAULT_CATEGORIES["plumbers"],
    )
    repository.upsert(
        replace(
            profile,
            source_profile_id="stable-b",
            profile_url="https://uslugi.yandex.ru/profile/Master-B-2",
        ),
        DEFAULT_CATEGORIES["plumbers"],
    )

    with sessions() as session:
        assert session.query(Professional).count() == 2


@pytest.mark.parametrize("source_profile_id", ["", "   "])
def test_repository_rejects_missing_stable_source_id(source_profile_id: str) -> None:
    """Не сохранять карточку без обязательного стабильного id источника."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    repository = ProfessionalRepository(make_session_factory(engine))
    profile = replace(
        make_profile(phone=None, phone_status="not_requested"),
        source_profile_id=source_profile_id,
    )

    with pytest.raises(ValueError, match="source_profile_id must not be empty"):
        repository.upsert(profile, DEFAULT_CATEGORIES["plumbers"])


def test_repository_rejects_conflicting_id_and_canonical_url() -> None:
    """Не объединять молча две строки при противоречащих ключах идентичности."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    repository = ProfessionalRepository(sessions)
    base_profile = make_profile(phone=None, phone_status="not_requested")
    first = replace(
        base_profile,
        source_profile_id="stable-a",
        profile_url="https://uslugi.yandex.ru/profile/Master-A-1",
    )
    second = replace(
        base_profile,
        source_profile_id="stable-b",
        profile_url="https://uslugi.yandex.ru/profile/Master-B-2",
    )

    repository.upsert(first, DEFAULT_CATEGORIES["plumbers"])
    repository.upsert(second, DEFAULT_CATEGORIES["electricians"])

    with pytest.raises(IdentityConflictError, match="belong to different"):
        repository.upsert(
            replace(first, profile_url=second.profile_url),
            DEFAULT_CATEGORIES["designers"],
        )

    with sessions() as session:
        assert session.query(Professional).count() == 2
        assert session.query(ProfessionalCategory).count() == 2


def test_repository_normalizes_stable_identity_parts() -> None:
    """Пробелы и регистр источника не должны создавать повторную запись."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    repository = ProfessionalRepository(sessions)
    base_profile = make_profile(phone=None, phone_status="not_requested")

    assert (
        repository.upsert(
            replace(base_profile, source=" USLUGI.YANDEX.RU ", source_profile_id=" 123 "),
            DEFAULT_CATEGORIES["plumbers"],
        )
        == "created"
    )
    assert repository.upsert(base_profile, DEFAULT_CATEGORIES["electricians"]) == "updated"

    with sessions() as session:
        professional = session.scalar(select(Professional))
        assert professional is not None
        assert professional.source == "uslugi.yandex.ru"
        assert professional.source_profile_id == "123"
        assert session.query(Professional).count() == 1
        assert session.query(ProfessionalCategory).count() == 2


def test_setting_repository_reads_key_value_rows_without_writing() -> None:
    """Проверить контракт read-only репозитория настроек для runtime-парсера."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    with sessions.begin() as session:
        session.add_all(
            [
                ParserSetting(key="SCRAPER_GEO", value="213-moscow"),
                ParserSetting(key="SCRAPER_MAX_RETRIES", value="3"),
            ]
        )

    assert ParserSettingRepository(sessions).read_all() == {
        "SCRAPER_GEO": "213-moscow",
        "SCRAPER_MAX_RETRIES": "3",
    }


def test_setting_repository_ignores_future_unknown_keys() -> None:
    """Не ломать старый parser при появлении нового ключа во время rolling deploy."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    raw_settings = Table(
        "settings",
        metadata,
        Column("key", String(64), primary_key=True),
        Column("value", Text, nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            raw_settings.insert(),
            [
                {"key": "SCRAPER_GEO", "value": "213-moscow"},
                {"key": "SCRAPER_FUTURE_OPTION", "value": "future"},
            ],
        )

    repository = ParserSettingRepository(make_session_factory(engine))

    assert repository.read_all() == {"SCRAPER_GEO": "213-moscow"}
