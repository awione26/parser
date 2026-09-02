"""Разбор категорий, рубрик и списков карточек из предзагруженного состояния."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from uslugi_parser.domain import (
    CategoryPage,
    DiscoveredProfile,
    ParsedProfessional,
    RubricEvidence,
)
from uslugi_parser.exceptions import ParseError
from uslugi_parser.parsing.preloaded_state import (
    extract_preloaded_state,
    source_profile_id,
    worker_items,
)
from uslugi_parser.parsing.urls import worker_profile_url


def _optional_int(value: object) -> int | None:
    """Безопасно преобразует целочисленное поле источника, исключая bool."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _optional_text(value: object) -> str | None:
    """Очищает необязательное текстовое поле и сводит пустое значение к None."""

    return str(value).strip() if value is not None and str(value).strip() else None


def rubric_evidence(worker: dict[str, Any]) -> tuple[RubricEvidence, ...]:
    """Извлекает иерархию рубрик мастера для точной проверки его категории."""

    result: list[RubricEvidence] = []
    occupations = worker.get("occupations")
    if not isinstance(occupations, list):
        return ()
    for occupation in occupations:
        if not isinstance(occupation, dict):
            continue
        occupation_attrs = occupation.get("attrs")
        occupation_experience = _optional_int(
            occupation_attrs.get("experience") if isinstance(occupation_attrs, dict) else None
        )
        result.append(
            RubricEvidence(
                level="occupation",
                number_id=_optional_int(occupation.get("numberId")),
                rubric_id=_optional_text(occupation.get("rubricId")),
                seo_id=_optional_text(occupation.get("seoId")),
                name=_optional_text(occupation.get("name")),
                experience_code=occupation_experience,
            )
        )
        specializations = occupation.get("specializations")
        if not isinstance(specializations, list):
            continue
        for specialization in specializations:
            if not isinstance(specialization, dict):
                continue
            attrs = specialization.get("attrs")
            specialization_experience = _optional_int(
                attrs.get("experience") if isinstance(attrs, dict) else None
            )
            result.append(
                RubricEvidence(
                    level="specialization",
                    number_id=_optional_int(specialization.get("numberId")),
                    rubric_id=_optional_text(specialization.get("rubricId")),
                    seo_id=_optional_text(specialization.get("seoId")),
                    name=_optional_text(specialization.get("name")),
                    experience_code=specialization_experience,
                )
            )
            services = specialization.get("services")
            if not isinstance(services, list):
                continue
            for service in services:
                if not isinstance(service, dict):
                    continue
                result.append(
                    RubricEvidence(
                        level="service",
                        number_id=_optional_int(service.get("numberId")),
                        rubric_id=_optional_text(service.get("rubricId")),
                        seo_id=_optional_text(service.get("seoId")),
                        name=_optional_text(service.get("name")),
                        # Опыт для услуги хранится в её родительской специализации.
                        experience_code=specialization_experience,
                    )
                )
    return tuple(result)


def match_rubric(
    profile: ParsedProfessional,
    number_id: int,
    expected_level: str | None = None,
) -> RubricEvidence | None:
    """Найти точную рубрику профиля по ID и уровню каталога.

    Уровень обязателен для целей, пришедших из Каталога Яндекса. Режим
    без уровня сохранён для ручного импорта старых файлов.
    """

    matches = [
        item
        for item in profile.rubrics
        if item.number_id == number_id and (expected_level is None or item.level == expected_level)
    ]
    if not matches:
        return None
    priority = {"service": 0, "specialization": 1, "occupation": 2}
    return min(matches, key=lambda item: priority.get(item.level, 99))


def parse_category_state(state: dict[str, Any]) -> CategoryPage:
    """Строит страницу уникальных разрешённых профилей и данные пагинации."""

    items = worker_items(state)
    search = state.get("search")
    search = search if isinstance(search, dict) else {}
    worker_ids = search.get("workerIds")
    ordered_ids: Iterable[str]
    if isinstance(worker_ids, list):
        ordered_ids = (str(value) for value in worker_ids)
    else:
        ordered_ids = items.keys()

    profiles: list[DiscoveredProfile] = []
    seen: set[str] = set()
    for worker_id in ordered_ids:
        worker = items.get(worker_id)
        if not worker:
            continue
        display_options = worker.get("displayOptions")
        if not (
            isinstance(display_options, dict) and display_options.get("allowProfileParsing") is True
        ):
            continue
        try:
            profile = DiscoveredProfile(
                source_profile_id=source_profile_id(worker),
                profile_url=worker_profile_url(worker),
            )
        except ParseError:
            continue
        if profile.profile_url not in seen:
            profiles.append(profile)
            seen.add(profile.profile_url)

    params = search.get("params")
    params = params if isinstance(params, dict) else {}
    pagination = params.get("pagination")
    pagination = pagination if isinstance(pagination, dict) else {}
    page = int(pagination.get("p") or 0)
    per_page = max(1, int(pagination.get("perPage") or len(profiles) or 1))
    total_items = max(len(profiles), int(pagination.get("totalItems") or len(profiles)))
    total_pages = max(1, math.ceil(total_items / per_page))
    return CategoryPage(
        profiles=tuple(profiles),
        page=page,
        per_page=per_page,
        total_items=total_items,
        total_pages=total_pages,
    )


def parse_category_html(html: str) -> CategoryPage:
    """Извлекает состояние из HTML категории и создаёт доменную страницу."""

    return parse_category_state(extract_preloaded_state(html))
