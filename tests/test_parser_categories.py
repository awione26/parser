from __future__ import annotations

from collections.abc import Iterable

import pytest
from sqlalchemy import create_engine, func, select

from uslugi_parser.catalog import DEFAULT_CATEGORIES, CategoryDefinition
from uslugi_parser.exceptions import ConfigurationError
from uslugi_parser.infrastructure.database import (
    Base,
    Category,
    ParserCategory,
    ParserCategoryRepository,
    make_session_factory,
)


def configured_repository(
    rows: Iterable[tuple[CategoryDefinition, bool, int]],
) -> tuple[ParserCategoryRepository, object]:
    """Создать SQLite-каталог с заданными master-строками и конфигурациями."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    with sessions.begin() as session:
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
    return ParserCategoryRepository(sessions), sessions


def test_repository_returns_database_snapshot_in_active_order() -> None:
    """Использовать имя, пути и порядок БД, а не статический runtime-каталог."""

    database_plumbers = CategoryDefinition(
        key="plumbers",
        name="Сантехник из БД",
        seed_paths=("database-plumber--9001",),
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


def test_repository_rejects_empty_or_unsafe_json_paths() -> None:
    """Не строить HTTP-запросы из пустого либо небезопасного JSON БД."""

    repository, sessions = configured_repository([(DEFAULT_CATEGORIES["plumbers"], True, 10)])
    with sessions.begin() as session:
        config = session.scalar(select(ParserCategory))
        assert config is not None
        config.seed_paths = []
    with pytest.raises(ConfigurationError, match="non-empty JSON array"):
        repository.list_active()

    with sessions.begin() as session:
        config = session.scalar(select(ParserCategory))
        assert config is not None
        config.seed_paths = ["https://evil.example/category--1"]
    with pytest.raises(ConfigurationError, match="relative URL path"):
        repository.list_active()


def test_repository_rejects_duplicate_rubric_ids_across_rows() -> None:
    """Не обходить две категории, претендующие на одну исходную рубрику."""

    repository, _sessions = configured_repository(
        [
            (
                CategoryDefinition("first", "Первая", ("first--10",)),
                True,
                10,
            ),
            (
                CategoryDefinition("second", "Вторая", ("second--10",)),
                True,
                20,
            ),
        ]
    )

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
