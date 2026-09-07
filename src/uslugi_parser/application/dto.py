"""Объекты параметров и порты, связывающие прикладные сценарии с адаптерами."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias

from uslugi_parser.catalog.categories import CategoryDefinition
from uslugi_parser.config import Settings
from uslugi_parser.domain import CrawlStats, ParsedProfessional, RubricEvidence


@dataclass(frozen=True, slots=True)
class CrawlOptions:
    """Хранит параметры одного сценария обхода категорий.

    Объект отделяет входные значения сценария от CLI и не позволяет запустить
    обход с отрицательными ограничениями.
    """

    max_pages: int
    max_profiles: int

    def __post_init__(self) -> None:
        """Проверить ограничения сразу после создания неизменяемого объекта."""

        if self.max_pages < 0 or self.max_profiles < 0:
            raise ValueError("max_pages and max_profiles cannot be negative")


@dataclass(frozen=True, slots=True)
class ProfileOptions:
    """Хранит параметры сценария загрузки одной актуальной карточки."""

    collect_phone: bool


CrawlProgressStage: TypeAlias = Literal[
    "started",
    "target_started",
    "page_fetching",
    "page_parsed",
    "profile_started",
    "profile_completed",
    "page_completed",
    "target_completed",
    "completed",
]


@dataclass(frozen=True, slots=True)
class CrawlProgressEvent:
    """Передавать в интерфейс неизменяемый снимок прогресса массового обхода."""

    stage: CrawlProgressStage
    categories_total: int
    category_index: int
    category_key: str | None
    category_name: str | None
    targets_total: int
    target_index: int
    target_rubric_number_id: int | None
    page_number: int
    pages_total: int | None
    profile_index: int
    profiles_total: int
    discovered: int
    fetched: int
    parsed: int
    created: int
    updated: int
    failed: int
    skipped_organizations: int
    skipped_category_mismatch: int
    robots_denied: int
    dry_run: bool
    outcome: str | None = None

    @classmethod
    def from_stats(
        cls,
        *,
        stage: CrawlProgressStage,
        stats: CrawlStats,
        categories_total: int,
        category_index: int = 0,
        category_key: str | None = None,
        category_name: str | None = None,
        targets_total: int,
        target_index: int = 0,
        target_rubric_number_id: int | None = None,
        page_number: int = 0,
        pages_total: int | None = None,
        profile_index: int = 0,
        profiles_total: int = 0,
        dry_run: bool = False,
        outcome: str | None = None,
    ) -> CrawlProgressEvent:
        """Скопировать счётчики, не передавая потребителю изменяемый ``CrawlStats``."""

        return cls(
            stage=stage,
            categories_total=categories_total,
            category_index=category_index,
            category_key=category_key,
            category_name=category_name,
            targets_total=targets_total,
            target_index=target_index,
            target_rubric_number_id=target_rubric_number_id,
            page_number=page_number,
            pages_total=pages_total,
            profile_index=profile_index,
            profiles_total=profiles_total,
            discovered=stats.discovered,
            fetched=stats.fetched,
            parsed=stats.parsed,
            created=stats.created,
            updated=stats.updated,
            failed=stats.failed,
            skipped_organizations=stats.skipped_organizations,
            skipped_category_mismatch=stats.skipped_category_mismatch,
            robots_denied=stats.robots_denied,
            dry_run=dry_run,
            outcome=outcome,
        )


class FetchedPage(Protocol):
    """Описывает страницу, которую сценарии получают от любого HTTP-клиента."""

    text: str
    url: str


class FetcherPort(Protocol):
    """Задаёт сетевой интерфейс для сценариев профиля и обхода категорий."""

    async def get(self, url: str) -> FetchedPage:
        """Безопасно загрузить URL и вернуть текст вместе с итоговым адресом."""

        ...


class PhoneCollectorPort(Protocol):
    """Задаёт браузерный интерфейс для явно разрешённого получения телефона."""

    async def collect(self, profile_url: str, country: str | None) -> str | None:
        """Открыть карточку и вернуть показанный интерфейсом номер, если он доступен."""

        ...


FetcherFactory: TypeAlias = Callable[[Settings], AbstractAsyncContextManager[FetcherPort]]
PhoneCollectorFactory: TypeAlias = Callable[
    [Settings], AbstractAsyncContextManager[PhoneCollectorPort]
]
CrawlProgressReporter: TypeAlias = Callable[[CrawlProgressEvent], None]


class ProfessionalWriter(Protocol):
    """Задаёт интерфейс сохранения мастера без привязки сценария к конкретной БД."""

    def upsert(
        self,
        profile: ParsedProfessional,
        category: CategoryDefinition,
        evidence: RubricEvidence | None = None,
    ) -> str:
        """Создать или обновить мастера и вернуть результат операции."""

        ...


class ParserCategoryReader(Protocol):
    """Задаёт интерфейс разрешения управляемых категорий без привязки к БД."""

    def resolve(self, keys: Sequence[str] | None) -> list[CategoryDefinition]:
        """Вернуть активные категории для `all` либо проверить явные ключи."""

        ...
