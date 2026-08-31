from __future__ import annotations

import pytest

from uslugi_parser.catalog import (
    DEFAULT_CATEGORIES,
    CategoryDefinition,
    validate_category_definitions,
)
from uslugi_parser.parsing import seed_number_id


def test_all_requested_categories_have_unique_exact_seed_ids() -> None:
    assert len(DEFAULT_CATEGORIES) == 11
    all_ids: list[int] = []
    for category in DEFAULT_CATEGORIES.values():
        assert category.seed_paths
        all_ids.extend(seed_number_id(path) for path in category.seed_paths)
    assert len(all_ids) == len(set(all_ids))
    assert len(all_ids) == 64


def test_requested_category_names_match_database_seed_contract() -> None:
    """Хранить отображаемые названия ровно в формулировке заказчика."""

    assert [category.name for category in DEFAULT_CATEGORIES.values()] == [
        "Дизайнеры",
        "Сметчики",
        "Сантехник",
        "Электрик",
        "Плотник",
        "Сборщик мебели",
        "Отделочник",
        "Мастер по ремонту бытовой техники",
        "Мастер по ремонту окон",
        "Мастер по замкам и дверям",
        "Мастер по слаботочным системам",
    ]


def test_broad_false_positive_seeds_are_not_used() -> None:
    configured = {
        seed_number_id(path)
        for category in DEFAULT_CATEGORIES.values()
        for path in category.seed_paths
    }
    assert {1800, 1816, 4647, 1708, 2178}.isdisjoint(configured)
    assert {1809, 1725, 4638, 4023}.issubset(configured)


@pytest.mark.parametrize(
    ("key", "name", "path", "message"),
    [
        ("Bad-Key", "Категория", "service--1", "category key"),
        ("valid", " Категория", "service--1", "category name"),
        ("valid", "Категория", "/service--1", "relative URL path"),
        ("valid", "Категория", "../service--1", "parent segments"),
        ("valid", "Категория", "%2e%2e/service--1", "positive rubric id"),
        ("valid", "Категория", "service--1?from=test", "query or fragment"),
        ("valid", "Категория", "service", "positive rubric id"),
    ],
)
def test_category_definition_rejects_invalid_database_values(
    key: str,
    name: str,
    path: str,
    message: str,
) -> None:
    """Отклонять небезопасные значения до построения сетевых URL."""

    with pytest.raises((TypeError, ValueError), match=message):
        CategoryDefinition(key=key, name=name, seed_paths=(path,))


def test_category_collection_rejects_empty_and_repeated_rubrics() -> None:
    """Не разрешать пустой обход и один rubric ID в двух категориях."""

    with pytest.raises(ValueError, match="at least one seed path"):
        validate_category_definitions(
            [CategoryDefinition(key="empty", name="Пустая", seed_paths=())]
        )

    with pytest.raises(ValueError, match="duplicate rubric id across categories"):
        validate_category_definitions(
            [
                CategoryDefinition(key="first", name="Первая", seed_paths=("first--10",)),
                CategoryDefinition(key="second", name="Вторая", seed_paths=("second--10",)),
            ]
        )
