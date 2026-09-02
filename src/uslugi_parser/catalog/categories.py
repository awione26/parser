"""Каталог целевых категорий и исходных URL сервиса Яндекс Услуги."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

BASE_URL = "https://uslugi.yandex.ru"
GEO_SLUG_PATTERN = re.compile(r"^[0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*$")
CATEGORY_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SEED_RUBRIC_PATTERN = re.compile(
    r"(?:[a-z0-9]+(?:-[a-z0-9]+)*/)*"
    r"[a-z0-9]+(?:-[a-z0-9]+)*--([1-9][0-9]*)$"
)
RESERVED_PARSER_CATEGORY_KEYS = frozenset({"all", "manual"})


def validate_geo_slug(geo: str) -> str:
    """Проверяет безопасный формат географического slug и возвращает его без изменений."""

    if len(geo) > 128 or not GEO_SLUG_PATTERN.fullmatch(geo):
        raise ValueError(
            "Yandex geo must be at most 128 characters, look like '213-moscow', and "
            "contain only lowercase ASCII letters, digits, and hyphens"
        )
    return geo


@dataclass(frozen=True, slots=True)
class CategoryDefinition:
    """Описывает категорию парсера и точный набор исходных путей Яндекс Услуг."""

    key: str
    name: str
    seed_paths: tuple[str, ...]
    note: str = ""
    taxonomy_levels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Проверить идентификатор, название и безопасные относительные пути категории."""

        validate_category_key(self.key)
        validate_category_name(self.name)
        if not isinstance(self.seed_paths, tuple):
            raise TypeError("category seed_paths must be a tuple")

        seen_paths: set[str] = set()
        seen_rubric_ids: set[int] = set()
        for path in self.seed_paths:
            rubric_id = validate_seed_path(path)
            if path in seen_paths:
                raise ValueError(f"duplicate category seed path: {path!r}")
            if rubric_id in seen_rubric_ids:
                raise ValueError(f"duplicate rubric id in category seed paths: {rubric_id}")
            seen_paths.add(path)
            seen_rubric_ids.add(rubric_id)

        if not isinstance(self.note, str):
            raise TypeError("category note must be a string")
        if not isinstance(self.taxonomy_levels, tuple):
            raise TypeError("category taxonomy_levels must be a tuple")
        if self.taxonomy_levels and len(self.taxonomy_levels) != len(self.seed_paths):
            raise ValueError("category taxonomy_levels must match seed_paths length")
        invalid_levels = set(self.taxonomy_levels) - {
            "occupation",
            "specialization",
            "service",
        }
        if invalid_levels:
            raise ValueError(
                "category taxonomy_levels contain unsupported values: "
                + ", ".join(sorted(invalid_levels))
            )

    def targets(self) -> tuple[tuple[str, str | None], ...]:
        """Вернуть URL-пути вместе с ожидаемым уровнем рубрики каталога."""

        if not self.taxonomy_levels:
            return tuple((path, None) for path in self.seed_paths)
        return tuple(zip(self.seed_paths, self.taxonomy_levels, strict=True))

    def urls(self, geo: str) -> tuple[str, ...]:
        """Строит абсолютные URL исходных рубрик для проверенного geo slug в заданном порядке."""

        geo = validate_geo_slug(geo)
        prefix = f"/{geo}/category/"
        return tuple(urljoin(BASE_URL, prefix + path.lstrip("/")) for path in self.seed_paths)


def validate_category_key(key: str) -> str:
    """Проверить неизменяемый ASCII-ключ категории и вернуть его без нормализации."""

    if not isinstance(key, str):
        raise TypeError("category key must be a string")
    if not CATEGORY_KEY_PATTERN.fullmatch(key):
        raise ValueError(
            "category key must start with a lowercase ASCII letter and contain only "
            "lowercase ASCII letters, digits, and underscores"
        )
    return key


