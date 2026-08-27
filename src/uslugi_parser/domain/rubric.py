"""Доказательство соответствия профиля целевой рубрике источника."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RubricEvidence:
    """Фиксирует данные исходной рубрики, подтверждающие категорию и опыт мастера."""

    level: str
    number_id: int | None
    rubric_id: str | None
    seo_id: str | None
    name: str | None
    experience_code: int | None
