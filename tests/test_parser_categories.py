from __future__ import annotations

from collections.abc import Iterable

import pytest
from sqlalchemy import create_engine, delete, func, select

from uslugi_parser.catalog import DEFAULT_CATEGORIES, CategoryDefinition
from uslugi_parser.exceptions import ConfigurationError
from uslugi_parser.infrastructure.database import (
    Base,
    Category,
    CategoryYandexOccupation,
    CategoryYandexSpecialization,
    ParserCategory,
    ParserCategoryRepository,
    ParserCategoryTarget,
    YandexOccupation,
    YandexSpecialization,
    make_session_factory,
)
from uslugi_parser.parsing import seed_number_id


def configured_repository(
    rows: Iterable[tuple[CategoryDefinition, bool, int]],
) -> tuple[ParserCategoryRepository, object]:
    """Создать SQLite-каталог с заданными master-строками и конфигурациями."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    with sessions.begin() as session:
        specialization_ids: dict[int, int] = {}
        for definition, is_active, sort_order in rows:
            category = Category(
                key=definition.key,
                name=definition.name,
                note=definition.note or None,
            )
            session.add(category)
            session.flush()
            session.add(
                ParserCategory(
                    category_id=category.id,
                    seed_paths=list(definition.seed_paths),
                    is_active=is_active,
                    sort_order=sort_order,
                )
            )
            session.flush()
            for position, path in enumerate(definition.seed_paths, start=1):
                rubric_id = seed_number_id(path)
                specialization_id = specialization_ids.get(rubric_id)
                if specialization_id is None:
                    specialization = YandexSpecialization(
                        external_number_id=rubric_id,
                        slug="/" + path.rsplit("--", 1)[0],
                        name=f"Рубрика {rubric_id}",
                        source_url=("https://uslugi.yandex.ru/213-moscow/category/" + path),
                        verification_status="discovered",
                    )
                    session.add(specialization)
                    session.flush()
                    specialization_id = specialization.id
                    specialization_ids[rubric_id] = specialization_id
                session.add(
                    CategoryYandexSpecialization(
                        category_id=category.id,
                        specialization_id=specialization_id,
                        sort_order=position * 10,
                    )
                )
                session.add(
                    ParserCategoryTarget(
                        category_id=category.id,
                        taxonomy_level="specialization",
                        source_rubric_number_id=rubric_id,
                        relative_path=path,
                        is_active=True,
                        sort_order=position * 10,
                    )
                )
    return ParserCategoryRepository(sessions), sessions


def test_repository_returns_database_snapshot_in_active_order() -> None:
    """Использовать имя, пути и порядок БД, а не статический runtime-каталог."""

    database_plumbers = CategoryDefinition(
        key="plumbers",
        name="Сантехник из БД",
        seed_paths=("database-plumber--9001",),
        taxonomy_levels=("specialization",),
    )
    repository, _sessions = configured_repository(
        [
            (DEFAULT_CATEGORIES["electricians"], True, 20),
            (database_plumbers, True, 10),
            (DEFAULT_CATEGORIES["designers"], False, 1),
        ]
    )

    categories = repository.list_active()

    assert [category.key for category in categories] == ["plumbers", "electricians"]
    assert categories[0] == database_plumbers


def test_repository_resolves_explicit_keys_in_requested_order_once() -> None:
    """Сохранять порядок явного выбора и удалять повтор одного ключа."""

    repository, _sessions = configured_repository(
        [
            (DEFAULT_CATEGORIES["plumbers"], True, 10),
            (DEFAULT_CATEGORIES["electricians"], True, 20),
        ]
    )

    categories = repository.resolve(["electricians", "plumbers", "electricians"])

    assert [category.key for category in categories] == ["electricians", "plumbers"]


def test_repository_resolves_all_and_empty_selection_to_active_rows() -> None:
    """Считать отсутствующий выбор и одиночный `all` выбором всех активных строк."""

    repository, _sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])

    assert repository.resolve(None) == repository.list_active()
    assert repository.resolve([]) == repository.list_active()
    assert repository.resolve(["all"]) == repository.list_active()


@pytest.mark.parametrize(
    ("keys", "message"),
    [
        (["missing"], "Unknown parser categories"),
        (["designers"], "Inactive parser categories"),
        (["all", "plumbers"], "cannot be combined"),
        (["Bad-Key"], "Invalid parser category key"),
    ],
)
def test_repository_fails_closed_for_invalid_explicit_selection(
    keys: list[str],
    message: str,
) -> None:
    """Остановить запуск для неизвестного, выключенного или неверного выбора."""

    repository, _sessions = configured_repository(
        [
            (DEFAULT_CATEGORIES["plumbers"], True, 10),
            (DEFAULT_CATEGORIES["designers"], False, 20),
        ]
    )

    with pytest.raises(ConfigurationError, match=message):
        repository.resolve(keys)


def test_repository_rejects_reserved_database_category_key() -> None:
    """Не смешивать пользовательские категории с `all` и ручным импортом."""

    repository, _sessions = configured_repository(
        [(CategoryDefinition("manual", "Не ручной импорт", ("service--42",)), True, 10)]
    )

    with pytest.raises(ConfigurationError, match="reserved key"):
        repository.list_active()


def test_repository_rejects_empty_or_unsafe_crawl_targets() -> None:
    """Не строить HTTP-запросы из пустых либо небезопасных целей обхода БД."""

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        session.execute(delete(ParserCategoryTarget))
    with pytest.raises(ConfigurationError, match="at least one active crawl target"):
        repository.list_active()

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        target = session.scalar(select(ParserCategoryTarget))
        assert target is not None
        target.relative_path = "https://evil.example/category--1"
    with pytest.raises(ConfigurationError, match="relative URL path"):
        repository.list_active()


def test_repository_rejects_target_id_that_does_not_match_path() -> None:
    """Не отправлять запрос, если нормализованный ID расходится с URL цели."""

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        target = session.scalar(select(ParserCategoryTarget))
        assert target is not None
        target.source_rubric_number_id += 1

    with pytest.raises(ConfigurationError, match="does not match path ID"):
        repository.list_active()


def test_repository_rejects_unknown_or_unmapped_catalog_target() -> None:
    """Не обходить legacy-цель или узел из чужой группы каталога."""

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        target = session.scalar(select(ParserCategoryTarget))
        assert target is not None
        target.taxonomy_level = "unknown"
    with pytest.raises(ConfigurationError, match="outside Yandex catalog"):
        repository.list_active()

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        session.execute(delete(CategoryYandexSpecialization))
    with pytest.raises(ConfigurationError, match="unmapped Yandex catalog"):
        repository.list_active()


def test_repository_rejects_unverified_or_noncanonical_catalog_node() -> None:
    """Принимать цель только из проверенной канонической строки справочника."""

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        node = session.scalar(select(YandexSpecialization))
        assert node is not None
        node.verification_status = "unverified"
    with pytest.raises(ConfigurationError, match="unverified specialization"):
        repository.list_active()

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        node = session.scalar(select(YandexSpecialization))
        assert node is not None
        node.source_url = "https://evil.example/category/not-yandex--1844"
    with pytest.raises(ConfigurationError, match="source_url is not canonical"):
        repository.list_active()


def test_repository_accepts_canonical_catalog_url_without_geo() -> None:
    """Принимать каноническую root-форму URL наравне с geo-формой."""

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        node = session.scalar(
            select(YandexSpecialization).where(YandexSpecialization.external_number_id == 1844)
        )
        assert node is not None
        node.source_url = (
            "https://uslugi.yandex.ru/category/"
            "remont-i-stroitelstvo/santehnicheskie-rabotyi-i-otoplenie--1844"
        )

    assert repository.list_active()[0].taxonomy_levels == (
        "specialization",
        "specialization",
    )


def test_repository_rejects_missing_catalog_source_url() -> None:
    """Не строить цель только из slug без канонического URL источника."""

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        node = session.scalar(select(YandexSpecialization))
        assert node is not None
        node.source_url = None

    with pytest.raises(ConfigurationError, match="source_url is missing"):
        repository.list_active()


def test_repository_rejects_duplicate_rubric_ids_across_rows() -> None:
    """Не обходить две категории, претендующие на одну исходную рубрику."""

    repository, sessions = configured_repository(
        [
            (
                CategoryDefinition("first", "Первая", ("first--10",)),
                True,
                10,
            ),
            (
                CategoryDefinition("second", "Вторая", ("second--20",)),
                True,
                20,
            ),
        ]
    )
    with sessions.begin() as session:
        second_category = session.scalar(select(Category).where(Category.key == "second"))
        assert second_category is not None
        second_target = session.scalar(
            select(ParserCategoryTarget).where(
                ParserCategoryTarget.category_id == second_category.id
            )
        )
        assert second_target is not None
        occupation = YandexOccupation(
            external_number_id=10,
            slug="/second",
            name="Вторая рубрика",
            source_url="https://uslugi.yandex.ru/category/second--10",
            verification_status="discovered",
        )
        session.add(occupation)
        session.flush()
        session.add(
            CategoryYandexOccupation(
                category_id=second_category.id,
                occupation_id=occupation.id,
                sort_order=10,
            )
        )
        second_target.taxonomy_level = "occupation"
        second_target.source_rubric_number_id = 10
        second_target.relative_path = "second--10"

    with pytest.raises(ConfigurationError, match="duplicate rubric id across categories"):
        repository.list_active()

    with pytest.raises(ConfigurationError, match="duplicate rubric id across categories"):
        repository.resolve(["first"])


def test_repository_is_read_only() -> None:
    """Не менять master-строки и настройки во время разрешения категорий."""

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])

    repository.resolve(["plumbers"])

    with sessions() as session:
        assert session.scalar(select(func.count(Category.id))) == 1
        assert session.scalar(select(func.count(ParserCategory.category_id))) == 1
