from __future__ import annotations

from datetime import date
from pathlib import Path

from uslugi_parser.parsing import match_rubric, parse_category_html, parse_profile_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_sanitized_profile_contract_fixture() -> None:
    html = (FIXTURES / "profile_contract.html").read_text(encoding="utf-8")
    profile = parse_profile_html(
        html,
        "https://uslugi.yandex.ru/profile/ContractMaster-1000001",
        today=date(2026, 8, 20),
    )
    assert profile.source_profile_id == "contract-worker-profile"
    assert profile.account_type == "person"
    assert profile.phone is None
    evidence = match_rubric(profile, 1844)
    assert evidence is not None
    assert evidence.experience_code == 2


def test_sanitized_category_contract_fixture() -> None:
    html = (FIXTURES / "category_contract.html").read_text(encoding="utf-8")
    page = parse_category_html(html)
    assert page.total_pages == 1
    assert [item.source_profile_id for item in page.profiles] == ["contract-worker-category"]