def validate_category_name(name: str) -> str:
    """Проверить непустое отображаемое название категории без скрытой нормализации."""

    if not isinstance(name, str):
        raise TypeError("category name must be a string")
    if not name or name != name.strip() or len(name) > 255:
        raise ValueError("category name must be non-empty, trimmed, and at most 255 characters")
    if any(ord(character) < 32 for character in name):
        raise ValueError("category name must not contain control characters")
    return name


def validate_seed_path(path: str) -> int:
    """Проверить безопасный относительный путь рубрики и вернуть её числовой ID."""

    if not isinstance(path, str):
        raise TypeError("category seed path must be a string")
    if not path or path != path.strip() or len(path) > 1024:
        raise ValueError(
            "category seed path must be non-empty, trimmed, and at most 1024 characters"
        )
    parsed = urlsplit(path)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or path.startswith("/")
        or "\\" in path
    ):
        raise ValueError("category seed path must be a relative URL path without query or fragment")
    segments = path.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError("category seed path must not contain empty, dot, or parent segments")
    match = SEED_RUBRIC_PATTERN.fullmatch(path)
    if match is None:
        raise ValueError(
            "category seed path must contain lowercase slug segments and end with "
            "'--<positive rubric id>'"
        )
    return int(match.group(1))


def validate_category_definitions(
    categories: list[CategoryDefinition] | tuple[CategoryDefinition, ...],
    *,
    require_seed_paths: bool = True,
) -> None:
    """Проверить уникальность ключей, путей и ID рубрик во всём наборе категорий."""

    seen_keys: set[str] = set()
    seen_paths: set[str] = set()
    seen_rubric_ids: set[int] = set()
    for category in categories:
        if require_seed_paths and not category.seed_paths:
            raise ValueError(f"category {category.key!r} must have at least one seed path")
        if category.key in seen_keys:
            raise ValueError(f"duplicate category key: {category.key!r}")
        seen_keys.add(category.key)
        for path in category.seed_paths:
            rubric_id = validate_seed_path(path)
            if path in seen_paths:
                raise ValueError(f"duplicate seed path across categories: {path!r}")
            if rubric_id in seen_rubric_ids:
                raise ValueError(f"duplicate rubric id across categories: {rubric_id}")
            seen_paths.add(path)
            seen_rubric_ids.add(rubric_id)


