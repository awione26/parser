"""Сущность статистики одного запуска обхода категорий."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CrawlStats:
    """Накапливает счётчики обхода и, в режиме без записи, публичные данные профилей."""

    category_pages: int = 0
    discovered: int = 0
    fetched: int = 0
    parsed: int = 0
    skipped_organizations: int = 0
    skipped_category_mismatch: int = 0
    created: int = 0
    updated: int = 0
    failed: int = 0
    robots_denied: int = 0
    phone_collected: int = 0
    phone_unavailable: int = 0
    profiles: list[dict[str, Any]] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        """Возвращает сериализуемую статистику, опуская пустой список профилей."""

        result = asdict(self)
        if not self.profiles:
            result.pop("profiles")
        return result
