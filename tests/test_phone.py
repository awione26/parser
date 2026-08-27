from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

import pytest

from uslugi_parser.exceptions import PhoneCollectorUnavailable, PhoneNavigationBlocked
from uslugi_parser.infrastructure.browser import PhoneCollector


class LaunchPage:
    def set_default_timeout(self, _: int) -> None:
        return None

    async def route(self, *_: object) -> None:
        return None


class LaunchContext:
    async def new_page(self) -> LaunchPage:
        return LaunchPage()

    async def close(self) -> None:
        return None


class LaunchBrowser:
    async def new_context(self, **_: object) -> LaunchContext:
        return LaunchContext()

    async def close(self) -> None:
        return None


class LaunchChromium:
    def __init__(self) -> None:
        self.options: dict[str, Any] = {}

    async def launch(self, **options: Any) -> LaunchBrowser:
        self.options = options
        return LaunchBrowser()


class LaunchPlaywright:
    def __init__(self) -> None:
        self.chromium = LaunchChromium()

    async def stop(self) -> None:
        return None


class LaunchStarter:
    def __init__(self, playwright: LaunchPlaywright) -> None:
        self.playwright = playwright

    async def start(self) -> LaunchPlaywright:
        return self.playwright


@pytest.mark.asyncio
async def test_browser_launch_enables_chromium_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    playwright = LaunchPlaywright()
    playwright_package = ModuleType("playwright")
    async_api = ModuleType("playwright.async_api")
    async_api.async_playwright = lambda: LaunchStarter(playwright)  # type: ignore[attr-defined]
    playwright_package.async_api = async_api  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", playwright_package)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api)
    monkeypatch.setenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium")
    collector = PhoneCollector(
        user_agent="TestParser/1.0",
        headless=True,
        timeout_seconds=1,
        min_delay_seconds=0,
    )

    async with collector:
        pass

    assert playwright.chromium.options == {
        "headless": True,
        "chromium_sandbox": True,
        "executable_path": "/usr/bin/chromium",
    }


@pytest.mark.asyncio
async def test_headed_linux_browser_requires_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """До запуска Chromium объяснить ограничение headed-режима в Docker/Linux."""

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    collector = PhoneCollector(
        user_agent="TestParser/1.0",
        headless=False,
        timeout_seconds=1,
        min_delay_seconds=0,
    )

    with pytest.raises(PhoneCollectorUnavailable, match="SCRAPER_PHONE_HEADLESS=true"):
        await collector.__aenter__()


class BrokenPage:
    async def goto(self, *_: object, **__: object) -> None:
        raise RuntimeError("browser page crashed")

    @property
    def url(self) -> str:
        raise RuntimeError("page is closed")

    def locator(self, *_: object) -> None:
        raise RuntimeError("page is closed")


@pytest.mark.asyncio
async def test_browser_failure_becomes_unavailable_phone() -> None:
    collector = PhoneCollector(
        user_agent="TestParser/1.0",
        headless=True,
        timeout_seconds=1,
        min_delay_seconds=0,
    )
    collector._page = BrokenPage()
    assert await collector.collect("https://uslugi.yandex.ru/profile/Test-1", "Россия") is None


class RedirectedPage:
    url = "http://127.0.0.1/private"

    async def goto(self, *_: object, **__: object) -> None:
        return None


@pytest.mark.asyncio
async def test_redirected_browser_page_is_blocked() -> None:
    collector = PhoneCollector(
        user_agent="TestParser/1.0",
        headless=True,
        timeout_seconds=1,
        min_delay_seconds=0,
    )
    collector._page = RedirectedPage()
    with pytest.raises(PhoneNavigationBlocked):
        await collector.collect("https://uslugi.yandex.ru/profile/Test-1", "Россия")


class ContractLocator:
    def __init__(self, *, text: str = "", count: int = 0) -> None:
        self.text = text
        self.result_count = count
        self.clicked = False

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return self.result_count

    async def click(self, **_: object) -> None:
        self.clicked = True

    async def wait_for(self, **_: object) -> None:
        return None

    async def inner_text(self) -> str:
        return self.text


class ContractPage:
    url = "https://uslugi.yandex.ru/profile/Test-1"

    def __init__(self) -> None:
        self.button = ContractLocator()
        self.phone = ContractLocator(text="8 (999) 123-45-67")

    async def goto(self, *_: object, **__: object) -> None:
        return None

    async def title(self) -> str:
        return "Публичный профиль"

    def locator(self, selector: str) -> ContractLocator:
        if selector == ".PhoneLoader-Phone":
            return self.phone
        assert selector == ".CheckboxCaptcha, .AdvancedCaptcha"
        return ContractLocator(count=0)

    def get_by_role(self, role: str, *, name) -> ContractLocator:
        assert role == "button"
        assert name.fullmatch("Телефон")
        return self.button


@pytest.mark.asyncio
async def test_phone_dom_selector_contract() -> None:
    collector = PhoneCollector(
        user_agent="TestParser/1.0",
        headless=True,
        timeout_seconds=1,
        min_delay_seconds=0,
    )
    page = ContractPage()
    collector._page = page
    assert await collector.collect(page.url, "Россия") == "+79991234567"
    assert page.button.clicked
