"""Объекты параметров и порты, связывающие прикладные сценарии с адаптерами."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from uslugi_parser.catalog.categories import CategoryDefinition
from uslugi_parser.config import Settings
from uslugi_parser.domain import ParsedProfessional, RubricEvidence


@dataclass(frozen=True, slots=True)
class CrawlOptions:
    """Хранит параметры одного сценария обхода категорий.

    Объект отделяет входные значения сценария от CLI и не позволяет запустить
    обход с отрицательными ограничениями.
    """

    max_pages: int
    max_profiles: int
    collect_phone: bool

    def __post_init__(self) -> None:
        """Проверить ограничения сразу после создания неизменяемого объекта."""

        if self.max_pages < 0 or self.max_profiles < 0:
            raise ValueError("max_pages and max_profiles cannot be negative")


@dataclass(frozen=True, slots=True)
class ProfileOptions:
    """Хранит параметры сценария загрузки одной актуальной карточки."""

    collect_phone: bool


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
