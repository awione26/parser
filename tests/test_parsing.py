from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from conftest import html_with_state, make_state, make_worker

from uslugi_parser.parsing import (
    ParseError,
    add_page_query,
    calculate_age,
    canonicalize_live_profile_url,
    canonicalize_profile_url,
    experience_label,
    match_rubric,
    normalize_phone,
    parse_category_html,
    parse_profile_html,
    seed_number_id,
)


def test_parse_profile_from_preloaded_state(profile_html: str) -> None:
    profile = parse_profile_html(
        profile_html,
        "https://uslugi.yandex.ru/profile/TestMaster-123456?utm_source=test",
        today=date(2026, 8, 20),
    )

    assert profile.source_profile_id == "worker-1"
    assert profile.profile_url == "https://uslugi.yandex.ru/profile/TestMaster-123456"
    assert profile.full_name == "Иван Тестов"
    assert profile.phone == "+79991234567"
    assert profile.phone_status == "public_messenger"
    assert (profile.city, profile.region, profile.country) == (
        "Тестоград",
        "Тестовая область",
        "Россия",
    )
    assert profile.age == 35
    assert profile.gender == "male"
    assert profile.experience_code == 11
    assert profile.experience_text == "Более 10 лет"
    assert profile.photo_url.endswith("/320x320")
    assert "dob" not in profile.public_dict()


def test_profile_owner_opt_out_is_respected(worker: dict[str, object]) -> None:
    opted_out = deepcopy(worker)
    opted_out["displayOptions"] = {"allowProfileParsing": False}
    html = html_with_state(make_state(opted_out))
    with pytest.raises(ParseError, match="did not allow"):
        parse_profile_html(html, "https://uslugi.yandex.ru/profile/TestMaster-123456")


@pytest.mark.parametrize("value", [None, "false", 0])
def test_profile_consent_fails_closed(worker: dict[str, object], value: object) -> None:
    malformed = deepcopy(worker)
    if value is None:
        malformed.pop("displayOptions")
    else:
        malformed["displayOptions"] = {"allowProfileParsing": value}
    with pytest.raises(ParseError, match="did not allow"):
        parse_profile_html(
            html_with_state(make_state(malformed)),
            "https://uslugi.yandex.ru/profile/TestMaster-123456",
        )


def test_phone_id_is_not_treated_as_phone(worker: dict[str, object]) -> None:
    without_public_phone = deepcopy(worker)
    without_public_phone["personalInfo"]["socialLinks"] = {"messengers": {}}
    html = html_with_state(make_state(without_public_phone))
    profile = parse_profile_html(
        html,
        "https://uslugi.yandex.ru/profile/TestMaster-123456",
        today=date(2026, 8, 20),
    )
    assert profile.phone is None
    assert profile.phone_status == "not_requested"


@pytest.mark.parametrize(
    "whatsapp_url",
    [
        "https://wa.me/79991234567?text=1234",
        "https://api.whatsapp.com/send?phone=79991234567&utm_campaign=2026",
    ],
)
def test_whatsapp_tracking_digits_are_not_appended(
    worker: dict[str, object], whatsapp_url: str
) -> None:
    with_tracking = deepcopy(worker)
    with_tracking["personalInfo"]["socialLinks"] = {"messengers": {"whatsapp": whatsapp_url}}
    profile = parse_profile_html(
        html_with_state(make_state(with_tracking)),
        "https://uslugi.yandex.ru/profile/TestMaster-123456",
    )
    assert profile.phone == "+79991234567"


def test_category_page_and_pagination() -> None:
    state = make_state(make_worker(), make_worker(worker_id="worker-2", seoid="2", seoname="B-2"))
    state["search"]["params"]["pagination"] = {"p": 1, "perPage": 10, "totalItems": 25}
    page = parse_category_html(html_with_state(state))
    assert [item.source_profile_id for item in page.profiles] == ["worker-1", "worker-2"]
    assert page.page == 1
    assert page.total_pages == 3


