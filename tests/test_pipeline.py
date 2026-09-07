from __future__ import annotations

from copy import deepcopy

import pytest
from conftest import html_with_state, make_state, make_worker

from uslugi_parser.application import CrawlProgressEvent, crawl, parse_live_profile
from uslugi_parser.catalog.categories import DEFAULT_CATEGORIES, CategoryDefinition
from uslugi_parser.config import Settings
from uslugi_parser.exceptions import CaptchaDetected, CrawlAborted
from uslugi_parser.infrastructure.http.fetcher import FetchResult


def live_settings() -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        user_agent="TestParser/1.0",
        geo="213-moscow",
        respect_robots=False,
        min_delay_seconds=0,
        max_delay_seconds=0,
        timeout_seconds=1,
        max_retries=0,
        collect_phone=False,
        phone_headless=True,
        phone_timeout_seconds=1,
        include_organizations=False,
    )


class FakeFetcher:
    def __init__(self, *results: FetchResult) -> None:
        self.results = list(results)
        self.urls: list[str] = []

    async def __aenter__(self) -> FakeFetcher:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str) -> FetchResult:
        self.urls.append(url)
        return self.results.pop(0)


def result(html: str, url: str) -> FetchResult:
    return FetchResult(text=html, url=url, status_code=200)


@pytest.mark.asyncio
async def test_category_captcha_aborts_entire_crawl() -> None:
    fake = FakeFetcher(
        result(
            "<html><head><title>Ой!</title></head></html>",
            "https://uslugi.yandex.ru/showcaptcha",
        )
    )
    with pytest.raises(CrawlAborted, match="CAPTCHA"):
        await crawl(
            settings=live_settings(),
            categories=[DEFAULT_CATEGORIES["plumbers"]],
            max_pages=1,
            max_profiles=1,
            repository=None,
            fetcher_factory=lambda _settings: fake,
        )


@pytest.mark.asyncio
async def test_profile_captcha_aborts_entire_crawl() -> None:
    worker = make_worker()
    fake = FakeFetcher(
        result(html_with_state(make_state(worker)), "https://uslugi.yandex.ru/category"),
        result(
            "<html><head><title>Ой!</title></head></html>",
            "https://uslugi.yandex.ru/showcaptcha",
        ),
    )
    with pytest.raises(CrawlAborted, match="CAPTCHA"):
        await crawl(
            settings=live_settings(),
            categories=[DEFAULT_CATEGORIES["plumbers"]],
            max_pages=1,
            max_profiles=1,
            repository=None,
            fetcher_factory=lambda _settings: fake,
        )


@pytest.mark.asyncio
async def test_unknown_account_type_is_skipped() -> None:
    worker = make_worker()
    worker["personalInfo"].pop("accountType")
    fake = FakeFetcher(
        result(html_with_state(make_state(worker)), "https://uslugi.yandex.ru/category"),
        result(
            html_with_state(make_state(worker)),
            "https://uslugi.yandex.ru/profile/TestMaster-123456",
        ),
    )
    stats = await crawl(
        settings=live_settings(),
        categories=[DEFAULT_CATEGORIES["electricians"]],
        max_pages=1,
        max_profiles=1,
        repository=None,
        fetcher_factory=lambda _settings: fake,
    )
    assert stats.skipped_organizations == 1
    assert stats.profiles == []


class CaptchaPhoneCollector:
    def __init__(self, **_: object) -> None:
        pass

    async def __aenter__(self) -> CaptchaPhoneCollector:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def collect(self, *_: object) -> None:
        raise CaptchaDetected("test CAPTCHA")


@pytest.mark.asyncio
async def test_direct_profile_phone_captcha_keeps_existing_flow() -> None:
    """Оставить UI-раскрытие телефона только в сценарии одиночного профиля."""

    worker = deepcopy(make_worker())
    worker["personalInfo"]["socialLinks"] = {"messengers": {}}
    fake = FakeFetcher(
        result(
            html_with_state(make_state(worker)),
            "https://uslugi.yandex.ru/profile/TestMaster-123456",
        ),
    )
    profile = await parse_live_profile(
        "https://uslugi.yandex.ru/profile/TestMaster-123456",
        live_settings(),
        collect_phone=True,
        fetcher_factory=lambda _settings: fake,
        phone_collector_factory=lambda _settings: CaptchaPhoneCollector(),
    )
    assert profile.phone is None
    assert profile.phone_status == "blocked_captcha"


