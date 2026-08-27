"""Бизнес-объекты жизненного цикла одного запуска парсера."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PARSER_RESOURCE = "uslugi.yandex.ru"
ParserRunResult = Literal["success", "failure"]


@dataclass(frozen=True, slots=True)
class ParserRunStart:
    """Описывать момент и ресурс начавшегося запуска парсера."""

    started_at: datetime
    resource: str = PARSER_RESOURCE

    def __post_init__(self) -> None:
        """Проверить формат времени и обязательное имя ресурса."""

        if self.started_at.tzinfo is not None:
            raise ValueError("parser run timestamps must be naive UTC datetimes")
        if not self.resource.strip():
            raise ValueError("parser run resource cannot be empty")
        if len(self.resource) > 255:
            raise ValueError("parser run resource cannot exceed 255 characters")


@dataclass(frozen=True, slots=True)
class ParserRunCompletion:
    """Описывать окончательный результат и время завершения запуска."""

    finished_at: datetime
    result: ParserRunResult
    error_reason: str | None = None

    def __post_init__(self) -> None:
        """Не допустить противоречивого результата или причины ошибки."""

        if self.finished_at.tzinfo is not None:
            raise ValueError("parser run timestamps must be naive UTC datetimes")
        if self.result not in {"success", "failure"}:
            raise ValueError("parser run result must be success or failure")
        if self.result == "success" and self.error_reason is not None:
            raise ValueError("successful parser run cannot have an error reason")
        if self.result == "failure" and not (self.error_reason or "").strip():
            raise ValueError("failed parser run must have an error reason")
