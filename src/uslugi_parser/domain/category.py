"""Сущности обнаруженной карточки и страницы категории."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscoveredProfile:
    """Хранит устойчивый идентификатор и канонический URL найденного профиля."""

    source_profile_id: str
    profile_url: str


@dataclass(frozen=True, slots=True)
class CategoryPage:
    """Описывает одну страницу категории вместе с профилями и данными пагинации."""

    profiles: tuple[DiscoveredProfile, ...]
    page: int
    per_page: int
    total_items: int
    total_pages: int
