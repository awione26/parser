from __future__ import annotations

from uslugi_parser.catalog import DEFAULT_CATEGORIES
from uslugi_parser.parsing import seed_number_id


def test_all_requested_categories_have_unique_exact_seed_ids() -> None:
    assert len(DEFAULT_CATEGORIES) == 11
    all_ids: list[int] = []
    for category in DEFAULT_CATEGORIES.values():
        assert category.seed_paths
        all_ids.extend(seed_number_id(path) for path in category.seed_paths)
    assert len(all_ids) == len(set(all_ids))


def test_broad_false_positive_seeds_are_not_used() -> None:
    configured = {
        seed_number_id(path)
        for category in DEFAULT_CATEGORIES.values()
        for path in category.seed_paths
    }
    assert {1800, 1816, 4647, 1708, 2178}.isdisjoint(configured)
    assert {1809, 1725, 4638, 4023}.issubset(configured)
