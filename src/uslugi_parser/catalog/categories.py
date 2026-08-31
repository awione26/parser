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
        seed_paths=("dizajneryi--217",),
    ),
    "estimators": CategoryDefinition(
        key="estimators",
        name="Сметчики",
        seed_paths=(
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/sostavlenie-smetyi--1809",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-stroitelnyie-rabotyi--1815",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-remontnyie-rabotyi--1814",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-proektnyie-rabotyi--1812",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-montazh-oborudovaniya--1811",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-izyiskatelskie-rabotyi--1810",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-puskonaladochnyie-rabotyi--1813",
        ),
        note="Объединение семи официальных услуг по составлению смет.",
    ),
    "plumbers": CategoryDefinition(
        key="plumbers",
        name="Сантехник",
        seed_paths=("remont-i-stroitelstvo/santehnicheskie-rabotyi-i-otoplenie--1844",),
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
            "remont-i-stroitelstvo/mebel/sborka-mebeli--4638",
            "remont-i-stroitelstvo/sborka-i-remont-mebeli/sborka-komplekta-mebeli--5954",
            "remont-i-stroitelstvo/mebel/sborka-kuhni--4641",
            "remont-i-stroitelstvo/mebel/sobrat-kuhonnyij-garnitur--4643",
            "remont-i-stroitelstvo/mebel/sobrat-shkaf--4635",
            "remont-i-stroitelstvo/mebel/sborka-shkafa--4642",
            "remont-i-stroitelstvo/mebel/sobrat-divan--4630",
        ),
        note="Точные услуги сборки; ремонт и разборка мебели исключены.",
    ),
    "finishers": CategoryDefinition(
        key="finishers",
        name="Отделочник",
        seed_paths=(
            "remont-i-stroitelstvo/remont-kvartir-i-domov/chistovaya-otdelka--1827",
            "remont-i-stroitelstvo/remont-kvartir-i-domov/chernovaya-otdelka--1826",
            "remont-i-stroitelstvo/remont-kvartir-i-domov/kosmeticheskij-remont-kvartiryi--1820",
            "remont-i-stroitelstvo/oboi-i-malyarnyie-rabotyi/poklejka-oboev--1679",
            "remont-i-stroitelstvo/oboi-i-malyarnyie-rabotyi/pokraska-sten--1686",
            "remont-i-stroitelstvo/oboi-i-malyarnyie-rabotyi/shtukaturka-sten--1692",
            "remont-i-stroitelstvo/oboi-i-malyarnyie-rabotyi/shpatlevanie-poverhnosti--1690",
            "remont-i-stroitelstvo/plitochnyie-rabotyi/ukladka-plitki--1755",
            "remont-i-stroitelstvo/polyi-i-napolnyie-pokryitiya/ukladka-laminata--1777",
            "remont-i-stroitelstvo/polyi-i-napolnyie-pokryitiya/ukladka-linoleuma--1778",
            "remont-i-stroitelstvo/drugoe/montazh-peregorodok-iz-gipsokartona--5695",
            "remont-i-stroitelstvo/drugoe/obshivka-sten-gipsokartonom--5697",
            "remont-i-stroitelstvo/potolki/ustanovka-natyajnogo-potolka--1795",
        ),
        note="Allowlist конкретных чистовых, черновых и отделочных услуг.",
    ),
    "appliance_repair": CategoryDefinition(
        key="appliance_repair",
        name="Мастер по ремонту бытовой техники",
        seed_paths=(
            "remont-i-ustanovka-tehniki/stiralnyie-mashinyi/remont-stiralnoj-mashinyi--4023",
            "remont-i-ustanovka-tehniki/posudomoechnyie-mashinyi/"
            "remont-posudomoechnyih-mashin--4064",
            "remont-i-ustanovka-tehniki/holodilniki/remont-holodilnika--2237",
            "remont-i-ustanovka-tehniki/kuhonnyie-plityi/remont-kuhonnoj-plityi--2079",
            "remont-i-ustanovka-tehniki/remont-melkoj-byitovoj-tehniki/"
            "remont-melkoj-byitovoj-tehniki--2101",
            "remont-i-ustanovka-tehniki/sushilnyie-mashinyi/remont-sushilnoj-mashinyi--4448",
            "remont-i-ustanovka-tehniki/dukhovie-shkafi/remont-dukhovogo-shkafa--6226",
            "remont-i-ustanovka-tehniki/varochnie-paneli/remont-varochnoi-paneli--6223",
            "remont-i-ustanovka-tehniki/morozilnie-kameri/remont-morozilnoi-kameri--6416",
            "remont-i-ustanovka-tehniki/remont-melkoj-byitovoj-tehniki/remont-vyityazhki--5362",
            "remont-i-ustanovka-tehniki/remont-melkoj-byitovoj-tehniki/remont-kofemashinyi--5360",
        ),
        note="Только услуги ремонта бытовой техники; установка исключена.",
    ),
    "window_repair": CategoryDefinition(
        key="window_repair",
        name="Мастер по ремонту окон",
        seed_paths=(
            "remont-i-stroitelstvo/okna-i-balkonyi/remont-okon--1725",
            "remont-i-stroitelstvo/okna-i-balkonyi/zamena-stekol--1715",
            "remont-i-stroitelstvo/okna-i-balkonyi/uteplenie-okon--4299",
            "remont-i-stroitelstvo/okna-i-balkonyi/ustanovka-ili-zamena-okonnyih-ruchek--1727",
            "remont-i-stroitelstvo/okna-i-balkonyi/"
            "germetizatsiya-mest-primyikaniya-okonnoj-ramyi--1712",
            "remont-i-stroitelstvo/okna-i-balkonyi/germetizatsiya-okon--1713",
            "remont-i-stroitelstvo/okna-i-balkonyi/zvukoizolyatsiya-okon--4300",
            "remont-i-stroitelstvo/okna-i-balkonyi/diagnostika--6405",
        ),
        note="Только ремонтные оконные услуги; балконные работы исключены.",
    ),
    "locks_and_doors": CategoryDefinition(
        key="locks_and_doors",
        name="Мастер по замкам и дверям",
        seed_paths=(
            "remont-i-stroitelstvo/dveri-i-zamki/remont-zamka--5320",
            "remont-i-stroitelstvo/remont-i-ustanovka-zamkov/"
            "remont-zamka-mezhkomnatnoi-dveri--6442",
            "remont-i-stroitelstvo/dveri-i-zamki/ustanovka-zamka--5321",
            "remont-i-stroitelstvo/remont-i-ustanovka-zamkov/"
            "ustanovka-zamka-dlya-mezhkomnatnoi-dveri--6441",
            "remont-i-stroitelstvo/dveri-i-zamki/zamena-zamka--5323",
            "remont-i-stroitelstvo/remont-i-ustanovka-zamkov/"
            "zamena-zamka-mezhkomnatnoi-dveri--6443",
            "remont-i-stroitelstvo/dveri-i-zamki/zamena-tsilindra-zamka--5322",
            "remont-i-stroitelstvo/dveri-i-zamki/vskryitie-zamka--5273",
            "remont-i-stroitelstvo/vskrytie-zamkov/vskritie-zamka-ot-vkhodnoi-dveri--6436",
            "remont-i-stroitelstvo/vskrytie-zamkov/vskritie-zamka-ot-mezhkomnatnoi-dveri--6437",
            "remont-i-stroitelstvo/dveri-i-zamki/remont-dverej--5314",
            "remont-i-stroitelstvo/dveri-i-zamki/ustanovka-mezhkomnatnoj-dveri--5291",
            "remont-i-stroitelstvo/dveri-i-zamki/ustanovka-vhodnoj-dveri--5295",
        ),
        note="Allowlist строительных дверей и замков; авто-, сейфовые и гаражные исключены.",
    ),
    "low_voltage": CategoryDefinition(
        key="low_voltage",
        name="Мастер по слаботочным системам",
        seed_paths=("remont-i-stroitelstvo/slabotochnye-sistemy--5784",),
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