DEFAULT_CATEGORIES: dict[str, CategoryDefinition] = {
    "designers": CategoryDefinition(
        key="designers",
        name="Дизайнеры",
        seed_paths=("dizajneryi/dizajner-intererov--258",),
        note="Точная специализация дизайнеров интерьеров из справочника Яндекса.",
    ),
    "estimators": CategoryDefinition(
        key="estimators",
        name="Сметчики",
        seed_paths=("remont-i-stroitelstvo/proektirovanie-i-smetyi--1800",),
        note="Специализация проектирования объектов и составления смет.",
    ),
    "plumbers": CategoryDefinition(
        key="plumbers",
        name="Сантехник",
        seed_paths=(
            "remont-i-stroitelstvo/santehnicheskie-rabotyi-i-otoplenie--1844",
            "remont-i-stroitelstvo/vodosnabzhenie-i-kanalizatsiya--1367",
        ),
    ),
    "electricians": CategoryDefinition(
        key="electricians",
        name="Электрик",
        seed_paths=("remont-i-stroitelstvo/elektromontazhnyie-rabotyi--2007",),
    ),
    "carpenters": CategoryDefinition(
        key="carpenters",
        name="Плотник",
        seed_paths=("remont-i-stroitelstvo/stoljarnye-i-plotnitskie-raboty--5788",),
    ),
    "furniture_assemblers": CategoryDefinition(
        key="furniture_assemblers",
        name="Сборщик мебели",
        seed_paths=(
            "remont-i-stroitelstvo/sborka-i-remont-mebeli--4647",
            "remont-i-stroitelstvo/izgotovlenie-mebeli--4618",
        ),
        note="Сборка, ремонт и изготовление мебели по приложенному справочнику.",
    ),
    "finishers": CategoryDefinition(
        key="finishers",
        name="Отделочник",
        seed_paths=(
            "remont-i-stroitelstvo/remont-kvartir-i-domov--1816",
            "remont-i-stroitelstvo/remont-ofisa--1828",
            "remont-i-stroitelstvo/oboi-i-malyarnyie-rabotyi--1668",
            "remont-i-stroitelstvo/plitochnyie-rabotyi--1749",
            "remont-i-stroitelstvo/polyi-i-napolnyie-pokryitiya--1757",
            "remont-i-stroitelstvo/potolki--1792",
            "remont-i-stroitelstvo/gipsokarton--5699",
        ),
        note="Семь подтверждённых отделочных специализаций из справочника Яндекса.",
    ),
    "appliance_repair": CategoryDefinition(
        key="appliance_repair",
        name="Мастер по ремонту бытовой техники",
        seed_paths=(
            "remont-i-ustanovka-tehniki/stiralnyie-mashinyi--2178",
            "remont-i-ustanovka-tehniki/posudomoechnyie-mashinyi--2140",
            "remont-i-ustanovka-tehniki/holodilniki--2227",
            "remont-i-ustanovka-tehniki/morozilnie-kameri--6412",
            "remont-i-ustanovka-tehniki/dukhovie-shkafi--6221",
            "remont-i-ustanovka-tehniki/varochnie-paneli--6220",
            "remont-i-ustanovka-tehniki/kuhonnyie-plityi--2077",
            "remont-i-ustanovka-tehniki/vytjazhki--5364",
            "remont-i-ustanovka-tehniki/konditsioneryi--2063",
            "remont-i-ustanovka-tehniki/remont-melkoj-byitovoj-tehniki--2094",
        ),
        note="Ремонт и установка бытовой техники по десяти подтверждённым специализациям.",
    ),
    "window_repair": CategoryDefinition(
        key="window_repair",
        name="Мастер по ремонту окон",
        seed_paths=("remont-i-stroitelstvo/okna-i-balkonyi--1708",),
        note="Ремонт и установка окон и балконов по приложенному справочнику.",
    ),
    "locks_and_doors": CategoryDefinition(
        key="locks_and_doors",
        name="Мастер по замкам и дверям",
        seed_paths=(
            "remont-i-stroitelstvo/remont-i-ustanovka-zamkov--5324",
            "remont-i-stroitelstvo/vskrytie-zamkov--5274",
            "remont-i-stroitelstvo/ustanovka-dverej--5311",
            "remont-i-stroitelstvo/remont-dverej--5319",
        ),
        note="Четыре подтверждённые специализации дверей и замков.",
    ),
    "low_voltage": CategoryDefinition(
        key="low_voltage",
        name="Мастер по слаботочным системам",
        seed_paths=(
            "remont-i-stroitelstvo/slabotochnye-sistemy--5784",
            "remont-i-stroitelstvo/ohrannyie-sistemyi-i-kontrol-dostupa--1729",
            "remont-i-stroitelstvo/umnyij-dom--1967",
            "remont-i-stroitelstvo/antenny--5798",
        ),
        note="Слаботочные системы, охрана/СКУД, умный дом и антенны.",
    ),
}

validate_category_definitions(tuple(DEFAULT_CATEGORIES.values()))


def select_categories(keys: list[str] | None) -> list[CategoryDefinition]:
    """Возвращает весь каталог для пустого выбора или all, иначе выбирает уникальные ключи.

    Порядок первого появления ключей сохраняется. Неизвестный ключ приводит к
    KeyError, кроме случая с ``all``, когда остальные значения не учитываются.
    """

    if not keys or "all" in keys:
        return list(DEFAULT_CATEGORIES.values())
    unknown = sorted(set(keys) - DEFAULT_CATEGORIES.keys())
    if unknown:
        raise KeyError(f"Unknown categories: {', '.join(unknown)}")
    return [DEFAULT_CATEGORIES[key] for key in dict.fromkeys(keys)]
