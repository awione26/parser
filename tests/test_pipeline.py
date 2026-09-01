from __future__ import annotations

from copy import deepcopy

import pytest
from conftest import html_with_state, make_state, make_worker

from uslugi_parser.application import crawl
from uslugi_parser.catalog.categories import DEFAULT_CATEGORIES
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

    async def __aenter__(self) -> FakeFetcher:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, _url: str) -> FetchResult:
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
            collect_phone=False,
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
            collect_phone=False,
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
        collect_phone=False,
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
async def test_phone_captcha_aborts_entire_crawl() -> None:
    worker = deepcopy(make_worker())
    worker["personalInfo"]["socialLinks"] = {"messengers": {}}
    fake = FakeFetcher(
        result(html_with_state(make_state(worker)), "https://uslugi.yandex.ru/category"),
        result(
            html_with_state(make_state(worker)),
            "https://uslugi.yandex.ru/profile/TestMaster-123456",
        ),
    )
    with pytest.raises(CrawlAborted, match="CAPTCHA"):
        await crawl(
            settings=live_settings(),
            categories=[DEFAULT_CATEGORIES["plumbers"]],
            max_pages=1,
            max_profiles=1,
            collect_phone=True,
            repository=None,
            fetcher_factory=lambda _settings: fake,
            phone_collector_factory=lambda _settings: CaptchaPhoneCollector(),
        )
