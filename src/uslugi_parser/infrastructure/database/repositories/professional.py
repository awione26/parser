"""Репозиторий идемпотентного сохранения мастеров и их рубрик."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from uslugi_parser import __version__
from uslugi_parser.catalog.categories import CategoryDefinition
from uslugi_parser.domain import ParsedProfessional, RubricEvidence
from uslugi_parser.infrastructure.database.models import (
    Category,
    Professional,
    ProfessionalCategory,
    ProfessionalCategoryRubric,
    utcnow,
)


def _content_hash(profile: ParsedProfessional) -> str:
    """Вычислить стабильный хеш публичного содержимого профиля без телефона."""

    payload = profile.content_payload()
    # Обычный SHA-256 телефона легко подобрать, поэтому не включаем номер в этот хеш.
    payload.pop("phone", None)
    payload.pop("phone_status", None)
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ProfessionalRepository:
    """Сохранять профили и их подтверждённые категории в одной транзакции."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Принять фабрику сессий для коротких транзакций записи."""

        self.session_factory = session_factory

    def upsert(
        self,
        profile: ParsedProfessional,
        category_definition: CategoryDefinition,
        evidence: RubricEvidence | None = None,
    ) -> Literal["created", "updated"]:
        """Создать или обновить мастера, категорию и их связь.

        Рубрика-основание сохраняется только при переданном evidence с number_id.
        """

        # Другой процесс может вставить тот же профиль между SELECT и INSERT.
        # Уникальные ограничения разрешают гонку, а повтор превращает её
        # в обычный сценарий обновления.
        for attempt in range(2):
            try:
                return self._upsert_once(profile, category_definition, evidence)
            except IntegrityError:
                if attempt:
                    raise
        raise AssertionError("unreachable")

    def _upsert_once(
        self,
        profile: ParsedProfessional,
        category_definition: CategoryDefinition,
        evidence: RubricEvidence | None,
    ) -> Literal["created", "updated"]:
        """Выполнить одну транзакционную попытку сохранения связанного графа."""

        now = utcnow()
        with self.session_factory.begin() as session:
            professional = session.scalar(
                select(Professional).where(
                    Professional.source == profile.source,
                    Professional.source_profile_id == profile.source_profile_id,
                )
            )
            outcome: Literal["created", "updated"]
            normalized_phone = _normalized_phone(profile.phone, profile.country)
            if professional is None:
                professional = Professional(
                    source=profile.source,
                    source_profile_id=profile.source_profile_id,
                    profile_url=profile.profile_url,
                    full_name=profile.full_name,
                    phone=normalized_phone,
                    phone_status=profile.phone_status,
                    city=profile.city,
                    region=profile.region,
                    country=profile.country,
                    age=profile.age,
                    age_as_of=profile.age_as_of,
                    gender=profile.gender,
                    experience_code=profile.experience_code,
                    experience_text=profile.experience_text,
                    photo_url=profile.photo_url,
                    account_type=profile.account_type,
                    content_hash=_content_hash(profile),
                    parser_version=__version__,
                    first_seen_at=now,
                    last_seen_at=now,
                    last_scraped_at=now,
                )
                session.add(professional)
                session.flush()
                outcome = "created"
            else:
                professional.profile_url = profile.profile_url
                professional.full_name = profile.full_name
                professional.city = profile.city
                professional.region = profile.region
                professional.country = profile.country
                professional.age = profile.age
                professional.age_as_of = profile.age_as_of
                professional.gender = profile.gender
                professional.experience_code = profile.experience_code
                professional.experience_text = profile.experience_text
                professional.photo_url = profile.photo_url
                professional.account_type = profile.account_type
                professional.content_hash = _content_hash(profile)
                professional.parser_version = __version__
                professional.last_seen_at = now
                professional.last_scraped_at = now
                if normalized_phone:
                    professional.phone = normalized_phone
                    professional.phone_status = profile.phone_status
                elif profile.phone_status in {"not_public", "permission_required"}:
                    # Учитываем явное удаление номера источником или отзыв локального разрешения.
                    professional.phone = None
                    professional.phone_status = profile.phone_status
                outcome = "updated"

            category = session.scalar(
                select(Category).where(Category.key == category_definition.key)
            )
            if category is None:
                category = Category(
                    key=category_definition.key,
                    name=category_definition.name,
                    note=category_definition.note or None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(category)
                session.flush()
            else:
                category.name = category_definition.name
                category.note = category_definition.note or None
                category.updated_at = now

            link = session.get(
                ProfessionalCategory,
                {"professional_id": professional.id, "category_id": category.id},
            )
            if link is None:
                link = ProfessionalCategory(
                    professional_id=professional.id,
                    category_id=category.id,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(link)
            else:
                link.last_seen_at = now
            if evidence is not None and evidence.number_id is not None:
                rubric = session.get(
                    ProfessionalCategoryRubric,
                    {
                        "professional_id": professional.id,
                        "category_id": category.id,
                        "source_rubric_number_id": evidence.number_id,
                    },
                )
                if rubric is None:
                    rubric = ProfessionalCategoryRubric(
                        professional_id=professional.id,
                        category_id=category.id,
                        source_rubric_number_id=evidence.number_id,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                    session.add(rubric)
                else:
                    rubric.last_seen_at = now
                rubric.source_rubric_id = evidence.rubric_id
                rubric.source_rubric_seo_id = evidence.seo_id
                rubric.source_rubric_name = evidence.name
                rubric.experience_code = evidence.experience_code
                rubric.experience_text = _experience_text(evidence.experience_code)
            return outcome


def _experience_text(code: int | None) -> str | None:
    """Преобразовать исходный код опыта в человекочитаемое описание."""

    # Локальный импорт не связывает порядок загрузки ORM с внутренностями парсинга.
    from uslugi_parser.parsing import experience_label

    return experience_label(code)


def _normalized_phone(phone: str | None, country: str | None) -> str | None:
    """Нормализовать присутствующий телефон или отклонить некорректное значение."""

    if phone is None:
        return None

        # Локальный импорт сохраняет независимость ORM от порядка загрузки парсера.
    from uslugi_parser.parsing import normalize_phone

    normalized = normalize_phone(phone, country)
    if normalized is None:
        raise ValueError("phone is present but cannot be normalized")
    return normalized
