"""Описание консольных команд и сборка их инфраструктурных зависимостей."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from uslugi_parser.application import (
    ParserRunService,
    crawl,
    parse_live_profile,
    parse_saved_profile,
    save_profile,
)
from uslugi_parser.catalog import CategoryDefinition
from uslugi_parser.config import Settings
from uslugi_parser.infrastructure.browser.phone_collector import PhoneCollector
from uslugi_parser.infrastructure.database.connection import make_engine, make_session_factory
from uslugi_parser.infrastructure.database.repositories.parser_category import (
    ParserCategoryRepository,
)
from uslugi_parser.infrastructure.database.repositories.parser_log import (
    ParserLogRepository,
)
from uslugi_parser.infrastructure.database.repositories.professional import (
    ProfessionalRepository,
)
from uslugi_parser.infrastructure.http.fetcher import HttpFetcher

logger = logging.getLogger(__name__)


def _json_dump(value: Any) -> None:
    """Вывести результат команды как читаемый JSON с русскими символами."""

    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False))


def _repository(settings: Settings) -> ProfessionalRepository:
    """Создать репозиторий мастеров для настроенного подключения к БД."""

    engine = make_engine(settings.database_url)
    return ProfessionalRepository(make_session_factory(engine))


def _category_repository(settings: Settings) -> ParserCategoryRepository:
    """Создать read-only репозиторий управляемых категорий парсинга."""

    engine = make_engine(settings.database_url)
    return ParserCategoryRepository(make_session_factory(engine))


def _resolve_save_category(
    settings: Settings,
    category_key: str | None,
) -> CategoryDefinition | None:
    """До разбора карточки разрешить один активный ключ категории из БД."""

    if category_key is None:
        return None
    categories = _category_repository(settings).resolve([category_key])
    if len(categories) != 1:
        raise ValueError("named save must resolve exactly one parser category")
    return categories[0]


def _parser_run_service(settings: Settings) -> ParserRunService:
    """Создать сервис журнала запусков на отдельной фабрике транзакций."""

    engine = make_engine(settings.database_url)
    writer = ParserLogRepository(make_session_factory(engine))
    return ParserRunService(writer)


def _fetcher(settings: Settings) -> HttpFetcher:
    """Создать HTTP-клиент с лимитами и политиками из настроек запуска."""

    return HttpFetcher(
        user_agent=settings.user_agent,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
        min_delay_seconds=settings.min_delay_seconds,
        max_delay_seconds=settings.max_delay_seconds,
        respect_robots=settings.respect_robots,
    )


def _phone_collector(settings: Settings) -> PhoneCollector:
    """Создать браузерный сборщик для публичного раскрытия телефона."""

    return PhoneCollector(
        user_agent=settings.user_agent,
        headless=settings.phone_headless,
        timeout_seconds=settings.phone_timeout_seconds,
        min_delay_seconds=settings.min_delay_seconds,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Собрать дерево аргументов и подкоманд консольного интерфейса."""

    parser = argparse.ArgumentParser(
        prog="uslugi-parser",
        description="Parser for public Yandex Services professional cards",
    )
    parser.add_argument("--verbose", action="store_true", help="enable informational logs")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("categories", help="show configured categories and seed URLs")
    parse_html = commands.add_parser("parse-html", help="parse a local saved profile page")
    parse_html.add_argument("file", type=Path)
    parse_html.add_argument(
        "--source-url",
        default="https://uslugi.yandex.ru/profile/local",
        help="original profile URL; a single worker can also be selected without it",
    )
    parse_html.add_argument("--save", action="store_true", help="upsert the result into MySQL")
    parse_html.add_argument("--category")

    parse_profile = commands.add_parser("parse-profile", help="fetch and parse one live profile")
    parse_profile.add_argument("url")
    profile_phone_group = parse_profile.add_mutually_exclusive_group()
    profile_phone_group.add_argument(
        "--collect-phone",
        dest="collect_phone",
        action="store_true",
    )
    profile_phone_group.add_argument(
        "--no-collect-phone",
        dest="collect_phone",
        action="store_false",
    )
    profile_phone_group.set_defaults(collect_phone=None)
    parse_profile.add_argument("--save", action="store_true", help="upsert the result into MySQL")
    parse_profile.add_argument("--category")
    parse_profile.add_argument(
        "--no-respect-robots",
        action="store_true",
        help="use only when written operator permission explicitly allows it",
    )

    crawl_parser = commands.add_parser("crawl", help="discover category cards and upsert profiles")
    crawl_parser.add_argument(
        "--category",
        action="append",
        help="repeatable database category key; defaults to all active categories",
    )
    crawl_parser.add_argument("--geo", help="Yandex geo slug, for example 213-moscow")
    crawl_parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="pages per seed; 0 means all pages allowed by policy (default: 1)",
    )
    crawl_parser.add_argument(
        "--max-profiles",
        type=int,
        default=0,
        help="maximum unique profiles; 0 means no additional limit",
    )
    crawl_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print JSON, do not write MySQL",
    )
    phone_group = crawl_parser.add_mutually_exclusive_group()
    phone_group.add_argument("--collect-phone", dest="collect_phone", action="store_true")
    phone_group.add_argument("--no-collect-phone", dest="collect_phone", action="store_false")
    phone_group.set_defaults(collect_phone=None)
    robots_group = crawl_parser.add_mutually_exclusive_group()
    robots_group.add_argument("--respect-robots", dest="respect_robots", action="store_true")
    robots_group.add_argument(
        "--no-respect-robots",
        dest="respect_robots",
        action="store_false",
        help="use only when written operator permission explicitly allows it",
    )
    robots_group.set_defaults(respect_robots=None)
    return parser


