"""Проверка и канонизация URL профилей, страниц и рубрик Яндекс Услуг."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from uslugi_parser.catalog.categories import BASE_URL
from uslugi_parser.exceptions import ParseError


def canonicalize_profile_url(url: str) -> str:
    """Приводит профиль к URL без query и fragment для надёжной дедупликации."""

    parsed = urlsplit(urljoin(BASE_URL, url))
    match = re.search(r"/profile/([^/?#]+)", parsed.path)
    if not match:
        raise ParseError(f"Not a profile URL: {url}")
    return urlunsplit(("https", "uslugi.yandex.ru", f"/profile/{match.group(1)}", "", ""))


def canonicalize_live_profile_url(url: str) -> str:
    """Проверяет live URL до запроса и удаляет параметры трекинга."""

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "uslugi.yandex.ru"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
        or re.fullmatch(r"/profile/[^/?#]+/?", parsed.path) is None
    ):
        raise ParseError("live URL must be an HTTPS uslugi.yandex.ru/profile/... URL")
    return canonicalize_profile_url(url)


def add_page_query(url: str, page: int) -> str:
    """Добавляет номер положительной страницы, сохраняя остальные части URL.

    Для нулевой и отрицательной страницы исходный URL возвращается без изменений.
    """

    if page <= 0:
        return url
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["p"] = str(page)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def worker_profile_url(worker: dict[str, object]) -> str:
    """Строит канонический публичный URL карточки по slug мастера."""

    seoname = worker.get("seoname") or worker.get("seonameOld")
    if not seoname:
        raise ParseError("worker has no public profile slug")
    return canonicalize_profile_url(f"/profile/{seoname}")


def seed_number_id(url: str) -> int:
    """Извлекает id рубрики из seed URL для точного сопоставления категории."""

    match = re.search(r"--([0-9]+)(?:[/?#]|$)", url)
    if not match:
        raise ParseError(f"category seed has no numeric rubric id: {url}")
    return int(match.group(1))
