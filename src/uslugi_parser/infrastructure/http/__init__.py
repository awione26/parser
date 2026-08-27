"""Публичные HTTP-адаптеры, ограничитель частоты и политика robots.txt."""

from uslugi_parser.infrastructure.http.fetcher import (
    ALLOWED_ORIGIN,
    BLOCKING_STATUSES,
    RETRYABLE_STATUSES,
    FetchResult,
    HttpFetcher,
    require_allowed_origin,
)
from uslugi_parser.infrastructure.http.rate_limiter import PoliteRateLimiter
from uslugi_parser.infrastructure.http.robots import RobotsPolicy

__all__ = [
    "ALLOWED_ORIGIN",
    "BLOCKING_STATUSES",
    "RETRYABLE_STATUSES",
    "FetchResult",
    "HttpFetcher",
    "PoliteRateLimiter",
    "RobotsPolicy",
    "require_allowed_origin",
]
