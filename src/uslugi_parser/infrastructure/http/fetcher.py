"""Защищённая загрузка страниц с редиректами, повторами и robots.txt."""

from __future__ import annotations

import asyncio
import email.utils
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from urllib.parse import urljoin, urlsplit

import httpx

from uslugi_parser.exceptions import (
    BlockedRedirect,
    BlockingFetchError,
    FetchError,
    RobotsDenied,
    RobotsUnavailable,
    ServerAskedToStop,
    UnexpectedOrigin,
)
from uslugi_parser.infrastructure.http.rate_limiter import PoliteRateLimiter
from uslugi_parser.infrastructure.http.robots import RobotsPolicy

RETRYABLE_STATUSES: Final = {408, 425, 429, 500, 502, 503, 504}
BLOCKING_STATUSES: Final = {403, 429}
ALLOWED_ORIGIN: Final = "https://uslugi.yandex.ru"


def require_allowed_origin(url: str) -> str:
    """Проверить, что URL принадлежит разрешённому HTTPS-origin Яндекс Услуг."""

    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "uslugi.yandex.ru":
        raise UnexpectedOrigin(f"refusing URL outside {ALLOWED_ORIGIN}: scheme/host is not allowed")
    if parsed.username is not None or parsed.password is not None or parsed.port not in {None, 443}:
        raise UnexpectedOrigin(f"refusing URL outside the canonical {ALLOWED_ORIGIN} origin")
    return url


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Хранить тело и метаданные успешно полученного HTTP-ответа."""

    text: str
    url: str
    status_code: int


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Преобразовать заголовок Retry-After в число секунд ожидания."""

    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())


class HttpFetcher:
    """Безопасно загружать страницы Яндекс Услуг с лимитами и robots.txt."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float,
        max_retries: int,
        min_delay_seconds: float,
        max_delay_seconds: float,
        respect_robots: bool = True,
    ) -> None:
        """Настроить HTTP-клиент, повторы запросов и вежливые интервалы."""

        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.respect_robots = respect_robots
        self.rate_limiter = PoliteRateLimiter(min_delay_seconds, max_delay_seconds)
        self.robots = RobotsPolicy(user_agent)
        self._robots_loaded: set[str] = set()
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> HttpFetcher:
        """Открыть асинхронный HTTP-клиент для серии контролируемых запросов."""

        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru,en;q=0.8",
            },
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=False,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        """Закрыть HTTP-клиент при выходе из асинхронного контекста."""

        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def _require_client(self) -> httpx.AsyncClient:
        """Вернуть открытый клиент или сообщить о неверном lifecycle объекта."""

        if self.client is None:
            raise RuntimeError("HttpFetcher must be used as an async context manager")
        return self.client

    async def _load_robots(self, url: str) -> None:
        """Загрузить и проверить robots.txt origin перед первым обращением к нему."""

        if not self.respect_robots:
            return
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots_loaded:
            return
        client = self._require_client()
        robots_url = origin + "/robots.txt"
        await self.rate_limiter.wait()
        try:
            response = await client.get(robots_url)
        except httpx.HTTPError as exc:
            raise RobotsUnavailable(f"could not load robots.txt for {origin}") from exc
        if response.status_code != 200:
            raise RobotsUnavailable(
                f"robots.txt returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        content_type = response.headers.get("Content-Type", "").casefold()
        body_head = response.text[:200_000]
        lowered = body_head.casefold()
        captcha_markers = ("checkboxcaptcha", "advancedcaptcha", "/showcaptcha")
        if not content_type.startswith("text/plain"):
            raise RobotsUnavailable("robots.txt did not return text/plain")
        if any(marker in lowered for marker in captcha_markers):
            raise RobotsUnavailable("robots.txt was replaced by a CAPTCHA")
        if re.search(r"(?im)^\s*user-agent\s*:\s*\S+", body_head) is None:
            raise RobotsUnavailable("robots.txt has no valid User-agent group")
        self.robots.add(origin, response.text)
        self._robots_loaded.add(origin)

    async def _get_following_safe_redirects(self, url: str) -> httpx.Response:
        """Выполнить GET, разрешая только проверенные редиректы внутри origin."""

        client = self._require_client()
        current_url = require_allowed_origin(url)
        for _ in range(11):
            await self._load_robots(current_url)
            if self.respect_robots and not self.robots.allowed(current_url):
                raise RobotsDenied(current_url)
            await self.rate_limiter.wait()
            response = await client.get(current_url)
            if not response.is_redirect:
                return response
            location = response.headers.get("Location")
            if not location:
                return response
            next_url = urljoin(current_url, location)
            require_allowed_origin(next_url)
            if "/showcaptcha" in urlsplit(next_url).path.casefold():
                raise BlockedRedirect("Yandex redirected the request to a CAPTCHA")
            await self._load_robots(next_url)
            if self.respect_robots and not self.robots.allowed(next_url):
                raise BlockedRedirect("redirect target is disallowed by robots.txt")
            current_url = next_url
        raise BlockedRedirect("too many redirects")

    async def get(self, url: str) -> FetchResult:
        """Получить страницу с повторами и остановкой при блокирующем ответе."""

        require_allowed_origin(url)

        last_error: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._get_following_safe_redirects(url)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(min(30.0, (2**attempt) + random.random()))
                continue

            if response.status_code in RETRYABLE_STATUSES:
                retry_after = _retry_after_seconds(response)
                if retry_after is not None and retry_after > 120:
                    raise ServerAskedToStop(
                        "server requested a long retry delay; collection stopped",
                        status_code=response.status_code,
                    )
                if attempt < self.max_retries:
                    backoff = (
                        retry_after if retry_after is not None else (2**attempt) + random.random()
                    )
                    await asyncio.sleep(min(120.0, backoff))
                    continue
            if response.status_code >= 400:
                error_type = (
                    BlockingFetchError if response.status_code in BLOCKING_STATUSES else FetchError
                )
                raise error_type(f"HTTP {response.status_code}", status_code=response.status_code)
            return FetchResult(
                text=response.text,
                url=str(response.url),
                status_code=response.status_code,
            )

        raise FetchError("request failed after retries") from last_error
