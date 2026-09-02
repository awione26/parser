"""Сборка карточки мастера из нормализованных частей исходного состояния."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from uslugi_parser.domain import ParsedProfessional
from uslugi_parser.exceptions import ParseError
from uslugi_parser.parsing.category_parser import rubric_evidence
from uslugi_parser.parsing.experience import (
    calculate_age,
    experience_label,
    experience_values,
    parse_dob,
)
from uslugi_parser.parsing.location import location
from uslugi_parser.parsing.phone import phone_from_worker
from uslugi_parser.parsing.preloaded_state import (
    extract_preloaded_state,
    find_profile_worker,
    source_profile_id,
)
from uslugi_parser.parsing.urls import worker_profile_url


def _photo_url(value: object) -> str | None:
    """Нормализует URL аватара и задаёт устойчивый размер, если он не указан."""

    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip()
    if re.search(r"/(?:orig|diploma|\d+x\d+)$", url):
        return url
    return url.rstrip("/") + "/320x320"


def parse_profile_state(
    state: dict[str, Any],
    profile_url: str,
    *,
    today: date | None = None,
    include_phone: bool = True,
) -> ParsedProfessional:
    """Создать карточку мастера из state при разрешённом разборе профиля.

    `include_phone=False` обозначает жёсткую границу: номер не извлекается
    даже из публичного WhatsApp или поля state. Этот режим использует
    массовый обход Каталога Яндекса.
    """

    worker = find_profile_worker(state, profile_url)
    display_options = worker.get("displayOptions")
    if not (
        isinstance(display_options, dict) and display_options.get("allowProfileParsing") is True
    ):
        raise ParseError("profile owner did not allow public profile parsing")
    personal = worker.get("personalInfo")
    personal = personal if isinstance(personal, dict) else {}
    canonical_url = worker_profile_url(worker)
    source_id = source_profile_id(worker)

    full_name = personal.get("displayName")
    if not full_name:
        full_name = " ".join(
            str(personal.get(key)).strip()
            for key in ("lastName", "firstName", "middleName")
            if personal.get(key)
        )
    full_name = str(full_name).strip() or None

    city, region, country = location(worker)
    scrape_date = today or date.today()
    dob = parse_dob(personal.get("dob"))
    age = calculate_age(dob, scrape_date) if dob else None
    if age is not None and not 14 <= age <= 100:
        age = None

    gender_value = personal.get("gender")
    gender_map = {"male": "male", "female": "female", "other": "other"}
    gender = gender_map.get(str(gender_value).lower()) if gender_value else None
    all_experience_values = experience_values(worker)
    experience_code = max(all_experience_values) if all_experience_values else None
    phone, phone_status = (
        phone_from_worker(worker, country) if include_phone else (None, "not_requested")
    )
    rubrics = rubric_evidence(worker)

    return ParsedProfessional(
        source_profile_id=source_id,
        profile_url=canonical_url,
        full_name=full_name,
        phone=phone,
        phone_status=phone_status,
        city=city,
        region=region,
        country=country,
        age=age,
        age_as_of=scrape_date,
        gender=gender,
        experience_code=experience_code,
        experience_text=experience_label(experience_code),
        photo_url=_photo_url(personal.get("avatar")),
        account_type=(
            str(personal.get("accountType") or worker.get("accountType"))
            if personal.get("accountType") or worker.get("accountType")
            else None
        ),
        rubrics=rubrics,
    )


def parse_profile_html(
    html: str,
    profile_url: str,
    *,
    today: date | None = None,
    include_phone: bool = True,
) -> ParsedProfessional:
    """Извлечь state из HTML и создать карточку с явной политикой телефона."""

    return parse_profile_state(
        extract_preloaded_state(html),
        profile_url,
        today=today,
        include_phone=include_phone,
    )
