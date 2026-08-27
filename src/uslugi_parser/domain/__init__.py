"""Публичные бизнес-сущности предметной области парсера."""

from uslugi_parser.domain.category import CategoryPage, DiscoveredProfile
from uslugi_parser.domain.crawl import CrawlStats
from uslugi_parser.domain.parser_log import (
    PARSER_RESOURCE,
    ParserRunCompletion,
    ParserRunResult,
    ParserRunStart,
)
from uslugi_parser.domain.professional import SOURCE, ParsedProfessional
from uslugi_parser.domain.rubric import RubricEvidence

__all__ = [
    "SOURCE",
    "CategoryPage",
    "CrawlStats",
    "DiscoveredProfile",
    "PARSER_RESOURCE",
    "ParsedProfessional",
    "ParserRunCompletion",
    "ParserRunResult",
    "ParserRunStart",
    "RubricEvidence",
]
