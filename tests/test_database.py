from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError

from uslugi_parser.catalog.categories import DEFAULT_CATEGORIES
from uslugi_parser.domain import ParsedProfessional, RubricEvidence
from uslugi_parser.infrastructure.database import (
    Base,
    Professional,
    ProfessionalCategory,
    ProfessionalCategoryRubric,
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
        make_profile(phone=None, phone_status="permission_required"),
        DEFAULT_CATEGORIES["plumbers"],
    )
    with sessions() as session:
        professional = session.scalar(select(Professional))
        assert professional is not None
        assert professional.phone is None
        assert professional.phone_status == "permission_required"


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