def _configure_logging(verbose: bool) -> None:
    """Настроить уровень и единый формат журналирования CLI."""

    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _run_categories(settings: Settings) -> int:
    """Показать настроенные категории и их стартовые URL."""

    rows = []
    for category in _category_repository(settings).list_active():
        rows.append(
            {
                "key": category.key,
                "name": category.name,
                "urls": list(category.urls(settings.geo)),
                "note": category.note or None,
            }
        )
    _json_dump(rows)
    return 0


def _run_parse_html(args: argparse.Namespace, settings: Settings) -> int:
    """Разобрать сохранённый HTML и при необходимости записать профиль в БД."""

    category = _resolve_save_category(settings, args.category) if args.save else None
    html = args.file.read_text(encoding="utf-8")
    profile = parse_saved_profile(html, args.source_url, settings)
    if args.save:
        outcome = save_profile(_repository(settings), profile, category)
        result = profile.public_dict()
        result["database"] = outcome
        _json_dump(result)
    else:
        _json_dump(profile.public_dict())
    return 0


async def _run_parse_profile(args: argparse.Namespace, settings: Settings) -> int:
    """Выполнить команду загрузки и разбора одной карточки мастера."""

    category = _resolve_save_category(settings, args.category) if args.save else None
    if args.no_respect_robots:
        settings = settings.with_overrides(respect_robots=False)
        logger.warning("robots_policy_override_enabled")
    collect_phone = settings.collect_phone if args.collect_phone is None else args.collect_phone
    profile = await parse_live_profile(
        args.url,
        settings,
        collect_phone=collect_phone,
        fetcher_factory=_fetcher,
        phone_collector_factory=_phone_collector,
    )
    result = profile.public_dict()
    if args.save:
        result["database"] = save_profile(_repository(settings), profile, category)
    _json_dump(result)
    return 0


async def _run_crawl(args: argparse.Namespace, settings: Settings) -> int:
    """Выполнить команду обхода категорий с параметрами пользователя."""

    changes: dict[str, object] = {}
    if args.geo:
        changes["geo"] = args.geo
    if args.respect_robots is not None:
        changes["respect_robots"] = args.respect_robots
    if changes:
        settings = settings.with_overrides(**changes)
    if not settings.respect_robots:
        logger.warning("robots_policy_override_enabled")
    collect_phone = settings.collect_phone if args.collect_phone is None else args.collect_phone
    categories = _category_repository(settings).resolve(args.category)
    repository = None if args.dry_run else _repository(settings)
    stats = await crawl(
        settings=settings,
        categories=categories,
        max_pages=args.max_pages,
        max_profiles=args.max_profiles,
        collect_phone=collect_phone,
        repository=repository,
        fetcher_factory=_fetcher,
        phone_collector_factory=_phone_collector,
    )
    _json_dump(stats.public_dict())
    return 0
