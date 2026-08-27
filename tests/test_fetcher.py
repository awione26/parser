from __future__ import annotations

import httpx
import pytest

from uslugi_parser.exceptions import (
    BlockedRedirect,
    BlockingFetchError,
    RobotsUnavailable,
    ServerAskedToStop,
    UnexpectedOrigin,
)
from uslugi_parser.infrastructure.http import HttpFetcher, RobotsPolicy


def test_robots_policy_understands_wildcards() -> None:
    policy = RobotsPolicy("ExampleParser/1.0")
    policy.add(
        "https://uslugi.yandex.ru",
        """
User-agent: *
Disallow: /*/category/*?p=*
Disallow: /api/*
Allow: /*
""",
    )
    assert policy.allowed("https://uslugi.yandex.ru/profile/Test-1")
    assert not policy.allowed("https://uslugi.yandex.ru/213-moscow/category/test--1?p=1")
    assert not policy.allowed("https://uslugi.yandex.ru/api/private")


def make_fetcher(handler: httpx.MockTransport, *, respect_robots: bool) -> HttpFetcher:
    fetcher = HttpFetcher(
        user_agent="TestParser/1.0",
        timeout_seconds=1,
        max_retries=1,
        min_delay_seconds=0,
        max_delay_seconds=0,
        respect_robots=respect_robots,
    )
    fetcher.client = httpx.AsyncClient(transport=handler, follow_redirects=False)
    return fetcher


@pytest.mark.asyncio
async def test_external_redirect_is_rejected_before_target_request() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})

    fetcher = make_fetcher(httpx.MockTransport(handler), respect_robots=False)
    try:
        with pytest.raises(UnexpectedOrigin):
            await fetcher.get("https://uslugi.yandex.ru/profile/Test-1")
    finally:
        await fetcher.__aexit__()
    assert requested == ["https://uslugi.yandex.ru/profile/Test-1"]


@pytest.mark.asyncio
async def test_redirect_target_is_checked_against_robots_before_request() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                headers={"Content-Type": "text/plain"},
                text="User-agent: *\nDisallow: /private\nAllow: /\n",
            )
        return httpx.Response(302, headers={"Location": "/private"})

    fetcher = make_fetcher(httpx.MockTransport(handler), respect_robots=True)
    try:
        with pytest.raises(BlockedRedirect, match="robots"):
            await fetcher.get("https://uslugi.yandex.ru/profile/Test-1")
    finally:
        await fetcher.__aexit__()
    assert requested_paths == ["/robots.txt", "/profile/Test-1"]


@pytest.mark.asyncio
async def test_malformed_robots_fails_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text="<html><body>temporary page</body></html>",
        )

    fetcher = make_fetcher(httpx.MockTransport(handler), respect_robots=True)
    try:
        with pytest.raises(RobotsUnavailable, match="text/plain"):
            await fetcher.get("https://uslugi.yandex.ru/profile/Test-1")
    finally:
        await fetcher.__aexit__()


@pytest.mark.asyncio
async def test_long_retry_after_stops_immediately() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(503, headers={"Retry-After": "999"})

    fetcher = make_fetcher(httpx.MockTransport(handler), respect_robots=False)
    try:
        with pytest.raises(ServerAskedToStop):
            await fetcher.get("https://uslugi.yandex.ru/profile/Test-1")
    finally:
        await fetcher.__aexit__()
    assert requests == 1


@pytest.mark.asyncio
async def test_blocking_http_status_has_dedicated_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    fetcher = make_fetcher(httpx.MockTransport(handler), respect_robots=False)
    try:
        with pytest.raises(BlockingFetchError) as error:
            await fetcher.get("https://uslugi.yandex.ru/profile/Test-1")
    finally:
        await fetcher.__aexit__()
    assert error.value.status_code == 403