@pytest.mark.asyncio
async def test_catalog_crawl_never_extracts_public_phone() -> None:
    """Не читать номер из state профиля при массовом обходе Каталога Яндекса."""

    worker = make_worker()
    one_target_category = CategoryDefinition(
        key="plumbers_test",
        name="Тестовая сантехника",
        seed_paths=("remont-i-stroitelstvo/santehnicheskie-rabotyi-i-otoplenie--1844",),
        taxonomy_levels=("specialization",),
    )
    fake = FakeFetcher(
        result(html_with_state(make_state(worker)), "https://uslugi.yandex.ru/category"),
        result(
            html_with_state(make_state(worker)),
            "https://uslugi.yandex.ru/profile/TestMaster-123456",
        ),
    )
    stats = await crawl(
        settings=live_settings(),
        categories=[one_target_category],
        max_pages=1,
        max_profiles=1,
        repository=None,
        fetcher_factory=lambda _settings: fake,
    )
    assert len(stats.profiles) == 1
    assert stats.profiles[0]["phone"] is None
    assert stats.profiles[0]["phone_status"] == "not_requested"


@pytest.mark.asyncio
async def test_crawl_reports_detailed_progress_snapshots() -> None:
    """Передавать CLI этапы целей, страниц и профилей вместе со счётчиками."""

    worker = make_worker()
    second_worker = make_worker(
        worker_id="worker-2",
        seoid="654321",
        seoname="SecondMaster-654321",
    )
    category = CategoryDefinition(
        key="plumbers_progress",
        name="Сантехник",
        seed_paths=("remont-i-stroitelstvo/santehnicheskie-rabotyi-i-otoplenie--1844",),
        taxonomy_levels=("specialization",),
    )
    fake = FakeFetcher(
        result(
            html_with_state(make_state(worker, second_worker)),
            "https://uslugi.yandex.ru/category",
        ),
        result(
            html_with_state(make_state(worker)),
            "https://uslugi.yandex.ru/profile/TestMaster-123456",
        ),
    )
    events: list[CrawlProgressEvent] = []

    stats = await crawl(
        settings=live_settings(),
        categories=[category],
        max_pages=1,
        max_profiles=1,
        repository=None,
        fetcher_factory=lambda _settings: fake,
        progress=events.append,
    )

    stages = [progress.stage for progress in events]
    assert stages == [
        "started",
        "target_started",
        "page_fetching",
        "page_parsed",
        "profile_started",
        "profile_completed",
        "page_completed",
        "target_completed",
        "completed",
    ]
    parsed_page = events[3]
    assert parsed_page.targets_total == 1
    assert parsed_page.target_rubric_number_id == 1844
    assert parsed_page.page_number == 1
    assert parsed_page.pages_total == 1
    assert parsed_page.profiles_total == 2
    assert events[5].outcome == "dry_run"
    assert events[-1].outcome == "limit_reached"
    assert events[-1].profile_index == 1
    assert events[-1].dry_run is True
    assert events[-1].discovered == stats.discovered == 2
    assert events[-1].fetched == stats.fetched == 1
    assert events[-1].parsed == stats.parsed == 1


@pytest.mark.asyncio
async def test_crawl_alternates_catalog_targets_between_pagination_rounds() -> None:
    """Не заканчивать все страницы одной рубрики до перехода к следующей."""

    empty_state = make_state()
    empty_state["workers"]["items"] = {}
    empty_state["workers"]["singleSearchResultId"] = None
    empty_state["search"]["workerIds"] = []
    empty_state["search"]["params"]["pagination"] = {
        "p": 0,
        "perPage": 1,
        "totalItems": 2,
    }
    category_html = html_with_state(empty_state)
    fake = FakeFetcher(
        *(result(category_html, "https://uslugi.yandex.ru/category") for _ in range(4))
    )
    categories = [
        CategoryDefinition(
            key="electricians_round_robin",
            name="Электрик",
            seed_paths=("remont-i-stroitelstvo/elektromontazhnyie-rabotyi--2007",),
            taxonomy_levels=("specialization",),
        ),
        CategoryDefinition(
            key="plumbers_round_robin",
            name="Сантехник",
            seed_paths=("remont-i-stroitelstvo/santehnicheskie-rabotyi-i-otoplenie--1844",),
            taxonomy_levels=("specialization",),
        ),
    ]
    events: list[CrawlProgressEvent] = []

    stats = await crawl(
        settings=live_settings(),
        categories=categories,
        max_pages=0,
        max_profiles=0,
        repository=None,
        fetcher_factory=lambda _settings: fake,
        progress=events.append,
    )

    page_targets = [
        event.target_rubric_number_id for event in events if event.stage == "page_fetching"
    ]
    assert page_targets == [2007, 1844, 2007, 1844]
    assert stats.category_pages == 4