def test_category_excludes_profiles_without_consent() -> None:
    allowed = make_worker()
    denied = make_worker(worker_id="worker-2", seoid="2", seoname="B-2")
    denied["displayOptions"]["allowProfileParsing"] = False
    page = parse_category_html(html_with_state(make_state(allowed, denied)))
    assert [item.source_profile_id for item in page.profiles] == ["worker-1"]


def test_location_fallback_does_not_mix_service_areas(worker: dict[str, object]) -> None:
    multiple_areas = deepcopy(worker)
    multiple_areas["address"] = {}
    multiple_areas["personalInfo"]["areasList"] = [
        {
            "name": "Первый город",
            "name_components": [
                {"kind": "country", "name": "Первая страна"},
                {"kind": "province", "name": "Первая область"},
            ],
        },
        {
            "name": "Второй город",
            "name_components": [
                {"kind": "country", "name": "Вторая страна"},
                {"kind": "province", "name": "Вторая область"},
            ],
        },
    ]
    profile = parse_profile_html(
        html_with_state(make_state(multiple_areas)),
        "https://uslugi.yandex.ru/profile/TestMaster-123456",
    )
    assert (profile.city, profile.region, profile.country) == (
        "Первый город",
        "Первая область",
        "Первая страна",
    )


@pytest.mark.parametrize(
    ("dob", "on_date", "expected"),
    [
        (date(2000, 8, 20), date(2026, 8, 20), 26),
        (date(2000, 8, 21), date(2026, 8, 20), 25),
        (date(2000, 2, 29), date(2026, 2, 28), 25),
        (date(2000, 2, 29), date(2026, 3, 1), 26),
    ],
)
def test_calculate_age(dob: date, on_date: date, expected: int) -> None:
    assert calculate_age(dob, on_date) == expected


def test_url_helpers() -> None:
    assert (
        canonicalize_profile_url("/profile/TestMaster-123?from=search#reviews")
        == "https://uslugi.yandex.ru/profile/TestMaster-123"
    )
    assert add_page_query("https://example.test/category?a=1", 2) == (
        "https://example.test/category?a=1&p=2"
    )
    assert (
        canonicalize_live_profile_url(
            "https://uslugi.yandex.ru/profile/TestMaster-123?utm_source=test#reviews"
        )
        == "https://uslugi.yandex.ru/profile/TestMaster-123"
    )
    with pytest.raises(ParseError):
        canonicalize_live_profile_url("https://127.0.0.1/profile/TestMaster-123")
    with pytest.raises(ParseError):
        canonicalize_live_profile_url("https://uslugi.yandex.ru/search")


def test_rubric_match_uses_exact_number_id(profile_html: str) -> None:
    profile = parse_profile_html(
        profile_html,
        "https://uslugi.yandex.ru/profile/TestMaster-123456",
    )
    specialization = match_rubric(profile, 1844)
    service = match_rubric(profile, seed_number_id("https://example.test/test--9999"))
    assert specialization is not None
    assert specialization.level == "specialization"
    assert specialization.experience_code == 11
    assert service is not None
    assert service.level == "service"
    assert service.experience_code == 11
    assert match_rubric(profile, 123456789) is None


def test_phone_normalization() -> None:
    assert normalize_phone("8 (999) 123-45-67", "Россия") == "+79991234567"
    assert normalize_phone("999 123-45-67", "Россия") == "+79991234567"
    assert normalize_phone("+800 1234 5678", "Россия") == "+80012345678"
    assert normalize_phone("8 123 456 7890", "Другая страна") == "+81234567890"
    assert normalize_phone("internal-id") is None


@pytest.mark.parametrize(
    ("code", "label"),
    [(1, "1 год"), (2, "2 года"), (5, "5 лет"), (10, "10 лет"), (11, "Более 10 лет")],
)
def test_experience_label(code: int, label: str) -> None:
    assert experience_label(code) == label
