"""Статические справочники категорий и рубрик парсера."""

from uslugi_parser.catalog.categories import (
    BASE_URL,
    CATEGORY_KEY_PATTERN,
    DEFAULT_CATEGORIES,
    GEO_SLUG_PATTERN,
    RESERVED_PARSER_CATEGORY_KEYS,
    SEED_RUBRIC_PATTERN,
    CategoryDefinition,
    select_categories,
    validate_category_definitions,
    validate_category_key,
    validate_category_name,
    validate_geo_slug,
    validate_seed_path,
)

__all__ = [
    "BASE_URL",
    "CATEGORY_KEY_PATTERN",
    "DEFAULT_CATEGORIES",
    "GEO_SLUG_PATTERN",
    "RESERVED_PARSER_CATEGORY_KEYS",
    "SEED_RUBRIC_PATTERN",
    "CategoryDefinition",
    "select_categories",
    "validate_category_definitions",
    "validate_category_key",
    "validate_category_name",
    "validate_geo_slug",
    "validate_seed_path",
]
