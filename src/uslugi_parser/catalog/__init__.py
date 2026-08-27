"""Статические справочники категорий и рубрик парсера."""

from uslugi_parser.catalog.categories import (
    BASE_URL,
    DEFAULT_CATEGORIES,
    GEO_SLUG_PATTERN,
    CategoryDefinition,
    select_categories,
    validate_geo_slug,
)

__all__ = [
    "BASE_URL",
    "DEFAULT_CATEGORIES",
    "GEO_SLUG_PATTERN",
    "CategoryDefinition",
    "select_categories",
    "validate_geo_slug",
]
