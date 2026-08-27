"""Главная точка диспетчеризации команд и обработки ожидаемых ошибок CLI."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy.exc import SQLAlchemyError

from uslugi_parser.cli.commands import (
    _build_parser,
    _configure_logging,
    _parser_run_service,
    _run_categories,
    _run_crawl,
    _run_parse_html,
    _run_parse_profile,
)
from uslugi_parser.config import Settings
from uslugi_parser.exceptions import (
    ConfigurationError,
    CrawlAborted,
    FetchError,
    ParseError,
    PhoneCollectorUnavailable,
    PhoneNavigationBlocked,
)

logger = logging.getLogger(__name__)


def _run_parsing_command(args: argparse.Namespace, settings: Settings) -> int:
    """Запустить выбранный сценарий разбора внутри жизненного цикла журнала."""

    command = getattr(args, "command", None)
    service = _parser_run_service(settings)
    if command == "parse-html":
        return service.execute(lambda: _run_parse_html(args, settings))
    if command == "parse-profile":
        return service.execute(lambda: asyncio.run(_run_parse_profile(args, settings)))
    if command == "crawl":
        return service.execute(lambda: asyncio.run(_run_crawl(args, settings)))
    raise ValueError(f"Unknown parsing command: {command}")


def main(argv: list[str] | None = None) -> int:
    """Разобрать аргументы командной строки и запустить выбранный сценарий."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        settings = Settings.from_env()
        if args.command == "categories":
            return _run_categories(settings)
        if args.command in {"parse-html", "parse-profile", "crawl"}:
            return _run_parsing_command(args, settings)
        parser.error(f"Unknown command: {args.command}")
    except (
        ConfigurationError,
        ParseError,
        PhoneCollectorUnavailable,
        PhoneNavigationBlocked,
        CrawlAborted,
        FetchError,
        SQLAlchemyError,
        OSError,
        ValueError,
    ) as exc:
        logger.error("%s", exc)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
