"""Сценарии приложения, координирующие работу компонентов парсера."""

from uslugi_parser.application.crawl_service import crawl
from uslugi_parser.application.dto import (
    CrawlOptions,
    FetcherFactory,
    FetcherPort,
    ParserCategoryReader,
    PhoneCollectorFactory,
    PhoneCollectorPort,
    ProfessionalWriter,
    ProfileOptions,
)
from uslugi_parser.application.parser_log_service import (
    ERROR_REASON_MAX_LENGTH,
    ParserLogWriter,
    ParserRunService,
    safe_failure_reason,
)
from uslugi_parser.application.profile_service import (
    apply_profile_policy,
    parse_live_profile,
    parse_saved_profile,
    save_profile,
)

__all__ = [
    "CrawlOptions",
    "FetcherFactory",
    "FetcherPort",
    "ERROR_REASON_MAX_LENGTH",
    "ParserLogWriter",
    "ParserCategoryReader",
    "ParserRunService",
    "PhoneCollectorFactory",
    "PhoneCollectorPort",
    "ProfessionalWriter",
    "ProfileOptions",
    "apply_profile_policy",
    "crawl",
    "parse_live_profile",
    "parse_saved_profile",
    "save_profile",
    "safe_failure_reason",
]
