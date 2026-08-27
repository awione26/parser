"""Безопасное получение показанного сайтом телефона через браузер."""

from __future__ import annotations

import asyncio
import os
import re
import sys
from types import TracebackType
from typing import Any

from uslugi_parser.exceptions import (
    CaptchaDetected,
    ParseError,
    PhoneCollectorUnavailable,
    PhoneNavigationBlocked,
)
from uslugi_parser.infrastructure.http import require_allowed_origin
from uslugi_parser.parsing import canonicalize_live_profile_url, normalize_phone


class PhoneCollector:
    """Получать телефон через тот же публичный интерфейс, что использует посетитель.

    Компонент намеренно не обращается к закрытым API, не переиспользует авторизованные
    сессии, не решает CAPTCHA и не обходит ограничения доступа.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        headless: bool,
        timeout_seconds: float,
        min_delay_seconds: float,
    ) -> None:
        """Сохранить настройки изолированного браузера для раскрытия телефона."""

        self.user_agent = user_agent
        self.headless = headless
        self.timeout_ms = int(timeout_seconds * 1000)
        self.min_delay_seconds = min_delay_seconds
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._captcha_redirect = False
        self._blocked_navigation = False

    async def __aenter__(self) -> PhoneCollector:
        """Запустить Chromium и подготовить защищённый контекст страницы."""

        if (
            not self.headless
            and sys.platform.startswith("linux")
            and not os.getenv("DISPLAY")
            and not os.getenv("WAYLAND_DISPLAY")
        ):
            raise PhoneCollectorUnavailable(
                "Headed phone collection on Linux requires DISPLAY or WAYLAND_DISPLAY; "
                "Docker users must keep SCRAPER_PHONE_HEADLESS=true."
            )
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise PhoneCollectorUnavailable(
                "Phone collection requires: pip install -e '.[phone]' and "
                "playwright install chromium. In Docker use the parser-phone service."
            ) from exc
        try:
            self._playwright = await async_playwright().start()
            launch_options: dict[str, Any] = {
                "headless": self.headless,
                "chromium_sandbox": True,
            }
            executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
            if executable_path:
                launch_options["executable_path"] = executable_path
            self._browser = await self._playwright.chromium.launch(**launch_options)
            self._context = await self._browser.new_context(
                user_agent=self.user_agent,
                locale="ru-RU",
            )
            self._page = await self._context.new_page()
            self._page.set_default_timeout(self.timeout_ms)

            async def guard_navigation(route: Any, request: Any) -> None:
                """Блокировать CAPTCHA и переходы документа за разрешённый origin."""

                if request.resource_type == "document":
                    target = str(request.url)
                    if "/showcaptcha" in target.casefold():
                        self._captcha_redirect = True
                        await route.abort()
                        return
                    try:
                        require_allowed_origin(target)
                    except (ValueError, RuntimeError):
                        self._blocked_navigation = True
                        await route.abort()
                        return
                await route.continue_()

            await self._page.route("**/*", guard_navigation)
        except Exception as exc:
            await self.__aexit__(type(exc), exc, exc.__traceback__)
            raise PhoneCollectorUnavailable(
                "Could not start Chromium for phone collection; run "
                "'playwright install chromium' and check the browser installation"
            ) from exc
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Освободить контекст, браузер и Playwright после завершения работы."""

        for resource, method_name in (
            (self._context, "close"),
            (self._browser, "close"),
            (self._playwright, "stop"),
        ):
            if resource is None:
                continue
            try:
                await getattr(resource, method_name)()
            except Exception:
                # Ошибка очистки не должна скрывать исходную ошибку браузера.
                pass

    async def collect(self, profile_url: str, country: str | None) -> str | None:
        """Открыть публичный профиль, нажать «Телефон» и нормализовать номер."""

        if self._page is None:
            raise RuntimeError("PhoneCollector must be used as an async context manager")
        await asyncio.sleep(self.min_delay_seconds)
        page = self._page
        self._captcha_redirect = False
        self._blocked_navigation = False
        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            if self._blocked_navigation:
                raise PhoneNavigationBlocked(
                    "phone page attempted to leave the allowed Yandex origin"
                )
            try:
                canonicalize_live_profile_url(str(page.url))
            except (ParseError, ValueError) as exc:
                raise PhoneNavigationBlocked(
                    "phone page did not remain on a public Yandex profile URL"
                ) from exc
            title = (await page.title()).casefold()
            if self._captcha_redirect or "ой!" in title or "/showcaptcha" in page.url:
                raise CaptchaDetected("Yandex requested a CAPTCHA during phone reveal")
            if await page.locator(".CheckboxCaptcha, .AdvancedCaptcha").count():
                raise CaptchaDetected("Yandex requested a CAPTCHA during phone reveal")

            button = page.get_by_role("button", name=re.compile(r"^\s*Телефон\s*$")).first
            await button.click(timeout=self.timeout_ms)
            phone_node = page.locator(".PhoneLoader-Phone").first
            await phone_node.wait_for(state="visible", timeout=self.timeout_ms)
            phone_text = await phone_node.inner_text()
        except (CaptchaDetected, PhoneNavigationBlocked):
            raise
        except Exception as exc:
            captcha_seen = self._captcha_redirect
            try:
                captcha_seen = captcha_seen or "/showcaptcha" in str(page.url)
            except Exception:
                pass
            try:
                captcha_seen = captcha_seen or bool(
                    await page.locator(".CheckboxCaptcha, .AdvancedCaptcha").count()
                )
            except Exception:
                pass
            if captcha_seen:
                raise CaptchaDetected("Yandex requested a CAPTCHA during phone reveal") from exc
            if self._blocked_navigation:
                raise PhoneNavigationBlocked(
                    "phone page attempted to leave the allowed Yandex origin"
                ) from exc
            return None
        return normalize_phone(phone_text, country)
